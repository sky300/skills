# AFFiNE Administration

[English](./README.md) | [简体中文](./README.zh-CN.md)

Managing a running self-hosted AFFiNE instance: which configuration layer actually governs a setting, wiring an external identity provider, pointing the built-in AI at your own endpoint, and granting an agent access through the MCP server — including what that server refuses to do until two separate gates are opened.

**Repository**: https://git.nite07.com/nite/skills (subdirectory: `affine-administration/`)

## What It Covers

- **Two configuration layers** — the deployment's config file versus the `app_configs` table, which wins, how to read what is in force, and why the layers apply at different times.
- **OIDC login** — the JSON blob the panel expects, the SSRF guard that keeps a correct-looking provider from ever registering, the resolution check that must run inside the app container, and the email-verification gate that surfaces as a generic OAuth error.
- **Copilot BYOK** — the switches that permit a custom AI endpoint, the entitlement bypass on a self-hosted instance, why the test probe asks a question about the container's network rather than the browser's, and the error taxonomy to ask for first.
- **MCP access** — the tool inventory, the two independent gates that decide whether write tools exist at all, how to prove a gate opened by reading a branch it drives, the credential step no API can perform, and how to inspect any gate inside a shipped bundle.
- **Working principles** — judge state from the layer that performs the action, treat the running bundle as the authority for what a build can do, and state the cost of enabling a flag before enabling it.

## Installation

```bash
# Global install (available across all projects)
npx skills add https://git.nite07.com/nite/skills.git -g -s affine-administration

# List available skills without installing
npx skills add https://git.nite07.com/nite/skills.git --list
```

**Manual install** (any agent, including Hermes Agent):

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/affine-administration <your agent's skills directory>/
```

`<your agent's skills directory>` is a deliberate placeholder — where skills are read from is the user's and the agent's decision, so this skill does not assume a location.

## When To Use It

Use this skill when you want to:

- find out why a setting the user changed appears to have no effect
- wire or debug an external identity provider
- point the built-in AI at a self-hosted OpenAI- or Gemini-compatible endpoint
- give an agent access to the instance through MCP, or find out why it can read but not write
- decide whether a feature even exists in a given build without waiting on release notes

## How To Use It

1. Say which instance and which surface the change was made on — the panel, the config file, or the environment.
2. Give it the evidence that exists: the failing log line, the probe's `errorKind`, the panel state.
3. Expect it to read the running instance (the database row, the container's own resolver and network, the shipped bundle) rather than to quote documentation.
4. For anything the user must supply — a client secret, an MCP token, an account's verification state — expect to be asked, since none of it is recoverable from the server.

## Project Structure

```text
affine-administration/
├── SKILL.md                        # Entry point: the two layers, identity, AI, MCP, principles
├── README.md                       # This file (English, canonical)
├── README.zh-CN.md                 # Simplified Chinese translation
└── references/
    ├── config-layering.md          # The second layer, the keys worth knowing, read recipes
    ├── oidc-sso.md                 # OIDC wiring and its look-alike failures
    ├── copilot-byok.md             # Custom AI endpoint and probe diagnosis
    └── mcp-access.md               # Tool inventory, write gates, flag proof, credentials, bundles
```

## Notes

- **The database layer wins.** A panel change and a config-file edit that disagree resolve in favour of the panel row — read it before theorising.
- **A gate that exists but is unreachable is worth stating plainly**, together with what enabling it costs elsewhere (a release channel, the UI a phone user sees).
- **Verification means the layer that performs the action**, not an equivalent-looking check somewhere else.
- Marked values in the references are deliberate: they are the reader's decision, not defaults this skill can pick.

## License

MIT
