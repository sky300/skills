---
name: affine-administration
description: "Use when managing a self-hosted AFFiNE instance: setting layers, OIDC login, Copilot BYOK, MCP access."
---

# AFFiNE administration

Managing a running self-hosted AFFiNE (Notion-style documents plus a whiteboard): which configuration layer wins, how identity and AI are wired, and how agent access through the MCP server is granted. It assumes the instance is already up — building the container set, the database, and the reverse-proxy path is separate work this skill does not cover.

## The management model: two configuration layers

- The **file layer** is the deployment's own config file (`config.json` in the mounted config directory): the public base URL, AI switches, the indexer choice.
- The **database layer** is the `app_configs` table. Everything an administrator changes in the panel lands there, and **the database wins** when the two disagree.
- So a setting that "did not apply" is usually a setting applied from the layer nobody read. Read the file and the row before theorising, and read the row directly when the panel is not enough to explain what is in force.
- The layers also differ in *when* they apply: file changes need a restart (there is no hot reload), while panel changes generally take effect on next use — do not restart the pod reflexively after a panel edit, and do not conclude a panel edit failed because a restart did not "activate" it.

`references/config-layering.md` has the keys worth knowing, the read recipes, and the equality that ties the public URL to what the frontend builds.

## Identity

An external OIDC provider is configured in the panel as a single JSON blob, lands in the database layer, and needs no restart to take effect. Its two failure modes both look like configuration errors and are not: an SSRF guard that refuses an issuer resolving to a private address (the provider then never registers, silently), and an `email_verified` requirement that aborts the callback with a generic OAuth error.

`references/oidc-sso.md` carries the blob, the exact log lines, the resolution check that must run inside the app container, and a symptom-to-suspect triage list.

## AI (Copilot BYOK)

A self-hosted instance may point the built-in AI at a custom OpenAI- or Gemini-compatible endpoint without a paid plan, gated by database-layer switches. The probe the panel offers runs **from inside the app container**, so reachability is a question about the pod's network, not the browser's; and a failing probe leaves nothing in the service log, because the errors come back in the response body.

`references/copilot-byok.md` covers the switches, the entitlement check, the endpoint/protocol pairing rule, and the error taxonomy to ask for first.

## Agent access (MCP server)

- Read tools register unconditionally; write tools register only when **two independent gates** are satisfied — a build-time namespace flag on the server *and* the credential's access mode. Satisfying one leaves the tools hidden, which is expected rather than a bug.
- The credential can only be created by a human in the panel, so ask for the token and say how to revoke it.
- **Do not report "writes are enabled" from the container's environment variables.** Read a branch the flag actually drives, and do not call writing verified until a tool listing shows the write tools and one real write has been read back.

`references/mcp-access.md` has the tool inventory, the recovered gate condition, the flag-proof probe, the credential step, and how to inspect any gate inside a shipped bundle.

## Working principles

- **Judge state from the layer that performs the action**, not from an equivalent-looking place: the app container's resolver (not the host's), the app container's network path (not the browser's), the running bundle (not the release notes). An outside check can agree with the wrong answer and send you into the wrong component.
- **The shipped bundle is the authority for what a build can do.** Grep it before telling a user a feature is missing or unsupported; a gate that exists but is unreachable is worth stating plainly, together with what enabling it costs.
- **State costs before enabling anything.** A flag that changes a release channel or the UI a user sees on their phone is a decision, not a troubleshooting step.
- Values only the user can supply — a client secret, an MCP token, an account's verification state — are asked for, never invented. Account and workspace creation are likewise panel actions with no API equivalent.

## Reference routing

- `references/config-layering.md` — the two layers, keys worth knowing, read recipes, when each applies.
- `references/oidc-sso.md` — OIDC wiring and its look-alike failures.
- `references/copilot-byok.md` — custom AI endpoint, probe behaviour, error taxonomy.
- `references/mcp-access.md` — MCP tool inventory, write gates, flag verification, credentials, bundle inspection.
