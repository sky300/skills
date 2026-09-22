# Projects, Roles, Grants, Applications and Role Assignments (ZITADEL v2 API)

Operate ZITADEL projects and everything hanging off them (project roles, project grants, OIDC/API/SAML
applications, client secrets and application keys, and role assignments) through the v2 APIs. Every
endpoint below is a Connect RPC on the `zitadel.project.v2.ProjectService`, `zitadel.application.v2.ApplicationService`
or `zitadel.authorization.v2.AuthorizationService` service; those three services expose no REST/OpenAPI
path, so Connect is the only interface. Verify a method on your own release before relying on it: an
unauthenticated call answers `401` when the RPC is registered and `404` when it is not. See "Verification
index" at the end for the per-path probe result.

## 0. Calling the v2 API

```bash
# Base URL is your instance domain. v2 services are Connect-only: there is no REST/OpenAPI path.
BASE="https://<your instance domain>"

curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/ListProjects" \
  -H 'Content-Type: application/json' \
  -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{"pagination":{"offset":0,"limit":100}}'
```

- Use the Connect path `/zitadel.<package>.v2.<Service>/<Method>` with HTTP POST, `Content-Type: application/json`
  and `Connect-Protocol-Version: 1`. Native gRPC on the same proto is equivalent.
- Do NOT look for `google.api.http` REST paths: the v2 project, application and authorization services
  define none. Only some other v2 services (user, org, oidc, session, settings) still expose REST paths.
- Request/response bodies are proto3 JSON: fields are `camelCase` (`projectId`, `roleKeys`, `expirationDate`),
  enums are sent as their proto names (`OIDC_GRANT_TYPE_AUTHORIZATION_CODE`, `PROJECT_STATE_ACTIVE`),
  timestamps are RFC 3339, and `google.protobuf.Duration` is a string (`"1s"`).
- Fields marked `optional` in the proto are "unset means unchanged" on updates; repeated fields are
  whole-value replacements (see Pitfalls).
- Authenticate with an access token that carries the audience scope `urn:zitadel:iam:org:project:id:zitadel:aud`
  plus the administrator role for the resource. Api access needs a service account with an administrator
  role; the token itself is passed in the `Authorization: Bearer` header.
- The proto comment of each RPC states the required permission (quoted per operation below). Some v2 RPCs
  declare the generic `authenticated` auth option instead of a concrete permission string, i.e. the
  specific role check happens inside the handler — do not assume that any valid token can call them.
- Unsupported calls fail with a Connect error object: `{"code":"permission_denied","message":"..."}`.
  `not_found` is returned for unknown IDs, and several delete/deactivate RPCs return success when the
  desired state already exists (they are idempotent by design).

## 1. Mental model: decide which organization owns the project first

- `instance` > `organization` > `project` > `application`. A project belongs to exactly one organization
  and groups applications, roles and role assignments.
- Roles are defined on the project and are the only thing authorizations reference: a role has a `key`
  (the contract used in code, tokens and permission checks), a `displayName` and an optional `group`
  (grouping for the UI only).
- A role assignment (API name: authorization; older name: user grant) binds *a user* to *role keys of a
  project*, in the context of one organization. All applications of a project share the same roles and
  role assignments.
- A project can be granted to another organization (project grant). The granted organization then manages
  the role assignments for *its own* users on that project, without owning it. The granting organization
  chooses which subset of role keys is available to the grantee.
- Decide the owning organization before creating anything: a project in the wrong organization cannot be
  moved, and every later decision (branding, who administers it, which users can hold roles, whether you
  need a grant at all) follows from it. Put a project in the organization that *operates* the software;
  the operator can then create role assignments for its own users directly, and grant the project out to
  customers instead of moving people between organizations.
- Multi-tenant rule of thumb: one project per software product, one grant per customer organization,
  roles defined once on the project.

## 2. Projects

### CreateProject — `project.create`

```bash
curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/CreateProject" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "organizationId": "<organization-id>",
    "name": "<project-name>",
    "projectRoleAssertion": true,
    "authorizationRequired": false,
    "projectAccessRequired": false,
    "privateLabelingSetting": "PRIVATE_LABELING_SETTING_ALLOW_LOGIN_USER_RESOURCE_OWNER_POLICY"
  }'
```

| field | meaning |
|---|---|
| `organizationId` (required) | organization that owns the project |
| `name` (required, 1–200 chars) | shown to users, e.g. in sign-in flows |
| `projectId` (optional, 1–200) | pin a project id; omit and let ZITADEL generate one (recommended, returned in the response) |
| `projectRoleAssertion` | include role information of the project in the userinfo endpoint (tokens still depend on application settings) |
| `authorizationRequired` | user must have at least one role of this project to log in to an application of it |
| `projectAccessRequired` | the user's organization must own the project or hold a grant, otherwise login is refused |
| `privateLabelingSetting` | which branding drives the login UI. `PRIVATE_LABELING_SETTING_ENFORCE_PROJECT_RESOURCE_OWNER_POLICY` = always the project owner's branding; `PRIVATE_LABELING_SETTING_ALLOW_LOGIN_USER_RESOURCE_OWNER_POLICY` = switch to the user's organization once identified (typical B2B); unspecified = system default |

