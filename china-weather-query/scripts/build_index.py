#!/usr/bin/env python3
"""Rebuild the bundled station index (scripts/cities.json) from nmc.cn.

Normal lookups read the committed index, so this only runs when the CMA's
station list may have changed, or to recover a missing or damaged index.

The build is all-or-nothing. A province that fails to download means its
stations are silently absent from the result, and a short index still looks
valid, so nothing is written unless every province arrived — pass
--allow-partial to override.

Usage:
    python3 scripts/build_index.py                  rebuild, report what changed
    python3 scripts/build_index.py --dry-run        report changes, write nothing
    python3 scripts/build_index.py --allow-partial  write despite failed provinces
    python3 scripts/build_index.py --output PATH    write somewhere else

Exit codes: 0 success, 1 download failed, 2 validation failed.
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
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://www.nmc.cn/rest"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(HERE, "cities.json")
CHANGE_LIST_LIMIT = 10

# Trailing administrative suffixes. Used to group stations that differ only by
# one of these characters, so duplicates are detected before they reach the
# index. Must stay in step with weather.py's SUFFIXES.
SUFFIXES = "市县区旗盟"


class BuildError(Exception):
    """The build could not complete."""


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


def fetch(path, attempts=3, timeout=25):
    """GET a REST path and return parsed JSON, retrying transient failures.

    One dropped connection must not be mistaken for a province that no longer
    exists, so every request retries before it is allowed to fail.
    """
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(BASE + path, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise BuildError(f"GET {path} failed after {attempts} attempts: {last}")


def fetch_all_provinces(provinces, workers):
    """Fetch every province's city list, reporting per-province failures.

    Provinces are independent, so they are fetched concurrently; the result is
    still assembled in the upstream province order for a stable file layout.
    """
    results, failures = {}, []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        pending = {pool.submit(fetch, f"/province/{p['code']}"): p for p in provinces}
        for future in as_completed(pending):
            prov = pending[future]
            try:
                results[prov["code"]] = future.result()
            except BuildError as exc:
                failures.append((prov, exc))
    return results, failures


# --------------------------------------------------------------------------
# Normalise
# --------------------------------------------------------------------------


def canonical_station(group):
    """Pick one station when several share a (province, city) name.

    A handful of names map to two codes; only one of them is referenced by the
    city's own forecast page, and the other returns plausible but different
    numbers. Prefer the one the page actually renders.
    """
    page = group[0].get("url")
    if page:
        try:
            req = urllib.request.Request("https://www.nmc.cn" + page, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", "replace")
            for cand in group:
                if cand["code"] in html:
                    return cand
        except Exception:
            pass  # unreachable page is not fatal: fall through to first entry
    return group[0]


def normalise(province_order, by_province):
    """Turn the raw province payloads into the canonical station list.

    Cities are sorted within each province so that repeated builds produce
    byte-identical output whenever upstream data is unchanged — which is what
    makes the diff below meaningful.
    """
    stations, duplicates = [], []
    for code in province_order:
        rows = by_province.get(code) or []
        grouped = defaultdict(list)
        for row in rows:
            grouped[(row["province"], row["city"])].append(row)
        for key in sorted(grouped, key=lambda k: k[1]):
            group = grouped[key]
            if len(group) > 1:
                duplicates.append((key, [c["code"] for c in group]))
            chosen = canonical_station(group) if len(group) > 1 else group[0]
            stations.append(
                {
                    "code": chosen["code"],
                    "city": chosen["city"],
                    "province": chosen["province"],
                }
            )
    return stations, duplicates


# --------------------------------------------------------------------------
# Compare
# --------------------------------------------------------------------------


def load_existing(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def diff_stations(old, new):
    """Report what changed, keyed by name so a code swap reads as a change."""
    def by_name(rows):
        return {(r["province"], r["city"]): r.get("code") for r in rows}

    o, n = by_name(old), by_name(new)
    added = sorted(set(n) - set(o))
    removed = sorted(set(o) - set(n))
    changed = sorted(k for k in set(o) & set(n) if o[k] != n[k])
    return added, removed, [(k, o[k], n[k]) for k in changed]


def print_change_report(old, new, duplicates):
    added, removed, changed = diff_stations(old, new)
    print(f"stations    : {len(new)} in the new index, {len(old)} in the old one")
    for label, items in (("added", added), ("removed", removed)):
        print(f"{label:<12}: {len(items)}")
        for province, city in items[:CHANGE_LIST_LIMIT]:
            print(f"    + {province} / {city}" if label == "added"
                  else f"    - {province} / {city}")
        if len(items) > CHANGE_LIST_LIMIT:
            print(f"    ... {len(items) - CHANGE_LIST_LIMIT} more")
    print(f"{'code changed':<12}: {len(changed)}")
    for (province, city), old_code, new_code in changed[:CHANGE_LIST_LIMIT]:
        print(f"    ~ {province} / {city}: {old_code} -> {new_code}")
    if len(changed) > CHANGE_LIST_LIMIT:
        print(f"    ... {len(changed) - CHANGE_LIST_LIMIT} more")
    if duplicates:
        print(f"duplicate names collapsed: {len(duplicates)}")
        for (province, city), codes in duplicates:
            print(f"    {province} / {city}: {', '.join(codes)}")
    return added, removed, changed


# --------------------------------------------------------------------------
# Write
# --------------------------------------------------------------------------


def validate(stations):
    """Checks that must hold before anything is written. Returns problems."""
    problems = []
    if not stations:
        problems.append("no stations were produced")
    for row in stations:
        for field in ("code", "city", "province"):
            if not row.get(field):
                problems.append(f"empty {field} in {row!r}")
                break
    names = [(r["province"], r["city"]) for r in stations]
    if len(set(names)) != len(names):
        repeated = {n for n in names if names.count(n) > 1}
        problems.append(f"duplicate (province, city) after de-duplication: {sorted(repeated)[:5]}")
    codes = [r["code"] for r in stations]
    if len(set(codes)) != len(codes):
        repeated = {c for c in codes if codes.count(c) > 1}
        problems.append(f"station code reused by multiple cities: {sorted(repeated)[:5]}")
    return problems


def render_index(stations):
    """One station per line, so a line filter returns rows and not the file."""
    rows = ",\n".join("  " + json.dumps(s, ensure_ascii=False, separators=(",", ":"))
                      for s in stations)
    return "[\n" + rows + "\n]\n"


def write_index(path, stations):
    """Write atomically, then read back to prove the file is usable."""
    payload = render_index(stations)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(payload)
    os.replace(tmp, path)
    with open(path, encoding="utf-8") as fh:
        reloaded = json.load(fh)
    if len(reloaded) != len(stations):
        raise BuildError(f"wrote {len(stations)} stations but read back {len(reloaded)}")
    return len(payload.encode("utf-8")), payload.count("\n")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild the china-weather-query station index")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="target file (default scripts/cities.json)")
    parser.add_argument("--dry-run", action="store_true", help="pull and report, but write nothing")
    parser.add_argument("--allow-partial", action="store_true", help="write even if some provinces failed")
    parser.add_argument("--workers", type=int, default=5, help="parallel province downloads (default 5)")
    args = parser.parse_args(argv)

    try:
        provinces = fetch("/province/all")
        print(f"provinces   : {len(provinces)} listed")
        by_province, failures = fetch_all_provinces(provinces, args.workers)
        print(f"            : {len(by_province)}/{len(provinces)} downloaded")
    except BuildError as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 1

    if failures:
        print(f"FAILED provinces: {len(failures)}", file=sys.stderr)
        for prov, exc in failures:
            print(f"  {prov['code']} {prov['name']}: {exc}", file=sys.stderr)
        if not args.allow_partial:
            print(
                "refusing to write a partial index — its stations would be silently "
                "missing. Re-run, or pass --allow-partial if the province is really gone.",
                file=sys.stderr,
            )
            return 1
        print("--allow-partial set: continuing with an incomplete index", file=sys.stderr)

    province_order = [p["code"] for p in provinces if p["code"] in by_province]
    stations, duplicates = normalise(province_order, by_province)

    old = load_existing(args.output)
    print(f"raw entries : {sum(len(v) for v in by_province.values())}")
    print(f"indexed     : {len(stations)} stations after de-duplication")
    added, removed, changed = print_change_report(old, stations, duplicates)

    problems = validate(stations)
    if problems:
        print("validation failed:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"dry run     : nothing written to {args.output}")
        return 0

    size, lines = write_index(args.output, stations)
    verb = "unchanged" if not (added or removed or changed) else "updated"
    print(f"written     : {args.output} ({size / 1024:.0f} KB, {lines} lines) — {verb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
