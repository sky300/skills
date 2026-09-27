# NapCat OneBot

[English](./README.md) | [简体中文](./README.zh-CN.md)

An agent skill for talking to QQ through a self-hosted [NapCat](https://github.com/NapNeko/NapCatQQ) protocol side that exposes [OneBot 11](https://github.com/botuniverse/onebot-11) over HTTP.

The agent gets what it needs to send group and private messages, read chat history on demand, look up groups and friends, and move files — plus the failure modes that look like coding bugs but are account or container problems.

## What it covers

- The HTTP request/response surface: `POST {base}/<action>`, one JSON object per call, one JSON envelope back
- Message content in segment-array form (text, at, reply, image, record, video, face, forward), with CQ-code strings as the fallback
- The action catalogue by task: send, read history, look up, manage, files and media
- Failure handling: token rejections, `retcode` semantics, ids that lose precision, files that do not resolve because the protocol side has its own filesystem
- Pacing, because the account — not the process — is what QQ's risk control acts on
- Where every fact comes from: the five authorities, what each covers, and the order to check them in
- The push transports (reverse WebSocket, HTTP report) and what they cost, for tasks where timing rather than content is the requirement
- Bringing up the protocol side itself when nothing answers, including the rootless-Podman detail that the image's entrypoint must start as root
- Unattended login persistence across container recreation: volume persistence, the four login environment variables, and device GUID / MAC address pinning
- Chat window takeover: decoupling background event sensors from agent reasoning turns, NapCat WebSocket server setup, and anti-risk pacing guidelines

## What it does not cover

Event push as a general messaging architecture. This skill defaults to reading history on demand for typical tasks, but provides complete blueprints in `references/chat-takeover.md` for scenarios requiring real-time session takeover.

## Installation

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s napcat-onebot
```

Manual installation: copy this directory into the skills directory your agent reads.

## Requirements

- A reachable NapCat instance with an OneBot HTTP server entry configured
- Two environment values, provided by your environment:
  - `NAPCAT_API_URL` — base URL of the OneBot HTTP server, no trailing slash
  - `NAPCAT_ACCESS_TOKEN` — the token configured on that server

There are no shipped scripts: every call in this skill is a documented request the agent composes.

## Structure

```text
SKILL.md                          # entry point: credentials, calling convention, rules
references/sources.md             # authorities, coverage, verification order
references/api-actions.md         # actions grouped by task, with parameters
references/request-and-errors.md  # envelope, auth, retcodes, id precision
references/message-segments.md    # segment types and fields, send and receive
references/events-and-push.md     # push transports and their cost, when timing matters
references/chat-takeover.md       # takeover architecture, WS sensor template, config guide
references/login-persistence.md   # container persistence, four env vars, GUID/MAC pinning
```

## Warning

Driving a personal QQ account through a protocol side violates QQ's terms of service and can get the account restricted. Use an account you can afford to lose, and do not bulk-send.
