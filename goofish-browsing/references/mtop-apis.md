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

`templates/mtop_request.py` builds this request for you — copy it, adapt the
marked lines, run it (stdlib only; it sends nothing unless you tell it to).
Sending it is your call — `curl`, `requests`, or a `fetch()` from a page already
open on `www.goofish.com` (same cookies, same origin).

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
| `FAIL_SYS_ILLEGAL_ACCESS` | risk-control level rejection; refreshing cookies does not help |

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

- Read-only item/search calls have been stable under human-paced use.
- Publish / send-message / delete are the sensitive surface. The upstream
  `goofish-cli` project ships a rate limiter (1 write/minute by default) and a
  circuit breaker that voluntarily pauses 10 minutes when it sees risk-control
  keywords — treat that as the floor for pacing, not a target.
- A limited or banned account is the cost of over-automation. Keep write actions
  manual and human-triggered.
