# China Weather Query

[English](./README.md) | [简体中文](./README.zh-CN.md)

Weather lookup for Chinese cities from the China Meteorological Administration's
public `nmc.cn` data: current observation, 7-day forecast, official warnings, and
air quality. No API key, no registration, reachable from mainland China.

**Repository**: https://git.nite07.com/nite/skills (subdirectory: `china-weather-query/`)

## Features

- **Observation-grade current conditions** — temperature, apparent temperature,
  humidity, precipitation, wind direction and force, sunrise/sunset
- **7-day forecast** — day and night conditions with temperatures and expected
  precipitation totals
- **Official warnings** — hazard type, severity colour, full statement text, and
  the CMA's guidance for the public
- **Air quality** — AQI value and band, where the station reports one
- **Bundled station index** — 2528 stations, no network sweep on a normal lookup
- **Name resolution** — suffix-insensitive (`大兴区` = `大兴`), with province
  hints for repeated names (`北京朝阳`, `北京 朝阳`, `辽宁朝阳`)
- **Zero dependencies** — Python standard library only, no `pip install`

## Precision

Stations are **county/district level**. The index holds no township, street,
or sub-district entries anywhere in the national list, so weather at that
granularity is not available from this source.

For a coordinate-precise reading, use a gridded model API; note that those
interpolate a global model grid (typically 9–13 km over China) and their
"current" values are model output, not observations.

## Quick Start

### Prerequisites

| Dependency | Notes |
|---|---|
| `python3` | 3.8 or newer; standard library only |

### Install the skill

This skill follows the [open agent skills ecosystem](https://www.npmjs.com/package/skills)
format and can be installed directly:

```bash
# Install globally (available across all projects)
npx skills add https://git.nite07.com/nite/skills.git -g -s china-weather-query

# List available skills without installing
npx skills add https://git.nite07.com/nite/skills.git --list
```

**Manual install** (any agent, including Hermes Agent):

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/china-weather-query <your agent's skills directory>/
```

`<your agent's skills directory>` is a deliberate placeholder — where skills are
read from is the user's and the agent's decision, so this skill does not assume a
location.

### Usage

```bash
python3 scripts/weather.py "上海"             # observation + 7-day forecast
python3 scripts/weather.py "大兴区" --days 3   # shorter forecast
python3 scripts/weather.py "北京 朝阳" --json  # machine-readable
python3 scripts/weather.py --search "深圳"     # find a station code
```

To rebuild the station index, run `scripts/build_index.py` — see
[Rebuilding the index](#rebuilding-the-index) below.

### Finding a station code

`scripts/cities.json` holds 2528 stations (~150 KB) — never read it in full. Ask
the script instead; it prints only the matching rows and never touches the
network:

```bash
python3 scripts/weather.py --search "深圳"
```

```
CODE    CITY        PROVINCE
AhpEU   深圳        广东省
```

Matching is substring-based over city name, province name, and station code,
capped at 30 rows (`--limit` to change). If the script cannot answer, narrow the
file with a filter instead of reading it — the index is one station per line, so
`grep -m` or `jq -c '.[] | select(...)'` returns just the rows you asked for.
Always cap the output.

### Rebuilding the index

`scripts/build_index.py` re-pulls the national station list (35 requests) and
rewrites `cities.json`. It is **opt-in and requires the user's consent** — it is
not part of any lookup, and an agent should never run it on its own initiative:

```bash
python3 scripts/build_index.py --dry-run   # pull and report changes, write nothing
python3 scripts/build_index.py             # rebuild in place
```

The build is all-or-nothing (a failed province would leave stations silently
missing, so nothing is written unless all 34 arrive), prints what changed, and
collapses the upstream's duplicate names. `--dry-run` first.

### Example output

```
广东省 深圳 [AhpEU]
  Now (2026-09-16 21:40): 多云  26.8°C  feels 30.6°C
       humidity 76%, wind 东南风 微风, sun 06:10–18:26
  Forecast (issued 2026-09-16 20:00):
    2026-09-16: day -- / night 多云 25°C
    2026-09-17: day 多云 32°C / night 晴 25°C
    2026-09-18: day 多云 32°C / night 晴 25°C
  Air quality: AQI 42 优 (updated 2026-09-16 21:00)
```

A `--` or an omitted line means the upstream value was the `9999` sentinel;
these are dropped rather than rendered.

### City names and repeated names

Names resolve without the administrative suffix — `大兴区` and `大兴` both work,
`南昌` and `南昌县` stay distinct.

When a name exists in more than one province, the script exits `2` and lists the
candidates rather than guessing:

```
$ python3 scripts/weather.py "朝阳"
"朝阳" matches 2 stations — ask the user which one:
  1. 北京市 / 朝阳
  2. 辽宁省 / 朝阳
```

Re-run with a province prefix, joined or space-separated:

```bash
python3 scripts/weather.py "北京朝阳"
python3 scripts/weather.py "北京 朝阳"
```

Exit codes: `0` success · `1` no station matched · `2` ambiguous · `3` upstream
unreachable or the station index is missing.

## Project Structure

```
china-weather-query/
├── SKILL.md                  # Skill definition: workflow, pitfalls, verification
├── README.md                 # This file (English, canonical)
├── README.zh-CN.md           # Simplified Chinese translation
├── scripts/
│   ├── weather.py            # Lookup, resolution, and rendering
│   ├── build_index.py        # Rebuild cities.json from upstream (opt-in)
│   └── cities.json           # Bundled station index (2528 stations)
├── tests/
│   └── test_build_index.py   # Build, validation, and diff logic (no network)
└── references/
    └── nmc-api.md            # Endpoint documentation and measured field details
```

## Data Source

Data comes from the public JSON endpoints under `https://www.nmc.cn/rest/`, the
same ones backing the CMA's forecast website. The endpoints are undocumented and
carry no published rate limit. Copyright in the data rests with the China
Meteorological Administration.

## License

MIT