Booleans default to `false` when omitted; set them deliberately rather than relying on that, because
`authorizationRequired` changes login behavior for every application of the project.

Response: `{"projectId":"<project-id>","creationDate":"..."}`.

*Console: Organization > Projects > Create New Project (name only; adjust role settings afterwards).*

### UpdateProject — `project.write`

```bash
curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/UpdateProject" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{"projectId":"<project-id>","name":"<new-project-name>","authorizationRequired":true}'
```

`name`, `projectRoleAssertion`, `authorizationRequired`, `projectAccessRequired` and
`privateLabelingSetting` are optional: omit a field to keep its current value. Response: `{"changeDate":"..."}`.

*Console: project detail page > General / Role Settings / Branding.*

### DeactivateProject / ActivateProject — `project.write`

```bash
-d '{"projectId":"<project-id>"}'    # DeactivateProject, ActivateProject
```

Deactivating stops login for every application in the project; both calls are idempotent. Response: `{"changeDate":"..."}`.

*Console: project detail page > Deactivate / Activate.*

### DeleteProject — `project.delete`

```bash
-d '{"projectId":"<project-id>"}'    # DeleteProject
```

Returns `{"deletionDate":"..."}`; a missing project is not an error (idempotent). The proto does not
document whether applications, roles and role assignments of the project are removed with it — verify on
a test project before deleting a project that still has applications, grants or role assignments.

*Console: project detail page > Delete.*

### GetProject — `project.read`

```bash
-d '{"projectId":"<project-id>"}'    # GetProject -> {"project": { ... }}
```

*Console: project detail page.*

### ListProjects — `project.read`

```bash
curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/ListProjects" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "pagination": {"offset": 0, "limit": 100, "asc": false},
    "sortingColumn": "PROJECT_FIELD_NAME_NAME",
    "filters": [
      {"projectNameFilter": {"projectName": "pos", "method": "TEXT_FILTER_METHOD_CONTAINS_IGNORE_CASE"}},
      {"organizationIdFilter": {"organizationId": "<organization-id>", "type": "OWNED_OR_GRANTED"}}
    ]
  }'
```

- Filters are combined with AND; each filter is a oneof, so send one key per filter object.
- `projectNameFilter`: `projectName` + `method` (`TEXT_FILTER_METHOD_EQUALS`, `_EQUALS_IGNORE_CASE`,
  `_STARTS_WITH`, `_STARTS_WITH_IGNORE_CASE`, `_CONTAINS`, `_CONTAINS_IGNORE_CASE`, `_ENDS_WITH`,
  `_ENDS_WITH_IGNORE_CASE`).
- `inProjectIdsFilter`: `{"ids":["<project-id>","<project-id>"]}`.
- `organizationIdFilter`: `organizationId` + `type` = `OWNED`, `GRANTED` or `OWNED_OR_GRANTED`
  (default when omitted: `OWNED_OR_GRANTED`). v2 unified owned and granted projects into this single
  endpoint, which is why a listing can contain projects owned by other organizations.
- `sortingColumn`: `PROJECT_FIELD_NAME_ID`, `_CREATION_DATE`, `_CHANGE_DATE`, `_NAME`.
- Response: `pagination.totalResult` / `pagination.appliedLimit` plus `projects[]` with `projectId`,
  `organizationId`, `creationDate`, `changeDate`, `name`, `state`
  (`PROJECT_STATE_ACTIVE` / `PROJECT_STATE_INACTIVE`), the three flags, `privateLabelingSetting`, and for
  granted projects the optional `grantedOrganizationId`, `grantedOrganizationName`, `grantedState`.

*Console: Organization > Projects (list, includes projects granted to the organization).*

## 3. Project roles

### AddProjectRole — `project.role.write`

```bash
curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/AddProjectRole" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{"projectId":"<project-id>","roleKey":"admin","displayName":"Administrator","group":"Administration"}'
```

- `roleKey` (required, ≤200) is the only attribute that matters at runtime: it is used for permission
  checks, in token claims and in userinfo responses.
- `displayName` (required) is human readable and shown to users; `group` (optional, ≤200) is a UI grouping
  helper only — not related to user groups.
- A role key must be unique within the project; re-adding an existing key fails.
- Because role keys appear in tokens and application code, treat them as a public API: pick stable,
  namespaced keys (`app.admin`) once, and never rename a key after applications depend on it.

Response: `{"creationDate":"..."}`.

*Console: project > Roles > Create New Role.*

### UpdateProjectRole — `project.role.write`

```bash
-d '{"projectId":"<project-id>","roleKey":"admin","displayName":"Administrator (renamed)","group":"Admins"}'
```

The key is not editable and `roleKey` identifies the role to change. Only `displayName` and `group` can
change. Response: `{"changeDate":"..."}`.

*Console: project > Roles > edit role.*

### RemoveProjectRole — `project.role.write`

```bash
-d '{"projectId":"<project-id>","roleKey":"admin"}'
```

Removes the role from the project *and* from every resource that depends on it: project grants and role
assignments. Removing a role therefore revokes that role from all users, in this organization and in
grantee organizations. Removing a non-existent key is not an error. Response: `{"removalDate":"..."}`.

*Console: project > Roles > delete role.*

### ListProjectRoles — `project.role.read`

