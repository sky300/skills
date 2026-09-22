# Authenticating to the ZITADEL APIs (service accounts, roles, credentials)

Everything ZITADEL exposes over HTTP falls into two families: the legacy **v1** APIs (Management, Admin,
Auth, System — JSON over REST on a prefixed base path, plus gRPC) and the newer **resource-based v2**
APIs (user, org, project, application, group, session, settings, OIDC, internal permission — gRPC and
ConnectRPC). Managing anything programmatically (organizations, projects, apps, users, settings) requires
a **service account** ("machine user"): a non-human user that authenticates with a key, a client secret or
a personal access token instead of a password, plus an **administrator role** granted on the resource you
want to touch. This document covers creating that service account, granting the right administrator role at
the right level, the three authentication methods with copy-pasteable requests, and the failure modes an
operator hits first. Values shown as `<placeholders>` come from the operator — the names this skill reads them
from are listed in `SKILL.md` under "Read the connection details from the environment".

## Version note: transports, and how to confirm an endpoint exists on *your* instance

- **v2 APIs use ConnectRPC.** A call is `POST https://<your instance domain>/<proto package>.<Service>/<Method>`
  with a JSON body, e.g. `POST /zitadel.user.v2.UserService/AddPersonalAccessToken`. Connect clients send the
  header `Connect-Protocol-Version: 1` and `Content-Type: application/json`; keep sending it for
  interoperability. Auth is the same `Authorization` header as everywhere else.
- **Some v2 services still answer the legacy REST path** derived from the proto's `google.api.http`
  annotation (`POST /v2/users/new`, `POST /v2/organizations/_search`, …), and those paths are what the
  public API reference documents. A few v2 services expose **only** Connect: `internal_permission.v2`
  (`CreateAdministrator` and friends) has no `google.api.http` annotation at all, so it is Connect-only.
  Docs announce REST/OpenAPI as sunset for v2 and name ConnectRPC the official replacement, yet the REST
  routes are still routed — prefer ConnectRPC for new code, and do not assume a REST path you saw in an old
  script still exists on a newer server.
- **v1 APIs are REST on a fixed base path**: `/management/v1/…`, `/admin/v1/…`, `/auth/v1/…`,
  `/system/v1/…`. The proto annotations are *relative* to that base path — the annotation for
  `ManagementService/AddMachineUser` literally reads `post: "/users/machine"` while the served URL is
  `POST /management/v1/users/machine` (the `base_path` lives in the service's OpenAPI option). Always
  prepend the base path yourself; a bare `/users/machine` returns 404.
- **Confirm any endpoint on your own version before relying on it.** Send an unauthenticated request:

  ```shell
  curl -s -o /dev/null -w '%{http_code}\n' -X POST \
    -H 'Content-Type: application/json' -d '{}' \
    'https://<your instance domain>/<path>'
  ```

  `401` / `403` = the route is registered and requires auth; `404` = not present on this version; `400`,
  `405`, `415` also prove the route exists (you just sent the wrong method/body). Every endpoint in this
  document was confirmed this way (401/403) against a live ZITADEL v4.18.0 instance, except where a note says
  otherwise.
- For OIDC/OAuth endpoints, read `GET /.well-known/openid-configuration` on your instance instead of
  hardcoding: it publishes `token_endpoint` (`/oauth/v2/token`), `introspection_endpoint`
  (`/oauth/v2/introspect`), `userinfo_endpoint` (`/oidc/v1/userinfo`), `jwks_uri` (`/oauth/v2/keys`),
  `revocation_endpoint` (`/oauth/v2/revoke`), the supported `grant_types_supported`
  (`client_credentials` and `urn:ietf:params:oauth:grant-type:jwt-bearer` included) and
  `token_endpoint_auth_methods_supported` (`client_secret_basic`, `client_secret_post`, `private_key_jwt`).

## Which API to call, and which one needs a service account

- **Auth API** (`/auth/v1/…`) — operations on the authenticated user itself, identified by the `sub` claim
  of the presented token. No service account needed: call it with the user's own (or the service account's
  own) token. Useful for self-diagnostics.
