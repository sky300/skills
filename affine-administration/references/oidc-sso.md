# OIDC / SSO (external identity provider)

Wiring a self-hosted AFFiNE to an external OIDC provider, and diagnosing the
login failures that follow. Rules are stated IdP-independently, with the symptom
attached, so they hold for any compliant provider.

Verified on 2026-09-22 against a stable-channel image; the login round trip is
**unverified** — see the last section. `<affine-origin>`, `<idp-issuer>`,
`<app-container>`, `<postgres-container>` and `<unit>` are deliberate
placeholders: those values are the operator's decision, not this skill's.

## Where the config lives

Admin panel → **Settings → OAuth**. Every provider there takes plain fields
except **OIDC, which takes a single JSON blob** — one textarea, no per-field
inputs. An unknown key is not rejected; the app reads only the keys in its own
schema, so a typo fails silently.

Admin-panel edits land in the **`app_configs`** table and override `config.json`,
so editing the OAuth keys in `config.json` and restarting changes nothing. Read
what is in force (`affine` is the app's default role and database name):

```bash
podman exec <postgres-container> psql -U affine -d affine -tAc \
  "select value::text from app_configs where id='oauth.providers.oidc';"
```

The authoritative schema is upstream
`packages/backend/server/src/plugins/oauth/config.ts`: read it for the required
keys, defaults and nesting — the claim mapping lives in a nested sub-object.

## The JSON blob

```json
{
  "clientId": "<the client id the user supplies>",
  "clientSecret": "<the client secret the user supplies>",
  "issuer": "https://<idp-issuer>",
  "allowPrivateNetwork": true,
  "args": {
    "scope": "openid profile email",
    "claim_id": "sub",
    "claim_email": "email",
    "claim_name": "name",
    "claim_email_verified": "email_verified"
  }
}
```

- The id and secret come from the IdP application registration and are the
  operator's to supply; this skill never holds them. Where another self-hosted app
  already trusts the same IdP, reuse that client.
- The `args` values are AFFiNE's own defaults, written out for legibility;
  leaving `args` empty behaves identically.

## `issuer` is the bare root

`issuer` takes the issuer root and nothing else — origin, no path, no
`.well-known` suffix; every endpoint (authorize, token, userinfo, jwks) comes
from the discovery document, so no endpoint URL is configured here. Never
retarget it to a merely convenient hostname: that breaks `iss` matching and
turns a config problem into a token-validation problem.

## `allowPrivateNetwork` and the SSRF guard

Set `"allowPrivateNetwork": true` when the app's own resolver resolves the issuer
hostname to a private or reserved address — common on a fleet that split-DNS's
its public hostnames to an overlay/CGNAT address: public outside, private from
inside the network. AFFiNE fetches the discovery document server-side; its SSRF
guard then refuses the target and the provider **silently never registers** — no
OIDC button on the login page — while the app's journal repeats, on a 60-second
retry, `Failed to validate OIDC configuration: issuer resolves to a private
network address` + `OAuth provider [oidc] unregistered` with
`ssrf_blocked_error: URL resolves to a private or reserved IP address`. Read
those from the app's own service log (`journalctl --user -u <unit>` where the app
runs as a systemd unit, or the container log).

**Do not judge the resolution from the host.** `getent hosts`, `dig` and browser
probes use a different resolver path than the app's runtime, so run the check
inside the container with that runtime:

```bash
podman exec <app-container> node -e \
  'fetch("https://<idp-issuer>/.well-known/openid-configuration").then(r=>console.log(r.status)).catch(e=>console.log(String(e)))'
```

## Redirect URI

The callback is **`https://<affine-origin>/oauth/callback`** — AFFiNE's own path,
**not** `/api/auth/callback`. Register it at the IdP together with both slash
variants (`…/oauth/callback` and `…/oauth/callback/`): exact matching rejects the
wrong trailing slash outright. The provider side has its own requirements — logout
URIs, allowed scopes, token lifetimes — so keep that checklist from your provider's
documentation rather than treating this file as complete.

## Claims and the `email_verified` gate

- Claims resolve from the **userinfo response and the id_token** as a fallback
  chain, so an IdP setting a guide calls mandatory — a "user info inside the ID
  token" toggle, for example — is **not** required here.
- **`email_verified` is a hard gate**: unless `claim_email_verified` resolves to
  exactly `true`, the callback aborts with `invalid_oauth_response` — a message
  that reads exactly like a client-registration bug. Once the registration and
  the redirect URI check out, the suspect left is the **account** at the IdP
  (address unverified, or the claim absent): an account problem, not a config
  problem, and the app will not say so.

## Applying and verifying

- Save is applied server-side with **no restart needed**: an OAuth change takes
  effect on the next login attempt, so do not restart the pod to "activate" it.
- The values are pasted by the operator, so the round trip stays **unverified
  until they complete one login** — that login is the evidence the account is
  auto-created and lands back on `<affine-origin>`. Ask, do not assume.
- Triage order, symptom → suspect:
  1. No OIDC button on the login page → the discovery fetch was refused; check
     `allowPrivateNetwork` and the resolution inside the container.
  2. `invalid_oauth_response` at the callback → the `email_verified` gate or the
     claim names, not the client registration.
  3. The browser lands on the **IdP's** error page naming `redirect_uri` with a
     silent app journal → the callback URI is not registered; probe the provider.