```bash
curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/ListProjectRoles" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "projectId": "<project-id>",
    "pagination": {"limit": 100},
    "sortingColumn": "PROJECT_ROLE_FIELD_NAME_KEY",
    "filters": [{"roleKeyFilter": {"key": "app.", "method": "TEXT_FILTER_METHOD_STARTS_WITH"}}]
  }'
```

- `sortingColumn`: `PROJECT_ROLE_FIELD_NAME_KEY`, `_CREATION_DATE`, `_CHANGE_DATE`.
- Filters: `roleKeyFilter` (`key` + `method`) or `displayNameFilter` (`displayName` + `method`).
- Response: `pagination` plus `projectRoles[]` = `{projectId, key, creationDate, changeDate, displayName, group}`.

*Console: project > Roles.*

## 4. Project grants

A project grant lets another organization manage role assignments for its own users on your project. The
grant carries the subset of role keys the grantee may hand out.

### CreateProjectGrant — `project.grant.create`

```bash
curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/CreateProjectGrant" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{"projectId":"<project-id>","grantedOrganizationId":"<organization-id>","roleKeys":["admin","viewer"]}'
```

- `grantedOrganizationId` is the customer/partner organization receiving the grant.
- `roleKeys` are role keys that already exist on the project; any key that is not a project role cannot be
  granted. Grant the minimum useful set.
- Response: `{"creationDate":"..."}` — there is no returned grant id. A grant is addressed by the pair
  (`projectId`, `grantedOrganizationId`) in every later call.

*Console: project > Project Grants > New > search the partner organization by domain > select roles > Save.*

### UpdateProjectGrant — `project.grant.write`

```bash
-d '{"projectId":"<project-id>","grantedOrganizationId":"<organization-id>","roleKeys":["admin","viewer","accounting"]}'
```

`roleKeys` is a full replacement: any role key left out is removed from the grant, and role assignments
that used a removed key are deleted as well. To add a role, resend the complete desired list. Response:
`{"changeDate":"..."}`.

*Console: project > Project Grants > edit the grant > change the selected roles.*

### DeactivateProjectGrant / ActivateProjectGrant — `project.grant.write`

```bash
-d '{"projectId":"<project-id>","grantedOrganizationId":"<organization-id>"}'
```

Deactivating a grant blocks login for applications of the project for users of the granted organization,
without touching their role assignments. Response: `{"changeDate":"..."}`.

*Console: project > Project Grants > deactivate / activate.*

### DeleteProjectGrant — `project.grant.delete`

```bash
-d '{"projectId":"<project-id>","grantedOrganizationId":"<organization-id>"}'
```

Deletes the grant and all role assignments created for it; the grantee's users lose access (if permissions
are checked). Idempotent. Response: `{"deletionDate":"..."}`.

*Console: project > Project Grants > delete.*

### ListProjectGrants — `project.grant.read`

```bash
curl -sS -X POST "$BASE/zitadel.project.v2.ProjectService/ListProjectGrants" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "pagination": {"limit": 100},
    "sortingColumn": "PROJECT_GRANT_FIELD_NAME_CREATION_DATE",
    "filters": [{"grantedOrganizationIdFilter": {"id": "<organization-id>"}}]
  }'
```

- `sortingColumn`: `PROJECT_GRANT_FIELD_NAME_PROJECT_ID`, `_CREATION_DATE`, `_CHANGE_DATE`.
- Filters: `projectNameFilter`, `roleKeyFilter` (`{"key":"admin"}`), `inProjectIdsFilter`
  (`{"ids":[...]}`), `organizationIdFilter` (granting org, `{"id":"..."}`), `grantedOrganizationIdFilter`
  (grantee org, `{"id":"..."}`).
- Response: `projectGrants[]` = `{organizationId (granter), grantedOrganizationId, grantedOrganizationName,
  grantedRoleKeys, projectId, projectName, creationDate, changeDate, state}`
  (`PROJECT_GRANT_STATE_ACTIVE` / `_INACTIVE`).

*Console: project > Project Grants.*

## 5. Applications

One endpoint creates all three types; the oneof you populate selects the type. The application name and
(in `UpdateApplication`) the project id are top-level fields for every type.

### 5.1 Web OIDC application with authorization code flow (+ PKCE) — `project.app.write`

```bash
curl -sS -X POST "$BASE/zitadel.application.v2.ApplicationService/CreateApplication" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "projectId": "<project-id>",
    "name": "<application-name>",
    "oidcConfiguration": {
      "redirectUris": ["https://<your app host>/auth/callback"],
      "postLogoutRedirectUris": ["https://<your app host>/signedout"],
      "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
      "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
      "applicationType": "OIDC_APP_TYPE_WEB",
      "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
      "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
      "idTokenRoleAssertion": true,
      "accessTokenRoleAssertion": true,
      "idTokenUserinfoAssertion": false,
      "developmentMode": false,
      "clockSkew": "1s",
      "additionalOrigins": [],
      "loginVersion": {"loginV2": {"baseUri": "https://<your login host>"}}
    }
  }'
```

Response: `{"applicationId":"<application-id>","creationDate":"...","oidcConfiguration":{"clientId":"...",
"clientSecret":"...","nonCompliant":false,"complianceProblems":[]}}` — `clientSecret` is only present for
the secret-based auth methods and is shown **once**.

