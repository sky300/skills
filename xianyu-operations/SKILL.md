---
name: xianyu-operations
description: "Use when reading or writing Xianyu/Goofish (闲鱼): search, item detail, own listings, chats, publish, message."
---

# Goofish / Xianyu Browsing

Access to Xianyu (闲鱼, Goofish), Alibaba's second-hand marketplace: keyword search,
item detail, your own listing list and IM chat list — and, under the rules in
"Writes", publishing listings, taking them down and sending messages.

There is **no official open API and no OAuth app registration**. Access is a
logged-in browser session exported as cookies, carried over one of two
transports:

| Transport | Endpoint | Needs a browser? | Good for |
|---|---|---|---|
| mtop JSON API | `POST https://h5api.m.goofish.com/h5/{api}/{version}/` | **No** — plain HTTP + md5 sign | item detail, own listings, chat list, any named internal endpoint |
| Rendered DOM | `https://www.goofish.com/search?q=…` | **Yes** | keyword search (the page is client-rendered) |

**Language:** every string in this skill — instructions, examples, and the
wording suggested for asking the user — is English so the skill stays usable by
any audience. Talk to the user in their own language and translate as needed;
nothing here requires English output. The only Chinese kept verbatim is literal
site text (risk-control markers) and the platform's own name, because those must
match what the site prints.

## What ships here, and why it is only that

- `templates/mtop_request.py` — a copy-and-adapt template: cookies + api + data
  in, a signed request out (optionally sent). Standard library only, and nothing
  happens behind your back — no network unless you flip the switch, no browser,
  no environment probing.
- `templates/publish_item.py` — listing publication: the payload assembly for the
  publish call (title/desc/images/price/delivery + the category and location the
  server returns), because those ~20 nested field names must be exact.
- `templates/im_send_message.py` — chat messages, which travel over a WebSocket and
  not HTTP: the LWP frame sequence, with the parts only you can know marked.
- Everything else is text: which endpoint answers which question, where the
  response fields live, how to fire the request, how to search through your own
  browser tool, how to tell a live session from a dead one, how to stand up a
  browser tool if the user has none, and the rules that govern writes.

The split is deliberate, and worth preserving when editing this skill: **code
only for the arithmetic that must be byte-exact every time; prose for everything
that depends on the environment or on judgement.** A script that probes the
machine, checks whether a browser exists, or verifies login state would be
usurping decisions the agent is better placed to make — it can see its own
tools, and it can open a page. Keeping the code narrow is what lets this skill
work on setups nobody anticipated.

It is a **template rather than a finished tool with parameters** for the same
reason. A fixed interface has to guess where your cookies live, which transport
you have, and how you retry; a snippet you edit has to guess nothing. Copy it,
change the marked lines, run it.

## Workflow

**1. Establish the session.** You need `unb` and `_m_h5_tk` from the user's
Xianyu cookies. To check whether a session is actually alive:

- if you have a browser tool, open `https://www.goofish.com` and look — a login
  wall versus the account's own nickname is the ground truth, and it needs no
  code;
- without one, fire any signed read call and read `ret` (`SUCCESS::调用成功` means
  live; the strings in `references/mtop-apis.md` mean expired or risk-blocked).

**2. Pick the transport.** Anything except keyword search goes over mtop, which
needs no browser at all. Search needs a rendered page — see
`references/browser-search.md` for the extractor and the steps.

**3. Build and send.** Take the signed request from the template (or write the two
lines yourself — the algorithm is below), then send it however your environment
allows: `curl`, a Python `requests` call, or a `fetch()` inside a page
you already have open on `www.goofish.com` (same cookies, same origin, so no CORS
question). `references/mtop-apis.md` lists the endpoints, their payloads, and the
field paths.

**4. If a browser is needed and you do not have one**, say so and ask the user for
a browser tool rather than improvising. `references/browser-tool-setup.md` is
written as instructions you can hand over or follow — including a CloakBrowser +
Playwright MCP recipe, and what to report when it does not work.

## Signing a request

Copy `templates/mtop_request.py` next to your work, adapt the three blocks marked
`# EDIT` — where the cookies are, which api and payload, and whether this machine
should send the request at all — then run it with whatever Python is available.
Read it before running it: it is a starting point, not an interface, and the parts
you change are the parts only you can know.

If you would rather write the call yourself, the whole algorithm is two lines:

```
sign = md5( <_m_h5_tk up to the first "_"> & t & 34839810 & data )
```

- `t` = millisecond timestamp string; `34839810` is the Xianyu web appKey.
- `data` = the JSON payload, serialised compactly (no spaces) — that exact string
  is what gets signed.
- `_m_h5_tk` is `<token>_<timestamp>`; only the part before the first `_` is
  signed.

