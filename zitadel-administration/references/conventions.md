# ZITADEL API conventions and legacy coverage

Reference for operating a self-hosted ZITADEL over its HTTP APIs: which host to talk to, which transport each
service is served over, how auth, errors, listing and organization context behave, and where a task must still
use the legacy v1 APIs.

Every endpoint path below was checked against the upstream protobuf definitions (`proto/zitadel/**`) and against
unauthenticated probes of a live ZITADEL v4.18.0 instance (`401/403` = registered, `404` = not registered,
`415` = wrong media type, `405` = wrong verb) on 2026-09-22. Transports and registrations are version-dependent — re-probe
your own version with the recipes in [Re-probing a version](#re-probing-a-version) before trusting a path.

## Base URL, issuer and audience

- **Use the instance domain as the base URL for every API call, the console, the hosted login and the OIDC
  issuer.** ZITADEL serves all of them from a single host: APIs under their own prefixes, the Management
  Console at `/ui/console/`, the login UI v2 at `/ui/v2/login`.
- **Read `/.well-known/openid-configuration` once per environment and take its `issuer` as the authority for the
  host you call.** The discovery document is unauthenticated and returns the issuer plus the OAuth/OIDC endpoints;
  if the issuer is `https://<your instance domain>` then API calls go to `https://<your instance domain>` and nowhere
  else.
- **Do not call a second hostname, IP, or internal service name that resolves to the same process.** ZITADEL checks
  that it is in the audience of the access token; a request that arrives on a host the token was not minted for fails
  authentication before your handler code runs — the symptom is a `401` (or a permission error) on a request whose
  token is otherwise valid.
- **Request service-account tokens with the audience scope `urn:zitadel:iam:org:project:id:zitadel:aud`** when using
  JWT-profile or client-credentials grants, because ZITADEL only accepts tokens that carry the ZITADEL API as
  audience. A Personal Access Token (PAT) is opaque, already scoped, and can be used as the bearer token directly.
- **Keep the console's client-facing domain out of automation configuration; store the issuer string and build URLs
  from it**, so that a domain change is a one-line config change instead of a hunt through scripts.

Minimal discovery check (no credentials):

```bash
curl -s "https://<your instance domain>/.well-known/openid-configuration" | jq '{issuer, token_endpoint, authorization_endpoint}'
```

## Transports: connectRPC for v2, REST/gRPC-gateway for v1

- **Call v2 services over connectRPC: `POST /<proto package>.<Service>/<Method>` with a JSON body.** That path is the
  protobuf fully-qualified method, not a REST path — e.g. `POST /zitadel.user.v2.UserService/ListUsers`.
- **Send `Content-Type: application/json` and `Connect-Protocol-Version: 1`.** The content type is mandatory: without
  it the Connect handler answers `415` before authentication runs. The `Connect-Protocol-Version` header keeps the call
  valid against every Connect server; on the tested version the JSON protocol still reached the auth layer without it,
  so a missing header is not what a `401` means.
- **Use `POST` — never `GET` — on a Connect path.** A `GET` on a registered method returns `405` with an empty body.
- **Generated SDKs (go, .NET, JS/TS, Python, Java, C#) hide all of this.** Use curl only for manual operations, and
  prefer an SDK for anything that runs on a schedule, because it keeps the package, service and method names in sync
  with the proto.
- **Discover the exact method name from the documentation reference URL.** Each method page is
  `https://zitadel.com/docs/reference/api/<resource>/<package>.<Service>.<Method>`; strip the prefix and you have the
  Connect path. Example: `/reference/api/user/zitadel.user.v2.UserService.ListUsers` → `/zitadel.user.v2.UserService/ListUsers`.
  The same information is in the proto file named in the page (`zitadel/user/v2/user_service.proto`).

```bash
curl -s -X POST "https://<your instance domain>/zitadel.user.v2.UserService/ListUsers" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Connect-Protocol-Version: 1" \
  -d '{"query":{"offset":0,"limit":10,"asc":true},"sortingColumn":"USER_FIELD_NAME_USER_NAME"}'
```

- **Call legacy v1 services as REST under their mounted prefix.** The legacy proto annotations are *relative*
  (`get: "/policies/lockout"`), so the prefix is added by the server, not by the proto. Prefix by service:

| Service | gRPC / Connect path prefix | REST (HTTP/JSON transcoding) prefix | Auth tier |
|---|---|---|---|
| `zitadel.management.v1.ManagementService` | `/zitadel.management.v1.ManagementService/` | `/management/v1/` | organization administrator |
| `zitadel.admin.v1.AdminService` | `/zitadel.admin.v1.AdminService/` | `/admin/v1/` | instance administrator |
| `zitadel.auth.v1.AuthService` | `/zitadel.auth.v1.AuthService/` | `/auth/v1/` | the authenticated user's own token |
| `zitadel.system.v1.SystemService` | `/zitadel.system.v1.SystemService/` | `/system/v1/` | self-hosted system user (self-signed JWT) |
| Assets API | — | `/assets/v1/` | user/org/instance administrator, depending on path |

- **Do not POST to a legacy Connect path expecting JSON.** On the tested version the connectRPC JSON protocol is not
  registered for the v1 services: `/zitadel.management.v1.ManagementService/<Method>` returns `404`
  (`{"code":5,"message":"Not Found"}`) while the REST path `/management/v1/<path>` returns `401`. Legacy services are
  reachable over gRPC binary and REST, not over the Connect JSON protocol.
- **Check the transport per service, not per version family.** On the tested version, of the v2 services only
  `user`, `org`, `settings`, `session` and `oidc` also carry REST paths; `project`, `application`, `authorization`,
  `instance`, `internal_permission`, `feature` and `action` are Connect-only:

| v2 service (Connect path verified `401`) | REST paths present | Notes |
|---|---|---|
| `zitadel.user.v2.UserService` | yes (`/v2/users…`) | 60 methods served |
| `zitadel.org.v2.OrganizationService` | yes (`/v2/organizations…`) | |
| `zitadel.settings.v2.SettingsService` | yes (`/v2/settings…`) | partially registered: 7 RPCs in the proto answer `404` |
| `zitadel.session.v2.SessionService` | yes (`/v2/sessions…`) | |
| `zitadel.oidc.v2.OIDCService` | yes (`/v2/oidc…`) | |
| `zitadel.project.v2.ProjectService` | no | Connect-only |
| `zitadel.application.v2.ApplicationService` | no | Connect-only |
| `zitadel.authorization.v2.AuthorizationService` | no | Connect-only |
| `zitadel.instance.v2.InstanceService` | no | Connect-only |
| `zitadel.internal_permission.v2.InternalPermissionService` | no | Connect-only |
| `zitadel.feature.v2.FeatureService` | no | Connect-only; not in the trimmed proto set, verified by probe |
| `zitadel.action.v2.ActionService` | no | Connect-only; not in the trimmed proto set, verified by probe |
| `zitadel.idp.v2.IdentityProviderService`, `zitadel.webkey.v2.WebKeyService`, `zitadel.saml.v2.SAMLService` | no | Connect-only, verified by probe |
| `zitadel.group.v2.GroupService` | n/a | not served on the tested version (documented as under development) |

- **Prefer `/<package>.<Service>/<Method>` over the `/v2/...` REST path when scripting v2**, because the REST path only
  exists where the proto still carries a `google.api.http` annotation, and the API design document deprecates those
  annotations for new services.

## Authentication header and failure shapes

- **Send `Authorization: Bearer <token>` on both surfaces, for every request.** There is no cookie or API-key
  alternative for the ZITADEL APIs; OAuth2/OIDC endpoints (`/oauth/v2/token`, `/oauth/v2/introspect`) follow RFC 6749
  and are the only places that use form parameters instead.
- **Use the user's own access token for the Auth API**, a service account (PAT, client credentials, or private-key JWT
  with the audience scope) plus an administrator role for the Management/Admin/Resource APIs, and a self-signed JWT
  with `iss`/`sub` set to a system user id and `aud` set to the instance domain for the System API (self-hosted only).
- **Recognize the error shape from an unauthenticated call to tell the surfaces apart** — three shapes exist:

| Surface | Body on a missing token | Content type |
|---|---|---|
| legacy REST (`/management/v1`, `/admin/v1`, `/auth/v1`, `/system/v1`) | `{"code":16, "message":"auth header missing"}` | JSON |
| Connect (`/zitadel.*.v*/…`) | `{"code":"unauthenticated","message":"auth header missing"}` | JSON |
| Assets API (`/assets/v1/…`) | `ID=AUT-1179 Message=auth header missing` | text/plain |

## Error model

- **Branch on the status code first, the body second.** Legacy REST returns a numeric gRPC code; Connect returns the
  same code as a name string; the Assets API returns plain text. Do not write one parser that assumes a single shape.

```json
// legacy gateway (REST)
{"code": 5, "message": "Not Found"}

// connectRPC (JSON protocol)
{"code": "not_found", "message": "user not found",
 "details": [{"type": "zitadel.error.v2.ErrorDetail", "value": "<base64>",
              "debug": {"slug": "user.not_found", "message": "user not found"}}]}
```

| gRPC code | Name | HTTP | Meaning / operator action |
|---|---|---|---|
| 0 | `ok` | 200 | success |
| 2 | `unknown` | 500 | unclassified failure — read the server log |
| 3 | `invalid_argument` | 400 | malformed or missing request fields — fix the request, not the server |
| 4 | `deadline_exceeded` | 504 | timeout in a downstream/DB call — look at latency and the log |
| 5 | `not_found` | 404 | resource *or route* absent — check the organization context and the path spelling |
| 6 | `already_exists` | 409 | uniqueness conflict (username, project name, domain) |
| 7 | `permission_denied` | 403 | token valid, role missing — the request is wrong, not the server |
| 9 | `failed_precondition` | 400 | state conflict (e.g. resource already deactivated, user not active) |
| 12 | `unimplemented` | 501 | method not served by this build (see the `settings.v2` gaps) |
| 13 | `internal` | 500 | invariant broken — server log required |
| 14 | `unavailable` | 503 | process/DB not ready — check `/debug/ready` before retrying |
| 16 | `unauthenticated` | 401 | missing, malformed, expired, or wrong-audience token — fix the caller |

- **Check the request before the log for `3`, `5`, `6`, `7`, `9`, `16`; check the log before the request for `2`, `4`,
  `13`.** A `404` on a path you copied from the reference docs usually means a wrong verb (the gateway answers `405`),
  a missing organization context, or a method that is not registered in your build — not a missing resource.
- **Read `details[].debug.slug` when present** on stable v2 services: it is a stable machine-readable error identifier
  (e.g. `user.already_exists`, `session.token_invalid`) and is the right thing to switch on. Treat `message` as
  developer diagnostics and do not surface it to end users.
- **Do not assume slugs exist on v1, v2beta or v3alpha endpoints.** They are emitted only on backend paths that run
  with relational-storage-backed logic; other errors carry a hand-assigned id such as `AUTH-7fs1e` inside
  `details[].id` (or `ID=… Message=…` plain text on the Assets API), which is not stable and is occasionally reused
  for different conditions.

## Failure modes of an under-privileged credential

A valid token without an administrator role does not fail loudly, and it does not fail uniformly. Measured by
sending the same read calls with a role-less service account and with an instance-level `IAM_LOGIN_CLIENT`:

| Call | with a role | role-less service account |
|---|---|---|
| `ListApplications` | 200, 13 items | 200, `totalResult` 13, **no `applications` key** |
| `ListApplications` + `projectIdFilter` | 200, 4 items | 200, `totalResult` 4, **no array** |
| `ListProjects` | 200, 3 items | **404 `membership not found (AUTHZ-…)`** |
| `ListProjectRoles` | 200, 1 item | **404 `membership not found (AUTHZ-…)`** |
| `GetGeneralSettings` / `GetLoginSettings` | 200 | **404 `membership not found (AUTHZ-…)`** |
| `ListOrganizations` | 200, 1 item | 200, `totalResult` 1, **no array** |
| `ListAuthorizations` | 200, 2 items | 200, `totalResult` 2, **no array** |
| `ListAdministrators` | 200, 6 items | 200, `totalResult` 6, **no array** |
| `ListUsers` | 200, 4410 total | 200, 1 item — itself |

Four readings:

- **`404 not_found` can mean "no membership"**, not "no such resource": endpoints that resolve a membership
  context first (`ListProjects`, `ListProjectRoles`, the `settings.v2` getters) answer `not_found` with
  `membership not found (AUTHZ-…)` in `message`, the machine-readable counterpart hidden in the base64
  `details[].value`.
- **Counts are not authorization-scoped.** `totalResult` reports the unfiltered size of the collection even when
  the caller may not see a single entry. A count is therefore not evidence that a credential works, and the
  counted-but-empty response is indistinguishable from a genuinely empty collection unless you know which role
  is missing.
- **Self-scoping hides the difference on users.** `ListUsers` returns only the caller, so a role-less credential
  reporting `totalResult: 1` looks like a small instance.
- **`403 permission_denied` is the honest case**, and it appears on writes whose request is otherwise well
  formed; a request that fails validation returns `400` before any authorization check runs.

Verify the credential before trusting any list: `/auth/v1/memberships/me/_search` for the roles actually held and
`/auth/v1/permissions/zitadel/me/_search` for the flat permission list (`{}` when there are none).

Granting a role flips every row at once, and the size of that permission list is a usable check that the handover
went as intended. Measured on one release: no role → `0` permissions; instance-level `IAM_LOGIN_CLIENT` → `34`
(read across the instance, but no `project.create` or `project.app.write`); instance-level `IAM_OWNER` → `96`, of
which `60` are create/write/delete, including `project.create`, `project.app.write`, `org.create` and `iam.write`.
With `IAM_OWNER` the same ten calls above returned items on every row, so a `200` without an item array is a
missing role rather than an empty collection. Read that list before the first real call and ask for the smallest
role that covers the task — the difference between "can read this instance" and "can restructure it" is one
membership.

## Pagination, filtering and sorting

- **Assume one of two generations of list request shape, and read the request message rather than guessing.**
  The older v2 services (`user`, `org`, `session`) use `zitadel.object.v2.ListQuery` as
  `query` plus repeated `queries` filters; the newer ones (`project`, `application`, `authorization`,
  `internal_permission`, `settings`, `feature`, `action`) use
  `zitadel.filter.v2.PaginationRequest` as `pagination` plus repeated typed `filters`.

| Field | Older v2 services (`object.v2`) | Newer v2 services (`filter.v2`) |
|---|---|---|
| pagination object | `"query": {"offset":0,"limit":100,"asc":true}` | `"pagination": {"offset":0,"limit":100,"asc":true}` |
| sort field | `"sortingColumn": "<RESOURCE>_FIELD_NAME_…"` | `"sortingColumn": "<RESOURCE>_FIELD_NAME_…"` |
| filters | `"queries": [{"userNameQuery":{"userName":"…","method":"TEXT_QUERY_METHOD_STARTS_WITH_IGNORE_CASE"}}]` | `"filters": [{"targetNameFilter":{"targetName":"…","method":"TEXT_FILTER_METHOD_EQUALS"}}]` |
| list details | `details.totalResult`, `details.processedSequence`, `details.timestamp` | `pagination.totalResult`, `pagination.appliedLimit` |
| result list | `"result": [...]` | service-specific (`"administrators"`, `"targets"`, …) |

- **Set `limit` explicitly on every list call.** The default is 100 and the maximum is 1000; a larger request is
  rejected. `asc` defaults to `false` (descending), so pass `"asc": true` when you want stable ascending paging.
- **A field from the wrong request generation is ignored, not rejected.** Unknown fields are discarded during
  decoding, so sending `{"query":{"limit":2}}` to a `filter.v2` list answers `200` with the *default* window
  (limit 100) rather than an error — the response looks valid and is unfiltered. Compare the returned
  `pagination.appliedLimit` with the limit you sent, and `totalResult` with the number of items you expect,
  before trusting a filtered list; a mismatch means the filter never applied. Misspelled *oneof* members are the
  exception and do fail validation (`value is required`), because the oneof would otherwise be empty.
- **Iterate pages with `offset` until you have seen `totalResult` items — do not page by continuing until an empty
  page arrives.** `totalResult` is the absolute count matching the query (independent of `limit`), so it is the
  termination condition and the sanity check for a partial read.
- **Sort by a stable, unique-ish column while paging.** The design document warns that changing the sorting column
  makes offset pagination inconsistent; a page written while you iterate can shift offsets.
- **Keep filter operator enums with their envelope**: `TEXT_QUERY_METHOD_*` inside `object.v2` queries,
  `TEXT_FILTER_METHOD_*` inside `filter.v2` filters, `LIST_*_METHOD_IN` for id lists, `TIMESTAMP_*_METHOD_*` for date
  ranges. Mixing them yields `invalid_argument` (`400`), not a silent no-match.
- **Use nested `andQuery`/`orQuery`/`notQuery` for compound user filters**, because the request is a list of filters
  that ZITADEL assumes to be joined by AND.

Real request and response (v2, older generation):

```bash
curl -s -X POST "https://<your instance domain>/zitadel.user.v2.UserService/ListUsers" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
        "query": {"offset": 0, "limit": 100, "asc": true},
        "sortingColumn": "USER_FIELD_NAME_USER_NAME",
        "queries": [
          {"organizationIdQuery": {"organizationId": "<organization-id>"}},
          {"typeQuery": {"type": "TYPE_MACHINE"}}
        ]
      }'
```

```json
{
  "details": {"totalResult": 213, "processedSequence": 267831, "timestamp": "2024-12-18T07:50:47.492Z"},
  "sortingColumn": "USER_FIELD_NAME_USER_NAME",
  "result": [
    {"userId": "<user-id>", "state": "USER_STATE_ACTIVE", "username": "automation",
     "details": {"sequence": "42", "creationDate": "2024-12-18T07:50:47.492Z", "resourceOwner": "<organization-id>"}}
  ]
}
```

## Organization context

- **Put the context in the request body on v2.** Where a resource needs an organization to exist, the request has a
  dedicated field: `organization_id` on `CreateProject`, on `zitadel.org.v2.AddOrganization` (for the resources it
  creates) and similar create/update requests — `organization_id`, not `org_id`.
- **Use `ctx` on the settings service.** Read settings with `{"ctx": {"orgId": "<organization-id>"}}` for an
  organization and `{"ctx": {"instance": true}}` for the instance; a missing context defaults to the caller.
- **Omit the context where the resource is already identified.** `GetUserByID`, `UpdateProject`, `DeleteUser` and
  friends resolve the resource from its id; passing an organization there is either a filter (list calls) or invalid.
- **Send `x-zitadel-orgid: <organization-id>` on legacy v1 REST calls** when the operation must act on an organization
  other than the caller's own; without the header the Management API falls back to the organization of the
  authenticated user. The Admin API is instance-wide and ignores an organization context except on explicit
  `/orgs/{org_id}/...` paths. Only `x-zitadel-orgid` is documented and verified — resolve an organization domain to
  its id first instead of relying on an org-domain header variant.
- **Treat the organization-scoped selectors in v1 paths as explicit context, not as a separate API.**
  `/management/v1/...` is "the caller's organization", `/admin/v1/orgs/{org_id}/policies/...` is "this instance
  administrator acting on that organization".
- **When a resource unexpectedly returns `not_found` (`404`/`code 5`), re-check the organization context before
  concluding that the resource does not exist.** In multi-tenant instances, a user, project, application, IDP or
  grant that exists in another organization is invisible — and reported as not found — to a caller scoped to a
  different organization. Reload the resource as an instance administrator, or with the correct
  `organization_id`/`x-zitadel-orgid`, before escalating to the logs.

## Versioning and deprecation

- **Version by major number per service: anything within a major version is backward compatible, and a breaking change
  forces a new major.** Service versions move independently (`user.v2` next to `action.v2` next to `instance.v2`), so
  never infer one service's state from another's.
- **Use `v2` for new work and `v2beta` only for what already exists there.** `/v2beta/` is kept for backward
  compatibility; both are usable, but `v2beta` is not where new features land.
- **Expect deprecated methods inside otherwise-current services.** Redundant methods are marked deprecated in the proto
  (with a pointer to the replacement, e.g. `AddHumanUser` → `CreateUser`, `GetMyInstance` → instance v2 `GetInstance`)
  and keep working; migrate when you touch them, not in bulk.
- **Treat v1 as legacy but supported, and required for the capabilities v2 has not absorbed.** Use the table below to
  decide per operation, and consult the migration guide before rewriting a whole integration.

| Resource / capability | Preferred API | What is missing there (still on the legacy API) |
|---|---|---|
| Users, human + machine, credentials, IDP links, PATs, keys | `user.v2` | changes feed (`ListUserChanges`), avatar upload/remove, user import with initial password (`ImportHumanUser`), passwordless/U2F auth-factor listing, global login-name lookup |
| Sessions, custom login | `session.v2`, `oidc.v2` | — |
| Organizations | `org.v2` | default-organization flag, org-by-domain lookup, org changes |
| Instance read/update, custom and trusted domains | `instance.v2` | secret generators, instance languages, admin-only org setup/teardown helpers |
| Projects, project roles, project grants, apps, app keys | `project.v2`, `application.v2` | changes feeds for projects, apps and grants |
| Administrators (instance/org/project/project-grant members) | `internal_permission.v2` | member-role catalogues (which roles exist per resource) |
| User grants (legacy per-user role assignment) | legacy `management.v1` only | whole concept — v2 models it as authorizations + administrator roles |
| Actions / executions / targets | `action.v2` (executions, targets) | v1 actions + flow triggers (`management.v1` `/actions`, `/flows`) |
| Policies: password complexity/age, lockout, login, privacy, notification, label, domain, orgIAM, security | legacy `admin.v1` / `management.v1` (write) + `settings.v2` (read) | writes: v2 exposes only security settings and hosted-login translation |
| Email/SMS/notification providers, SMTP config | legacy `admin.v1` | no v2 equivalent; SMTP config endpoints are deprecated in favour of email providers |
| Identity providers (instance and org configuration) | legacy `admin.v1` / `management.v1` | `idp.v2` exists (read-oriented) and `settings.v2` lists active IDPs for a context |
| Branding colours, logo, icon, font | legacy `admin.v1` (label policy) + Assets API (`/assets/v1/`) | no v2 resource for brand assets |
| Feature flags | `feature.v2` | nothing except the single v1 flag `login_default_org` |
| Event API, failed events, views, data export | legacy `admin.v1` only | no v2 event API |
| Groups | `group.v2` | documented as under development; absent on the tested version |
| Web keys, SAML request handling | `webkey.v2`, `saml.v2` | — |

## Legacy coverage map: where each operational task lives

Paths are relative to the base URL. "Tier" is who may call it: *instance* = Admin API (`/admin/v1/…`), *org* =
Management API (`/management/v1/…`), *self* = the user's own token (`/auth/v1/…`), *system* = self-hosted System API.

### Instance settings and policies

| Task | Endpoint | Tier |
|---|---|---|
| Read password complexity | `GET /admin/v1/policies/password/complexity` (instance), `GET /management/v1/policies/password/complexity` (org) | instance / org |
| Set password complexity | `PUT /admin/v1/policies/password/complexity`, `PUT /management/v1/policies/password/complexity` (org custom), `DELETE /management/v1/policies/password/complexity` (reset to default) | instance / org |
| Read/set password age (expiry) | `GET`/`PUT /admin/v1/policies/password/age`; org variants at `/management/v1/policies/password/age` | instance / org |
| Read lockout policy | `GET /admin/v1/policies/lockout`, `GET /management/v1/policies/lockout` | instance / org |
| Set lockout policy | `PUT /admin/v1/policies/password/lockout` (instance), `PUT /management/v1/policies/lockout` (org custom) | instance / org |
| Read/set login policy | `GET`/`PUT /admin/v1/policies/login`; org custom at `/management/v1/policies/login` | instance / org |
| Attach an IDP to the login policy | `POST /admin/v1/policies/login/idps`, `POST /management/v1/policies/login/idps`, `DELETE .../idps/{idp_id}` | instance / org |
| Second factors / multi-factors on the login policy | `POST /admin/v1/policies/login/second_factors`, `/multi_factors` (+ `_search`, `DELETE .../{type}`) | instance / org |
| Read/set notification policy | `GET`/`PUT /admin/v1/policies/notification`; org custom at `/management/v1/policies/notification` | instance / org |
| Read/set privacy policy | `GET`/`PUT /admin/v1/policies/privacy`; org custom at `/management/v1/policies/privacy` | instance / org |
| Read/set label (branding) policy | `GET`/`PUT /admin/v1/policies/label`, `POST /admin/v1/policies/label/_activate`; org custom at `/management/v1/policies/label` | instance / org |
| Domain policy, org-IAM policy | `GET`/`PUT /admin/v1/policies/domain`, `/admin/v1/policies/orgiam`; per-org overrides at `POST /admin/v1/orgs/{org_id}/policies/domain` and `.../orgiam` | instance |
| Read/set instance security policy | `GET /admin/v1/policies/security`, `PUT /admin/v1/policies/security` | instance |
| Read/set OIDC token lifetimes (access/id token) | `GET /admin/v1/settings/oidc`, `PUT /admin/v1/settings/oidc` (also `POST` to create) | instance |
| Read instance metadata | `GET /admin/v1/instances/me` | instance |
| List instance domains / trusted domains | `POST /admin/v1/domains/_search`, `POST /admin/v1/trusted_domains/_search`, `POST /admin/v1/trusted_domains`, `DELETE /admin/v1/trusted_domains/{domain}` | instance |
| Secret generators (username/init/phone/email codes) | `POST /admin/v1/secretgenerators/_search`, `GET`/`PUT /admin/v1/secretgenerators/{generator_type}` | instance |
| Message texts and login texts | `GET`/`PUT /admin/v1/text/login/{language}`, `GET`/`PUT /admin/v1/text/message/<template>/{language}` (org variants under `/management/v1/text/...`) | instance / org |
| Default organization flag (v1 feature) | `PUT /admin/v1/features/login_default_org` | instance |

### Notification, email and SMS providers

| Task | Endpoint | Tier |
|---|---|---|
| List email providers / read active one | `POST /admin/v1/email/_search`, `GET /admin/v1/email`, `GET /admin/v1/email/{id}` | instance |
| Add/update an SMTP email provider | `POST /admin/v1/email/smtp`, `PUT /admin/v1/email/smtp/{id}`, `PUT /admin/v1/email/smtp/{id}/password` | instance |
| Add/update an HTTP email provider | `POST /admin/v1/email/http`, `PUT /admin/v1/email/http/{id}` | instance |
| Activate/deactivate/remove/test a provider | `POST /admin/v1/email/{id}/_activate`, `POST /admin/v1/email/{id}/_deactivate`, `DELETE /admin/v1/email/{id}`, `POST /admin/v1/email/smtp/_test` | instance |
| SMS providers (Twilio / HTTP) | `POST /admin/v1/sms/_search`, `POST /admin/v1/sms/twilio`, `POST /admin/v1/sms/http`, `POST /admin/v1/sms/{id}/_activate` | instance |
| Notification providers for testing | `GET /admin/v1/notification/provider/file`, `GET /admin/v1/notification/provider/log` | instance |
| Legacy SMTP configuration (deprecated) | `GET /admin/v1/smtp`, `POST /admin/v1/smtp`, `POST /admin/v1/smtp/_search`, `PUT /admin/v1/smtp/{id}` | instance |

Prefer the email-provider endpoints over the deprecated SMTP configuration: both write the same delivery path, but
only the email providers support more than one configuration and activation.

### Identity providers

| Task | Endpoint | Tier |
|---|---|---|
| List / read instance IDPs | `POST /admin/v1/idps/_search`, `GET /admin/v1/idps/{idp_id}` | instance |
| Add an instance OIDC or JWT IDP | `POST /admin/v1/idps/oidc`, `POST /admin/v1/idps/jwt` | instance |
| Update / deactivate / reactivate / remove an instance IDP | `PUT /admin/v1/idps/{idp_id}`, `POST /admin/v1/idps/{idp_id}/_deactivate`, `POST /admin/v1/idps/{idp_id}/_reactivate`, `DELETE /admin/v1/idps/{idp_id}` | instance |
| Add a provider template (Google, GitHub, GitLab, Azure AD, Apple, LDAP, SAML, …) | `POST /admin/v1/idps/<provider>` (e.g. `google`, `github`, `gitlab`, `azure`, `apple`, `ldap`, `saml`, `generic_oidc`, `generic_oauth`, `generic_jwt`) | instance |
| List / add / remove org IDPs | `POST /management/v1/idps/_search`, `POST /management/v1/idps/oidc`, `POST /management/v1/idps/jwt`, `DELETE /management/v1/idps/{idp_id}` | org |
| Show which IDPs are enabled for a login context | `GET /v2/settings/login/idps` (`settings.v2`) | org / instance |
| Link a user to an IDP | `POST /v2/users/{user_id}/links`, `POST /v2/users/{user_id}/links/_search`, `DELETE /v2/users/{user_id}/links/{idp_id}/{linked_user_id}` | org / instance |

### Administrator (member) management

| Task | Endpoint | Tier |
|---|---|---|
| List / grant / change / revoke instance administrators | `POST /admin/v1/members/_search`, `POST /admin/v1/members`, `PUT /admin/v1/members/{user_id}`, `DELETE /admin/v1/members/{user_id}`, `POST /admin/v1/members/roles/_search` | instance |
| List / grant / change / revoke organization members | `POST /management/v1/orgs/me/members/_search`, `POST /management/v1/orgs/me/members`, `PUT /management/v1/orgs/me/members/{user_id}`, `DELETE /management/v1/orgs/me/members/{user_id}`, `POST /management/v1/orgs/members/roles/_search` | org |
| List / grant / change / revoke project members | `POST /management/v1/projects/{project_id}/members/_search`, `POST /management/v1/projects/{project_id}/members`, `PUT|DELETE /management/v1/projects/{project_id}/members/{user_id}`, `POST /management/v1/projects/members/roles/_search` | org |
| Project-grant members | `POST /management/v1/projects/{project_id}/grants/{grant_id}/members/_search`, `POST .../members`, `PUT|DELETE .../members/{user_id}` | org |
| Resource-based administrator grants (v2, instance / org / project / project-grant scope) | `POST /zitadel.internal_permission.v2.InternalPermissionService/CreateAdministrator` with `{"userId":"<user-id>","resource":{"organizationId":"<organization-id>"},"roles":["ORG_OWNER"]}`; list with `ListAdministrators`, remove with `DeleteAdministrator` | org / instance |
| Which memberships does a user have | `POST /management/v1/users/{user_id}/memberships/_search` | org |
| Which memberships do I have | `POST /auth/v1/memberships/me/_search` | self |

The v2 administrator grant carries its scope inside `resource`, as a oneof: `{"instance": true}` for the instance,
`{"organizationId":"<organization-id>"}`, `{"projectId":"<project-id>"}`, or
`{"projectGrant":{"projectId":"<project-id>","organizationId":"<organization-id>"}}`. Roles are resource-type
specific, so granting organization *and* project administrator rights to one user takes two `CreateAdministrator`
calls.

### User grants (legacy role assignment)

| Task | Endpoint | Tier |
|---|---|---|
| List / add / change / remove user grants | `POST /management/v1/users/grants/_search`, `POST /management/v1/users/{user_id}/grants`, `PUT /management/v1/users/{user_id}/grants/{grant_id}`, `DELETE /management/v1/users/{user_id}/grants/{grant_id}` | org |
| Bulk remove user grants | `DELETE /management/v1/user_grants/_bulk` | org |
| Grant a project to another organization | `POST /management/v1/projects/{project_id}/grants`, `PUT /management/v1/projects/{project_id}/grants/{grant_id}` | org |
| Read the projects granted to my organization | `POST /management/v1/granted_projects/_search` | org |

User grants have no v2 replacement; on v2 the equivalent model is `authorization.v2` authorizations plus
`internal_permission.v2` administrator roles. Keep new automation on the v2 model and treat `/users/grants` as
compatibility surface.

### Operations, health and observability

| Task | Endpoint | Notes |
|---|---|---|
| Liveness (process alive) | `GET /debug/healthz` | plain text `ok`; suitable as a Kubernetes `livenessProbe` |
| Readiness (accepts traffic, migrations finished) | `GET /debug/ready` | JSON string `"ok"`; use as `readinessProbe` during upgrades |
| Metrics | `GET /debug/metrics` | OpenTelemetry/Prometheus-scrapeable; may be disabled by configuration, in which case the path answers `404` |
| Per-API health probes | `GET /healthz` (grpc-health style, `{"status":"SERVING"}`) and `GET /admin/v1/healthz`, `GET /management/v1/healthz`, `GET /auth/v1/healthz` (empty `{}`) | unauthenticated; useful to confirm a prefix is mounted at all |
| Event API: audit trail | `POST /admin/v1/events/_search` (filters: sequence, editor user, event types, aggregate id/type, resource owner, creation date) | instance, requires `IAM_OWNER_VIEWER` or `IAM_OWNER` |
| Event types / aggregate types | `POST /admin/v1/events/types/_search`, `POST /admin/v1/aggregates/types/_search` | instance, `events.read` |
| Failed events and view state | `POST /admin/v1/failedevents/_search`, `DELETE /admin/v1/failedevents/{database}/{view_name}/{failed_sequence}`, `POST /admin/v1/views/_search` | instance |
| Data export | `POST /admin/v1/export` | instance; heavy — run against a maintenance window |

- **Treat the event store, not the projections, as the audit ground truth.** After a state change that "did not take",
  `POST /admin/v1/events/_search` filtered by aggregate id and a short time range shows whether the write happened;
  `POST /admin/v1/views/_search` shows whether the projection caught up; `POST /admin/v1/failedevents/_search` shows
  whether a projection handler failed.
- **Read the application log for failures the API could not classify** (`unknown`, `deadline_exceeded`, `internal`):
  the API response deliberately does not carry the internal cause, and the log line carries the request id you can
  quote in a bug report.
- **Probe `/debug/ready` before blaming the API on a `503`**, because a migration or a slow startup makes every
  endpoint return `unavailable` while liveness stays green.

## Task → API quick table

| Operator asks for | Use | Path / method |
|---|---|---|
| Add an OIDC application for a self-hosted service | `project.v2` + `application.v2` (Connect) | `POST /zitadel.project.v2.ProjectService/CreateProject` `{"organization_id":"<organization-id>","name":"…"}` then `POST /zitadel.application.v2.ApplicationService/CreateApplication` `{"projectId":"<project-id>","name":"…","oidcConfiguration":{…}}` |
| Find the client id/secret of an app | `application.v2` | `POST /zitadel.application.v2.ApplicationService/GetApplication`, `POST .../GenerateClientSecret`; legacy alternative `POST /management/v1/projects/{project_id}/apps/{app_id}/oidc_config/_generate_client_secret` |
| Create an organization for a customer | `org.v2` (Connect; REST `POST /v2/organizations`) | `POST /zitadel.org.v2.OrganizationService/AddOrganization` `{"name":"…","admins":[{"human":{…},"roles":["ORG_OWNER"]}]}` |
| Create a project (v1 body) for legacy tooling | legacy `management.v1` | `POST /management/v1/projects` |
| Give an automation its own identity | `user.v2` + `internal_permission.v2` (Connect) | `POST /zitadel.user.v2.UserService/CreateUser` with a `machine` field, then `POST /zitadel.internal_permission.v2.InternalPermissionService/CreateAdministrator` `{"userId":"<user-id>","resource":{"organizationId":"<organization-id>"},"roles":["ORG_OWNER"]}` |
| Give a machine user a token or key | `user.v2` | `POST /v2/users/{user_id}/secret` (client secret), `POST /v2/users/{user_id}/keys` (key), `POST /v2/users/{user_id}/pats` (PAT) |
| Invite a human user | `user.v2` | `POST /v2/users/new` (or `POST /v2/users/human`), then `POST /v2/users/{user_id}/invite_code` |
| Reset a user's password / email | `user.v2` | `POST /v2/users/{user_id}/password_reset`, `POST /v2/users/{user_id}/email` (legacy alternative under `/management/v1/users/{id}/...`) |
| Harden password rules or lockout for one tenant | legacy `management.v1` custom policies | `PUT /management/v1/policies/password/complexity` (+ header `x-zitadel-orgid: <organization-id>`), `PUT /management/v1/policies/lockout` |
| Change token lifetime | legacy `admin.v1` OIDC settings | `PUT /admin/v1/settings/oidc` (instance-wide `accessTokenLifetime`/`idTokenLifetime`; there is no v2 replacement) |
| Let users log in with Google | legacy `admin.v1` IDP + login policy | `POST /admin/v1/idps/google`, then `POST /admin/v1/policies/login/idps` with the new IDP id |
| Let one org bring its own IDP | legacy `management.v1` | `POST /management/v1/idps/generic_oidc` (org-scoped), then `POST /management/v1/policies/login/idps` |
| Enable the login v2 UI | `feature.v2` (Connect) | `POST /zitadel.feature.v2.FeatureService/SetInstanceFeatures` `{"loginV2":{"required":true}}` |
| Point the login at the default organization | `feature.v2` or legacy `admin.v1` | `POST /zitadel.feature.v2.FeatureService/SetInstanceFeatures` `{"loginDefaultOrg":true}` — the v1 equivalent is `PUT /admin/v1/features/login_default_org` |
| Replace the logo/font for the login UI | Assets API + legacy label policy | `POST /assets/v1/instance/policy/label/logo`, `POST /assets/v1/instance/policy/label/font`, then activate via `POST /admin/v1/policies/label/_activate` |
| Send mail through a new relay | legacy `admin.v1` | `POST /admin/v1/email/smtp`, then `POST /admin/v1/email/{id}/_activate` |
| Audit who changed what | legacy `admin.v1` Event API | `POST /admin/v1/events/_search` |
| Wire up a probe | health endpoints | `/debug/healthz`, `/debug/ready`, `/healthz` |
| Scrape metrics | `/debug/metrics` | enable the metrics endpoint in the runtime configuration first |

## Re-probing a version

Do not trust a transport table across upgrades. Confirm registration with an unauthenticated call per candidate
method and read the status:

```bash
# connectRPC: 401/403 = method registered, 404 = service or method absent, 415 = wrong content type
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Content-Type: application/json' -d '{}' \
  "https://<your instance domain>/<package>.<Service>/<Method>"

# legacy REST: 401/403 = route registered, 405 = wrong verb, 404 = not registered
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Content-Type: application/json' -d '{}' \
  "https://<your instance domain>/admin/v1/<relative-path>"
```

- **`415` and `405` are positive signals.** They are produced by the Connect or gateway handler, which means the
  service (or the route) is mounted; only a `404` with a JSON body means "not registered" for Connect, and only a
  `404` after checking the verb means "not registered" for REST.
- **Distinguish "unknown method" from "unknown service"**: an unknown method on a registered service answers
  `404 page not found` as plain text, an unknown service answers `{"code":5,"message":"Not Found"}` as JSON.
- **Extract the candidate list from the protos** (`proto/zitadel/<resource>/v2/*_service.proto`, and the legacy
  `admin.proto`, `management.proto`, `auth.proto`) so the probe covers every RPC of a release, not just the ones you
  happen to need.
