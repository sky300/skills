---
name: china-weather-query
description: "Use when asked for weather in a Chinese city: observation, forecast, warnings, AQI."
---

# China Weather Query

Weather for Chinese cities from the China Meteorological Administration's public
`nmc.cn` endpoints: current observation, 7-day forecast, official warnings, and
air quality. No API key, no registration, reachable from mainland China.

This is **observation-grade** data for the present moment — unlike global model
APIs, the current reading comes from the station itself. The trade-off is reach:
stations are county/district level, so there is no township or street data.

## When to Use

- The user asks about weather in a Chinese city, now or in the next few days.
- Warnings matter: typhoon, heavy rain, high temperature, fog, cold wave.
- "What is it like outside right now" — the current reading is a real observation.
- Air quality is part of the question and the station reports an AQI.

**Don't use for:**

- Township, street, or sub-district detail. The station list stops at county
  level; a request for a township or sub-district name (`镇` / `街道`) will not
  resolve. Say so instead of substituting a nearby county reading as if it were
  local.
- Precise temperature at a coordinate. Use a gridded model API for that.
- International locations. This covers mainland China, Hong Kong, Macao, and
  Taiwan only.

## Prerequisites

- Python 3.8+ and the standard library. No `pip install`, no virtualenv.
- `scripts/cities.json` — the bundled station index (2528 stations). Committed
  to the repository and read locally; it is **not** fetched at runtime.
- Network access to `www.nmc.cn` for the weather lookup itself. A browser
  `User-Agent` is sent automatically.

## How to Run

```bash
python3 scripts/weather.py "上海"
python3 scripts/weather.py "大兴区" --days 3
python3 scripts/weather.py "北京 朝阳" --json
python3 scripts/weather.py --search "上海"
```

Run it through the `terminal` tool with a path to the script:

```
terminal(command="python3 <skill_dir>/scripts/weather.py '上海'")
```

`<skill_dir>` is a deliberate placeholder: it is wherever the host agent installed this skill, and only the host knows that. Substitute the real directory instead of assuming a fixed one.

## Quick Reference

| Argument | Effect |
|:---|:---|
| `"<city>"` | City or district name; a province hint may be prefixed |
| `"<province> <city>"` / `"<province><city>"` | Disambiguate a repeated name |
| `--search KEYWORD` | Find station codes without querying the weather |
| `--days N` | Print N forecast days (default 7, upstream provides exactly 7) |
| `--json` | Emit the normalised report as JSON instead of text |
| `--list-provinces` | Print the 34 province names and codes |

Exit codes: `0` success · `1` no station matched · `2` ambiguous, ask the user ·
`3` upstream unreachable, or the station index is missing.

## The Station Index

`scripts/cities.json` holds 2528 stations — one per county/district. Normal
lookups read it locally and never touch the network.

### Rebuilding it requires the user's consent

`scripts/build_index.py` makes **35 network requests** to pull the full national
city list. That is far heavier than any lookup, and it is almost never what the
user actually asked for.

**Ask the user for permission before running it, every time.** State what it
does and how heavy it is, then wait for an explicit yes. Only run it after that.

Never run it as a side effect of a failed lookup, a missing station, or your own
curiosity about whether the list changed — a name that does not resolve is a
normal answer (county-level reach), not an index problem.

```bash
python3 scripts/build_index.py --dry-run   # pull and report changes, write nothing
python3 scripts/build_index.py             # rebuild in place
```

If the user approves, prefer `--dry-run` first so the change can be reviewed
before the file is rewritten. The build is **all-or-nothing**: a province that
fails to download would leave its stations silently absent, and a short index
still looks valid, so nothing is written unless every province arrived
(`--allow-partial` overrides). It prints what changed — stations added or
removed, and any code swap. A duplicate-name collision (江苏省淮安 is listed
twice upstream) is collapsed and reported rather than passed through.

`weather.py` exits `3` with a rebuild hint if the index is absent. Report that
to the user and let them decide; do not rebuild on their behalf.

## Never Load the Index Into Context

`scripts/cities.json` holds 2528 stations (~150 KB). **Do not read it into
context — not with `read_file`, not with `search_files`, not in full.** One
lookup does not need 2528 rows, and the cost is taken out of the context window
you need for the actual answer.

Three tiers, in order. Always try the first before the second.

**1. Use the script (default).** Covers every normal case and never touches the
network:

```bash
python3 scripts/weather.py --search "深圳"       # by station name
python3 scripts/weather.py --search "广东"       # by province
python3 scripts/weather.py --search "AhpEU"     # by code
```

```
CODE    CITY        PROVINCE
AhpEU   深圳        广东省
```

Substring matching over city name, province name, and station code; capped at
30 rows (`--limit` to change).

**2. Narrow the file with a filter (only when the script cannot answer).** The
file is one station per line, so a line filter returns just the matching rows.
Always constrain the output — `head`, `-m`, `--limit` — because an unconstrained
pattern over a province or a common character still returns hundreds of lines:

```bash
grep -m 5 '广东省' cities.json              # line filter
jq -c '.[] | select(.city=="深圳")' cities.json      # exact field match
jq -r '.[] | select(.province=="广东省") | .city' cities.json | head
```

