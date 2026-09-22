---
name: zitadel-administration
description: Use when managing a ZITADEL instance through its APIs — service accounts, administrator roles, projects, applications, organizations and user grants. Covers the connectRPC v2 surface, the legacy v1 REST surface, and the credentials each one needs.
license: MIT
# Optional: hosts that support an env-var declaration (Hermes Agent does) expose these names to
# the agent and pass the ones that are set through to sandboxed commands. All are marked optional
# on purpose — no single set is required, because the credential can arrive as a token, a client
# secret or a key file. See "Read the connection details from the environment" in the body.
required_environment_variables:
  - name: ZITADEL_DOMAIN
    prompt: ZITADEL instance domain (issuer host, no scheme)
    help: Read the issuer from https://<instance domain>/.well-known/openid-configuration
    required_for: every API call
    optional: true
  - name: ZITADEL_TOKEN
    prompt: Bearer token for the ZITADEL API
    help: A personal access token, or a token obtained through one of the other grants
    required_for: authentication, simplest path
    optional: true
  - name: ZITADEL_CLIENT_ID
    prompt: Service-account id (its username)
    required_for: the client credentials grant
    optional: true
  - name: ZITADEL_CLIENT_SECRET
    prompt: Service-account client secret
    required_for: the client credentials grant
    optional: true
  - name: ZITADEL_USER_ID
    prompt: Service-account user id used as the JWT issuer and subject
    required_for: the private key JWT grant
    optional: true
  - name: ZITADEL_KEY_ID
    prompt: Key id of the registered public key
    required_for: the private key JWT grant
    optional: true
  - name: ZITADEL_KEY_FILE
    prompt: Path to the PEM private key
    required_for: the private key JWT grant
    optional: true
  - name: ZITADEL_ORG_ID
    prompt: Organization id for organization-scoped calls
    required_for: calls that take an organization
    optional: true
---

# ZITADEL administration

Manage a ZITADEL instance programmatically: create and configure service accounts,
projects, applications, organizations, roles and authorizations, and know which
credential and which API surface each operation needs.

This skill is about *operating* an existing instance. It does not cover deploying
ZITADEL itself, nor configuring an application to accept ZITADEL logins — that
application-side work belongs in that application's own runbook.

## Mental model

Learn this before calling anything; most "not found" and "permission denied"
answers come from getting a level wrong.

- **Instance** — one ZITADEL deployment. It has one issuer (the domain in
  `/.well-known/openid-configuration`) and contains many organizations.
- **Organization** — owns users, projects, policies and its own settings. Every
  user and every project belongs to exactly one organization.
- **Project** — a container for applications, roles and authorizations.
- **Application** — an OIDC / API / SAML client inside a project. Applications
  are what a user's software is configured with (client id + secret).
- **Role** — defined on a project (`key` + `displayName`), referenced by role key
  in tokens. Used by *your* applications.
- **Authorization (role assignment)** — assigns project roles to a user. A user
  with no authorization for a project gets no roles for it.
- **Administrator role** — a *ZITADEL* operator role, at four levels: instance
  (`IAM_*`), organization (`ORG_*`), project (`PROJECT_OWNER`), project grant
  (`PROJECT_GRANT_OWNER`). Administrator roles are what let a service account
  call the ZITADEL APIs at all; project roles do not.

Prominent trap: applications **read** roles, they do not grant them. A user is
"in" an application only through an authorization on its project, and only
instance-level administrators act across organizations.

## Before the first call

You need three things; get them from the user rather than guessing.

1. The **instance domain** (the OIDC issuer). Confirm it by reading
   `https://<instance domain>/.well-known/openid-configuration` — the `issuer`
   field is the value that token audiences must match.
2. A **credential**: a personal access token, or a service-account key pair /
   client secret. See `references/authentication.md`.
3. Enough **administrator role** for the operation. A credential that can read
   usually cannot write, and only an instance-level role reaches across
   organizations.

Never ask the user to paste a secret into a chat log or a repository. Take it
from a file or an environment variable, and tell them how to revoke it when the
task is done.

### Read the connection details from the environment

Names are fixed so a user can prepare a machine once and every task picks them
up. Read them from the environment; never invent a value.

