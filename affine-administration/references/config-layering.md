# Configuration layers: file, then database

Where an AFFiNE setting actually lives, which layer wins, and how to read what is
in force. Two layers exist and they disagree by design.

Verified on 2026-09-22 against AFFiNE **0.27.4** (image channel tag `stable`).

**Placeholders are deliberate** — each stands for a value only the operator knows:
`<postgres-container>` (the container running AFFiNE's Postgres),
`<affine-origin>` (the public base URL), `<deployment-dir>` (where the mounted
config directory lives).

## The file layer

`config.json` in the mounted config directory — the deployment's own file, edited
by whoever runs the instance. Keys worth knowing:

- `server.externalUrl` — the public base URL.
- `copilot.byok` — enables a custom AI endpoint instead of AFFiNE's paid AI.
- `indexer` — the embedded in-process indexer, appropriate at single-user scale.

File changes need a **restart**: there is no hot reload for this file.

## The database layer

**Panel edits do not go into the file.** They land in the **`app_configs`** table
of the same database and **override** `config.json`; when the two disagree, the
database wins. `copilot.enabled` is the usual surprise — someone flips a switch in
the panel, later edits the file, and the panel value still governs.

Read a row directly when the panel is not enough to explain what is in force:

```bash
podman exec <postgres-container> psql -U affine -d affine -tAc \
  "select id, value::text from app_configs order by id;"
```

(`affine` is the image's default database name and role; adjust if the deployment
changed them.) A single key, when the full list is noise:

```bash
podman exec <postgres-container> psql -U affine -d affine -tAc \
  "select value::text from app_configs where id='oauth.providers.oidc';"
```

Keys observed in the wild: `oauth.providers.oidc`, `copilot.enabled`,
`copilot.byok.allowCustomEndpoint`, `copilot.byok.allowPrivateEndpoint`,
`server.externalUrl`.

Database-layer changes generally take effect **on next use** — OAuth config
applies on the next login attempt, AI switches on the next request — so do not
restart the pod to "activate" a panel change, and do not read a missing restart as
a failed save.

## The tie between the two layers

`server.externalUrl` must equal the public origin, or the frontend builds broken
asset and callback URLs: the app hands the browser absolute URLs derived from this
value, so an origin change means changing this key too — in **both** layers if the
panel has a copy, because the database copy wins.

## Reading order when a setting "did not apply"

1. Ask what the user changed and where (panel or file).
2. Read the database row — it wins.
3. Read the file value, for comparison and to see whether a restart is even
   relevant.
4. Only then look at the component that consumes the setting (the OAuth plugin,
   the AI resolver), and prefer its own log line over a general assumption about
   caching.
