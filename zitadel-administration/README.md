# ZITADEL Administration

[English](./README.md) | [简体中文](./README.zh-CN.md)

Operate a self-hosted [ZITADEL](https://zitadel.com/) instance through its APIs: service accounts and their credentials, administrator roles, projects, applications, organizations, users and role assignments. The skill carries the exact request shapes, the two API generations ZITADEL serves side by side, and the failure modes that look like bugs but are permission or context mistakes.

**Repository**: https://git.nite07.com/nite/skills (subdirectory: `zitadel-administration/`)

## What It Covers

- **Getting access** — creating a service account (machine user), granting it an administrator role at the right level, and the three ways it can authenticate: personal access token, private key JWT, and client credentials. Includes the ZITADEL API audience scope, without which every call is rejected, and how to revoke each credential.
- **Projects and applications** — creating projects, project roles, project grants, and OIDC / API / SAML applications with their full configuration fields; generating client secrets and application keys; and the role assignments that actually let a user into an application.
- **Organizations and users** — creating organizations (with their first administrators), human and machine users, verification flows, metadata, instance settings, custom domains, and instance- versus organization-level administrator grants.
- **API conventions** — which transport each service is served over, the error model and its codes, pagination and filtering, organization context, versioning and deprecation, and the map of which tasks still require the legacy v1 APIs.

## The Three Facts That Drive the Troubleshooting

1. **Two API generations live side by side.** The resource-based v2 APIs are served over connectRPC (`POST /<package>.<Service>/<Method>` with a JSON body); the legacy v1 services (Management, Admin, Auth) are REST under `/management/v1/…`, `/admin/v1/…`, `/auth/v1/…` with camelCase bodies. Mixing the idioms — a v1 body casing on a v2 path, or the v1 organization header on a v2 call — is the usual cause of a "mysterious" error.
2. **A valid credential is not an authorized one.** A service account with no administrator role authenticates perfectly, then fails unevenly: some endpoints answer `404` with `membership not found`, others answer `200` with a `totalResult` but no item array, and user search returns only the caller. Roles are granted per resource level, and only instance-level roles reach across organizations.
3. **Route registrations are release-dependent.** A path that exists on one ZITADEL release can be absent on another, and responses come in more than one envelope shape. Probe the route (401 = exists, 404 = absent) and read the field names in the response instead of assuming either.

## Installation

```bash
# Global install (available across all projects)
npx skills add https://git.nite07.com/nite/skills.git -g -s zitadel-administration

# List available skills without installing
npx skills add https://git.nite07.com/nite/skills.git --list
```

**Manual install** (any agent, including Hermes Agent):

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/zitadel-administration <your agent's skills directory>/
```

`<your agent's skills directory>` is a deliberate placeholder — where skills are read from is the user's and the agent's decision, so this skill does not assume a location.

## When To Use It

Use this skill when you want to:

- let an automation or CI job manage ZITADEL without a human in the loop
- create a project and wire an application to it (redirect URIs, client secret, roles)
- onboard a customer as a new organization, with its own administrators
- find out why a service account authenticates but every call is refused
- change an instance setting, or discover that only the legacy API can change it
- clean up: rotate keys, revoke a personal access token, deactivate an integration account

## How To Use It

1. Give the agent the **instance domain** (the OIDC issuer) and a **credential** — a personal access token or a service-account key. Keep the secret in a file or environment variable, never in the conversation if avoidable.
2. Describe the outcome you want in ZITADEL terms (project name, application type, organization), not in terms of endpoint names — the skill routes to the right reference.
3. Expect a **read-back after every write** and a real end-to-end check for anything login-facing. A configuration that reads back correctly is not yet evidence that a login works.
4. Ask for the release it was verified against. Route registrations differ between releases; the skill's probe recipe settles the question in one request.

## Configuration

The skill reads its connection details from environment variables, so a machine can be prepared once and every later task picks them up.

| Variable | Holds |
|---|---|
| `ZITADEL_DOMAIN` | issuer host without scheme (`id.example.com`) |
| `ZITADEL_TOKEN` | a ready bearer token — a personal access token, or one obtained elsewhere |
| `ZITADEL_USER_ID` | service-account user id, for the private key JWT |
| `ZITADEL_KEY_ID` | key id of the registered public key |
| `ZITADEL_KEY_FILE` | path to the PEM private key |
| `ZITADEL_CLIENT_ID` | machine user id (its username), for client credentials |
| `ZITADEL_CLIENT_SECRET` | the machine user's secret |
| `ZITADEL_ORG_ID` | organization id, for calls that take one |

Which ones you need depends on the credential: `ZITADEL_TOKEN` alone is enough for a short task, client credentials suit a service that already holds a secret, and a key file is the option when the secret must not travel as a string. A missing variable is a question for the user — never fill it in with a plausible value.

The same names are declared in `SKILL.md`'s frontmatter for hosts that support environment-variable declarations (Hermes Agent lists them for the agent and passes the ones that are set through to sandboxed commands). Every declaration there is marked optional on purpose: no single set is required, because the credential can arrive as a token, a client secret or a key file.

## Project Structure

```text
zitadel-administration/
├── SKILL.md                          # Entry point: mental model, request shape, rules, routing
├── README.md                         # This file (English, canonical)
├── README.zh-CN.md                   # Simplified Chinese translation
├── references/
│   ├── authentication.md             # Service accounts, administrator roles, PAT / private key JWT / client credentials
│   ├── projects-and-applications.md  # Projects, roles, grants, OIDC/API/SAML apps, secrets, keys, role assignments
│   ├── organizations-users-instance.md # Organizations, human and machine users, settings, domains, administrators
│   └── conventions.md                # Transports, error model, pagination, org context, legacy coverage map
└── templates/
    └── service-account-token.sh      # Copy-and-adapt: exchange a service-account key for an access token
```

## Notes

- **Personal access tokens skip the audience requirement; OAuth tokens do not.** A token minted through private key JWT or client credentials must request `urn:zitadel:iam:org:project:id:zitadel:aud`, otherwise the API rejects it while it still introspects fine.
- **Secrets and key files are shown once.** Capture them at creation time into a secret manager; there is no read-back path.
- **The legacy v1 APIs are not a fallback you can skip.** Several settings have no v2 write endpoint, so the legacy Admin/Management REST routes are the only programmatic path to them.
- Marked values in `templates/` and placeholders in the references are deliberate: they are the reader's decision, not defaults this skill can pick.

## License

MIT
