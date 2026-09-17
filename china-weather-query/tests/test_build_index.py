#!/usr/bin/env python3
"""Failure-path tests for build_index.py, using a stubbed upstream (no network)."""
import importlib.util, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "build_index", os.path.join(os.path.dirname(HERE), "scripts", "build_index.py"))
bi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bi)

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


print("== normalise: ordering and de-duplication ==")
by_prov = {
    "ABJ": [{"code": "c2", "city": "朝阳", "province": "北京市", "url": "/p/x.html"},
            {"code": "c1", "city": "北京", "province": "北京市", "url": "/p/bj.html"}],
    "AGD": [{"code": "a1", "city": "中山", "province": "广东省", "url": "/p/zs.html"},
            {"code": "a2", "city": "中山", "province": "广东省", "url": "/p/zs.html"},
            {"code": "a3", "city": "深圳", "province": "广东省", "url": "/p/sz.html"}],
}
bi.canonical_station = lambda group: sorted(group, key=lambda c: c["code"])[0]
stations, dups = bi.normalise(["ABJ", "AGD"], by_prov)
check("province order preserved", [s["city"] for s in stations][:2] == ["北京", "朝阳"],
      [s["city"] for s in stations])
abj = [s["city"] for s in stations if s["province"] == "北京市"]
agd = [s["city"] for s in stations if s["province"] == "广东省"]
check("cities sorted within each province", abj == sorted(abj) and agd == sorted(agd),
      (abj, agd))
check("duplicate collapsed to one row", len([s for s in stations if s["city"] == "中山"]) == 1)
check("duplicate reported", len(dups) == 1 and dups[0][0] == ("广东省", "中山"), dups)
check("url stripped from output", all("url" not in s for s in stations))
check("station count", len(stations) == 4, len(stations))

print("\n== normalise: idempotent ordering ==")
s2, _ = bi.normalise(["ABJ", "AGD"], by_prov)
check("same input -> same order", [s["city"] for s in s2] == [s["city"] for s in stations])

print("\n== validate ==")
check("clean list passes", bi.validate(stations) == [])
check("empty list rejected", bi.validate([]) != [])
check("missing code rejected",
      bi.validate([{"code": "", "city": "x", "province": "y"}]) != [])
dupname = [{"code": "a", "city": "中山", "province": "广东省"},
           {"code": "b", "city": "中山", "province": "广东省"}]
check("duplicate name rejected", bi.validate(dupname) != [])
dupcode = [{"code": "a", "city": "深圳", "province": "广东省"},
           {"code": "a", "city": "珠海", "province": "广东省"}]
check("reused code rejected", bi.validate(dupcode) != [])

print("\n== diff_stations ==")
old = [{"code": "x1", "city": "北京", "province": "北京市"},
       {"code": "x2", "city": "gone", "province": "北京市"}]
new = [{"code": "x1", "city": "北京", "province": "北京市"},
       {"code": "x9", "city": "fresh", "province": "北京市"},
       {"code": "x3", "city": "gone", "province": "北京市"}]
added, removed, changed = bi.diff_stations(old, new)
check("added detected", added == [("北京市", "fresh")], added)
check("removed detected", removed == [], removed)
check("code change detected", changed == [(("北京市", "gone"), "x2", "x3")], changed)

print("\n== render / write round-trip ==")
tmp = tempfile.mktemp(suffix=".json")
size, lines = bi.write_index(tmp, stations)
check("write reports size and lines", size > 0 and lines == len(stations) + 2, (size, lines))
with open(tmp, encoding="utf-8") as fh:
    back = json.load(fh)
check("read back parses", back == stations)
raw = open(tmp, encoding="utf-8").read()
check("one station per line", raw.count("\n") == len(stations) + 2, raw.count("\n"))
check("indices not comma-joined", "},{" not in raw)
os.unlink(tmp)

print("\n== partial-write refusal ==")
tmp2 = tempfile.mktemp(suffix=".json")
open(tmp2, "w").write("SENTINEL")
PROVS = [{"code": "ABJ", "name": "北京市"}, {"code": "AGD", "name": "广东省"}]
GOOD = [{"code": "s1", "city": "北京", "province": "北京市", "url": "/p/bj.html"}]


def boom(path, **k):
    raise bi.BuildError("simulated network failure")


def stub_fetch(path, **k):
    if path == "/province/all":
        return PROVS
    if path == "/province/ABJ":
        return GOOD
    raise bi.BuildError("simulated network failure")


bi.fetch = stub_fetch
rc = bi.main(["--output", tmp2])
check("refuses partial index (exit 1)", rc == 1, f"rc={rc}")
check("existing file left untouched", open(tmp2).read() == "SENTINEL",
      open(tmp2).read()[:40])

rc = bi.main(["--output", tmp2, "--allow-partial"])
check("--allow-partial writes the reachable province (exit 0)", rc == 0, f"rc={rc}")
written = json.load(open(tmp2, encoding="utf-8"))
check("partial file holds the reachable station", [s["city"] for s in written] == ["北京"], written)

# An empty result must never be written, even with --allow-partial.
bi.fetch = lambda path, **k: (PROVS if path == "/province/all" else boom(path))
rc = bi.main(["--output", tmp2, "--allow-partial"])
check("empty index still rejected (exit 2)", rc == 2, f"rc={rc}")
check("file preserved on rejection", json.load(open(tmp2, encoding="utf-8")) == written)
os.unlink(tmp2)

print(f"\n== {passed} passed, {failed} failed ==")
sys.exit(1 if failed else 0)