- **Management API** (`/management/v1/…`) — organization-administrator scope: users, projects, apps, org
  settings, org-level administrators of the caller's organization.
- **Admin API** (`/admin/v1/…`) — instance-administrator scope: instance settings, IAM members,
  organizations, OIDC settings, identity providers of the instance.
- **System API** (`/system/v1/…`) — self-hosted only, superordinate over all instances. **Not reachable by
  service accounts**: it authenticates a self-signed JWT whose public key is configured in the runtime
  settings (`SystemAPIUsers`), with claims `iss`/`sub` = the configured system user id and
  `aud` = the instance domain. Keep it out of service-account automation.
- **Resource-based v2 APIs** — the recommended target for new automation; the same service-account token
  works for all of them.

Practical rule: **to manage projects, organizations, apps or users programmatically you need a service
account that carries an administrator role.** A service account with no administrator role authenticates fine,
then fails unevenly rather than with one clean error: a `404` with `membership not found` from the endpoints that
resolve a membership before anything else, a `200` whose `totalResult` is filled in while the item array is
absent from the ones that count before they filter, and only the caller itself from user search —
`references/conventions.md` has the measured table. Roles are granted *per resource level*, and instance-level
administrator roles are what make an API usable across all organizations — "only the administrators on the
instance level can view resources, such as users, across all organizations". An organization-level
administrator is confined to that organization.

## 1. Create the service account (machine user)

Console path: **Users > Service Accounts > New**, enter a username and a display name, **Create**. Credentials
are added afterwards on the account's detail page (Keys / Personal Access Token / Actions > Generate Client
Secret).

API (v2, preferred) — required permission `user.write`:

```shell
# POST /v2/users/new          (Connect: POST /zitadel.user.v2.UserService/CreateUser)
curl -X POST 'https://<your instance domain>/v2/users/new' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Connect-Protocol-Version: 1' \
  -d '{
        "organization_id": "<organization-id>",
        "username": "ci-deployer",
        "machine": {
          "name": "CI deployer",
          "description": "manages projects and apps in this instance",
          "access_token_type": "ACCESS_TOKEN_TYPE_BEARER"
        }
      }'
```

Fields that matter:

- `organization_id` — the organization the service account belongs to. In v2 all contextual data such as the
  organization moved from the request header into the body.
- `username` — unique inside the organization. If omitted, ZITADEL sets it to the `user_id` for machine users
  (and to the email for humans).
- `user_id` — optional; set your own ID (e.g. a UUID) if you need idempotent provisioning. Not changeable
  later.
- `machine.name` (required, ≤200 chars) and `machine.description` (≤500) — the human-readable identity you
  will see in audit logs; keep them meaningful.
- `machine.access_token_type` — `ACCESS_TOKEN_TYPE_BEARER` (default, opaque token) or `ACCESS_TOKEN_TYPE_JWT`
  (self-contained; note that a *revoked* JWT may still be accepted until it expires, so validate JWTs via
  userinfo/introspection). `AddSecret`, `AddKey` and `AddPersonalAccessToken` all require a **machine**
  user; they fail for human users.

Response is `{"id": "<service-account-user-id>", "creation_date": "…"}` — keep that `id`: it is the `user_id`
for every credential call below and the `iss`/`sub` of JWT assertions.

Legacy v1 alternative (both transports work on current versions) — same `user.write` permission:

```shell
# POST /management/v1/users/machine   (REST; service ManagementService, RPC AddMachineUser)
curl -X POST 'https://<your instance domain>/management/v1/users/machine' \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'x-zitadel-orgid: <organization-id>' \
  -d '{"userName":"ci-deployer","name":"CI deployer","description":"CI","accessTokenType":"ACCESS_TOKEN_TYPE_BEARER"}'
```

