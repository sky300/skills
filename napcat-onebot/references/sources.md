# Sources

Where to verify anything in this skill against its authority, and in what order. Every page below was reachable on 2026-09-22; when one moves, find it from the project sites rather than trusting an old link.

## Verification order

1. **Machine-readable type definitions** — parameter names, optionality and types, straight from the implementation. Nothing else overrides this.
2. **NapCat extension API docs** — the actions NapCat adds on top of OneBot 11, with field tables and response shapes.
3. **NapCat's action list** — the one-line-per-action index, grouped by area. Fast to scan, no request/response detail.
4. **Apifox** — worked examples per action: values, sample responses. The most concrete layer, and the one that needs a browser.
5. **Upstream OneBot 11** — the envelope and the message segment model, which NapCat implements rather than defines.

If two layers disagree, the lower number wins: a type definition beats a table, a table beats an example.

## Sources

| Source | Covers | Notes |
|---|---|---|
| `NapNeko/NapCatQQ` → `packages/napcat-onebot/types/` | Action parameter and message segment schemas (TypeBox) | `message.ts` holds the segment definitions; `data.ts` and `quick.ts` hold request/response data shapes. Fetch these raw rather than reading them through a renderer. |
| <https://napneko.github.io/develop/api/doc> | NapCat's own extension actions, with field tables and response structures | The page says it only lists extensions — standard OneBot actions are documented upstream. |
| <https://napneko.github.io/onebot/api> | Full action index grouped by area (account, friend, group, message, file, AI, …) | A list, not a reference: it gives the action name, its purpose, and parameter names only. |
| <https://napneko.github.io/onebot/segment> | Message segment types, send-side and receive-side fields | The source for `message-segments.md`. |
| <https://napcat.apifox.cn> | Worked request/response examples for individual actions | A JavaScript application: a plain fetch returns nothing useful. Open it in a browser. |
| `NapNeko/NapCatDocs` → `src/onebot/`, `src/develop/`, `src/config/`, `src/guide/` | The documentation site's own markdown, plus install and configuration guides | The clean path to the three doc pages above: fetch the markdown from the repository instead of scraping the rendered site. |
| <https://github.com/botuniverse/onebot-11> | The OneBot 11 standard: request/response envelope, segment model, event model | Defines the protocol; when NapCat's docs and this disagree about the envelope, this is why. |
| <https://github.com/NapNeko/NapCat-Docker> | The container image's deployment contract: ports, volumes, environment variables, entrypoint behaviour | Read its `Dockerfile` and `entrypoint.sh` before changing how the container is run. |
| <https://docs.go-cqhttp.org/api/> | Legacy go-cqhttp API documentation | Historical only. go-cqhttp stopped at v1.2.0 in October 2023 and its own release notes point users elsewhere, but NapCat kept many go-cqhttp-compatible action names, so this is useful when a name's origin is unclear. Never treat it as current behaviour. |

## Mirrors

NapCat's documentation site is served from several hosts with the same content — `napneko.github.io`, `doc.napneko.icu`, `napneko.pages.dev`. When one is unreachable, another usually is not. The repository markdown (`NapNeko/NapCatDocs`) is the copy to prefer, since it is the source the mirrors render.

## Reporting a version

NapCat's version is readable at runtime (`get_version_info`), and the documented surface grows between releases. When a finding in this skill matters to a decision, say which NapCat version it was confirmed against instead of asserting it as permanent.
