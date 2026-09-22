# MCP access: what an agent can and cannot do, and how to grant it

AFFiNE bundles an official MCP server inside the app image. Its read tools register
unconditionally; its write tools register only behind two independent gates, so a
healthy MCP endpoint that cannot write anything is a normal state — not a
misconfiguration to hunt for.

Verified on 2026-09-22 against AFFiNE **0.27.4** (image channel tag `stable`); every
command and byte count below was run against that image. The one claim marked
*reported* was not re-measured.

**Placeholders are deliberate** — each stands for a value only the operator knows:
`<app-container>` / `<postgres-container>` (container names), `<affine-origin>`
(public base URL), `<host-port>` (the port the app publishes on the host),
`<workspace-id>`, `<token>` (the credential the user creates in the UI). Paths
beginning `/app/` are paths **inside the app image**, identical for every deployment
of that image — not paths on the operator's host.

## Tool inventory

- **Read, unconditional**: `doc_read`, `doc_canvas_read`, `doc_search`,
  `frontend_read_selection`, `frontend_read_nodes`, `frontend_snapshot_document`.
- **Write, only under the canary gate**: `create_document`, `update_document`
  (body-only, structure-aware), `update_document_meta` (title only).
- Client-facing names as an aggregator sees them: `doc_search`, `read_document`,
  `create_document`, `update_document`, `update_document_meta`; the internal
  primitives carry a second layer (`doc_create`, `doc_update`, `doc_update_meta`).
  The client-facing aliases are what `tools/list` returns.
- **No delete or trash tool exists.** A document an agent created while testing is
  removable only by a human in the UI — say so when test content is left behind.

## The gate

The minified condition, recovered from the bundle:

```js
if (r === McpAccessMode.READ_WRITE && (env.dev || env.namespaces.canary)) { /* write tools */ }
```

The env accessors it reads, from the same bundle:

```js
get dev() { return "development" === this.NODE_ENV }   // NODE_ENV is hardcoded "production" in the image
NAMESPACE = readEnv("AFFINE_ENV", "production", ...)
get namespaces() { return { canary: "dev" === this.NAMESPACE, beta: ..., production: ... } }
```

- `NODE_ENV` is a literal `"production"` in the shipped bundle, so the `env.dev`
  half is unreachable in a stable image. The one reachable knob is `AFFINE_ENV=dev`
  on the server container, which flips `namespaces.canary`.
- **Two independent gates guard writes** — the canary namespace *and* the
  credential's `access_mode`. Satisfying one still hides the tools, which is why
  "I set the credential to read-write and nothing changed" is expected, not a bug.
- Access mode defaults to read-only: the read path defaults its mode argument to
  `McpAccessMode.READ_ONLY`.

Two side effects of `AFFINE_ENV=dev`, both real, neither blocking the MCP goal —
state them before enabling it:

- Upgrade checks follow the **canary** channel and `availableUpgrade` becomes
  canary-shaped, which has blanked the admin panel (*reported*, not re-measured).
- `canary` also serves the **mobile frontend** to mobile user agents — different
  UI, same data. The user will notice it on their phone.

Undo by removing the env line, reloading systemd, and restarting the app.

## Proving the gate opened, with no credential

Do not report "canary is on" from the container's environment alone — read a branch
the flag drives. `canary` selects which static page is served to mobile user
agents, and both candidates ship in the image, so the **served byte count** is the
readout.

```bash
# the two candidate pages as baked into the image — take sizes from here, never hardcode them
podman exec <app-container> sh -c 'ls -l /app/static/selfhost.html /app/static/mobile/selfhost.html'

M='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1'
D='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
curl -s -o /dev/null -w 'mobile  %{http_code} %{size_download}\n' -A "$M" http://127.0.0.1:<host-port>/
curl -s -o /dev/null -w 'desktop %{http_code} %{size_download}\n' -A "$D" http://127.0.0.1:<host-port>/
```

The baseline is **the same byte count for both user agents** (the root page). With
`AFFINE_ENV=dev` in effect the mobile agent reports the
`static/mobile/selfhost.html` size while desktop keeps the root size. On 0.27.4
those files are 2690 and 2689 bytes — a **1-byte difference** — so compare the
numbers exactly against what the container reports; "the sizes look different" does
not hold here.