**Token rotation:** the server hands out a fresh `_m_h5_tk` in `Set-Cookie` on
most responses. Read it from the live jar every time — never cache the token in
your own state. If a call returns a token-expired `ret`, the same response
already carried the replacement: update the jar and retry once, then stop.

## Writes

Publishing a listing, taking one down, and sending chat messages are all covered —
`references/write-operations.md` carries the recipes and `templates/` carries the
two payload/socket builders. Three rules come with them, and they are not
optional:

1. **Explicit user approval for the exact content before every write.** Draft the
   title/description/price, or the message text, show it to the user, wait for a
   yes. Nothing visible to others goes out because you decided it should.
2. **Human pacing — roughly one write per minute, and at most one session writing
   at a time.** The upstream project ships exactly that as its default limiter plus
   a 10-minute circuit breaker on risk-control keywords; treat it as the floor.
3. **Verify by reading back.** A `SUCCESS` ret or an ack `code=200` means the
   server accepted the request, not that the listing is live or the message was
   delivered. Re-read, then report what you actually see.

Never blind-retry a write: a failed attempt may have half-landed (images uploaded,
listing created without a price, message sent with a late ack). Read first.

## When to Use

- Look up Xianyu item details or prices by item id.
- Search listings by keyword (market prices, competitor listings, "is anyone
  selling this service" checks).
- Read your own listings or chat/session list.
- Any task where the answer lives in Xianyu's data and the user provides cookies.

**Don't use for:**

- Writes without the user's explicit approval for the exact content. Publishing
  and messaging are supported — see "Writes" — but nothing visible to others goes
  out on your own judgement, and nothing here does bulk or automated outreach.
- Anything without a logged-in session: Xianyu gates search and detail behind
  login, and anonymous requests get a login wall instead of data.

## Handling the cookies

Required: **`unb`** and **`_m_h5_tk`**. Missing either means every request is
treated as signed-out. Useful extras: `cookie2`, `_tb_token_`, `sgcookie`, `cna`.

**Security:** a cookie file is a live account session. Keep it out of version
control, out of chat logs, and out of the conversation; `chmod 600` it and put it
somewhere short-lived if the user did not say otherwise. Afterwards, tell the user
they can revoke it from the Xianyu app ("log out of all devices").

## Pitfalls

- **`baxia` in the page source is not a risk-control hit** — it is Alibaba's
  anti-bot JS library and appears on every page. Real markers:
  `哎哟喂`, `RGV587`, `FAIL_SYS_USER_VALIDATE`, `/punish`, or visible page text
  like 验证码 / 安全验证 / 异常访问 / 请先登录.
- **Field paths are nested deeper than expected.** Item data lives under
  `data.itemDO` (title, soldPrice in yuan, desc, itemStatus, `skuList[].price` in
  fen), the seller under `data.sellerDO.nick`. `data.trackParams` carries only
  `itemId` — reading `trackParams.title` yields nulls.
- **Search selectors are internal class names** (`row1-wrap-title`,
  `row2-wrap-cpv`, `price-wrap`) and drift between releases. When a search returns
  zero cards, check the page text for a login wall or a verification page before
  blaming the selectors.
- **Search pages by clicking the right arrow, not by changing the query
  parameter** — the page owns its pagination. Scrolling and re-extracting is the
  release-stable approach.
- **Rate and risk limits:** the IM-token endpoint
  (`mtop.taobao.idlemessage.pc.login.token`) is the most heavily guarded; the
  upstream project's own notes say frequent calls trigger `RGV587`. Read-type item
  and search calls are far more forgiving, but keep everything human-paced.
- **Writes are where accounts get limited or banned.** They are supported here,
  but only under the approval/pacing/read-back rules above. The IM token endpoint
  (`mtop.taobao.idlemessage.pc.login.token`) is the single most guarded call in the
  API surface — fetch it once and cache it rather than per message.

## Files

- `templates/mtop_request.py` — copy, adapt, run: signs an mtop request and can
  send it.
- `references/mtop-apis.md` — verified endpoints, payloads, response fields,
  error codes, and account-risk notes.
- `references/browser-search.md` — the search extractor and the browser steps, as
  text, for whichever browser tool you have.
- `references/write-operations.md` — publish / delete / message recipes, the
  WebSocket sequence, and the rules that govern them.
- `references/browser-tool-setup.md` — how to stand up a browser tool when the
  environment has none.
- `templates/mtop_request.py`, `templates/publish_item.py`,
  `templates/im_send_message.py` — copy, adapt, run.

API names, request shapes, and the search extractor were cross-checked against the
upstream project
[`fancyboi999/goofish-cli`](https://github.com/fancyboi999/goofish-cli) (Apache-2.0);
this skill does not depend on it at runtime.