Note the casing and the context rule: v2 accepts both the proto field name (`organization_id`) and
lowerCamelCase (`organizationId`), while legacy v1 examples are camelCase throughout (`userName`,
`accessTokenType`) — match the surface you are calling instead of converting by reflex. The organization
context differs too: v1 reads it from the `x-zitadel-orgid` header, v2 takes `organizationId` in the body.

## 2. Grant administrator roles

Roles are granted with `CreateAdministrator`, whose `resource` oneof *is* the level. Note the resource-specific
permissions from the proto comments: `iam.member.write` (instance), `org.member.write` (organization),
`project.member.write` (project), `project.grant.member.write` (project grant).

**Instance level** — this is the grant that makes ZITADEL APIs usable across all organizations. Connect-only
(no REST path):

```shell
# POST /zitadel.internal_permission.v2.InternalPermissionService/CreateAdministrator
#   (no legacy REST equivalent; requires iam.member.write)
curl -X POST 'https://<your instance domain>/zitadel.internal_permission.v2.InternalPermissionService/CreateAdministrator' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Connect-Protocol-Version: 1' \
  -d '{
        "user_id": "<service-account-user-id>",
        "resource": {"instance": true},
        "roles": ["IAM_OWNER"]
      }'
```

**Organization level** (requires `org.member.write`) — the level is expressed as a plain string:

```shell
curl -X POST 'https://<your instance domain>/zitadel.internal_permission.v2.InternalPermissionService/CreateAdministrator' \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"user_id":"<service-account-user-id>","resource":{"organization_id":"<organization-id>"},"roles":["ORG_OWNER"]}'
```

**Project level** — `{"resource":{"project_id":"<project-id>"},"roles":["PROJECT_OWNER"]}`.
**Project grant level** — `{"resource":{"project_grant":{"project_id":"<project-id>","organization_id":"<granted-org-id>"}},"roles":["PROJECT_GRANT_OWNER"]}`.

The response contains only `creation_date`. Roles are **resource-type specific**: granting a role for an
organization and a project requires two separate calls. `UpdateAdministrator` (same RPC family) *replaces*
the role list — any role previously granted and absent from the request is revoked — and
`DeleteAdministrator` revokes all roles for that user on that resource (it returns success even if there was
nothing to delete).

Legacy v1 equivalents (REST, still routed):

| Level | Endpoint | Permission |
| --- | --- | --- |
| Instance | `POST /admin/v1/members` with `{"userId":"…","roles":["IAM_OWNER"]}` | `iam.member.write` |
| Instance (update/remove) | `PUT /admin/v1/members/{user_id}`, `DELETE /admin/v1/members/{user_id}` | `iam.member.write` / `iam.member.delete` |
| Organization | `POST /management/v1/orgs/me/members` (add `x-zitadel-orgid` to target a specific org) | `org.member.write` |
| Organization (update/remove) | `PUT /management/v1/orgs/me/members/{user_id}`, `DELETE …` | `org.member.write` / `org.member.delete` |
| Project | `POST /management/v1/projects/{project_id}/members` | `project.member.write` |
| Project grant | `POST /management/v1/projects/{project_id}/grants/{grant_id}/members` | `project.grant.member.write` |

Read them back with `POST /admin/v1/members/_search`, `POST /management/v1/orgs/me/members/_search`, or
`POST /zitadel.internal_permission.v2.InternalPermissionService/ListAdministrators` (Connect-only; its filters
cover instance, organization, project and project grant).

**The console grant path is not on the service account.** Its page has no permissions or roles section, which is
where people look first — administrator roles are memberships *of a resource*, so they are granted from that
resource: open the instance, organization, project or project grant, use the **Administrators** panel on the right
(the `+` in its header), and search for the service account. Switch the search scope from the current organization
to global/instance when the account belongs to another organization, or it will never appear in the results. The
`POST` endpoints above do the same thing and are the only route when the account sits in a different organization
than the resource.

### Role names

Instance (IAM) level:

