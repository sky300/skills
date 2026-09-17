#!/usr/bin/env python3
"""Weather lookup backed by the China Meteorological Administration's public
nmc.cn JSON endpoints (observation + forecast + air quality + warnings).

Data source: https://www.nmc.cn (public endpoints, no key, no registration).
Precision ceiling: county/district level. There is no town/street coverage.

Usage:
    python3 weather.py <city>                 # resolve + print current & forecast
    python3 weather.py <city> --days 3        # limit forecast length
    python3 weather.py <city> --json          # machine-readable output
    python3 weather.py --list-provinces       # print province codes

Rebuilding scripts/cities.json is scripts/build_index.py's job, not this
script's: a rebuild is 35 network requests, so README.md and SKILL.md both
require the user's consent before it runs.

City argument may be province-qualified when a name is ambiguous:
    python3 weather.py "朝阳"          -> ambiguous
    python3 weather.py "北京 朝阳"     -> resolved
    python3 weather.py "广东 深圳"     -> resolved

Exit codes: 0 success, 1 city not found, 2 ambiguous (caller must ask the user),
3 upstream/network failure or a missing station index.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

BASE = "https://www.nmc.cn/rest"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MISSING = "9999"  # upstream sentinel for unavailable values
DEFAULT_DAYS = 7

# Trailing administrative suffixes stripped before comparing names, so that
# "兰考" and "兰考县" both resolve, and "南昌" vs "南昌县" stay distinct.
SUFFIXES = "市县区旗盟"

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(HERE, "cities.json")


class UpstreamError(Exception):
    """nmc.cn unreachable or returned an unusable body."""


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


def fetch(path, attempts=3):
    """GET a REST path and return parsed JSON, retrying transient failures.

    A single dropped connection must not be reported as "city not found", so
    province sweeps and one-off lookups share this retry path.
    """
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(BASE + path, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise UpstreamError(f"GET {path} failed after {attempts} attempts: {last}")


def load_index():
    """Return the bundled station index.

    The index is built by scripts/build_index.py and committed, so a normal
    lookup never touches the network. If it is missing, that is a setup problem
    worth naming rather than papering over with an unannounced 35-request sweep.
    """
    if not os.path.exists(INDEX_PATH):
        raise UpstreamError(
            f"station index missing: {INDEX_PATH}\n"
            "Rebuild it with: python3 scripts/build_index.py"
        )
    with open(INDEX_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# City resolution
# --------------------------------------------------------------------------


def base_name(name):
    return re.sub(rf"[{SUFFIXES}]+$", "", name.strip())


def province_forms(name):
    """All short forms of a province name: 江苏省->江苏, 广西壮族自治区->广西."""
    forms = {name}
    for suffix in ("省", "市", "特别行政区", "自治区"):
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            forms.add(stem)
            # Autonomous regions carry an ethnic adjective: 广西壮族->广西.
            trimmed = re.sub(r"(壮族|回族|维吾尔)$", "", stem)
            if trimmed:
                forms.add(trimmed)
    return forms


def province_prefixes(cities):
    """Every province name and its short forms, longest first.

    Used to strip a leading province from a run-together query in one pass
    instead of guessing split points.
    """
    forms = set()
    for name in {c["province"] for c in cities}:
        forms |= province_forms(name)
    return sorted(forms, key=len, reverse=True)


def match_city(query, cities):
    """Exact name first, then suffix-insensitive ("大兴区" -> "大兴")."""
    query = query.strip()
    if not query:
        return []
    exact = [c for c in cities if c["city"] == query]
    if exact:
        return exact
    base = base_name(query)
    return [c for c in cities if base_name(c["city"]) == base]


def resolve(query, cities):
    """Return (entry, error). error is None, "not_found", or a candidate list.

    Two forms are accepted:
      - a city name: "上海", "大兴区"
      - province + city, joined or space-separated: "北京朝阳", "北京 朝阳"
    """
    query = query.strip()
    direct = match_city(query, cities)
    if len(direct) == 1:
        return direct[0], None

    for prefix in province_prefixes(cities):
        rest = ""
        if query.startswith(prefix):
            rest = query[len(prefix):]
        elif f" {prefix}" in query or f"{prefix} " in query:
            rest = query.replace(prefix, "", 1)
        rest = rest.strip()
        if not rest:
            continue
        scoped = [c for c in cities if c["province"].startswith(prefix) or prefix.startswith(c["province"])]
        found = match_city(rest, scoped or cities)
        if len(found) == 1:
            return found[0], None

    if not direct:
        return None, "not_found"
    return None, direct


# --------------------------------------------------------------------------
# Value formatting
# --------------------------------------------------------------------------


def clean(value):
    """Map upstream sentinels and empties to None."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", MISSING):
        return None
    if isinstance(value, float) and value == float(MISSING):
        return None
    if isinstance(value, str) and value.strip() == "-":
        return None
    return value