There is no PKCE field: PKCE is a property of the authorization request the client sends
(`code_challenge`/`code_verifier`), not of the application. What you configure here is the code response
type + authorization-code grant type + a client type that can hold a secret (Web) or not (User Agent,
Native). Keep `developmentMode: false` for production, so only `https` redirect URIs are accepted.

#### OIDC configuration fields

| field | meaning | default when omitted |
|---|---|---|
| `redirectUris` | allowed callback URIs; the `redirect_uri` of the auth request must match one exactly. Native apps may use custom schemes (`myapp://`) | empty (no callback allowed) |
| `postLogoutRedirectUris` | allowed `post_logout_redirect_uri` values | empty |
| `responseTypes` | `OIDC_RESPONSE_TYPE_CODE`, `_ID_TOKEN`, `_ID_TOKEN_TOKEN` | `OIDC_RESPONSE_TYPE_UNSPECIFIED` (not allowed in create requests — the value must be set) |
| `grantTypes` | flows the app may use: `OIDC_GRANT_TYPE_AUTHORIZATION_CODE`, `_IMPLICIT` (deprecated), `_REFRESH_TOKEN`, `_DEVICE_CODE`, `_TOKEN_EXCHANGE` | `OIDC_GRANT_TYPE_AUTHORIZATION_CODE` (value 0) |
| `applicationType` | client type: `OIDC_APP_TYPE_WEB` (confidential), `_USER_AGENT` (SPA), `_NATIVE` (mobile/desktop). Affects allowed grants/auth methods; cannot be changed after creation | `OIDC_APP_TYPE_WEB` (value 0) |
| `authMethodType` | how the client authenticates at the token endpoint: `OIDC_AUTH_METHOD_TYPE_BASIC` (client id + secret, HTTP Basic), `_POST` (secret in the body), `_NONE` (public client, PKCE only), `_PRIVATE_KEY_JWT` (signed assertion, no shared secret) | `OIDC_AUTH_METHOD_TYPE_BASIC` (value 0) |
| `version` | OIDC version; only `OIDC_VERSION_1_0` exists | `OIDC_VERSION_1_0` |
| `developmentMode` | allow non-compliant/insecure settings such as HTTP or glob redirect URIs. Never enable in production | `false` |
| `accessTokenType` | `OIDC_TOKEN_TYPE_BEARER` (opaque, must be introspected) or `OIDC_TOKEN_TYPE_JWT` (self-contained, validatable offline) | `OIDC_TOKEN_TYPE_BEARER` (value 0) |
| `accessTokenRoleAssertion` | put the user's roles into the access token; only meaningful with a JWT access token and when roles are also requested/asserted on the project | `false` |
| `idTokenRoleAssertion` | put the user's roles into the ID token | `false` |
| `idTokenUserinfoAssertion` | add profile/email/address/phone claims to the ID token even when an access token is issued. Violates the OIDC spec and leaks personal data into a browser-stored token — enable only when a client cannot call userinfo | `false` |
| `clockSkew` | tolerance for clock differences; added to `exp`, subtracted from `iat`, `auth_time`, `nbf`. Range 0s–5s | `0s` |
| `additionalOrigins` | extra HTTP origins (scheme+host+port) allowed to call the API, on top of the origins derived from `redirectUris`; needed for SPAs calling ZITADEL from another origin | empty |
| `skipNativeAppSuccessPage` | skip the "open the application again" success page for native apps | `false` |
| `backChannelLogoutUri` | endpoint notified about terminated sessions per OIDC back-channel logout | empty |
| `loginVersion` | which login UI handles authentication: `{"loginV1":{}}` (hosted login V1) or `{"loginV2":{"baseUri":"..."}}` (new login UI, optionally self-hosted). Unset = instance default | unset (instance default) |
| `ios` / `android` | native app-link (passkey) associations: `{"teamId":"ABCDE12345","bundleId":"com.example.app"}` and `{"packageName":"com.example.app","sha256CertFingerprints":["<64 hex chars>"]}` | empty |

### 5.2 API application (machine-to-machine) — `project.app.write`

```bash
curl -sS -X POST "$BASE/zitadel.application.v2.ApplicationService/CreateApplication" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "projectId": "<project-id>",
    "name": "<api-application-name>",
    "apiConfiguration": {"authMethodType": "API_AUTH_METHOD_TYPE_PRIVATE_KEY_JWT"}
  }'
```

- `API_AUTH_METHOD_TYPE_BASIC`: the API authenticates with the generated `clientSecret` (HTTP Basic or
  client-credentials body). The create response contains `clientSecret` once.
- `API_AUTH_METHOD_TYPE_PRIVATE_KEY_JWT`: no shared secret; you create an application key and sign a JWT
  assertion with it (client-credentials style with private key JWT). Prefer this for new APIs.
- Response: `{"applicationId":"...","creationDate":"...","apiConfiguration":{"clientId":"...","clientSecret":"..."}}`
  (`clientSecret` only for the basic method).

*Console: project > Applications > New > API > choose (Private Key) JWT or Basic.*

### 5.3 SAML application — `project.app.write`

Provide exactly one of `metadataUrl` (≤2048 chars) or `metadataXml` (raw XML, ≤500 KB; base64 in JSON), plus
optionally `loginVersion`. Response: `{"applicationId":"...","creationDate":"...","samlConfiguration":{}}`.

