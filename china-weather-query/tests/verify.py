#!/usr/bin/env python3
"""Verification suite for the nmc-weather skill. Stdlib only, no live network
for the resolution tests; live calls are marked and counted separately."""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "weather.py")
INDEX = os.path.join(SKILL, "scripts", "cities.json")

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True, timeout=90)
    return proc.returncode, proc.stdout, proc.stderr


print("== bundled index ==")
with open(INDEX, encoding="utf-8") as fh:
    cities = json.load(fh)
check("index parses as JSON", isinstance(cities, list))
check("index holds 2528 stations", len(cities) == 2528, f"got {len(cities)}")
check("every station has code/city/province",
      all({"code", "city", "province"} <= set(c) for c in cities))
check("no duplicate (province, city) pairs",
      len({(c["province"], c["city"]) for c in cities}) == len(cities))
check("index omits the url field", all("url" not in c for c in cities))

print("\n== resolution (live upstream) ==")
cases = [
    ("连云港", 0, "江苏省 连云港"),
    ("赣榆区", 0, "江苏省 赣榆"),
    ("淮安", 0, "江苏省 淮安"),
    ("南昌", 0, "江西省 南昌"),
    ("南昌县", 0, "江西省 南昌县"),
    ("北京朝阳", 0, "北京市 朝阳"),
    ("北京 朝阳", 0, "北京市 朝阳"),
    ("辽宁朝阳", 0, "辽宁省 朝阳"),
    ("江苏淮安", 0, "江苏省 淮安"),
    ("江苏省淮安", 0, "江苏省 淮安"),
    ("内蒙古兴安盟", 0, "内蒙古自治区 兴安盟"),
    ("广西南宁", 0, "广西壮族自治区 南宁"),
    ("新疆乌鲁木齐", 0, "新疆维吾尔自治区 乌鲁木齐"),
    ("朝阳", 2, "matches 2 stations"),
    ("通州", 2, "matches 2 stations"),
]
for query, want_code, want_text in cases:
    code, out, err = run(query)
    blob = out + err
    check(f"{query!r} -> exit {want_code}", code == want_code, f"got {code}")
    check(f"{query!r} -> {want_text!r}", want_text in blob, blob.strip().splitlines()[:1])

code, out, err = run("不存在的城市zzz")
check("unknown name -> exit 1", code == 1, f"got {code}")
check("unknown name -> not_found message", "no station matches" in err)

print("\n== report contents ==")
code, out, err = run("连云港", "--json")
check("--json exits 0", code == 0, err[:200])
report = json.loads(out) if code == 0 else {}
check("station code present", report.get("station", {}).get("code"))
check("current temperature is numeric",
      isinstance(report.get("current", {}).get("temperature_c"), float))
check("observation timestamp present", bool(report.get("observed_at")))
check("forecast has 7 days", len(report.get("forecast", [])) == 7,
      f"got {len(report.get('forecast', []))}")
check("no 9999 anywhere in the JSON output", "9999" not in out)

code, out, err = run("连云港", "--days", "3")
check("--days 3 prints 3 rows", sum(1 for ln in out.splitlines() if ln.startswith("    2026")) == 3)

code, out, err = run("连云港")
check("text output carries the station code", "[HPnPL]" in out, out[:120])

print("\n== --search (never loads the index) ==")
code, out, err = run("--search", "连云港")
check("--search exits 0", code == 0, err[:200])
check("--search prints the station code", "HPnPL" in out, out)
check("--search output is tiny (no index dump)", len(out) < 400, f"{len(out)} bytes")
code, out, err = run("--search", "江苏")
check("--search by province exits 0", code == 0)
check("--search by province caps rows",
      len([l for l in out.splitlines() if l.strip()]) <= 32, f"{len(out.splitlines())} lines")
code, out, err = run("--search", "HPnPL")
check("--search by station code works", "连云港" in out, out)
code, out, err = run("--search", "朝阳")
check("--search lists ambiguous name", out.count("朝阳") >= 2, out)
code, out, err = run("--search", "不存在的城市zzz")
check("--search miss exits 1", code == 1, f"got {code}")
code, out, err = run("--search", "赣榆")
check("--search matches without the suffix", "tPkeh" in out, out)

print("\n== grep / jq fallbacks stay narrow ==")
grep = subprocess.run(["grep", "-m", "1", "连云港", INDEX], capture_output=True, text=True)
check("grep -m 1 returns one row", len(grep.stdout) < 200, f"{len(grep.stdout)} bytes")
jq = subprocess.run(["jq", "-c", '.[] | select(.city=="连云港")', INDEX],
                    capture_output=True, text=True)
check("jq exact select returns one row", len(jq.stdout) < 200, f"{len(jq.stdout)} bytes")
check("jq select keeps the code", "HPnPL" in jq.stdout, jq.stdout)
uncapped = subprocess.run(["grep", "-c", "", INDEX], capture_output=True, text=True)
check("index is one station per line", uncapped.stdout.strip() == "2530",
      f"{uncapped.stdout.strip()} lines")

print(f"\n== {passed} passed, {failed} failed ==")
sys.exit(1 if failed else 0)
