# Xianyu mtop APIs — verified reference

Verified against live responses with a logged-in session (2026-09). Xianyu ships
no API documentation; everything here was read off the wire. Names and bodies can
change without notice — when a call starts failing, re-derive from the web app's
own network tab before assuming the session is dead.

## Request shape

```
POST https://h5api.m.goofish.com/h5/{api}/{version}/
  ?jsv=2.7.2
  &appKey=34839810
  &t=<ms timestamp>
  &sign=<md5>
  &v={version}
  &type=originaljson
  &accountSite=xianyu
  &dataType=json
  &timeout=20000
  &api={api}
  &sessionOption=AutoLoginOnly
  &spm_cnt=<page token, e.g. a21ybx.item.0.0>
Body (form-encoded): data={"compact":"json"}
```

`sign = md5(token & t & 34839810 & data)` where `token` is the `_m_h5_tk` cookie
up to the first `_`.

## How to send it — in the page, not from the host

Sign on the host (that is pure arithmetic), then run the request **inside the
browser**, in a page you already have open on `www.goofish.com`. Verified form:

```js
async (url, body) => {
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',                                  // sends the page's cookies
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,                                                    // "data=" + encodeURIComponent(json)
  });
  return await res.json();                                   // { api, v, ret, data }
}
```

Call it with the signed URL and `data=<urlencoded compact JSON>`.

**Do not issue this from the agent's host** (`curl`, `requests`, `urllib`). Same
session, same signed call, measured 2026-09:

| Issued from | Result |
|---|---|
| host HTTP client | 11 calls fine → `FAIL_SYS_USER_VALIDATE` + `RGV587_ERROR::SM::哎哟喂,被挤爆啦` at call 12 |
| `fetch()` in the open page | 12 / 12 `SUCCESS::调用成功` |

The endpoint accepts a host-side request — that is what makes this expensive to
learn: it works, then a dozen calls later risk control lands, and it reads like a
broken session. The in-page call carries the browser's fingerprint and
same-origin context instead.

### Finding the token to sign with

A jar can hold **two different `_m_h5_tk` values that both go to
`h5api.m.goofish.com`** — the site sets them on `.goofish.com` and on
`.taobao.com`. Only one is the live signing token; the other yields
`FAIL_SYS_ILLEGAL_ACCESS::非法请求`.

So read the token from the browser's own jar for the API host — the cookies the
browser will actually attach — rather than from a hand-assembled string. In a
browser tool, that is its cookie API scoped to the API URL, e.g.
`context.cookies('https://h5api.m.goofish.com/')`, then take `_m_h5_tk` and keep
the part before the first `_`. If a call returns `ILLEGAL_ACCESS`, try the other
`_m_h5_tk` before concluding anything about the session: it is a token mismatch,
**not** risk control.

On a token-expired `ret`, the response already carries a fresh `_m_h5_tk` in
`Set-Cookie`: update the jar and retry **once**. That is the only retry policy
worth having — a loop turns a risk-control warning into a block.

Response envelope:

```json
{"api": "...", "v": "...", "ret": ["SUCCESS::调用成功"], "data": { ... }}
```

`ret[0]` carries the verdict. Worth branching on:

| `ret[0]` contains | Meaning |
|---|---|
| `SUCCESS` | ok |
| `FAIL_SYS_TOKEN_EXOIRED` / `FAIL_SYS_SESSION_EXPIRED` | stale `_m_h5_tk` / session cookie — the server also sends a fresh one via `Set-Cookie`; re-read the jar and retry once |
| `FAIL_SYS_USER_VALIDATE`, `RGV587_ERROR`, `/punish` in the body, `哎哟喂` | risk control. Back off; retrying immediately makes it worse |
| `FAIL_SYS_ILLEGAL_ACCESS` | **signing/token mismatch, not risk control.** The jar can hold two `_m_h5_tk` values for the API host and only one signs correctly — re-sign with the other before blaming the session. Refreshing cookies does not fix a wrong-token sign |

Note that `FAIL_SYS_TOKEN_EXOIRED` is the server's own spelling of "expired".

## Verified endpoints

| api | version | request `data` | notes |
|---|---|---|---|
| `mtop.taobao.idle.pc.detail` | 1.0 | `{"itemId":"<id>"}` | Item detail. `spm_cnt=a21ybx.item.0.0` |
| `mtop.idle.web.xyh.item.list` | 1.0 | `{"needGroupInfo":true,"pageNumber":1,"userId":"<unb>","pageSize":30}` | Seller's own listings. `userId` is the `unb` cookie. Doubles as a session probe (`pageSize:1`) |
| `mtop.taobao.idle.kgraph.property.recommend` | 1.0 | `{"title":"<draft title>","lockCpv":false,"multiSKU":false,"publishScene":"mainPublish"}` | Category/attribute suggestions for the publish form |
| `mtop.taobao.idlemessage.pc.session.sync` | 3.0 | `{"fetchNum":20}` | IM chat/session list. `spm_cnt=a21ybx.im.0.0` |
| `mtop.taobao.idlemessage.pc.loginuser.get` | 1.0 | `{}` | IM-side user info |
| `mtop.taobao.idlemessage.pc.login.token` | 1.0 | app/device scoped (see upstream) | WebSocket access token for the IM long connection. **Most risk-guarded call of the set** |
| `mtop.taobao.idle.local.poi.get` | 1.0 | location scoped | Local POI lookup |
| `mtop.idle.pc.idleitem.publish` | 1.0 | the ~20-field payload assembled in `templates/publish_item.py` | **Write.** Listing creation; returns `data.itemId` |
| `com.taobao.idle.item.delete` | 1.1 | `{"itemId":"<id>"}` | **Write.** Takes a listing down |
| `mtop.taobao.idle.kgraph.property.recommend` | 2.0 | `{"title":…,"lockCpv":false,"multiSKU":false,"publishScene":"mainPublish","scene":"newPublishChoice","description":…,"imageInfos":[…],"uniqueCode":…}` | Category prediction for the publish form; result at `data.categoryPredictResult` |
| `mtop.taobao.idle.local.poi.get` | 1.0 | `{"longitude":…,"latitude":…}` | Posting location; result at `data.commonAddresses[]` / `data.selectedPoi` |