```bash
# CreateApplication with samlConfiguration (endpoint as in 5.1)
curl -sS -X POST "$BASE/zitadel.application.v2.ApplicationService/CreateApplication" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "projectId": "<project-id>",
    "name": "<saml-application-name>",
    "samlConfiguration": {"metadataUrl": "https://<sp host>/saml/metadata"}
  }'
```

*Console: project > Applications > New > SAML > paste or link the metadata.*

### 5.4 Update, deactivate, delete, list, get

```bash
# UpdateApplication — project.app.write. Fields left out stay unchanged; repeated fields are replaced.
-d '{"applicationId":"<application-id>","projectId":"<project-id>","name":"<new-name>",
     "oidcConfiguration":{"redirectUris":["https://<your app host>/auth/callback"]}}'

# DeactivateApplication / ReactivateApplication / DeleteApplication — take both ids.
-d '{"applicationId":"<application-id>","projectId":"<project-id>"}'

# GetApplication — project.app.read
-d '{"applicationId":"<application-id>"}'          # -> {"application":{...,"oidcConfiguration":{...}}}
```

- `UpdateApplication` returns the application's `changeDate`; if nothing changed you get the previous
  `changeDate`, which is the cheap way to detect a no-op update.
- `DeactivateApplication` (permission `project.app.write`) blocks logins without deleting configuration.
  `DeleteApplication` (permission `project.app.delete`) is idempotent and returns `deletionDate`.
- `ListApplications` — `project.app.read`:

```bash
-d '{
  "pagination": {"limit": 100},
  "sortingColumn": "APPLICATION_SORT_BY_NAME",
  "filters": [
    {"projectIdFilter": {"projectId": "<project-id>"}},
    {"typeFilter": "APPLICATION_TYPE_OIDC"},
    {"stateFilter": "APPLICATION_STATE_ACTIVE"}
  ]
}'
```

  Filters (AND-combined, one key each): `projectIdFilter`, `nameFilter` (`name`+`method`), `stateFilter`
  (`APPLICATION_STATE_ACTIVE` / `_INACTIVE` / `_REMOVED`), `typeFilter` (`APPLICATION_TYPE_OIDC` / `_API` /
  `_SAML`, `UNSPECIFIED` rejected), `clientIdFilter` (exact match; OIDC/API only), `entityIdFilter` (exact
  match; SAML only). `sortingColumn`: `APPLICATION_SORT_BY_ID`, `_NAME`, `_STATE`, `_CREATION_DATE`,
  `_CHANGE_DATE`. Response: `applications[]` + `pagination`; each item carries exactly one configuration
  object (`oidcConfiguration` with `clientId`, `apiConfiguration` with `clientId`+`authMethodType`, or
  `samlConfiguration`).
- `ListApplications` takes the `filter.v2` shape (`pagination` + `filters`), **not** the `query` + `queries`
  shape that `ListUsers` and `ListOrganizations` take. A `query` sent here is silently ignored: the call
  answers `200` with every application at the default limit of 100, so an unfiltered list is easy to
  mistake for a filtered one. Check `pagination.appliedLimit` whenever you narrow a query.
- Omitting `filters` lists every application the credential can read, across projects (each item carries
  `projectId`, so the result can be grouped per project without further calls). For an instance
  administrator that is the whole instance: one call, then read `pagination.totalResult`, which is the
  cheapest way to answer "how many applications does this instance have". An organization-scoped
  credential sees only its own organization, so state which credential produced the number.

*Console: project > Applications (list, state column, deactivate/delete in the row menu).*

## 6. Application credentials: client id, client secret, application keys

### Where the client id lives

`clientId` is returned by `CreateApplication` (`oidcConfiguration.clientId` / `apiConfiguration.clientId`)
and can be read later with `GetApplication`, `ListApplications` (also as an exact-match filter via
`clientIdFilter`) or the application detail page in the Console. It is not secret.

Read it back with `GetApplication` -> `oidcConfiguration.clientId` / `apiConfiguration.clientId`.

### Client secret — `project.app.write`, shown once

```bash
curl -sS -X POST "$BASE/zitadel.application.v2.ApplicationService/GenerateClientSecret" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{"applicationId":"<application-id>","projectId":"<project-id>"}'
# -> {"clientSecret":"<client-secret>","creationDate":"..."}
```

- Works for API and OIDC applications whose auth method uses a secret; it is the only way to get a secret
  if you lost the one from `CreateApplication`, and it is the rotation mechanism.
- The response is the only place the value ever appears: ZITADEL does not expose secrets for reading.
  Consume it programmatically into your secret manager in the same step; do not print it into a shell
  history, a note, a skill/runbook or a ticket.
- Store credentials only where the workload can read them (secret manager, orchestrator secret, mounted
  file with tight permissions) — never inside a repository, an infrastructure-as-code default value, or
  documentation. Put the rotation procedure, not the value, in your runbooks.
- Rotate on schedule and on suspicion: generate a new secret, deploy it to the client, then verify logins
  before decommissioning the old credential. Whether the previously issued secret keeps working after
  regeneration is not documented — treat every rotation as "verify with the client".

*Console: (service account or application detail) > Actions > Generate Client Secret — value shown once.*

### Application keys — `project.app.write`, returned once