| Variable | Holds | Used for |
|---|---|---|
| `ZITADEL_DOMAIN` | issuer host without scheme (`id.example.com`) | every call |
| `ZITADEL_TOKEN` | a ready bearer token (PAT or one obtained elsewhere) | the simplest path |
| `ZITADEL_USER_ID` | service-account user id | private key JWT (`iss`/`sub`) |
| `ZITADEL_KEY_ID` | key id of the registered public key | private key JWT (`kid`) |
| `ZITADEL_KEY_FILE` | path to the PEM private key | private key JWT |
| `ZITADEL_CLIENT_ID` | machine user id, i.e. its username | client credentials |
| `ZITADEL_CLIENT_SECRET` | the machine user's secret | client credentials |
| `ZITADEL_ORG_ID` | organization id | calls that take an organization |

Which one to reach for: a token is enough for a short task, client credentials
suit a service that already has a secret, and a key file is the option when the
credential must not travel as a string. The System API uses its own system user
and key — point `ZITADEL_KEY_FILE` at that key and see
`references/authentication.md`.

Rules that keep this predictable:

- **Unset means ask, not guess.** Name the missing variable and what it is for;
  do not substitute a plausible domain, organization id or user id.
- **Confirm the domain through discovery**, not through the variable's name: a
  wrong `ZITADEL_DOMAIN` answers `401` to everything and reads like a bad
  credential.
- **Never echo a secret** and never write one into a file inside a repository.
  Mask it in your own output, and hand the user commands that read it from the
  environment rather than embedding it.
- **Prefer the narrowest credential the task allows**, and ask for a role rather
  than a wider one.
- **Several instances mean several values.** Do not overwrite a variable to
  switch instances mid-task; pass the value per call.

### What you can do with no credential at all

Zero-credential access is limited to: the discovery document
(`/.well-known/openid-configuration`), the liveness and readiness endpoints
(`/debug/healthz`, `/debug/ready`), the hosted login page and the console page
(both serve HTML to anyone), and route-existence probing — a `401` proves a
method is registered, a `404` proves it is not. Every data API answers
`401 {"code":"unauthenticated","message":"auth header missing"}` and the token
endpoint refuses without a client assertion, so no amount of probing yields an
inventory, resource ids or even the organization list.

So a credential is the prerequisite for everything, and **a role is not a
credential**. An administrator role that exists in the instance is unusable from
a remote machine until someone produces a PAT, a key pair or a client secret. If
the only copy of a credential lives on the deployment host — the login client's
PAT that Login V2 bootstraps, for instance — a remote operator without access to
that host has no path to it, and re-issuing one needs a credential that can
write user credentials. The credential-free ways out are the console (a human
with an account there creates the service account, grants the role, and issues
the credential) or an existing administrator credential. Plan the first run
around that handover, and ask for a role no wider than the task.

## The request shape

The v2 APIs are served over connectRPC: a plain HTTP `POST` to

```
POST https://<instance domain>/<proto package>.<Service>/<Method>
Authorization: Bearer <access token>
Content-Type: application/json
Connect-Protocol-Version: 1

{ ...request fields... }
```

Example (list projects):

```bash
curl -sS -X POST "https://$ZITADEL_DOMAIN/zitadel.project.v2.ProjectService/ListProjects" \
  -H "Authorization: Bearer $ZITADEL_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Connect-Protocol-Version: 1" \
  -d '{"query":{"limit":50}}'
```

The legacy v1 services use their own REST paths (`/management/v1/...`,
`/admin/v1/...`, `/auth/v1/...`) with the same `Authorization` header and
camelCase bodies. Use them only for what v2 does not offer — see the legacy
coverage map in `references/conventions.md`.

Method names come from the protobuf definition, so a method that exists in your
release appears in the official reference page for that service. Before writing
automation against an unfamiliar version, probe the method unauthenticated:
**401/403 means the route exists, 404 means it does not** (wrong release, wrong
surface, or a typo in the package).

Two details that save time:

- **Field names are flexible on the way in and consistent on the way out.**
  Connect request bodies accept both the proto name and lowerCamelCase
  (`organization_id` and `organizationId` both work); responses come back in
  lowerCamelCase.
- **Legacy v1 annotations in the protos are relative.** The served URL is the
  prefix plus the annotation: `post: "/users/machine"` is
  `POST /management/v1/users/machine`. A bare annotation path answers 404.

## Where to look