Image upload for listings is **not** mtop: `POST
https://stream-upload.goofish.com/api/upload.api?floderId=0&appkey=xy_chat&_input_charset=utf-8`
with a multipart `file` field, cookies attached, no signature. Returns
`object.url` / `object.pix` ("1024x1024") / `object.size`.

The write recipes — the call order, the approval/pacing rules and the WebSocket
message path — are in `references/write-operations.md`.

## Field paths for item detail

The useful data is under `data.itemDO`, **not** `data.trackParams` (which only
carries `itemId`) — a distinction that silently yields nulls in code that reads
`trackParams.title`.

| What | Path | Unit |
|---|---|---|
| title | `data.itemDO.title` | |
| current price | `data.itemDO.soldPrice` | yuan (string) |
| description | `data.itemDO.desc` | |
| status | `data.itemDO.itemStatus` | 0 = on sale |
| SKU prices | `data.itemDO.skuList[].price` | **fen** (2800 = ¥28) |
| SKU stock | `data.itemDO.skuList[].quantity` | |
| seller nickname | `data.sellerDO.nick` | |
| seller's other items | `data.sellerDO.sellerItems[]` | |
| "wanted" count | `data.b2cItemDO.wantBuyCount` | |

Other top-level `data` keys seen in a detail response (mostly UI config, safe to
ignore): `b2cBuyerDO`, `picDetailDO`, `brokerDO`, `logisticsDO`, `buyerDO`,
`commerceDO`, `interactDO`, `uiTemplateDO`, `seafoodDO`, `charityLuxuryDO`.

## Search (browser path)

Search is deliberately not an mtop call. The web app renders
`https://www.goofish.com/search?q=<urlencoded>` and the cards are read from the
DOM. Selectors in use (internal class names — expect drift):

```
card:      a[href*="/item?id="]
title:     [class*="row1-wrap-title"], [class*="main-title"]
attrs:     [class*="row2-wrap-cpv"] span[class*="cpv--"]
price:     [class*="price-wrap"] [class*="number"] + [class*="decimal"]
seller:    [class*="row4-wrap-seller"] [class*="seller-text"]
```

Item ids come out of the card href (`/item?id=<digits>`); dedupe on them.
More results load on scroll, not on a `page=` query parameter.

## IM messages are not plain JSON

Chat *sessions* come back as JSON, but message *bodies* travel as protobuf over a
WebSocket (`wss://wss-goofish.dingtalk.com/`, the DingTalk-based push gateway the
web client itself uses). Decoding message content requires a protobuf schema;
this skill stops at the session list by design.

## Provenance

API names, request shapes, and the search-page DOM selectors were derived from
and verified against the upstream project
[`fancyboi999/goofish-cli`](https://github.com/fancyboi999/goofish-cli)
(Apache-2.0) — reading its source plus live probing. The bundled script here is a
from-scratch reimplementation with no runtime dependency on that project.

## Account-risk notes

- **The transport is the first-order risk factor, not the call rate.** The same
  signed read call that survives 12/12 in-page got `RGV587` at call 12 from a
  host HTTP client (measured 2026-09). Fix the transport before tuning pacing.
- Read-only item/search calls have been stable under human-paced use **from the
  page**.
- Publish / send-message / delete are the sensitive surface. The upstream
  `goofish-cli` project ships a rate limiter (1 write/minute by default) and a
  circuit breaker that voluntarily pauses 10 minutes when it sees risk-control
  keywords — treat that as the floor for pacing, not a target.
- A limited or banned account is the cost of over-automation. Keep write actions
  manual and human-triggered.

## Verification status (2026-09)

Checked live against a real logged-in account from an agent browser tool:

| Path | Status |
|---|---|
| search + pagination via rendered DOM | working — 30 cards/page, 40+ pages walked, zero risk-control hits |
| item detail via in-page `fetch()` | working — `data.itemDO.title` / `soldPrice` / `browseCnt` read back |
| own listings (`mtop.idle.web.xyh.item.list`) via in-page `fetch()` | working — `data.cardList[]` returned |
| the same calls from a host HTTP client | **degrades to `RGV587` under burst** — do not use |
| IM endpoints (`…loginuser.get`, `…session.sync`) via in-page `fetch()` | returned `FAIL_SYS_SESSION_EXPIRED` when probed; **not exercised successfully** — treat as unverified |
| publish / delete / WebSocket messaging | transcribed from upstream, not run against a live account |