```bash
curl -sS -X POST "$BASE/zitadel.application.v2.ApplicationService/CreateApplicationKey" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "applicationId": "<application-id>",
    "projectId": "<project-id>",
    "expirationDate": "2027-01-01T00:00:00Z"
  }'
# -> {"keyId":"<key-id>","creationDate":"...","keyDetails":"<base64 JSON key file>"}
```

- `keyDetails` is the serialized private key (a JSON key file, comparable to the key file used for
  client-credentials/JSON key authentication); it is returned once and cannot be retrieved again.
- The v2 request takes only the application, the project and an expiration date — there is **no key type
  enum in the v2 API**. The key-type field (`KEY_TYPE_JSON`) belongs to the legacy v1 `AddAppKey`, which
  lives under the Management REST prefix (`POST /management/v1/projects/{project_id}/apps/{app_id}/keys`
  with a camelCase body). Migrate tooling to v2 rather than porting the type parameter.
- Always set `expirationDate` (the proto example uses a far-future date, but a bounded lifetime is the
  point of a key) and store the key file like a password.

```bash
# List keys — project.app.read
-d '{
  "pagination": {"limit": 100},
  "sortingColumn": "APPLICATION_KEYS_SORT_BY_EXPIRATION",
  "filters": [{"applicationIdFilter": {"applicationId": "<application-id>"}}]
}'
# -> {"keys":[{"keyId":"...","applicationId":"...","projectId":"...","organizationId":"...",
#             "creationDate":"...","expirationDate":"..."}],"pagination":{...}}

# Get one key (metadata only) — project.app.read
-d '{"keyId":"<key-id>"}'                    # GetApplicationKey

# Delete a key — project.app.write
-d '{"keyId":"<key-id>","applicationId":"<application-id>","projectId":"<project-id>"}'   # DeleteApplicationKey
```

- Other key filters: `projectIdFilter` (`{"projectId":"<project-id>"}`) and `organizationIdFilter`
  (`{"organizationId":"<organization-id>"}`), for cross-application key inventories.
- `sortingColumn`: `APPLICATION_KEYS_SORT_BY_ID`, `_PROJECT_ID`, `_APPLICATION_ID`, `_CREATION_DATE`,
  `_ORGANIZATION_ID`, `_EXPIRATION`, `_TYPE` (default is by key id).
- Keep an inventory: list keys per application, expire-dates in view, and delete keys whose client no
  longer exists.

*Console: application detail page > Keys / (Private Key) JWT section — create, list, delete.*

## 7. Role assignments (authorizations)

Terminology: the API/service is `AuthorizationService` and the resource is an "authorization"; the Console
and newer docs call the same thing "role assignment" (older docs: "user grant").

### CreateAuthorization — `user.grant.write`

```bash
curl -sS -X POST "$BASE/zitadel.authorization.v2.AuthorizationService/CreateAuthorization" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "userId": "<user-id>",
    "projectId": "<project-id>",
    "organizationId": "<organization-id>",
    "roleKeys": ["admin"]
  }'
# -> {"id":"<authorization-id>","creationDate":"..."}
```

| field | meaning |
|---|---|
| `userId` (required) | the user receiving the roles |
| `projectId` (required) | project whose roles are assigned |
| `organizationId` (required) | organization the authorization belongs to: the organization that **owns** the project, or the organization that **holds the grant** for it. It does not have to be the user's own organization — for a granted project, pass the grantee organization when the grantee assigns roles to its users |
| `roleKeys` (unique) | role keys to grant; must be roles of this project (or of the grant, for a granted project). An unknown key cannot be granted — the request fails rather than silently ignoring it |

Response `id` is the authorization id used by all subsequent update/activate/delete calls.

*Console: Organization > Users > user > Authorizations > New (also reachable from the project's Role
Assignments section or the organization page).*

### UpdateAuthorization — `user.grant.write`

```bash
-d '{"id":"<authorization-id>","roleKeys":["admin","viewer"]}'
```

Full replacement: role keys omitted from the list are revoked. Response: `{"changeDate":"..."}`.

*Console: user > Authorizations > edit the role assignment.*

### Activate / Deactivate / Delete — `user.grant.write` (`user.grant.delete` for delete)

```bash
-d '{"id":"<authorization-id>"}'    # ActivateAuthorization, DeactivateAuthorization, DeleteAuthorization
```

- Deactivating keeps the record but removes the roles from any authorization information such as an access
  token; the data stays queryable through the API.
- Deleting is idempotent and returns `deletionDate`. Both are the fast ways to revoke access for a single
  user without touching the project, its roles or its grants.

*Console: user > Authorizations > deactivate / delete.*

### ListAuthorizations — `user.grant.read`

```bash
# All role assignments of a project, filtered by role key -> who holds role "admin" in this project
curl -sS -X POST "$BASE/zitadel.authorization.v2.AuthorizationService/ListAuthorizations" \
  -H 'Content-Type: application/json' -H 'Connect-Protocol-Version: 1' \
  -H "Authorization: Bearer <access-token>" \
  -d '{
    "pagination": {"offset": 0, "limit": 100},
    "sortingColumn": "AUTHORIZATION_FIELD_NAME_CREATED_DATE",
    "filters": [
      {"projectId": {"id": "<project-id>"}},
      {"roleKey": {"key": "admin", "method": "TEXT_FILTER_METHOD_EQUALS"}}
    ]
  }'
```