| Role | Meaning |
| --- | --- |
| `IAM_OWNER` | Manage the instance and all organizations with their content. |
| `IAM_OWNER_VIEWER` | View the instance and all organizations with their content. |
| `IAM_ORG_MANAGER` | Manage all organizations including their policies, projects and users. |
| `IAM_USER_MANAGER` | Manage all users and their authorizations across all organizations. |
| `IAM_ADMIN_IMPERSONATOR` | Impersonate admin and end users from all organizations. |
| `IAM_END_USER_IMPERSONATOR` | Impersonate end users from all organizations. |
| `IAM_LOGIN_CLIENT` | Everything needed to implement your own Login UI. |

Organization level:

| Role | Meaning |
| --- | --- |
| `ORG_OWNER` | Manage everything within the organization. |
| `ORG_OWNER_VIEWER` | View everything within the organization. |
| `ORG_USER_MANAGER` | Manage users and their authorizations within the organization. |
| `ORG_USER_PERMISSION_EDITOR` | Manage user grants and everything needed for that. |
| `ORG_PROJECT_PERMISSION_EDITOR` | Grant projects to other organizations and everything needed for that. |
| `ORG_PROJECT_CREATOR` | For users in the global organization: create projects and manage them. |
| `ORG_DYNAMIC_CLIENT_REGISTRAR` | Register OAuth 2.0 clients via dynamic client registration, nothing else. |
| `ORG_ADMIN_IMPERSONATOR` | Impersonate admin and end users of the organization. |
| `ORG_END_USER_IMPERSONATOR` | Impersonate end users of the organization. |
| `ORG_USER_SELF_MANAGER` | Read policies and delete the user's own account. |
| `SELF_MANAGEMENT_GLOBAL` | In the global organization: create organizations, read policies, delete own account. |

Project level: `PROJECT_OWNER` (manage everything in a project, including granting users),
`PROJECT_OWNER_VIEWER` (view only), `PROJECT_OWNER_GLOBAL` / `PROJECT_OWNER_VIEWER_GLOBAL` (same in the
global organization), `PROJECT_GRANT_OWNER` (same as `PROJECT_OWNER` for a granted project).

Self-hosted System API roles (`SYSTEM_OWNER`, `SYSTEM_OWNER_VIEWER`) belong to the runtime-configured system
user, not to service accounts. `ORG_SETTINGS_MANAGER` and `PROJECT_GRANT_OWNER_VIEWER` appear as columns in the
Administrator Permission Matrix on the administrators reference page but carry no description in its roles
table — read their permissions from the matrix before using them.

**Pick the minimal role.** Grant `*_OWNER_VIEWER` for read-only integrations, `ORG_USER_MANAGER` /
`IAM_USER_MANAGER` when the automation only manages users and service accounts, `ORG_OWNER` (or
`IAM_ORG_MANAGER` for all organizations) when it manages projects and applications, `PROJECT_OWNER` when it
must stay inside one project, and reserve `IAM_OWNER` for bootstrap tooling. Every RPC states the permission
string it needs in its proto comment (e.g. `CreateUser`/`AddKey`/`AddSecret`/`AddPersonalAccessToken` →
`user.write`; the list RPCs → `user.read`), which is the fastest way to reason about a role choice. The
role→permission mapping itself lives in the runtime's `defaults.yaml` under
`InternalAuthZ.RolePermissionMappings`, so a self-hosted operator can read or override it.

## 3. Authenticate the service account

### Common ground: token endpoint and the audience scope