Do **not** use a byte comparison of the two files as the readout: they are baked at
build time, so `cmp -s /app/static/selfhost.html /app/static/mobile/selfhost.html`
prints `DIFFER` on that image whatever the flag says. It is a constant of the
image, not a state of the server.

Generalise it: **when a flag has no direct readout, find a branch whose observable
output differs between the two states** — a served file, a rendered page, a
response header — and probe that. "The variable is set in the container spec" is
intent; a changed response is evidence.

## Closing the loop: credential and endpoint

The flag only makes the write tools *registrable*. A write still needs a credential
whose `access_mode` is `READ_WRITE`, and the API cannot create one — the user
creates it in the app (workspace settings → Integrations → MCP server → create
credential). The UI ships both modes (i18n keys
`com.affine.integration.mcp-server.access.read-only` / `…access.read-write`) plus
expiry, rotate and revoke actions. Ask the user for the token, and tell them how to
revoke it afterwards — the UI's revoke action, which stamps `revoked_at`.

- Endpoint: `POST https://<affine-origin>/api/workspaces/<workspace-id>/mcp`
  (bundle route literal `/api/workspaces/:workspaceId/mcp`). It takes JSON-RPC
  bodies, and the request needs the `Authorization` header whose value is `Bearer`,
  a space, then `<token>`.
- Resolve `<workspace-id>` from the database instead of guessing:
  `podman exec <postgres-container> psql -U affine -d affine -tAc "select id, name from workspaces;"`
- Verify by **listing tools**, then doing one real write and reading it back. Until
  a `tools/list` shows `create_document` / `update_document`, the honest status is
  "the gate is open, the tool will register" — never "writing works". The same
  discipline covers the write itself: reading the document back is the evidence,
  not the absence of an error.

## Inspecting the credential in the database

```bash
podman exec <postgres-container> psql -U affine -d affine -x -tAc \
  "select id, name, access_mode, revoked_at, created_at, last_used_at, fingerprint from mcp_credentials order by created_at desc limit 3;"
```

- An empty result means no credential exists. A user reporting "the MCP is
  read-only" in that state is relaying the documentation, not an observation — say
  so rather than debugging a connection that does not exist.
- Other columns: `family_id`, `generation`, `secret_hash`, `user_id`,
  `workspace_id`, `expires_at`, `replaced_by_id`, `grace_ends_at`. `access_mode` is
  an enum type.
- **The plaintext token is not recoverable**: the table holds `secret_hash` plus a
  `fingerprint`, so a lost token means rotate or create a new credential in the UI,
  never a database read.

## Inspecting an unknown gate in a shipped bundle

```bash
# context around a symbol in the minified bundle — widen .{N} until the enclosing `if` is visible
podman exec <app-container> sh -c 'grep -o ".\{300\}<symbol>.\{400\}" /app/dist/main.js | head -2'
# enumerate registered names
podman exec <app-container> sh -c 'grep -oE "\"(create_document|update_document)\"" /app/dist/main.js | sort -u'
# recover a whole condition
podman exec <app-container> sh -c 'grep -o "READ_WRITE&&([^)]*)" /app/dist/main.js'
# confirm the feature's enum/type exists in this build at all
podman exec <app-container> sh -c 'grep -o ".\{0,60\}McpAccessMode.\{0,40\}" /app/dist/main.js | head -5'
# i18n keys the frontend actually ships (they live in the JS i18n bundles, not in an asset directory)
podman exec <app-container> sh -c 'grep -rho "com.affine.<area>[^\"]*" /app/static/js /app/static/admin/js | sort -u'
```

`grep -o` with a fixed-width context window is the fastest way to read a minified
conditional without pulling the source tree. The i18n grep shows what the UI offers
a user; for the MCP panel it also exposes `…capabilities.write`, which the UI
displays even in a build whose server-side gate withholds the write tools.

Rule of thumb: **before telling a user a self-hosted feature is missing, broken or
unsupported, grep the running bundle for the gate.** Docs describe the release
channel; the bundle describes this build. A gate that exists but is unreachable is
also worth stating plainly, together with what enabling it costs elsewhere.
