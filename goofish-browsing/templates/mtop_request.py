#!/usr/bin/env python3
"""TEMPLATE — copy this file next to your work, adapt the EDIT lines, then run it.

It signs one mtop call for Goofish/Xianyu and (optionally) sends it. This is a
starting point, not an interface: read it, change what your environment needs,
run it. Nothing here needs third-party packages.

Three things are environment-specific, marked with `# EDIT`:

  1. COOKIES — where the user's session is. A raw "k=v; k=v" string, or a file
     holding one (raw, a JSON list from DevTools/Cookie-Editor, or a flat dict).
  2. API / DATA — which endpoint and payload. See references/mtop-apis.md.
  3. SEND — whether to fire the request from here. If this machine cannot send
     HTTP, leave it False and paste the printed request into a fetch() inside a
     page you already have open on www.goofish.com.

Two functions at the bottom are the whole algorithm; keep them if you rewrite
the rest:
    h5_token(jar)                 -> the part of _m_h5_tk before the first "_"
    sign(token, t_ms, data)       -> md5(token & t & appKey & data)

Usage after adapting:  python3 mtop_request.py
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

# ---------------------------------------------------------------- EDIT 1: cookies
COOKIES = ""            # raw string, or a path to a file holding one
# e.g. COOKIES = "unb=2207410505407; _m_h5_tk=ffae47a5..._1789637526019"
# or   COOKIES = "/tmp/xianyu-cookies.txt"

# ------------------------------------------------------------- EDIT 2: the call
API = "mtop.taobao.idle.pc.detail"
DATA: dict | str = {"itemId": "1059363804910"}
VERSION = "1.0"
SPM = "a21ybx.item.0.0"        # page token; see references/mtop-apis.md
APP_KEY = "34839810"           # Xianyu web appKey — a protocol constant
MTOP_HOST = "https://h5api.m.goofish.com"

# ------------------------------------------------------------- EDIT 3: sending
SEND = False                   # True -> POST it here; False -> just print it
HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.goofish.com",
    "referer": "https://www.goofish.com/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}


# ------------------------------------------------------------------- the maths
def h5_token(jar: dict[str, str]) -> str:
    """Everything before the first '_' in _m_h5_tk (the cookie is <token>_<ts>).

    The server rotates it via Set-Cookie on most responses: re-read it from the
    live jar every call rather than caching it anywhere.
    """
    return (jar.get("_m_h5_tk") or "").split("_")[0]


def sign(token: str, t_ms: str, data: str, app_key: str = APP_KEY) -> str:
    """md5(token & t & appKey & data) — the entire signing algorithm."""
    return hashlib.md5(f"{token}&{t_ms}&{app_key}&{data}".encode()).hexdigest()


# ------------------------------------------------------------------ plumbing
def load_cookies(source: str) -> dict[str, str]:
    """Raw string, or a file holding a raw string / JSON list / flat JSON dict."""
    text = source.strip()
    p = Path(text).expanduser()
    if text and "\n" not in text and "=" not in text and p.is_file():
        text = p.read_text(encoding="utf-8").strip()
    if text.startswith("[") or text.startswith("{"):
        data = json.loads(text)
        if isinstance(data, list):
            return {c["name"]: c["value"] for c in data
                    if isinstance(c, dict) and "name" in c and "value" in c}
        return {str(k): str(v) for k, v in data.items()}
    jar: dict[str, str] = {}
    for part in re.split(r"[;\n]", text):
        if "=" in part:
            k, v = part.split("=", 1)
            jar[k.strip()] = v.strip()
    return jar


def build(jar: dict[str, str], api: str, data, version: str, spm: str) -> dict:
    """The signed request: URL, query params, form body, headers."""
    from urllib.parse import urlencode
    payload = (data if isinstance(data, str)
               else json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    token = h5_token(jar)
    t_ms = str(int(time.time() * 1000))
    query = {
        "jsv": "2.7.2", "appKey": APP_KEY, "t": t_ms,
        "sign": sign(token, t_ms, payload),
        "v": version, "type": "originaljson", "accountSite": "xianyu",
        "dataType": "json", "timeout": "20000", "api": api,
        "sessionOption": "AutoLoginOnly", "spm_cnt": spm,
    }
    return {
        "url": f"{MTOP_HOST}/h5/{api}/{version}/",
        "query_string": urlencode(query),
        "body": f"data={urlencode({'data': payload})[5:]}",
        "headers": dict(HEADERS),
        "t": t_ms, "token": token,
    }


def send(req: dict) -> str:
    """POST it from here. Swap in whatever this machine actually has."""
    import urllib.request
    body = req["body"].encode()
    http = urllib.request.Request(f"{req['url']}?{req['query_string']}",
                                  data=body, headers=req["headers"], method="POST")
    with urllib.request.urlopen(http, timeout=30) as r:
        return f"HTTP {r.status}\n" + r.read().decode("utf-8", "replace")[:2000]


if __name__ == "__main__":
    jar = load_cookies(COOKIES)
    if not h5_token(jar):
        print("! _m_h5_tk missing — this request will be treated as signed-out.")
    req = build(jar, API, DATA, VERSION, SPM)
    print(json.dumps({k: req[k] for k in ("url", "query_string", "body", "headers")},
                     ensure_ascii=False, indent=2))
    if SEND:
        out = send(req)
        print("\n--- response ---\n" + out)
        # A rotated _m_h5_tk arrives in Set-Cookie on the way back; if the ret says
        # the token expired, update the jar and retry ONCE. Do not loop.