def to_number(value):
    """Parse a possibly-missing upstream value into a float, or None.

    Reports keep numbers as numbers so that --json output can be consumed
    without re-parsing; formatting happens at render time.
    """
    v = clean(value)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f == float(MISSING) else f


def fmt(value, digits=1):
    """Render a numeric value for display, trimming a trailing .0."""
    if value is None:
        return None
    f = float(value)
    return f"{f:.0f}" if f == int(f) else f"{f:.{digits}f}"


def dash(value):
    v = clean(value)
    return v if v is not None else "--"


def collect(entry):
    """Fetch and normalise one station's report."""
    body = fetch(f"/weather?stationid={entry['code']}")
    data = body.get("data")
    if not data:
        raise UpstreamError(f"no data for station {entry['code']}")

    real = data.get("real") or {}
    wx = real.get("weather") or {}
    wind = real.get("wind") or {}
    warn = real.get("warn") or {}
    sun = real.get("sunriseSunset") or {}
    predict = data.get("predict") or {}
    air = data.get("air") or {}

    days = []
    for item in predict.get("detail") or []:
        day = item.get("day") or {}
        night = item.get("night") or {}
        days.append(
            {
                "date": item.get("date"),
                "day_weather": clean((day.get("weather") or {}).get("info")),
                "day_temp": to_number((day.get("weather") or {}).get("temperature")),
                "day_wind": clean((day.get("wind") or {}).get("direct")),
                "day_power": clean((day.get("wind") or {}).get("power")),
                "night_weather": clean((night.get("weather") or {}).get("info")),
                "night_temp": to_number((night.get("weather") or {}).get("temperature")),
                "night_wind": clean((night.get("wind") or {}).get("direct")),
                "night_power": clean((night.get("wind") or {}).get("power")),
                "precipitation": to_number(item.get("precipitation")),
            }
        )

    alert = None
    if clean(warn.get("alert")):
        alert = {
            "signal_type": clean(warn.get("signaltype")),
            "signal_level": clean(warn.get("signallevel")),
            "issued": clean(warn.get("issuetime")),
            "text": clean(warn.get("issuecontent")) or clean(warn.get("alert")),
            "guidance": clean(warn.get("fmeans")),
        }

    aqi = air.get("aqi")
    air_quality = None
    if isinstance(aqi, (int, float)) and aqi != int(MISSING):
        air_quality = {
            "aqi": int(aqi),
            "level": clean(air.get("text")),
            "updated": clean(air.get("forecasttime")),
        }

    return {
        "station": {
            "code": entry["code"],
            "city": real.get("station", {}).get("city") or entry["city"],
            "province": real.get("station", {}).get("province") or entry["province"],
        },
        "observed_at": clean(real.get("publish_time")),
        "forecast_issued_at": clean(predict.get("publish_time")),
        "current": {
            "weather": clean(wx.get("info")),
            "temperature_c": to_number(wx.get("temperature")),
            "feels_like_c": to_number(wx.get("feelst")),
            "humidity_pct": to_number(wx.get("humidity")),
            "precipitation_mm": to_number(wx.get("rain")),
            "wind_direction": clean(wind.get("direct")),
            "wind_power": clean(wind.get("power")),
            "wind_speed_ms": to_number(wind.get("speed")),
            "sunrise": clean(sun.get("sunrise")),
            "sunset": clean(sun.get("sunset")),
        },
        "forecast": days,
        "alert": alert,
        "air_quality": air_quality,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render(report, days=DEFAULT_DAYS):
    st, cur = report["station"], report["current"]
    out = [f"{st['province']} {st['city']} [{st['code']}]"]

    observed = report["observed_at"] or "time unknown"
    head = "  ".join(
        p
        for p in (
            dash(cur["weather"]),
            f"{fmt(cur['temperature_c'])}°C" if cur["temperature_c"] is not None else None,
            f"feels {fmt(cur['feels_like_c'])}°C" if cur["feels_like_c"] is not None else None,
        )
        if p
    )
    out.append(f"  Now ({observed}): {head}")
    bits = []
    if cur["humidity_pct"] is not None:
        bits.append(f"humidity {fmt(cur['humidity_pct'])}%")
    if cur["precipitation_mm"]:
        bits.append(f"rain {fmt(cur['precipitation_mm'])} mm")
    wind = " ".join(p for p in (dash(cur["wind_direction"]), dash(cur["wind_power"])) if p != "--")
    if wind:
        bits.append(f"wind {wind}")
    if cur["sunrise"] and cur["sunset"]:
        bits.append(f"sun {cur['sunrise'][-5:]}–{cur['sunset'][-5:]}")
    if bits:
        out.append("       " + ", ".join(bits))

    alert = report["alert"]
    if alert:
        label = " ".join(p for p in (alert["signal_type"], alert["signal_level"]) if p)
        out.append(f"  WARNING {label}: {alert['text']}")
        if alert["guidance"]:
            out.append(f"          {alert['guidance']}")

    out.append(f"  Forecast (issued {report['forecast_issued_at'] or 'unknown'}):")
    for day in report["forecast"][:days]:
        left = " ".join(
            p
            for p in (
                dash(day["day_weather"]),
                f"{fmt(day['day_temp'])}°C" if day["day_temp"] is not None else None,
            )
            if p
        )
        right = " ".join(
            p
            for p in (
                dash(day["night_weather"]),
                f"{fmt(day['night_temp'])}°C" if day["night_temp"] is not None else None,
            )
            if p
        )
        line = f"    {day['date']}: day {left or '--'} / night {right or '--'}"
        if day["precipitation"]:
            line += f"  ({fmt(day['precipitation'])} mm)"
        out.append(line)

    air = report["air_quality"]
    if air:
        out.append(f"  Air quality: AQI {air['aqi']} {dash(air['level'])} (updated {air['updated'] or 'unknown'})")
    return "\n".join(out)


def search_stations(keyword, cities, limit=30):
    """Substring search over city, province, and station code.

    Exists so an agent never has to load the index into context: the caller
    runs this and reads back only the matching rows.
    """
    needle = keyword.strip()
    if not needle:
        return []
    hits = []
    for c in cities:
        haystack = (c["city"], c["province"], c["code"], base_name(c["city"]))
        if any(needle in field for field in haystack):
            hits.append(c)
    # Exact name first, then shorter names, so the obvious answer leads.
    hits.sort(key=lambda c: (c["city"] != needle, len(c["city"]), c["province"]))
    return hits[:limit]


def format_search(hits, total):
    """Compact rows: code, city, province — one per line."""
    lines = [f"{'CODE':<8}{'CITY':<12}PROVINCE"]
    for c in hits:
        lines.append(f"{c['code']:<8}{c['city']:<12}{c['province']}")
    if total > len(hits):
        lines.append(f"... {total - len(hits)} more match(es); narrow the keyword")
    return "\n".join(lines)


def render_ambiguity(query, candidates):
    lines = [f'"{query}" matches {len(candidates)} stations — ask the user which one:']

    def label(c):
        return f"{c['province']} / {c['city']}"

    seen = defaultdict(list)
    for c in candidates:
        seen[label(c)].append(c)
    for i, (name, group) in enumerate(seen.items(), 1):
        lines.append(f"  {i}. {name}")
    lines.append("")
    lines.append("Re-run with a province hint, e.g. \"<province> <city>\" or \"<province><city>\".")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="nmc.cn weather lookup")
    parser.add_argument("city", nargs="?", help="city or district name (Chinese); optional province hint")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"forecast days to print (default {DEFAULT_DAYS})")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of formatted text")
    parser.add_argument("--search", metavar="KEYWORD", help="find station codes without querying the weather")
    parser.add_argument("--limit", type=int, default=30, help="max rows for --search (default 30)")
    parser.add_argument("--list-provinces", action="store_true", help="print province codes and exit")
    args = parser.parse_args(argv)

    try:
        if args.list_provinces:
            for prov in fetch("/province/all"):
                print(f"{prov['code']}  {prov['name']}")
            return 0

        cities = load_index()

        if args.search:
            hits = search_stations(args.search, cities, limit=max(1, args.limit))
            if not hits:
                print(f"no station matches {args.search!r}", file=sys.stderr)
                return 1
            total = len(search_stations(args.search, cities, limit=len(cities)))
            print(format_search(hits, total))
            return 0

        if not args.city:
            parser.error("city is required (or use --search KEYWORD)")

        entry, err = resolve(args.city, cities)
        if err == "not_found":
            print(f"no station matches {args.city!r}", file=sys.stderr)
            return 1
        if err:
            print(render_ambiguity(args.city, err), file=sys.stderr)
            return 2

        report = collect(entry)
    except UpstreamError as exc:
        print(f"upstream failure: {exc}", file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report, days=max(0, args.days)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
