# Copilot / AI BYOK — pointing the built-in AI at a custom endpoint

AFFiNE's built-in AI (Copilot) can be pointed at an OpenAI- or Gemini-compatible endpoint instead of AFFiNE's paid service, and a self-hosted instance is entitled to do so without a plan. This file covers where the switches live, where the test probe runs, and how to reach the cause of a failing probe.

Placeholders are deliberate — each value is the environment's or the user's decision: `<app-container>` (the container running the AFFiNE server), `<db-container>` (its Postgres), `<container-runtime>` (`podman` or `docker`), `<affine-origin>` (the public URL), `<endpoint-port>` (the port the AI endpoint is reached on), `<host-ip>` (the host's LAN or private-overlay address), `<endpoint-url>` (the endpoint the user supplies). Facts marked **verified** were reproduced against a stable self-hosted image; the rest is labelled as an unverified generalisation.

## Where the switches live

- Configure the feature at workspace settings → Integrations → **AI BYOK**. Do not hunt for provider fields in the admin panel: Admin → AI carries the enable switch only and points back at workspace settings.
- Read the switches out of the `app_configs` **table**, not the config file, because admin-panel edits land in the database and override the file when the two disagree:

  ```bash
  <container-runtime> exec <db-container> psql -U affine -d affine -tAc \
    "select id, value::text from app_configs where id ~ 'copilot|byok';"
  ```

- Require `copilot.enabled`, `copilot.byok.allowCustomEndpoint` and `copilot.byok.allowPrivateEndpoint` to all be `true` before touching the endpoint field. **Verified:** with either byok flag false the UI refuses the endpoint *before any request leaves the container*, and each disabled case has its own message key (`byok.endpoint.custom-disabled`, `byok.endpoint.private-disabled`) — so there is nothing to diagnose on the network yet.
- Expect two key-storage modes in the panel — key kept in the browser, key stored server-side — each with its own fallback order. The modes are verified to exist; their precedence was not read out of the bundle (unverified).

## Entitlement is not the gate on a self-hosted instance

- Check the deployment type before blaming a plan, because `hasServerEntitlement()` short-circuits to `true` when `env.selfhosted`. Read the server's own view rather than inferring it from how the instance was deployed:

  ```bash
  curl -s <affine-origin>/info
  # {"compatibility":"<x>","message":"AFFiNE <x> Server","type":"selfhosted","flavor":"..."}
  ```

  `type` is `env.DEPLOYMENT_TYPE`; only `selfhosted` there puts the server on the bypass branch (verified).
- Ignore `byok.locked.*` strings found in the JS bundle: the panel ships copy for every state, so the string's presence says nothing about the live state (verified).

## The test button probes from inside the container

- Treat the endpoint as something the **container** must reach, not the browser: the panel's test delegates server-side to the native runtime (`probeWorkspaceByokDraft` → `runtime.probeByokDraft`), so the connection is made from the app container's network namespace (verified). Probe from there with the image's own runtime:

  ```bash
  <container-runtime> exec <app-container> node -e '
  for (const u of ["http://host.containers.internal:<endpoint-port>/v1/models",
                   "http://<host-ip>:<endpoint-port>/v1/models",
                   "http://127.0.0.1:<endpoint-port>/v1/models"]) {
    const s = Date.now();
    fetch(u, {signal: AbortSignal.timeout(8000)})
      .then(r => console.log(u, r.status, ((Date.now()-s)/1000).toFixed(2)+"s"))
      .catch(e => console.log(u, "FAIL", e.cause?.code));
  }'
  ```

- Use the host gateway name (`host.containers.internal:<host-port>`) or the host's LAN/private-overlay address (`<host-ip>:<host-port>`) as the endpoint; both reach a service on the host, and a `401` with no key is the success signal — the endpoint answered and only the credential is missing (verified). Never enter `127.0.0.1:<host-port>`: inside the pod that address is the pod itself and the probe fails with `ECONNREFUSED` (verified).
- Do not suspect the container's egress first — from inside the container, public AI APIs of several major providers answered in under a second with no proxy environment set (verified), so a failure is far more likely the address, the path, or the key than the network.
- Remember the probe's HTTP shape lives in the server's native module, not in the JS bundle, so grepping the JS bundle for the request shape finds nothing (verified).

## Diagnose by `errorKind`, then stop

- Ask for `errorKind` from the probe response **first**, before any log work; it splits the problem in half:

  | `errorKind` | meaning |
  |---|---|
  | `unreachable` | never connected — wrong host/port, or a loopback address seen from inside the pod |
  | `unauthorized` | connected, and the endpoint rejected the key |
  | `not_found` | connected, `404` — that path does not exist there |
  | `invalid_response` | connected, got a response, but the body is not a completion payload — wire-format/path problem, not connectivity and not auth |
  | `timeout` / `rate_limited` / `unsupported` | upstream-side conditions |

- Never try to fix `invalid_response` by re-testing reachability: the request did arrive. Go to the pairing rule below and inspect what the endpoint returns for the exact URL the probe builds (verified).
- Read `X-Operation-Name` in the reverse proxy's access log when the user's toast is not enough — the client stamps every GraphQL request with it, so the log reconstructs the session. `createWorkspaceByokProfile` present means the user got past the test; absent means every attempt died in `probeWorkspaceByokDraft`. A **multi-second** duration is a real network wait; **under 0.1 s** means input validation rejected the attempt before any request was made, so re-read the fields the user typed instead of the network (verified).

## The provider choice and the endpoint form must agree

- Enter a **base URL** and expect AFFiNE to append the protocol path (verified):

  | provider chosen in the panel | AFFiNE appends | the endpoint must therefore be |
  |---|---|---|
  | OpenAI-compatible / custom | `/chat/completions` | `<endpoint-url>` **including** `/v1` |
  | Gemini-style | `/v1beta/models/<model>:generateContent` | the bare base URL, **without** `/v1` |

- Do not follow the form's own placeholder (`https://api.example.com/v1`): it is correct only for the OpenAI-compatible row. A Gemini-style provider that keeps `/v1` requests `/v1/v1beta/models/<model>:generateContent`, which yields `404` or an invalid body (verified).
- Reproduce both paths from inside the container before editing the form, and list the endpoint's models to confirm the model id exists there. When a stored key is a `${VAR}` reference, resolve it out of the environment file and never echo it.

## Traps that hide the cause

- Do not read the service journal for a failed probe. **Verified:** GraphQL errors come back as **HTTP 200 with the error in the body** and the BYOK resolvers swallow them, so the journal shows nothing at all — no `ERROR`, no request line. Read the user's toast (the copy behind `byok.notify.test-failed.title`) or the `probeWorkspaceByokDraft` response body in DevTools instead.
- Distinguish a failed **test** from a failed **save**: they are separate messages, and the test is its own operation (`byok.action.test`). A failed test leaves `ai_workspace_byok_configs` empty, which is expected rather than evidence of a deeper config fault.
- Expect `200 text/html` from an endpoint that also serves a web UI on the same port (verified for one gateway; treat as a general trap): its SPA fallback answers unknown paths with `200` and an HTML page, the client reports `invalid_response`, and the endpoint's own log stays empty because the request never reached an API handler. Check the content-type of the suspect path — `200 text/html` means the path is wrong, `401`/`404 application/json` means a real API route.
- Do not assume the endpoint value the app reports is the string the user typed: the reported value can reflect the URL the client builds from the base, so compare the combination that will actually be requested (base + appended protocol path) and reproduce that URL instead of trusting the display.
- Tell "the request never arrived" from "it arrived on a dead path" by the client IP the endpoint logged: traffic from inside the pod carries the pod's NAT gateway address, traffic from the host carries the host's own LAN address. Only failed API calls are logged there, so an empty log is not proof of absence (verified).

## Adjacent facts

- The BYOK catalogue the panel renders comes from the `workspaceByokSettings` query, so that request in the access log proves the panel loaded the live policy.
- Transcript and workspace-indexing capabilities need a **server-side Gemini** key specifically, or fall back to the paid plan; a key that satisfies chat only leaves those two uncovered (`byok.coverage.title`).
- `ai_workspace_byok_configs` is the server-side key store; the other `ai_*` tables stay empty until a chat actually runs, so an empty table is not a configuration problem.
- There is no upstream documentation page for these gates — the shipped image is the spec. Enumerate in this order: the i18n bundle for the feature's states and message keys, the client JS for the GraphQL documents and operation names, then the server's non-minified dist bundle for the entitlement and resolver gates (verified).
