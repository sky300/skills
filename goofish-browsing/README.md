# goofish-browsing

[English](./README.md) | [简体中文](./README.zh-CN.md)

[Xianyu (闲鱼 / Goofish)](https://www.goofish.com) operations for AI agents:
keyword search, item detail, your own listings and IM sessions — plus publishing,
taking listings down and sending messages (writes, each one approved by the user).

Xianyu has no open API and no OAuth registration, so access is a logged-in
browser session exported as cookies. The skill carries it over two transports —
whichever your environment can support:

- **mtop JSON API over plain HTTP** (no browser): item detail, own listings,
  chat list, and any other internal mtop endpoint you name.
- **Rendered DOM in a browser**: keyword search, because the search page is
  client-rendered and the site itself treats the browser path as the more robust
  one.

## Install

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s goofish-browsing
```

Or copy the directory into your agent's skills folder.

## What is in here

One template and three reference documents:

| File | Role |
|---|---|
| `templates/mtop_request.py` | A copy-and-adapt snippet: signs an mtop request (and can send it). **Standard library only**, no network unless you enable it |
| `templates/publish_item.py` | Payload assembly for publishing a listing (images, price, delivery, category, location) |
| `templates/im_send_message.py` | Chat messages over the WebSocket gateway: the LWP frame sequence (needs `websockets`) |
| `references/mtop-apis.md` | Verified endpoints, payloads, field paths, error codes, risk notes |
| `references/browser-search.md` | The search extractor and browser steps, as text |
| `references/write-operations.md` | Publish / take-down / message recipes, and the rules that govern writes |
| `references/browser-tool-setup.md` | How to stand up a browser tool when the machine has none |

The narrow code is intentional, and it is a template rather than a tool: it
computes the one thing that must be byte-exact, and lets you edit where your
cookies live, which transport you have, and how you retry. Everything that
depends on the environment or on judgement stays in prose, so the agent adapts
instead of waiting for the skill to support its setup.

## Requirements

- Python 3 (any recent version). No third-party packages: not `requests`, not
  `playwright`.
- A logged-in Xianyu session exported as cookies (`unb` and `_m_h5_tk` are
  mandatory).
- A browser tool **only if you need keyword search** — the agent's own browser
  tool if it has one (with any way to inject cookies), otherwise one set up per
  `references/browser-tool-setup.md`. Item detail, listings and chats need no
  browser at all.

## Usage

```bash
cp templates/mtop_request.py ./mtop_request.py
$EDITOR mtop_request.py     # three marked blocks: cookies, api/payload, send-or-not
python3 mtop_request.py
```

It prints the URL, query string, form body and starting headers (and posts it if
you set `SEND = True`). Send the result with `curl`, `requests`, or a `fetch()`
from a page already open on `www.goofish.com`. Then read
`references/mtop-apis.md` for how the response is shaped; item data lives under
`data.itemDO`.

Keyword search is a browser job: follow `references/browser-search.md`, which
carries the extractor and the steps.

## Writes

Publishing a listing, taking one down and sending chat messages are supported,
under three rules: **the user approves the exact content first**, writes stay at
roughly one per minute, and every write is verified by reading it back (a
`SUCCESS` ret means accepted, not live). No bulk actions and no automated
outreach — that is where accounts get limited.

## Security

A cookie file is a live account session. Keep it out of version control, out of
chat logs, and out of the conversation; `chmod 600` it. To revoke it, use the
Xianyu app's "log out of all devices".

## Notes

Unofficial: it speaks the web client's internal endpoints, which can change
without notice. Verified against live responses in 2026-09; the request shapes,
field paths, and known response codes are documented in
[`references/mtop-apis.md`](./references/mtop-apis.md).