- Filters (AND-combined, one key each): `authorizationIds` (`{"ids":[...]}`), `organizationId`
  (`{"id":"..."}`, the org the authorization was granted for), `state`
  (`{"state":"STATE_ACTIVE"}` / `STATE_INACTIVE`), `inUserIds` (`{"ids":[...]}`), `userOrganizationId`,
  `userPreferredLoginName`, `userDisplayName`, `projectId`, `projectName`, `roleKey`,
  `projectGrantId` (`{"id":"..."}`).
- `projectId`, `projectName` and `projectGrantId` filters also match authorizations created through grants
  of the same project, so do not interpret a hit as "owned by this organization".
- `sortingColumn`: `AUTHORIZATION_FIELD_NAME_CREATED_DATE`, `_CHANGED_DATE`, `_ID`, `_USER_ID`,
  `_PROJECT_ID`, `_ORGANIZATION_ID`, `_USER_ORGANIZATION_ID`.
- Response: `authorizations[]` with `id`, `creationDate`, `changeDate`, `state`, the resolved `project`
  (`id`, `name`, `organizationId`), `organization` (`id`, `name` — the org the assignment belongs to),
  `user` (`id`, `preferredLoginName`, `displayName`, `avatarUrl`, `organizationId`) and `roles[]`
  (`key`, `displayName`, `group`). This is the query to answer "which users hold role X in project Y" and
  "which roles does user U have (and in which organization)".
- Listing your own authorizations needs no permission; listing others' requires `user.grant.read`.

*Console: user > Authorizations, or project > Role Assignments (both show the same data).*

## 8. Console equivalents

| operation | Console path |
|---|---|
| List/create/update/deactivate/delete project | Organization > Projects > Create New Project; project detail page > General / Role Settings / Branding / Deactivate / Delete |
| Project roles (add/update/remove/list) | project > Roles > New / edit / delete |
| Project grants (create/update/deactivate/delete/list) | project > Project Grants > New (search partner org by domain, select roles) / edit / deactivate / delete |
| Create application (OIDC web/native/user-agent, API, SAML) | project > Applications > New > pick type > stepper > review > create |
| Application settings (redirect URIs, dev mode, token settings, additional origins, auth method, native app links, login UI) | application detail page > sections Redirect URIs / Development Mode / Token Settings / Additional Origins / Auth Method / Native App Links / Use new login UI |
| Client id / client secret | application detail page > Client information; Actions > Generate Client Secret (value shown once) |
| Application keys | application detail page > Keys / (Private Key) JWT section |
| Role assignments (authorizations) | user page > Authorizations > New, or project > Role Assignments > New (also from the organization page) |

Prefer the Console for one-off inspections and for the branding/UI-only settings; prefer the API for
anything reproducible, reviewable or multi-tenant (creating a grant per customer, assigning the same role
set to many users, provisioning applications in a pipeline).

## 9. Pitfalls

1. **Deleting an application deletes only the client.** Roles live on the project and users live in the
   organization, so deleting (or deactivating) an application leaves users and their role assignments
   untouched. To remove access you must change role assignments, roles, or the project/grant state.
2. **A grant's role keys must be a subset of the project's roles at grant time.** Only role keys that
   already exist on the project can be granted; grant the minimum set, because a granter that adds roles
   later does not automatically extend existing grants.
3. **Repeated fields are replaced, not merged.** `UpdateProjectGrant.roleKeys`,
   `UpdateAuthorization.roleKeys`, `UpdateOIDCApplicationConfiguration.redirectUris` and friends are
   whole-list replacements. Always read-modify-write, or you will silently revoke roles and lose redirect
   URIs. Removing a role from a grant also deletes the role assignments that used it.
4. **Removing a project role cascades.** `RemoveProjectRole` deletes the role from grants and from all role
   assignments, for every organization involved. Renaming a role key is not possible — create the new key,
   migrate consumers and assignments, then remove the old one.
5. **`DeleteProjectGrant` revokes access for a whole customer.** It also removes the role assignments
   created for that grant. Deactivate instead of deleting when you may need the configuration back.
6. **Deactivating a project kills logins for all its applications; deactivating a grant kills logins for
   that customer.** Neither touches the other's configuration, but both are effectively an outage, so
   schedule them and check whether `authorizationRequired` / `projectAccessRequired` are enabled — those
   flags turn a "missing role" or "missing grant" into a hard login failure.
7. **Required permission per operation** (from the proto comments):

   | operation | permission |
   |---|---|
   | CreateProject | `project.create` |
   | UpdateProject, DeactivateProject, ActivateProject | `project.write` |
   | DeleteProject | `project.delete` |
   | GetProject, ListProjects | `project.read` |
   | AddProjectRole, UpdateProjectRole, RemoveProjectRole | `project.role.write` |
   | ListProjectRoles | `project.role.read` |
   | CreateProjectGrant | `project.grant.create` |
   | UpdateProjectGrant, DeactivateProjectGrant, ActivateProjectGrant | `project.grant.write` |
   | DeleteProjectGrant | `project.grant.delete` |
   | ListProjectGrants | `project.grant.read` |
   | CreateApplication, UpdateApplication, DeactivateApplication, ReactivateApplication, GenerateClientSecret, CreateApplicationKey, DeleteApplicationKey | `project.app.write` |
   | GetApplication, ListApplications, GetApplicationKey, ListApplicationKeys | `project.app.read` |
   | DeleteApplication | `project.app.delete` |
   | CreateAuthorization, UpdateAuthorization, ActivateAuthorization, DeactivateAuthorization | `user.grant.write` |
   | DeleteAuthorization | `user.grant.delete` |
   | ListAuthorizations | `user.grant.read` (not required for your own authorizations) |

   The permission names are namespaced per resource (`project.app.write`, not `app.write`); grant the
   narrowest one to the service account that runs your tooling instead of Org Owner.