`jq` matches whole lines by object, so it never returns the file; prefer it when
you need an exact field rather than a substring.

**3. If neither works, say what you could not find.** Do not escalate to reading
the whole file — a 2528-row dump answers far less than the one row you wanted.

## Procedure

1. **Pass the city name as the user wrote it.** `"上海"`, `"大兴区"`, and
   `"南昌县"` all resolve directly; no code lookup is needed by hand.

   *Completion:* the script prints a report and exits `0`.

2. **When unsure whether a name exists, or which province it belongs to, run
   `--search` first.** Reading the index is never the cheap option.

   *Completion:* you have the candidate rows, and none of them came from loading
   a file into context.

3. **On exit `2`, ask the user — do not guess.** The script lists the candidate
   `province / city` pairs. Quote them back and let the user choose; then re-run
   with the province prefix (`"北京 朝阳"` or `"北京朝阳"`).

   *Completion:* the chosen station is named in your reply, or the user declines.

4. **On exit `1`, report the miss and offer the nearest alternative** from the
   same province — a county reading is usually the answer the user wants for a
   township, but present it as the county's weather, not as local data.

   *Completion:* the user knows the request could not be answered at the
   granularity asked.

5. **Surface warnings first when present.** A warning is the highest-value fact
   in the report; lead with it rather than appending it after the temperatures.

   *Completion:* every warning in the output appears in your reply, with its
   severity colour.

6. **Quote the observation timestamp** (`publish_time`) whenever you report the
   current reading, so the user can judge freshness.

   *Completion:* the reply contains the timestamp from the report.

7. **Prefer `--json` when the answer needs computation** — comparing days,
   picking the warmest slot, or feeding another tool. Parse it rather than
   scraping the formatted text.

   *Completion:* values are read from the parsed object, not the rendered text.

## Reading the Output

```
广东省 深圳 [AhpEU]
  Now (2026-09-16 21:40): 多云  26.8°C  feels 30.6°C
       humidity 76%, wind 东南风 微风, sun 06:10–18:26
  WARNING 暴雨 黄色: ...statement text...
          ...official guidance...
  Forecast (issued 2026-09-16 20:00):
    2026-09-16: day -- / night 多云 25°C
    2026-09-17: day 多云 32°C / night 晴 25°C
  Air quality: AQI 42 优 (updated 2026-09-16 21:00)
```

- `Now` is an observation, `Forecast` is the CMA's prediction — do not present
  one as the other.
- `--` means the upstream value was the `9999` sentinel. Omit it; never report
  "9999 degrees" or an AQI of 9999.
- The first forecast row usually shows `day --` — that period has already
  passed today. Normal, not a gap in the data.
- Air quality is missing for roughly half of stations. Silently omitting it is
  correct; do not substitute a neighbouring city's AQI.
- The `[AhpEU]` suffix is the station code, useful when the user wants to
  re-query the same station or cross-check on the website.

## Pitfalls

1. **Never read `scripts/cities.json` in full.** It holds 2528 stations (~150 KB).
   Use `--search KEYWORD`; if that cannot answer, narrow the file with `grep -m`
   or `jq` and always cap the output. A full read or an uncapped search costs a
   large slice of the context window for one row.
2. **Never run `build_index.py` without asking.** It is a 35-request sweep, not a
   lookup. Ask first, state the cost, and wait for a yes.
3. **Do not invent township-level answers.** The index has no township or
   sub-district (`镇` / `街道`) entries. Names like 景德镇, 天镇, and 武乡 that
   end in those characters are counties.
4. **`code` is not a WMO number.** A 5-digit station id returns an empty body
   with a success status — validate that `data` is non-empty, never the status.
5. **Duplicate station names exist.** 江苏省淮安 is listed twice upstream; the
   bundled index is already de-duplicated, so re-generating it matters if the
   CMA's list changes shape.
6. **The `air` block is often entirely `9999`** — common, not a fetch failure.
7. **Pressure from `real.airpressure` is usually `9999`.** The real series is in
   `passedchart[].pressure`, outside the normalised report.
8. **`climate` normals use a 1981–2010 baseline.** Context only, never a
   forecast; label it as the long-term normal if you quote it.
9. **Forecast temperature strings can be `"9999"`** even on days 2–7 (rare, but
   it happens mid-rollover). Treat as missing.
10. **Do not poll in a loop.** The service is free and undocumented; a single
    query per request is the intended pace.

## Verification

- A successful run exits `0` and prints a header line carrying a station code in
  square brackets.
- `scripts/cities.json` parses as JSON and holds 2528 station objects with
  `code`, `city`, and `province` keys. Checking this is a `jq length` away — do
  not read the file to confirm it.
- Pitfall 1 is checkable: `--search "深圳"` prints a few rows; `grep -m 1
  '深圳' cities.json` returns 59 bytes, not the file. An unconstrained
  `grep '广东省' cities.json` returns 91 lines — that is the trap.
- Pitfall 4 is checkable: `--json` on a valid station yields a non-empty
  `current` object with a numeric `temperature_c`.
- For the ambiguity path: `python3 scripts/weather.py "朝阳"` exits `2` and lists
  Beijing and Liaoning; adding the province hint exits `0`.
