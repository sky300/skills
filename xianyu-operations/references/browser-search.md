# Searching Xianyu through a browser tool

Keyword search is the one job that cannot be done over mtop: the search page is
client-rendered, and Xianyu itself treats the browser path as the more robust
one. Everything here is text and one JS snippet — there is no script for it,
because *which* browser you drive, and how you inject cookies into it, depends on
your environment.

## Preconditions

1. A browser tool you can drive — your own agent browser tool (any implementation
   with cookie injection: cloak, Playwright MCP, browser-use, a CDP-attached
   Chromium), or Playwright in the local environment. If neither exists, ask the
   user and follow `browser-tool-setup.md`.
2. Cookie injection into that browser: a storage-state/session file, a
   cookie-setting tool, CDP `Network.setCookie`, or a profile the user already
   logged into. You need `unb` and `_m_h5_tk` at minimum, but injecting the whole
   Xianyu jar is closer to a real browser.
3. Confirm the session by looking: open `https://www.goofish.com` first. The
   account's nickname in the header means logged in; a login wall means the
   cookies are dead and there is no point searching yet.

## Steps

1. Navigate to `https://www.goofish.com/search?q=<urlencoded keyword>`.
2. Wait for the item cards to render, then scroll a few times to trigger lazy
   loading (the page paginates with a right-arrow control, not a query
   parameter — clicking it or scrolling both work, re-extracting is what keeps it
   stable).
3. Evaluate the extractor below and read back the `items` array.
4. For more results, repeat scroll + evaluate and dedupe by `id`.
5. Check `body` / `risk_markers` before trusting an empty result: if they show a
   login wall or verification text, the session or the browser is the problem,
   not the selectors.

## Extractor

Written as a `browser_evaluate` payload. Keep the JSON escaping in mind: `\s`
inside a JSON string value must stay `\s`; real newlines and tabs get decoded
before the JS sees them and will break the regex.

```js
() => {
    const clean = (v) => (v || '').replace(/\s+/g, ' ').trim();
    const sel = {
        card: 'a[href*="/item?id="]',
        title: '[class*="row1-wrap-title"], [class*="main-title"]',
        attrs: '[class*="row2-wrap-cpv"] span[class*="cpv--"]',
        priceWrap: '[class*="price-wrap"]',
        priceNum: '[class*="number"]',
        priceDec: '[class*="decimal"]',
        sellerWrap: '[class*="row4-wrap-seller"]',
        sellerText: '[class*="seller-text"]',
    };
    const out = [], seen = {};
    document.querySelectorAll(sel.card).forEach((card) => {
        const href = card.href || card.getAttribute('href') || '';
        const m = href.match(/[?&]id=(\d+)/);
        if (!m || seen[m[1]]) return;
        seen[m[1]] = 1;
        const pw = card.querySelector(sel.priceWrap);
        const price = pw ? clean((pw.querySelector(sel.priceNum) || {}).textContent)
            + clean((pw.querySelector(sel.priceDec) || {}).textContent) : '';
        const sw = card.querySelector(sel.sellerWrap);
        out.push({
            id: m[1],
            url: 'https://www.goofish.com/item?id=' + m[1],
            title: clean((card.querySelector(sel.title) || {}).textContent),
            price: price,
            attrs: Array.from(card.querySelectorAll(sel.attrs))
                .map((e) => clean(e.textContent)).filter(Boolean),
            seller: sw ? clean((sw.querySelector(sel.sellerText) || {}).textContent) : '',
        });
    });
    return {
        items: out,
        url: location.href,
        title: document.title,
        risk_markers: (document.body.innerText || '').match(
            /哎哟喂|RGV587|FAIL_SYS_USER_VALIDATE|\/punish|验证码|安全验证|异常访问|请先登录/g) || [],
        body: (document.body.innerText || '').slice(0, 400),
    };
}
```

Returns `items[]` with `id`, `url`, `title`, `price`, `attrs`, `seller`, plus the
page `url`/`title`, a `risk_markers` array, and the first 400 characters of the
page text for diagnosis.

## Notes

- The selectors are internal class names and drift between releases. If a search
  returns zero cards *and* the page text looks normal, the selectors are the
  suspect — dump the DOM and re-derive rather than guessing at other causes.
- The risk-control alternation above is verbatim site text; it has to stay in
  Chinese to match.
- Item ids from the search cards feed straight into the mtop detail call
  (`references/mtop-apis.md`), which needs no browser at all.