| Task | Reference |
| --- | --- |
| Create a service account, give it an administrator role, obtain a token | `references/authentication.md` |
| Projects, project roles, project grants | `references/projects-and-applications.md` |
| Applications (OIDC / API / SAML), client secrets, application keys | `references/projects-and-applications.md` |
| Role assignments that bind users to project roles | `references/projects-and-applications.md` |
| Organizations, users (human and machine), instance settings, custom domains, administrator grants | `references/organizations-users-instance.md` |
| Which API to use, transports, error codes, pagination, organization context, legacy coverage | `references/conventions.md` |
| Exchange a service-account key for a token (adaptable template) | `templates/service-account-token.sh` |

## Worked example: put an application behind ZITADEL

The most common request. Three API steps plus a real verification.

1. Ensure the project exists — `CreateProject` needs an explicit
   `organizationId`, there is no implicit default:

   ```bash
   POST /zitadel.project.v2.ProjectService/CreateProject
   {"organizationId":"<organization-id>","name":"my-app"}
   ```

   Keep the returned `projectId`.
2. Create the OIDC application inside it:

   ```bash
   POST /zitadel.application.v2.ApplicationService/CreateApplication
   {"projectId":"<project-id>","name":"my-app","oidcConfiguration":{...}}
   ```

   The full config field list is in `references/projects-and-applications.md`.
   Keep `applicationId`; read `clientId` from the same response.
3. Generate the client secret if the application authenticates with one:
   `POST /zitadel.application.v2.ApplicationService/GenerateClientSecret`.
   The secret is returned **once** — put it into the application's configuration
   immediately, and nowhere else.
4. Verify by exercising the real flow, not by re-reading the config: request
   `https://<instance domain>/oauth/v2/authorize?client_id=...&redirect_uri=...`
   and confirm the redirect is accepted (an unregistered `redirect_uri` is
   rejected with an explicit message). A config that reads back correctly can
   still be wrong.

## Rules that prevent most damage

- **Read back before reporting success.** After every write, call the matching
  `Get`/`List` method and quote the field you changed. A 200 on the write is not
  evidence that the intended value landed.
- **Confirm destructive operations with the user first.** Delete and deactivate
  are sometimes irreversible and they cascade: deleting an organization takes
  its users, projects and applications with it.
- **Never invent identifiers.** Project ids, application ids, user ids, key ids
  and role keys are opaque strings; resolve them with a `List` call.
- **Do not assume a response envelope.** Some v2 lists answer
  `{"pagination":{...},"<things>":[...]}`, others `{"details":{...},"result":[...]}`.
  Read the field names in the response; an empty-looking result usually means you
  assumed the wrong envelope rather than that the call failed.
- **A `200` with counts but no item array means no permission, not an empty
  collection.** Some lists (`ListApplications`, `ListAuthorizations`,
  `ListAdministrators`, `ListOrganizations`) fill `pagination.totalResult` and
  omit the array entirely when the credential may not read the entries — and
  those counts are not authorization-scoped, so a role-less credential reads the
  same totals as an instance administrator while seeing nothing. Never report a
  count taken from `totalResult` alone: require the array, and if it is missing,
  say the credential cannot read the list. Check
  `/auth/v1/memberships/me/_search` and `/auth/v1/permissions/zitadel/me/_search`
  before trusting any list.
- **A request field from the wrong shape is ignored, not rejected.** Unknown
  fields are dropped while decoding, so a filter written for `query`/`queries`
  against a service that expects `pagination`/`filters` answers `200` with an
  unfiltered list at the default limit of 100. Compare the returned
  `appliedLimit` with the limit you asked for before reporting counts.
- **Treat 405, 404 and 403 as three different things.** 405 = wrong HTTP verb
  (a `GET`-registered route called with `POST`), 404 = no such route or resource
  in this context, 403 / `permission_denied` = the credential is valid but the
  role is missing. Only the last one is fixed by granting something.
- **Keep instance-specific values out of the skill and out of version control.**
  Domains, ids, and credential locations belong in a local unpublished note.
- **Rotate, do not share.** When a credential was created for this task, say how
  to revoke it (`references/authentication.md`) before you finish.

## Verifying your work

Three levels, in increasing strength — use the strongest one the change allows:

1. **Read back** the resource through the API and compare the field.
2. **Existence check** for a route you were unsure about: an unauthenticated
   `POST` should answer 401/403, not 404.
3. **End-to-end** for anything login-facing: drive the OIDC `authorize` endpoint
   with the application's real `client_id` and `redirect_uri` and confirm the
   outcome. Configuration that looks right is not the same as a login that
   works.

Route registrations are release-dependent: a path that works on the release you
tested can be absent on another. Re-probe rather than assuming, and record the
release you verified against when you report back.
