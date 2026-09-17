#!/usr/bin/env python3
"""Convert a FunASR transcription JSON to an SRT subtitle file (stdlib only, no project venv).

Usage:
  python convert_srt.py <input.json> [-o output.srt] [options]

Input is the output of funasr-nano / funasr-fast: a segments[] array whose entries carry
start/end (milliseconds) and text. Output is standard SRT (UTF-8).

Options:
  -o, --output <path>   output SRT path (default: same directory and stem as the input JSON)
  --max-duration <sec>  split entries longer than this many seconds on terminal punctuation (default 8)
  --max-chars <n>       split entries longer than this many characters (default 50)
  --no-split            disable long-segment splitting (one entry per transcription segment)
  --speaker-prefix      prefix every entry with [SPK{n}] when the JSON has speaker fields
  --bom                 write UTF-8 with BOM (for legacy Windows players)
  --min-duration <ms>   drop segments shorter than this (default 0 = keep everything)

Splitting: the ASR model may merge several sentences into one long segment (up to 15-20s).
Over-long segments are split at full stops / question marks / exclamation marks / semicolons,
with time distributed by character count and the last piece aligned to the original end time.
Those split timestamps are estimates: drag the entries in the NLE to fine-tune.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Terminal punctuation: the sub-sentence split boundaries (the punctuation itself is kept).
# These are the characters the source text uses verbatim, so the regex stays as it is.
SPLIT_RE = re.compile(r"(?<=[。！？!?；;…])")


def fmt_ts(ms: int) -> str:
    """Milliseconds -> SRT timestamp HH:MM:SS,mmm."""
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, msec = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{msec:03d}"


def split_sentence(text: str) -> list[str]:
    """Split into sub-sentences at terminal punctuation, keeping it; return the line as-is if none."""
    parts = [p.strip() for p in SPLIT_RE.split(text)]
    return [p for p in parts if p]


def chunk_segment(text: str, start_ms: int, end_ms: int,
                  max_duration: float, max_chars: int) -> list[tuple[str, int, int]]:
    """Return [(sub_sentence, start, end)]. Short segments pass through; long ones share time by char count."""
    dur = end_ms - start_ms
    if dur <= max_duration * 1000 and len(text) <= max_chars:
        return [(text, start_ms, end_ms)]
    parts = split_sentence(text)
    if len(parts) <= 1:
        return [(text, start_ms, end_ms)]
    total = sum(len(p) for p in parts)
    cur = start_ms
    out = []
    for p in parts:
        nxt = cur + dur * len(p) / total
        out.append((p, round(cur), round(nxt)))
        cur = nxt
    # Align the last piece with the original segment end to avoid floating-point drift
    out[-1] = (out[-1][0], out[-1][1], end_ms)
    return out


def load_segments(json_path: Path) -> list[dict]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segs = []
    for s in data.get("segments", []):
        text = (s.get("text") or "").strip()
        start = s.get("start")
        end = s.get("end")
        if not text or start is None or end is None:
            continue
        segs.append({"start": int(start), "end": int(end),
                     "text": text, "speaker": s.get("speaker")})
    segs.sort(key=lambda s: s["start"])
    return segs


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert a FunASR transcription JSON to SRT subtitles")
    ap.add_argument("input", help="FunASR transcription JSON file")
    ap.add_argument("-o", "--output", help="output SRT path (default: same directory and stem as the input)")
    ap.add_argument("--max-duration", type=float, default=8.0,
                    help="max seconds per subtitle entry; longer entries are split (default 8)")
    ap.add_argument("--max-chars", type=int, default=50,
                    help="max characters per subtitle entry; longer entries are split (default 50)")
    ap.add_argument("--no-split", action="store_true", help="disable long-segment splitting")
    ap.add_argument("--speaker-prefix", action="store_true",
                    help="prefix every entry with a [SPK{n}] speaker tag")
    ap.add_argument("--bom", action="store_true", help="write UTF-8 with BOM")
    ap.add_argument("--min-duration", type=int, default=0,
                    help="drop segments shorter than this many milliseconds (default 0)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 1
    dst = Path(args.output) if args.output else src.with_suffix(".srt")

    segs = load_segments(src)
    if not segs:
        print(f"error: no valid segments in the JSON: {src}", file=sys.stderr)
        return 1

    lines: list[str] = []
    idx = 1
    for s in segs:
        if s["end"] - s["start"] < args.min_duration:
            continue
        chunks = [(s["text"], s["start"], s["end"])]
        if not args.no_split:
            chunks = chunk_segment(s["text"], s["start"], s["end"],
                                   args.max_duration, args.max_chars)
        for text, st, en in chunks:
            if en <= st:
                en = st + 500  # fallback: keep the duration positive
            prefix = ""
            if args.speaker_prefix and s.get("speaker") is not None:
                prefix = f"[SPK{s['speaker']}] "
            lines.append(f"{idx}\n{fmt_ts(st)} --> {fmt_ts(en)}\n{prefix}{text}\n")
            idx += 1

    encoding = "utf-8-sig" if args.bom else "utf-8"
    dst.write_text("\n".join(lines) + "\n", encoding=encoding)
    print(f"SRT written: {dst}")
    print(f"segments: {len(segs)} -> subtitle entries: {idx - 1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