8. **Organization context moved into the body in v2.** Pass `organizationId` in the request
   (`CreateProject.organizationId`, `CreateAuthorization.organizationId`); the legacy v1 REST API takes it
   from the `x-zitadel-orgid` header (`POST /management/v1/…`). Do not build new tooling around that
   header; prefer the v2 Connect call wherever the resource exists there, and keep the two idioms apart:
   v1 = REST prefix + camelCase body + org header, v2 = Connect path + JSON body carrying the org id.
9. **Secrets and keys are write-once reads.** `GenerateClientSecret`, the `clientSecret` in
   `CreateApplication`/`CreateOIDCApplicationResponse` and `CreateApplicationKey.keyDetails` return the
   value in the response only. Persist it in a secret manager as part of the same operation, never in
   notes, repositories or tickets, and rotate it (generate new, deploy, verify, retire) instead of sharing
   it around.
10. **Client ids are not secrets, client secrets are not configuration.** Store the client id wherever it
    is convenient (it appears in tokens and URLs), but treat the secret/key file as a credential with a
    lifetime; set `expirationDate` on application keys and keep them listed and reviewed.
11. **Enabling `projectRoleAssertion` alone does not put roles into tokens.** Token claims need the
    per-application switches (`idTokenRoleAssertion`, `accessTokenRoleAssertion`) and a JWT access token —
    with `OIDC_TOKEN_TYPE_BEARER` the roles are not in the token at all and consumers must introspect.
    Roles can alternatively be requested per scope, which is the cleaner option for third-party clients.
12. **`idTokenUserinfoAssertion` is non-compliant by design.** It copies profile/email/address/phone claims
    into the ID token even when an access token exists, which leaks personal data into a token that
    browsers store. Use it only for clients that cannot call the userinfo endpoint.
13. **`developmentMode` weakens redirect-URI validation** (HTTP, glob patterns, wildcard-ish patterns).
    Keep it off outside local development and re-check `nonCompliant` / `complianceProblems` in the create
    response, since ZITADEL reports non-compliant configurations there instead of failing the call.
14. **An application's type cannot be changed after creation** — `UpdateApplication` can change the
    configuration of the existing type, not swap OIDC for SAML/API. To re-type an application, create a new
    one and move the dependency to its new client id/secret.
15. **Always paginate with an explicit limit and keep the sorting column stable.** The default limit is
    finite and a high limit is rejected; changing `sortingColumn` while paging through a result set gives
    inconsistent pages, so page with one fixed sort order and check `pagination.appliedLimit`.
16. **Do not use the default project.** Every instance ships a project named `ZITADEL` that protects the
    Console and the APIs; creating roles, applications or grants there can break administration of the
    instance itself.
17. **Role keys are an interface.** They are persisted in tokens, application code and database rows of
    consumers. Define them once, document the meaning outside the key name if it may change, and add a new
    key plus a migration window instead of reusing a key with new semantics.

## Verification index

Probe of a live ZITADEL v4.18 instance without credentials. `401` = the RPC exists and requires
authentication; `404` would mean it is not registered on that build. The three v2 services below expose no
REST/OpenAPI path, so the Connect path is the only interface. Every endpoint documented above returned 401:

```
zitadel.project.v2.ProjectService          CreateProject  UpdateProject  DeleteProject  GetProject
                                           ListProjects  DeactivateProject  ActivateProject
                                           AddProjectRole  UpdateProjectRole  RemoveProjectRole
                                           ListProjectRoles
                                           CreateProjectGrant  UpdateProjectGrant  DeleteProjectGrant
                                           DeactivateProjectGrant  ActivateProjectGrant
                                           ListProjectGrants
zitadel.application.v2.ApplicationService  CreateApplication  UpdateApplication  GetApplication
                                           DeleteApplication  DeactivateApplication
                                           ReactivateApplication  GenerateClientSecret
                                           ListApplications  CreateApplicationKey  DeleteApplicationKey
                                           GetApplicationKey  ListApplicationKeys
zitadel.authorization.v2.AuthorizationService
                                           ListAuthorizations  CreateAuthorization
                                           UpdateAuthorization  DeleteAuthorization
                                           ActivateAuthorization  DeactivateAuthorization
```

Not documented here: the legacy v1 services (`zitadel.management.v1`, `zitadel.admin.v1`,
`zitadel.auth.v1`) are REST-only on the tested release — their Connect paths answer `404` while
`/management/v1/…`, `/admin/v1/…` and `/auth/v1/…` are mounted (unauthenticated calls answer `401`).
Administrator roles (`InternalPermissionService`), users, sessions and organizations belong to their own
references.
