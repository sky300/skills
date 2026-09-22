# Organizations, Users, Instances and Administrators through the ZITADEL v2 API

Purpose: give an operator the exact request shapes for creating and maintaining organizations, human users, machine users (service accounts), instance domains and instance/organization administrators on a self-hosted ZITADEL, using only the resource-based v2 APIs.

Everything marked as verified below was checked against the published protobuf definitions and against the Connect/REST routes of a running instance. Anything not verified is called out inline as `unverified`.

Version note: transports and route registrations were verified against ZITADEL v4.18.0 (probes run 2026-09-22); they are release-dependent — re-probe your own release with the recipe in [conventions](./conventions.md#re-probing-a-version) before automating a call that matters.

## Calling convention

- Connect RPC is the primary interface: `POST https://<your instance domain>/<package>.<Service>/<Method>` with `Content-Type: application/json`, `Connect-Protocol-Version: 1` and `Authorization: Bearer <token>`.
- The annotated REST gateway paths (`/v2/organizations`, `/v2/users/...`, `/v2/settings/...`) are still registered on current releases (an unauthenticated call answers `401`), but ZITADEL documents the OpenAPI/REST interface as being sunset in favour of Connect RPC. Prefer Connect; treat REST as a compatibility path.
- `InstanceService` and `InternalPermissionService` have no HTTP annotations at all: they are Connect/gRPC only.
- Your token must carry the ZITADEL API audience, i.e. the scope `urn:zitadel:iam:org:project:id:zitadel:aud`. A token without it authenticates you but every management call fails on permissions.
- A `404` on a Connect path means that RPC does not exist in your release. Check for the specific methods called out below before automating them.
- Fine-grained permissions: v2 methods declare `authenticated` as their auth option and enforce the real permission inside the command (the "Required permission" line of each method). A service account holding a role that lacks the permission gets `403 Permission denied`, not `401`.

## 1. Organizations

An organization is the tenant: every user, project, policy and administrator grant belongs to exactly one organization, and users cannot be moved between organizations. The instance is the top node (one instance normally runs on one domain and represents one issuer); it holds the default settings — branding, login policy, password policy — that organizations inherit. Exactly one organization of the instance is the default organization, used whenever no organization is given explicitly (for example during login without domain discovery): read it as `defaultOrganizationId` from `GetGeneralSettings` and change it in the console. Instance administrators see all organizations; an organization's administrators see only their own, and only instance-level administrators can list resources across organizations.

There is no `GetOrganization` RPC. "Get one organization" is `ListOrganizations` with an id filter.

### Create an organization

Connect: `POST /zitadel.org.v2.OrganizationService/AddOrganization` (REST: `POST /v2/organizations`, success `201`)
Required permission: `org.create`

```bash
curl -X POST "https://<your instance domain>/zitadel.org.v2.OrganizationService/AddOrganization" \
  -H "Authorization: Bearer <token>" -H "Connect-Protocol-Version: 1" -H "Content-Type: application/json" \
  -d '{
    "name": "Acme",
    "organizationId": "<organization-id>",
    "admins": [
      {
        "human": {
          "username": "acme-admin",
          "profile": { "givenName": "Acme", "familyName": "Admin" },
          "email": { "email": "admin@acme.example", "sendCode": {} },
          "password": { "password": "<initial password>", "changeRequired": true }
        },
        "roles": ["ORG_OWNER"]
      }
    ]
  }'
```

- `name` is required and must be unique across the instance; `organizationId` is optional (omit it and let the system generate one — recommended).
- `admins[]` is a oneof: either `userId` (an existing user that gets a membership) or `human` (an `AddHumanUser` request body, i.e. the user is created as part of the call). `roles` defaults to `ORG_OWNER` when omitted. Omit `admins` entirely to create an org that only instance administrators can manage.
- Response: `organizationId`, `details`, and `createdAdmins[]` with `userId`, `emailCode`, `phoneCode`. **The response returns every resource the call created** — organisation, each human user, each membership. Persist all of them; the generated `organizationId` is not the id you sent unless you sent one.
- Console: organizations dropdown in the console header → *New organization*; choose *Current User* (you become org manager) or *New Account* (a new account is created for the org). Self-service org creation is `https://<your instance domain>/ui/login/register/org`.

### Update, deactivate, activate, list, delete

| Operation | Connect path (method) | REST | Required permission | Console |
| --- | --- | --- | --- | --- |
| Update (rename) | `POST /zitadel.org.v2.OrganizationService/UpdateOrganization` | `POST /v2/organizations/{organization_id}` | `org.write` | Org settings → *Rename* |
| Deactivate | `...OrganizationService/DeactivateOrganization` | `POST /v2/organizations/{organization_id}/deactivate` | `org.write` | Org → *Deactivate* |
| Activate | `...OrganizationService/ActivateOrganization` | `POST /v2/organizations/{organization_id}/activate` | `org.write` | Org → *Activate* |
| List / get one | `...OrganizationService/ListOrganizations` | `POST /v2/organizations/_search` | `org.read` | Orgs list |
| Delete | `...OrganizationService/DeleteOrganization` | `DELETE /v2/organizations/{organization_id}` | `org.delete` | Org → *Delete* |

Update body: `{"organizationId": "<organization-id>", "name": "Acme Holding"}` → response `changeDate`. Renaming changes the organization's generated default domain and therefore the login names that use it; explicitly added organization domains are unaffected.

Deactivate/activate body: `{"organizationId": "<organization-id>"}`. Deactivation blocks login for every user of the org; activation is only accepted when the org is currently deactivated.

Deleting an organization **cascades**: the proto states "Deletes the organization and all its resources (Users, Projects, Grants to and from the org)". Take a data export first; there is no undelete.

### List organizations with filters and pagination

```json
{
  "query": { "offset": 0, "limit": 100, "asc": false },
  "sortingColumn": "ORGANIZATION_FIELD_NAME_NAME",
  "queries": [
    { "nameQuery": { "name": "Acme", "method": "TEXT_QUERY_METHOD_CONTAINS_IGNORE_CASE" } },
    { "domainQuery": { "domain": "acme.example", "method": "TEXT_QUERY_METHOD_EQUALS" } },
    { "stateQuery": { "state": "ORGANIZATION_STATE_ACTIVE" } },
    { "idQuery": { "id": "<organization-id>" } },
    { "defaultQuery": {} }
  ]
}
```

- Filters in `queries` are combined with AND, and the organization search has no OR/NOT combinator: to match several values of one field, use a fuzzy `TEXT_QUERY_METHOD_*` method (`CONTAINS`, `STARTS_WITH`, `ENDS_WITH`) inside one filter, or issue several requests. (User search does offer `orQuery`/`andQuery`/`notQuery` — see section 3.)
- Sort with `ORGANIZATION_FIELD_NAME_NAME` or `ORGANIZATION_FIELD_NAME_CREATION_DATE` (default: creation date). Beware that changing the sorting column between paged calls makes offsets inconsistent.
- Response: `details` (`totalResult`, `processedSequence`, `timestamp`), `sortingColumn`, `result[]` with `id`, `state`, `name`, `primaryDomain`, `details`.
- `query.limit` defaults to a server-side maximum; always set an explicit `limit` when you page.

### Organization domains

Domains are how a user's login name is qualified and how domain discovery maps a login name to an organization. A domain is unique across the instance; only one organization can own it.

| Operation | Connect path | REST | Permission |
| --- | --- | --- | --- |
| Add | `...OrganizationService/AddOrganizationDomain` | `POST /v2/organizations/{organization_id}/domains` | `org.write` |
| List | `...OrganizationService/ListOrganizationDomains` | `POST /v2/organizations/{organization_id}/domains/search` | `org.read` |
| Generate validation | `...OrganizationService/GenerateOrganizationDomainValidation` | `POST .../domains/validation/generate` | `org.write` |
| Verify | `...OrganizationService/VerifyOrganizationDomain` | `POST .../domains/validation/verify` | `org.write` |
| Delete | `...OrganizationService/DeleteOrganizationDomain` | `DELETE /v2/organizations/{organization_id}/domains` | `org.write` |

Add: `{"organizationId": "<organization-id>", "domain": "acme.example"}` → response `creationDate`. Returns `409` if the domain already exists on the instance.

Generate a challenge (do this before verifying):

```json
{ "organizationId": "<organization-id>", "domain": "acme.example", "type": "DOMAIN_VALIDATION_TYPE_DNS" }
```

Response: `token` and `url`. For `DOMAIN_VALIDATION_TYPE_DNS` publish the token as a TXT record; for `DOMAIN_VALIDATION_TYPE_HTTP` serve it at the returned `url`. **The challenge expires after one hour** — generate a new one if you did not verify in time.

Verify: `{"organizationId": "<organization-id>", "domain": "acme.example"}` → response `changeDate`. Repeat generation + verification for each domain.

List body: `{"organizationId": "<organization-id>", "pagination": {"offset": 0, "limit": 100, "asc": false}, "sortingColumn": "DOMAIN_FIELD_NAME_NAME", "filters": [{"domainFilter": {"domain": "acme", "method": "TEXT_QUERY_METHOD_CONTAINS"}}]}` → `pagination` and `domains[]` with `organizationId`, `domain`, `isVerified`, `isPrimary`, `validationType`.

Delete body: `{"organizationId": "<organization-id>", "domain": "acme.example"}`. Deleting a domain that is used as a login-name suffix locks those users out until they use another domain; domain discovery for it stops working too.

Why verification comes first: the instance's domain setting `requireOrgDomainVerification` (see `GetDomainSettings`) decides whether an added domain is created as verified or as unverified. When verification is required, **an unverified domain cannot be used as the organization's login domain** — users cannot log in with `user@acme.example` and domain discovery will not resolve it until `VerifyOrganizationDomain` succeeded. Set the domain setting to false only on a self-hosted instance where you deliberately skip ownership proof. After verification, keep the DNS record in place: ownership is re-checked periodically. The domain marked `isPrimary` is the one shown in the UI and asserted as `preferred_username`.

Console: Organization → *Organization Domains* → add domain, click it to get DNS/HTTP challenge, *Verify*, then *Set as primary*.

## 2. Organization metadata

Metadata is a free-form key/value store on the organization, ideal for automation markers (`provisioned-by`, `billing-id`, `tenant-state`) that your tooling reads back.

| Operation | Connect path | REST | Permission |
| --- | --- | --- | --- |
| Set | `POST /zitadel.org.v2.OrganizationService/SetOrganizationMetadata` | `POST /v2/organizations/{organization_id}/metadata` | `org.write` |
| List | `...OrganizationService/ListOrganizationMetadata` | `POST .../metadata/search` | `org.read` |
| Delete | `...OrganizationService/DeleteOrganizationMetadata` | `DELETE .../metadata` | `org.write` |

```bash
curl -X POST "https://<your instance domain>/zitadel.org.v2.OrganizationService/SetOrganizationMetadata" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"organizationId": "<organization-id>",
       "metadata": [{"key": "provisioned-by", "value": "dGVycmFmb3Jt"}]}'
```

- Values are `bytes`, so over HTTP they must be **base64 encoded** (`echo -n terraform | base64`). Response: `setDate`.
- Setting is an upsert keyed by `key`: matching keys are overwritten, other keys are untouched. Passing an empty value deletes an existing key (a no-op for a key that does not exist) — but prefer the delete call for clarity.
- List: `{"organizationId": "<organization-id>", "pagination": {"offset": 0, "limit": 100, "asc": false}, "filters": [{"keyFilter": {"key": "provisioned-by"}}]}` → `pagination`, `metadata[]` with `key` and base64 `value`.
- Delete: `{"organizationId": "<organization-id>", "keys": ["provisioned-by"]}` → `deletionDate`.
- Console: Organization → *Metadata* (key/value editor).

## 3. Human users

A human user exists in exactly one organization. Uniqueness of the username depends on instance/organization settings: with `loginNameIncludesDomain` disabled, usernames are unique **across the whole instance**; with organization-scoped usernames enabled, they are unique per organization.

### `CreateUser` vs `AddHumanUser`

`CreateUser` (`POST /zitadel.user.v2.UserService/CreateUser`, REST `POST /v2/users/new`) is **the** creation endpoint: one request type for humans and service accounts, with an explicit `organizationId`. `AddHumanUser` (REST `POST /v2/users/human`, `user.write`) is deprecated and only accepts the organization as an `organization` object instead of a top-level id. Use `CreateUser`; keep `AddHumanUser` only for code that cannot be changed.

### Create a human user

Required permission: `user.write` (declared on `AddHumanUser`; `CreateUser` is declared as `authenticated` and enforces the same permission in the command).

Plain password, verified email, no onboarding mail:

```bash
curl -X POST "https://<your instance domain>/zitadel.user.v2.UserService/CreateUser" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "organizationId": "<organization-id>",
    "username": "minnie-mouse",
    "human": {
      "profile": { "givenName": "Minnie", "familyName": "Mouse",
                   "displayName": "Minnie Mouse", "preferredLanguage": "en", "gender": "GENDER_FEMALE" },
      "email": { "email": "minnie@acme.example", "isVerified": true },
      "password": { "password": "<initial password>", "changeRequired": true }
    }
  }'
```

Variants of the same body:

- Username omitted: the email address is used as the username. `userId` omitted: the system generates one; set it yourself only for migrations (`userId` cannot be changed later).
- Force onboarding instead of a password: drop `password` and set `email` to `{"email": "...", "returnCode": {}}` or `{"sendCode": {"urlTemplate": "https://<your app>/invite?userID={{.UserID}}&code={{.Code}}&orgID={{.OrgID}}"}}`, then call `CreateInviteCode` (below) so the user can set their first authentication method.
- Let the API hand you the code instead of mailing it: `"email": {"email": "...", "returnCode": {}}` → response field `emailCode`. Same for phone with `returnCode` → `phoneCode`.
- Import an existing hash instead of a plain password: `"hashedPassword": {"hash": "<modular-crypt-format hash>", "changeRequired": true}`.
- Phone: `"phone": {"phone": "+41...", "isVerified": true}`; sending a code requires a configured SMS provider.
- Attach metadata at creation with the root-level `metadata` array (`human.metadata` is deprecated; setting both fails validation).

Response: `id` (the new user id), `creationDate`, and `emailCode`/`phoneCode` when requested with `returnCode`. `AddHumanUser` answers with `userId` + `details` instead.

Console: *Users* → *New* → *Human User* tab (on instances created before v3 the deprecated *Human User [deprecated]* UI is shown until the feature flag *Use V2 Api in Management Console for User creation* is enabled in Default Settings). Choose: set up authentication later, send an invitation mail, or set an initial password with the email marked verified.

### Email and phone verification flow

| Step | Connect path | REST |
| --- | --- | --- |
| Change email (+ choose verification) | `POST /zitadel.user.v2.UserService/SetEmail` | `POST /v2/users/{user_id}/email` |
| Send a fresh code | `...UserService/SendEmailCode` | `POST /v2/users/{user_id}/email/send` |
| Resend after a change | `...UserService/ResendEmailCode` | `POST /v2/users/{user_id}/email/resend` |
| Verify | `...UserService/VerifyEmail` | `POST /v2/users/{user_id}/email/verify` |

```json
// 1) Set the address and ask for a code (or use {"returnCode": {}} to get it in the response)
{ "userId": "<user-id>", "email": "new@acme.example", "sendCode": { "urlTemplate": "https://<your app>/verify?userID={{.UserID}}&code={{.Code}}&orgID={{.OrgID}}" } }

// 2) Verify with the code the user received
{ "userId": "<user-id>", "verificationCode": "SKJd342k" }
```

- `SendEmailCode`/`ResendEmailCode` body is a oneof: `sendCode` (mail with your template) or `returnCode` (response carries `verificationCode`). Without a choice the default ZITADEL mail is sent.
- `VerifyEmail` requires the code; the response is `details`. Verification does not change the user state.
- Setting the address without a verification choice sends the default mail; `"isVerified": true` marks it verified immediately, which is only appropriate when you have another way to prove ownership.
- Phone equivalents: `SetPhone`, `ResendPhoneCode`, `VerifyPhone`, `RemovePhone`. Console: user detail → *Contact* → change email/phone and *Verify*.

### Passwords

- Set for another user (administrator path): `POST /zitadel.user.v2.UserService/SetPassword`, REST `POST /v2/users/{user_id}/password` — deprecated in favour of `UpdateUser`, but still the simplest admin call.

```json
{ "userId": "<user-id>", "newPassword": { "password": "<new password>", "changeRequired": false } }
```

- Reset flow: `PasswordReset` (REST `POST /v2/users/{user_id}/password_reset`) with `{"userId": "...", "sendLink": {"notificationType": "NOTIFICATION_TYPE_Email", "urlTemplate": "https://<your app>/reset?userID={{.UserID}}&code={{.Code}}&orgID={{.OrgID}}"}}`, or `{"returnCode": {}}` → response `verificationCode`. Then `SetPassword` (or `UpdateUser.password`) with `"verificationCode": "<code>"`.
- `SetPassword` needs one of `currentPassword` or `verificationCode` unless the caller holds the permission to reset passwords.
- Console: user detail → *Password* → *Reset password* / *Set password*.

### Update, state changes, get, list

| Operation | Connect path | REST | Note |
| --- | --- | --- | --- |
| Update (partial) | `POST /zitadel.user.v2.UserService/UpdateUser` | `PATCH /v2/users/{user_id}` | `user.write`; preferred over the deprecated `UpdateHumanUser` (`PUT`-style full update) |
| Deactivate | `.../DeactivateUser` | `POST /v2/users/{user_id}/deactivate` | error if already inactive |
| Reactivate | `.../ReactivateUser` | `POST /v2/users/{user_id}/reactivate` | error if not inactive |
| Lock | `.../LockUser` | `POST /v2/users/{user_id}/lock` | error if already locked |
| Unlock | `.../UnlockUser` | `POST /v2/users/{user_id}/unlock` | error if not locked |
| Delete | `.../DeleteUser` | `DELETE /v2/users/{user_id}` | sets state `deleted` |
| Get by id | `.../GetUserByID` | `GET /v2/users/{user_id}` | returns full user incl. profile, email, phone |
| List | `.../ListUsers` | `POST /v2/users` | see below |

`UpdateUser` takes `userId` plus any of `username`, `human.profile`, `human.email`, `human.phone`, `human.password`, `machine`, `metadata` (base64). **Changing the username invalidates the user's active tokens and sessions.** To remove a phone number, send an empty `phone` with no verification field.

`GetUserByID` body: `{"userId": "<user-id>"}` → `user` with `userId`, `state`, `username`, `loginNames[]`, `preferredLoginName`, `human` or `machine`, `details`.

List users with the v2 query filters:

```json
{
  "query": { "offset": 0, "limit": 100, "asc": false },
  "sortingColumn": "USER_FIELD_NAME_USER_NAME",
  "queries": [
    { "organizationIdQuery": { "organizationId": "<organization-id>" } },
    { "userNameQuery": { "userName": "minnie", "method": "TEXT_QUERY_METHOD_CONTAINS_IGNORE_CASE" } },
    { "emailQuery": { "emailAddress": "@acme.example", "method": "TEXT_QUERY_METHOD_ENDS_WITH" } },
    { "displayNameQuery": { "displayName": "Minnie", "method": "TEXT_QUERY_METHOD_CONTAINS_IGNORE_CASE" } },
    { "stateQuery": { "state": "USER_STATE_ACTIVE" } },
    { "typeQuery": { "type": "TYPE_HUMAN" } }
  ]
}
```

- Available query keys: `userNameQuery`, `firstNameQuery`, `lastNameQuery`, `nickNameQuery`, `displayNameQuery`, `emailQuery`, `phoneQuery`, `loginNameQuery`, `stateQuery`, `typeQuery`, `inUserIdsQuery`, `inUserEmailsQuery`, `organizationIdQuery`, `metadataKeyFilter`, `metadataValueFilter`, and the combinators `orQuery`/`andQuery`/`notQuery`.
- `organizationIdQuery` is the only reliable way to scope a list to one organization. Without it the result depends on the caller: an instance administrator gets all users of the instance, an organization administrator only their own.
- Sorting (`sortingColumn`): `USER_FIELD_NAME_USER_NAME`, `_FIRST_NAME`, `_LAST_NAME`, `_NICK_NAME`, `_DISPLAY_NAME`, `_EMAIL`, `_STATE`, `_TYPE`, `_CREATION_DATE` (default). Response: `details`, `sortingColumn`, `result[]` where each entry has the flat fields plus a `human` or `machine` sub-object.

### User state transitions

Derived from the RPC descriptions (v2 removed the automatic `initial` state: new users are active immediately, even without a password or verified email; `USER_STATE_INITIAL` remains in the enum for legacy data):

| From | Call | To | Errors |
| --- | --- | --- | --- |
| (none) | `CreateUser` / `AddHumanUser` | `active` | — |
| `active` | `DeactivateUser` | `inactive` | error if already `inactive` |
| `inactive` | `ReactivateUser` | `active` | error if not `inactive` |
| `active` | `LockUser` | `locked` | error if already `locked` |
| `locked` | `UnlockUser` | `active` | error if not `locked` |
| `active` | too many failed password attempts (lockout setting) | `locked` | — |
| any | `DeleteUser` | `deleted` | afterwards `GetUserByID` returns not-found |

Lock is the temporary, reversible block that lockout policy also uses; deactivate is the deliberate "no longer allowed, keep the data" block. Email/phone verification never changes the state.

## 4. Machine users (service accounts)

Machine users represent workloads and have no profile, no password, no MFA: only a name, a description and a username. They are created through the same `CreateUser` call with the `machine` oneof instead of `human`.

```bash
curl -X POST "https://<your instance domain>/zitadel.user.v2.UserService/CreateUser" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "organizationId": "<organization-id>",
    "username": "ci-runner",
    "machine": {
      "name": "CI Runner",
      "description": "Calls the session API from the build pipeline",
      "accessTokenType": "ACCESS_TOKEN_TYPE_BEARER"
    }
  }'
```

- `accessTokenType` is `ACCESS_TOKEN_TYPE_BEARER` (default, opaque token — revocations take effect immediately) or `ACCESS_TOKEN_TYPE_JWT` (self-contained token with user and permission information; **a revoked JWT stays valid until it expires**, so introspection is still required for revocation-critical flows).
- Without an explicit `username` the user id is used as the username.
- A machine user with no credential cannot authenticate at all, and a credential without a role cannot do anything: **grant it administrator roles or project roles after creation** (section 7 and the authorization/role-assignment reference of this skill). Credentials for machine users: `AddSecret` (client id = username, secret pair for client-credentials/JWT-profile), `AddKey` (JWT profile with a private key), `AddPersonalAccessToken` (section 5).
- Update machine properties with `UpdateUser` (`machine.name`, `machine.description`, `machine.accessTokenType`).
- Console: *Users* → *New* → *Service Account* tab.

## 5. User authentication methods an administrator manages

### Personal access tokens (PAT)

| Operation | Connect path | REST | Permission |
| --- | --- | --- | --- |
| Create | `POST /zitadel.user.v2.UserService/AddPersonalAccessToken` | `POST /v2/users/{user_id}/pats` | `user.write` |
| List | `...UserService/ListPersonalAccessTokens` | `POST /v2/users/pats/search` | `user.read` |
| Delete | `...UserService/RemovePersonalAccessToken` | `DELETE /v2/users/{user_id}/pats/{token_id}` | `user.write` |

```json
{ "userId": "<user-id>", "expirationDate": "2026-01-01T00:00:00Z" }
```

- `expirationDate` is required. The response carries `tokenId`, `creationDate` and `token` — **the token value is returned once and cannot be read again**; store it in your secret manager immediately.
- Listing is a search: `{"pagination": {"offset": 0, "limit": 100, "asc": false}, "sortingColumn": "PERSONAL_ACCESS_TOKEN_FIELD_NAME_CREATED_DATE", "filters": [{"userIdFilter": {"id": "<user-id>"}}]}` → `result[]` with `id`, `userId`, `organizationId`, `creationDate`, `expirationDate`. Never shipped in the list response: the token itself.
- Deleting needs both `userId` and `tokenId`; only users of type machine can hold PATs.
- Console: user detail → *Personal Access Tokens* → *New*.

### Keys (JWT profile for service accounts)

| Operation | Connect path | REST | Permission |
| --- | --- | --- | --- |
| Add | `POST /zitadel.user.v2.UserService/AddKey` | `POST /v2/users/{user_id}/keys` | `user.write` |
| List | `...UserService/ListKeys` | `POST /v2/users/keys/search` | `user.read` |
| Remove | `...UserService/RemoveKey` | `DELETE /v2/users/{user_id}/keys/{key_id}` | `user.write` |

```json
{ "userId": "<user-id>", "expirationDate": "2026-01-01T00:00:00Z" }
```

- Omitting `publicKey` makes ZITADEL generate the pair and return it in `keyContent` (a `bytes` field, therefore base64 over HTTP) together with `keyId` and `creationDate`; supplying a base64 `publicKey` keeps the private key on your side. The key content is returned **once** — the list response only carries metadata (`id`, `userId`, `organizationId`, `creationDate`, `expirationDate`).
- Keys can be exchanged for short-lived tokens only through the JWT-profile grant — see the authentication reference of this skill. Only machine users can hold keys.
- Console: service account detail → *Keys* → *New*.

### Secrets

`AddSecret` (`POST /v2/users/{user_id}/secret`) generates/overwrites the client secret for a machine user, with the username as client id; the response carries `clientSecret` and `creationDate` — the secret cannot be retrieved again. `RemoveSecret` (`DELETE /v2/users/{user_id}/secret`) removes both. Both need `user.write`. No console step, both are CLI-friendly.

### User metadata

`SetUserMetadata` (`POST .../SetUserMetadata`, REST `POST /v2/users/{user_id}/metadata`), `ListUserMetadata` (`POST .../metadata/search`), `DeleteUserMetadata` (`DELETE .../metadata`) with permissions `user.write`, `user.read`, `user.write`. Body shape and base64 rule are identical to organization metadata; useful for external ids (`stripeCustomerId`), migration markers and automation flags. Metadata can be exposed to applications through the userinfo endpoint or the ID token — treat it as non-secret.

### Inspect which methods a user has

`ListAuthenticationMethodTypes` — `GET /zitadel.user.v2.UserService/ListAuthenticationMethodTypes` (REST `GET /v2/users/{user_id}/authentication_methods`). The service declares only `authenticated` for it and the method documents no explicit permission; expect it to require read rights on the user (`user.read` — unverified).

```json
// request
{ "userId": "<user-id>", "domainQuery": { "domain": "acme.example" } }
// response
{ "details": { "totalResult": 3, "processedSequence": 42, "timestamp": "..." },
  "authMethodTypes": ["AUTHENTICATION_METHOD_TYPE_PASSWORD", "AUTHENTICATION_METHOD_TYPE_PASSKEY", "AUTHENTICATION_METHOD_TYPE_OTP_EMAIL"] }
```

Possible values: `AUTHENTICATION_METHOD_TYPE_PASSWORD`, `_PASSKEY`, `_IDP`, `_TOTP`, `_U2F`, `_OTP_SMS`, `_OTP_EMAIL`, `_RECOVERY_CODE`. This is the check to run before claiming a user "has MFA". To list the concrete configured factors (with ids and states) use `ListAuthenticationFactors`.

## 6. The instance and its settings

### Instance

| Operation | Connect path | Permission | Notes |
| --- | --- | --- | --- |
| Get | `POST /zitadel.instance.v2.InstanceService/GetInstance` | `iam.read` (`system.instance.read` when `instanceId` is set) | without `instanceId` the instance of the request host is returned |
| Update | `...InstanceService/UpdateInstance` | `iam.write` (`system.instance.write` with `instanceId`) | body `{"instanceId": "...", "instanceName": "..."}` |
| List | `...InstanceService/ListInstances` | `system.instance.read` | system level, cannot be called from an instance context |
| Delete | `...InstanceService/DeleteInstance` | `system.instance.delete` | system level |

`InstanceService` has **no REST annotation**: call it over Connect (`POST /zitadel.instance.v2.InstanceService/<Method>` with `Connect-Protocol-Version: 1`). Response fields of `GetInstance`: `instance.id`, `instance.name`, `instance.version` (managed by the system), `instance.state` (`STATE_RUNNING`, …), `creationDate`, `changeDate`, `customDomains[]`.

`ListInstances` body: `{"pagination": {"offset": 0, "limit": 100, "asc": false}, "sortingColumn": "FIELD_NAME_CREATION_DATE", "filters": [{"customDomainsFilter": {"domains": ["auth.example"]}}]}` → `instances[]`, `pagination`. Add `{"inIdsFilter": {"ids": ["<instance-id>"]}}` to look up specific instances.

### Custom domains

| Operation | Connect path | Permission |
| --- | --- | --- |
| Add | `POST /zitadel.instance.v2.InstanceService/AddCustomDomain` | `system.domain.write` |
| Remove | `...InstanceService/RemoveCustomDomain` | `system.domain.write` |
| List | `...InstanceService/ListCustomDomains` | `iam.read` (`system.instance.read` with `instanceId`) |

```json
{ "instanceId": "<instance-id>", "customDomain": "auth.example.com" }
```

- A custom domain **is the issuer of every token the instance mints**: adding one changes `iss` in the discovery document, the ID tokens, and the audience/issuer your applications and SAML metadata check. Register and trust it in every relying party before switching, and make sure DNS/TLS for the domain terminates at the instance (routing is done by host name). Removing it stops that routing and breaks existing integrations and sessions.
- The domain must be unique across all instances; auto-generated domains (`generated: true`) cannot be removed, but the primary domain can be switched to a manually added one.
- List body: `{"instanceId": "<instance-id>", "pagination": {...}, "sortingColumn": "DOMAIN_FIELD_NAME_DOMAIN", "filters": [{"primaryFilter": true}]}` → `domains[]` with `instanceId`, `domain`, `primary`, `generated`, `creationDate`.

### Trusted domains

| Operation | Connect path | Permission |
| --- | --- | --- |
| Add | `POST /zitadel.instance.v2.InstanceService/AddTrustedDomain` | `iam.write` |
| Remove | `...InstanceService/RemoveTrustedDomain` | `iam.write` |
| List | `...InstanceService/ListTrustedDomains` | `iam.read` |

Body: `{"instanceId": "<instance-id>", "trustedDomain": "login.example.com"}`. Trusted domains are **not** used for routing and therefore need not be unique to one instance; they let a deployment that is reached through another host name (reverse proxy, custom login UI) appear consistently in API responses such as OIDC discovery and email templates. Add one when your login UI lives on a different host than the instance's custom domain, otherwise redirects and discovery documents point at the wrong host.

### Settings endpoints an operator actually needs

All of these are read-only except the two security ones; every "get" needs `policy.read` unless noted, and organization-scoped reads fall back to the instance values when the organization has no override.

| Setting | Connect path | REST | Notes |
| --- | --- | --- | --- |
| General | `POST /zitadel.settings.v2.SettingsService/GetGeneralSettings` | `GET /v2/settings` | default organization, default/allowed/supported languages |
| Login | `...SettingsService/GetLoginSettings` | `GET /v2/settings/login` | `allowUsernamePassword`, `allowLocalAuthentication`, `allowRegister`, `allowExternalIdp`, `forceMfa`, `passkeysType`, `hidePasswordReset`, `ignoreUnknownUsernames`, `defaultRedirectUri`, various check lifetimes |
| Active IdPs | `...SettingsService/GetActiveIdentityProviders` | `GET /v2/settings/login/idps` | filter by creation/linking/auto-creation/auto-linking |
| Password complexity | `...SettingsService/GetPasswordComplexitySettings` | `GET /v2/settings/password/complexity` | `minLength`, `requiresUppercase/Lowercase/Number/Symbol` |
| Password expiry | `...SettingsService/GetPasswordExpirySettings` | `GET /v2/settings/password/expiry` | `maxAgeDays`, `expireWarnDays` |
| Lockout | `...SettingsService/GetLockoutSettings` | `GET /v2/settings/lockout` | `maxPasswordAttempts`, `maxOtpAttempts` (0 = never lock) |
| Branding | `...SettingsService/GetBrandingSettings` | `GET /v2/settings/branding` | logos, colours, fonts, theme |
| Domain | `...SettingsService/GetDomainSettings` | `GET /v2/settings/domain` | `loginNameIncludesDomain`, `requireOrgDomainVerification`, `smtpSenderAddressMatchesInstanceDomain` |
| Legal and support (deprecated) | `...SettingsService/GetLegalAndSupportSettings` | `GET /v2/settings/legal_support` | superseded by link settings |
| Security | `...SettingsService/GetSecuritySettings` / `SetSecuritySettings` | `GET` / `PUT /v2/settings/security` | `iam.policy.read` / `iam.policy.write`; iframe embedding + allowed origins, impersonation, dynamic client registration |
| Hosted login translation | `...SettingsService/GetHostedLoginTranslation` / `SetHostedLoginTranslation` | `GET` / `PUT /v2/settings/hosted_login_translation` | `iam.policy.read` / `iam.policy.write` |
| Organization settings (username scope) | `...SettingsService/SetOrganizationSettings`, `DeleteOrganizationSettings`, `ListOrganizationSettings` | `POST`/`DELETE`/`POST .../organization` | **not registered** on current releases — see below |
| Effective settings | `...SettingsService/GetEffectiveSettings` | — | **not registered** on current releases |
| Link settings | `...SettingsService/GetLinkSettings`, `SetLinkSettings`, `ResetLinkSettings` | — | **not registered** on current releases |

Two facts to plan around:

1. Several settings RPCs exist in the definition but return `404` on the tested release: the organization-scoped username settings, the link settings and the effective-settings aggregate. Do not build automation that depends on them.
2. Several settings have **no v2 write endpoint** (only `SetSecuritySettings` and the hosted-login translation do). Those are still writable through the legacy v1 Admin/Management API, which is mounted as REST under `/admin/v1/…` and `/management/v1/…` (unauthenticated calls answer `401`, so the routes exist). Use it deliberately and mind its idioms: camelCase bodies and the `x-zitadel-orgid` header for organization context, versus snake_case/camelCase bodies with the organization id inside the body for v2.

Console: *Default settings* (instance level, `https://<your instance domain>/ui/console/orgs` is its organization scope) → *Login*, *Password*, *Lockout*, *Branding*, *Domain*, *Features*, *Security*. Organization → *Settings* overrides the instance defaults.

Account state investigation: the login settings' check lifetimes, lockout settings and `ListAuthenticationMethodTypes` together explain almost every "user cannot log in" report.

## 7. Instance- and organization-level administrators

All administrator grants go through `InternalPermissionService` (Connect only, no REST annotations). Note the resource type is part of the request, not the path.

| Operation | Connect path | Required permission (by resource) |
| --- | --- | --- |
| List | `POST /zitadel.internal_permission.v2.InternalPermissionService/ListAdministrators` | `iam.member.read` (instance), `org.member.read` (org), `project.member.read`, `project.grant.member.read`; listing your own grants needs no permission |
| Create | `...InternalPermissionService/CreateAdministrator` | `iam.member.write` / `org.member.write` / `project.member.write` / `project.grant.member.write` |
| Update | `...InternalPermissionService/UpdateAdministrator` | same write permissions |
| Delete | `...InternalPermissionService/DeleteAdministrator` | `iam.member.delete` / `org.member.delete` / `project.member.delete` / `project.grant.member.delete` |

Instance-level grant:

```json
{ "userId": "<user-id>", "resource": { "instance": true }, "roles": ["IAM_ORG_MANAGER"] }
```

Organization-level grant:

```json
{ "userId": "<user-id>", "resource": { "organizationId": "<organization-id>" }, "roles": ["ORG_OWNER"] }
```

- `userId` is always a **user id** (human or machine), never a username or login name; the id inside `resource` is the **organization** (or project) id. Instance level is expressed by `resource.instance: true` (a boolean that must be `true`), which is the only shape without an id.
- Roles are resource-type specific: a grant for an organization does **not** carry over to its projects, and one grant cannot cover an instance and an organization at once. Create two grants for two levels.
- `UpdateAdministrator` replaces the role list: **any role not present in the request is revoked.** Send only the previous roles you want to keep plus the new one, or you will silently downgrade an administrator.
- `DeleteAdministrator` is idempotent: if the grant is already gone the call still succeeds, and `deletionDate` may be absent — do not interpret an empty `deletionDate` as failure.
- Scope rule: an **instance-level administrator acts across all organizations** of the instance (instance owners manage the instance and all organizations with their content); an **organization-level administrator can only touch their own organization's** resources and settings, and never sees users or resources of other organizations. Grant the narrowest level that does the job — instance-level roles such as `IAM_OWNER` are the ones that make an automation token dangerous.
- Useful roles: `IAM_OWNER`, `IAM_ORG_MANAGER` (manage all organizations and their content), `IAM_USER_MANAGER` (manage users and authorizations across organizations), `IAM_LOGIN_CLIENT` (build a custom login UI), `ORG_OWNER`, `ORG_USER_MANAGER`, `ORG_PROJECT_CREATOR`.
- Response: `CreateAdministrator` → `creationDate`; `UpdateAdministrator` → `changeDate`; `DeleteAdministrator` → `deletionDate`.
- `ListAdministrators` body: `{"pagination": {"offset": 0, "limit": 100, "asc": false}, "sortingColumn": "ADMINISTRATOR_FIELD_NAME_USER_ID", "filters": [{"resource": {"organizationId": "<organization-id>"}}, {"inUserIdsFilter": {"ids": ["<user-id>"]}}, {"role": {"roleKey": "ORG_OWNER"}}]}` → `administrators[]` with `user` (`id`, `preferredLoginName`, `displayName`, `organizationId`), the resource oneof, `roles[]`, `creationDate`, `changeDate`. Filters combine with `and`/`or`/`not` sub-filters.
- Console: the resource's right-hand panel → *Administrators* → *New*. By default only users of the selected organization are suggested; switch to global search and type the exact login name to grant roles across organizations.

## 8. Console equivalents

- Create organization: organizations dropdown → *New organization* (*Current User* or *New Account*); self-service at `/ui/login/register/org`. Default organization: Default settings page (`/ui/console/orgs`) → *Set as default organization*.
- Create human user: *Users* → *New* → *Human User* (choose setup later / invitation mail / initial password; tick "email verified" to skip the initialization mail).
- Create service account: *Users* → *New* → *Service Account*; then the detail page for *Secret*, *Keys* and *Personal Access Tokens*.
- Verify an organization domain: Organization → *Organization Domains* → add → click the domain → DNS or HTTP challenge → *Verify* → optional *Set as primary*.
- Settings: *Default settings* for instance level, Organization → *Settings* for overrides; domain verification requirement, login behaviour and language settings live under *Default settings*.
- Administrators: the *Administrators* panel of the instance, organization, project or granted project.

## 9. Pitfalls

- Username uniqueness is per instance unless organization-scoped usernames are enabled: reusing `admin` in a second organization fails with an already-exists error. Prefix usernames per tenant, or turn organization-scoped usernames on deliberately — the setting is only accepted while the usernames in scope are still unique.
- Choose the email path on purpose: `sendCode`/default (mail goes out), `returnCode` (you get `verificationCode` back and mail is **not** sent), `isVerified: true` (no proof at all). Marking emails verified to skip onboarding mail is how unverified addresses end up in production.
- Deleting a user does **not** remove what the user authored or was granted: role grants, project grants, personal access tokens and keys issued for the account, and audit history stay behind. Revoke or reassign administrator grants explicitly before deleting, and delete the PATs and keys you created for the account.
- Deleting an organization cascades to its users, projects and grants. Export first; there is no undo.
- Never treat "unverified domain" as usable: with `requireOrgDomainVerification` on, the domain cannot serve as the login domain and cannot be discovered until verified, and verification challenges expire after an hour.
- Authentication and deletion are different verbs: `DeleteUser` is a state change, `LockUser`/`UnlockUser` are temporary, `DeactivateUser`/`ReactivateUser` are policy decisions. Picking the wrong one either leaves a working login or destroys data.
- `UpdateAdministrator` revokes roles you omit — always send the full intended role list.
- Permissions are per operation and per resource owner: creating a user needs `user.write` in that organization, `org.create` is a global-ish permission, instance reads need `iam.read`. A `403` is a permission problem, never a path problem.
- Organization context lives in the **request body** in v2 (`organizationId`, or `resource.organizationId` for administrator grants). The v1 `x-zitadel-orgid` header is not the v2 mechanism; do not set it and expect an effect. Same for `AddHumanUser`, which carries the org in its `organization` object (and is deprecated for exactly this kind of ambiguity).
- The response of a composite call (for example `AddOrganization` with admins) must be persisted in full: it contains ids you cannot reconstruct afterwards, and codes that are returned only once.
- Legacy v1 is REST-only: `/management/v1/…`, `/admin/v1/…` and `/auth/v1/…` are mounted (the REST routes exist), while the Connect path of those services (`POST /zitadel.management.v1.ManagementService/<Method>`) answers `404`. Reach for v1 when a task has no v2 endpoint (see the settings table), and keep the idioms apart.
- `InstanceService` and `InternalPermissionService` are Connect-only; calling them via a REST path cannot work. `ListInstances`, `DeleteInstance` and the domain write calls are system-level and cannot be used from an instance context.
- Group APIs are not available yet: on the tested release `group.v2.GroupService` answers `404` for every method while the API reference marks the resource as under development (expect it on newer releases; re-probe before relying on it). Model group-like structures with projects + role grants and metadata until the group API is live on your release.