The token endpoint is `POST https://<your instance domain>/oauth/v2/token` with
`Content-Type: application/x-www-form-urlencoded`. A successful response is
`{"access_token":"…","token_type":"Bearer","expires_in":43199}` (the documented sample: ≈12 h; the real value
comes from your instance's OIDC settings). Use the token as `Authorization: Bearer <access_token>`.

### (a) Personal access token — simplest, no audience scope needed

```shell
# POST /v2/users/{user_id}/pats   (Connect: POST /zitadel.user.v2.UserService/AddPersonalAccessToken)
# required permission: user.write
curl -X POST "https://<your instance domain>/v2/users/<service-account-user-id>/pats" \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"expiration_date":"2030-01-01T00:00:00Z"}'
# → {"creation_date":"…","token_id":"<pat-id>","token":"<the PAT>"}
```

- Only **machine** users can have PATs (human PATs are not supported).
- The `token` value is returned **once and never again**; if it is lost, create a new PAT.
- Send it directly: `curl -H "Authorization: Bearer <the PAT>" https://<your instance domain>/management/v1/orgs/me`.
- No audience scope is needed — a PAT is a ready-to-use credential accepted directly by the APIs, whereas the
  OAuth methods below must request the API audience explicitly.
- The v2 request carries a `(validate.rules).timestamp.required = true` constraint on `expiration_date`, so
  send an explicit expiry when you use the API. The Console/API-reference flow ("Personal Access Token > New")
  lets you leave the date empty for a non-expiring token — treat non-expiring PATs as an exception, not the
  default.

### (b) Private key JWT — recommended for automation

1. Generate a key pair and register the public key (or let ZITADEL generate the pair and hand you the JSON key
   file once):

   ```shell
   openssl genrsa -out service-account.pem 2048
   openssl rsa -in service-account.pem -pubout -out service-account.pub
   ```

   ```shell
   # POST /v2/users/{user_id}/keys   (Connect: POST /zitadel.user.v2.UserService/AddKey)
   # required permission: user.write
   curl -X POST "https://<your instance domain>/v2/users/<service-account-user-id>/keys" \
     -H "Authorization: Bearer $BOOTSTRAP_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"expiration_date":"2030-01-01T00:00:00Z","public_key":"<base64 of service-account.pub>"}'
   # → {"creation_date":"…","key_id":"<key-id>","key_content":"<base64 JSON key file, returned once>"}
   ```

   - `public_key` is optional: supply it when you generated the pair yourself. If you let ZITADEL generate the
     key, `key_content` holds the JSON key file (`{"type":"serviceaccount","keyId":"…","key":"…","userId":"…"}`)
     and is returned **once**.
   - `expiration_date` is required by the v2 validation; when ZITADEL generates the key in the Console you may
     leave it empty, and a Console-set expiry ends at midnight of the chosen day.
   - **Key type enum:** the v2 `AddKey` request has *no* key-type field — the type is implicit. The
     `zitadel.authn.v1.KeyType` enum (`KEY_TYPE_JSON`) belongs to the **legacy v1** `AddMachineKey`, where
     `"type":"KEY_TYPE_JSON"` is a required field of the body:

     ```shell
     # POST /management/v1/users/{user_id}/keys   (REST; ManagementService/AddMachineKey, type is required)
     curl -X POST "https://<your instance domain>/management/v1/users/<service-account-user-id>/keys" \
       -H "Authorization: Bearer $BOOTSTRAP_TOKEN" -H 'Content-Type: application/json' \
       -d '{"type":"KEY_TYPE_JSON","expirationDate":"2030-01-01T00:00:00Z"}'
     # → {"keyId":"…","keyDetails":"<base64 JSON key file>","details":{…}}
     ```
   - The legacy v1 service *also* accepts a self-provided `publicKey` and returns `clientId` on
     `PUT /management/v1/users/{user_id}/secret`; if you are migrating scripts, expect camelCase bodies and the
     `x-zitadel-orgid` header instead of `organization_id` in the body.

2. Build the assertion — RS256, header `{"alg":"RS256","kid":"<key-id>"}` and payload:

   ```json
   {"iss":"<service-account-user-id>","sub":"<service-account-user-id>",
    "aud":"https://<your instance domain>","iat":<now>,"exp":<now + 300>}
   ```

   `iss` and `sub` are the service account's user id; `aud` is your instance domain (the issuer); `iat` must not
   be older than one hour, and if `exp` is set further than one hour out `iat` takes precedence — the assertion
   simply stops being accepted. Use the `keyId` from the key file as `kid`.

3. Exchange it:

   ```shell
   curl -X POST 'https://<your instance domain>/oauth/v2/token' \
     -H 'Content-Type: application/x-www-form-urlencoded' \
     --data-urlencode 'grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer' \
     --data-urlencode 'scope=openid profile urn:zitadel:iam:org:project:id:zitadel:aud' \
     --data-urlencode 'assertion=<signed JWT>'
   ```

### (c) Client credentials — add a secret, then use HTTP Basic

```shell
# POST /v2/users/{user_id}/secret   (Connect: POST /zitadel.user.v2.UserService/AddSecret)
# required permission: user.write; re-issuing overwrites any previous secret
curl -X POST "https://<your instance domain>/v2/users/<service-account-user-id>/secret" \
  -H "Authorization: Bearer $BOOTSTRAP_TOKEN" -H 'Content-Type: application/json' -d '{}'
# → {"creation_date":"…","client_secret":"<the secret, shown once>"}

curl -X POST 'https://<your instance domain>/oauth/v2/token' \
  -u '<service-account-username>:<client_secret>' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode 'scope=openid profile urn:zitadel:iam:org:project:id:zitadel:aud'
```

- The **client id is the service account's username** in v2 (the response returns only the secret). The Console
  dialog shows both `ClientID` and `ClientSecret`; the legacy `PUT /management/v1/users/{user_id}/secret`
  returns `client_id` and `client_secret` explicitly.
- `-u` is `client_secret_basic`. With `client_secret_post`, send `client_id` and `client_secret` as form fields
  instead. When building the Basic header by hand, URL-encode id and secret before base64:
  `base64(formUrlEncode(client_id) + ":" + formUrlEncode(client_secret))`.
- Delete a secret with `DELETE /v2/users/{user_id}/secret` (Connect: `RemoveSecret`) or rotate it by calling
  `AddSecret` again — the old secret stops working immediately.

### (d) Optional: pin the token to one organization

Add the reserved scope `urn:zitadel:iam:org:id:{organization-id}` to the token request. ZITADEL then enforces
that the subject is a member of that organization (an unknown organization fails the request) and asserts the
resource-owner claims. `urn:zitadel:iam:org:domain:primary:{domain}` is the domain-based variant. This is the
documented mechanism for restricting a service-account token to a single tenant; use it when one
service account must not act on other organizations even though it holds a wider role.

## 4. Why the audience scope matters

`urn:zitadel:iam:org:project:id:zitadel:aud` adds the ZITADEL project id to the access token's `aud` claim.
**ZITADEL APIs check that they are in the audience and reject a token that does not carry it**, so any token
obtained through the OAuth flows in (b) and (c) must request that scope. **PATs are exempt** — they are accepted
directly as a bearer credential.

Recognisable symptoms of a missing audience:

- `401 UNAUTHENTICATED` with a body like
  `{"code":16,"message":"Token is invalid (AUTH-7fs1e)","details":[{"@type":"type.googleapis.com/zitadel.v1.ErrorDetail","id":"AUTH-7fs1e","message":"Token is invalid"}]}`.
- An "Invalid audience" error from the API, mentioned in ZITADEL's own troubleshooting text for exactly this
  mistake (typically after authenticating a user without the scope and then calling a management API).
- The token introspects fine and its signature verifies, yet every API call 401s — the classic signature: the
  token is structurally valid but not addressed to the API.
- Legacy v1 endpoints describe the same condition in the older style, e.g. a message like `Errors.Token.Invalid`
  (the exact string depends on the version — verify it on your own instance before matching on it).

Fix: re-request the token with `scope=openid profile urn:zitadel:iam:org:project:id:zitadel:aud`. Note the
scope string is the literal project id `zitadel`, not one of your project ids.

## 5. Lifecycle, rotation, hygiene

- **Access tokens** are short-lived; the documented sample returns `expires_in: 43199` (≈12 h). The lifetime is
  an instance-wide setting: `GET /admin/v1/settings/oidc` (permission `iam.read`) and
  `PUT /admin/v1/settings/oidc` (permission `iam.write`) with the fields `access_token_lifetime`,
  `id_token_lifetime`, `refresh_token_idle_expiration`, `refresh_token_expiration`. Do not cache tokens longer
  than their `expires_in`.
- **PATs and keys** carry their own `expiration_date`, set per credential at creation. There is no global default
  you can rely on; a credential created without an expiry lives until deleted. Always set one.
- **Rotate a key without downtime**: call `AddKey` (new key id), ship the new key id to the consumer, wait for
  the change to take effect, then `DELETE /v2/users/{user_id}/keys/{key_id}` (Connect: `RemoveKey`). Because the
  assertion's `kid` selects the key, both keys are valid during the overlap window. Rotate secrets with
  `AddSecret` (overwrites the previous secret immediately — no overlap, so schedule it as a short interruption),
  and replace PATs by creating the new PAT, switching the consumer, then deleting the old one.
- **Revoke a PAT**: `DELETE /v2/users/{user_id}/pats/{token_id}` (Connect: `RemovePersonalAccessToken`).
  `token_id` is the *id*, not the token string; list them with
  `POST /v2/users/pats/search` (Connect: `ListPersonalAccessTokens`, permission `user.read`) or list keys with
  `POST /v2/users/keys/search` (Connect: `ListKeys`). Legacy equivalents exist on
  `/management/v1/users/{user_id}/keys`, `/management/v1/users/{user_id}/pats`.
- **Deactivating or deleting the service account is the kill switch.** `POST /v2/users/{user_id}/deactivate`
  moves the user to `deactivated` (no further authentication — the token endpoint rejects it), and
  `DELETE /v2/users/{user_id}` moves it to `deleted`, after which endpoints that reference the user return
  "User not found". Both stop the service account from minting new tokens; already-issued access tokens expire on
  their own (short-lived), so combine deactivation with a token-lifetime you accept as a worst case. PATs and
  keys belonging to the user are unusable once it can no longer authenticate.
- **Introspect / debug a token**:
  - `POST /oauth/v2/introspect` with form field `token=<access_token>` and client authentication
    (`client_secret_basic` or `private_key_jwt`). Unlike client-side JWT validation this also checks revocation.
  - `GET /oauth/v2/keys` (the `jwks_uri`) to validate JWTs locally, `GET /.well-known/openid-configuration` for
    the endpoints above.
  - Ask the API what the service account can actually do, using its **own** token against the Auth API:
    `GET /auth/v1/users/me`, `POST /auth/v1/permissions/zitadel/me/_search` (the effective permission list),
    `POST /auth/v1/memberships/me/_search` (the administrator roles granted). `GET /auth/v1/healthz` is
    unauthenticated and useful as a reachability check.
- **Never store credentials in a skill or repository.** Keep key files, client secrets and PATs in a secret
  manager or injected environment variables, reference them as `<path to key file>` / `$SERVICE_ACCOUNT_TOKEN`,
  and add the patterns to `.gitignore`. A PAT authenticates as its service account until deleted or expired —
  treating it as code is treating administrator access as code. If a credential may have leaked, revoke first
  (delete the PAT / secret / key), then rotate.

## 6. Common failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| `401` with `"message":"Token is invalid"` and a validated token | Auth header missing, mis-schemed (`Bearer` required), expired access token, or the token lacks the ZITADEL API audience | Check `Authorization: Bearer <token>`; re-request with `scope=openid profile urn:zitadel:iam:org:project:id:zitadel:aud`; use a PAT for a quick sanity check (PATs need no audience scope). |
| `401` invalid audience but the token introspects fine | Token was issued without the `urn:zitadel:iam:org:project:id:zitadel:aud` scope | Re-issue the token with that scope; it must be present for private key JWT and client credentials. |
| `400` on `POST /oauth/v2/token` with `invalid_request` / `grant_type missing` | Wrong form encoding or a grant type the instance does not support | Post `application/x-www-form-urlencoded` with `--data-urlencode`; confirm the grant type in `grant_types_supported` from `/.well-known/openid-configuration`. |
| `400 invalid_grant` on the jwt-bearer grant | Assertion `aud` is not the instance issuer, `iss`/`sub` are not the service account's user id, or `iat` is older than one hour | Set `aud` to `https://<your instance domain>`, `iss`/`sub` to the service-account user id, and keep `iat` fresh (`exp` no more than an hour out). |
| Signing fails locally: library cannot read the key | The RSA private key is passphrase-protected, or you fed the JSON key file's `key` field where a PEM/base64 PEM is expected | Use the unencrypted PEM you generated (`openssl genrsa -out service-account.pem 2048`), or pass the passphrase to your JWT library; ZITADEL never sees the private key and cannot help. |
| `403 PERMISSION_DENIED` on a write | The service account authenticated but holds no administrator role for that resource/level | Grant the role at the correct level: instance (`resource.instance`), organization (`organization_id`), project, or project grant — a role is valid only for the level it was granted on; verify with `POST /auth/v1/memberships/me/_search` and `POST /auth/v1/permissions/zitadel/me/_search`. |
| `403` that looks random: some calls succeed, others fail | The token is pinned to one organization, or the account holds an org-level role while the call targets another organization's resource | Remember only instance-level administrators act across all organizations; drop the `urn:zitadel:iam:org:id:{id}` pin or grant an instance role where appropriate. |
| `404` on a path copied from the protos | The proto annotation is relative; the service base path was not prepended (`/users/machine` instead of `/management/v1/users/machine`) | Use the full served path, or the Connect route. Verify with an unauthenticated probe (401 = exists, 404 = absent). |
| `404` "not found" on an object you know exists | The call is executing in the wrong organization context: v1 defaults to the caller's own organization, v2 needs `organization_id` | v1: send `x-zitadel-orgid: <organization-id>` (or target the org by API). v2: put `organization_id` in the request body. |
| v1 REST call rejected with a marshalling/validation error | v1 bodies are camelCase while v2 uses snake_case | Match the casing to the transport you call (`userName` vs `username`, `accessTokenType` vs `access_token_type`). |
| `405` / `415` on a v2 REST path | The REST route exists for another method, or you sent the wrong content type | Prefer the Connect URL `/<package>.<Service>/<Method>` with `Content-Type: application/json` and `Connect-Protocol-Version: 1`. |
| `404` on `/system/v1/…` when the instance is cloud-hosted | The System API is self-hosted only and is not reachable by service accounts | Use the Admin/Management/v2 APIs with an instance administrator; the System API needs a runtime-configured system user with a self-signed JWT. |
| A Key/Secret/PAT call fails though the user exists | The target user is a **human** user, not a machine user | `AddKey`, `AddSecret` and `AddPersonalAccessToken` are machine-user only. Create the account with `machine` (v2) / `AddMachineUser` (v1); `409` on creation usually means the username is taken in that organization. |
| Assigning a role fails silently in effect: token unchanged | Tokens carry roles as claims issued at mint time; a token obtained before the grant has no new roles | Re-request the access token after changing administrator roles. |

## 7. Verification checklist

1. `curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' https://<your instance domain>/<path>`
   → `401` proves the endpoint exists on this version.
2. `GET /.well-known/openid-configuration` → confirm `token_endpoint`, `grant_types_supported` and
   `token_endpoint_auth_methods_supported` for your instance.
3. Create the service account, then `POST /auth/v1/memberships/me/_search` and
   `POST /auth/v1/permissions/zitadel/me/_search` with its own token to confirm exactly which administrator
   roles and permissions the credential ended up with.
4. Make one read call you expect to succeed (`GET /management/v1/orgs/me`) and one write you expect to be
   denied, to prove the role boundary is where you think it is.
