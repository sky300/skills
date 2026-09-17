#!/usr/bin/env python3
"""Merge SenseVoice emotion/event labels into a Nano transcription JSON by time range.

Both JSONs come from this skill's transcription scripts and share the fsmn-vad stage,
so their segment boundaries line up. Each SenseVoice segment's emotion/events are
attached to the matching Nano segment by start timestamp (within tolerance).

Usage:
    python merge_emotion.py NANO_JSON SENSEVOICE_JSON [-o OUTPUT_JSON]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MATCH_TOLERANCE_MS = 200


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def match_segment(seg_start_ms: int, sense_segments: list[dict], used: list[bool]) -> int | None:
    """Return the index of the closest unused SenseVoice segment within tolerance, else None."""
    best: int | None = None
    best_diff = MATCH_TOLERANCE_MS + 1
    for i, s in enumerate(sense_segments):
        if used[i]:
            continue
        diff = abs(int(s.get("start", 0)) - seg_start_ms)
        if diff < best_diff:
            best_diff = diff
            best = i
    return best


def merge(nano_json: dict, sense_json: dict) -> dict:
    nano_segments = nano_json.get("segments") or []
    sense_segments = sense_json.get("segments") or []
    used = [False] * len(sense_segments)

    matched = 0
    for seg in nano_segments:
        idx = match_segment(int(seg.get("start", 0)), sense_segments, used)
        if idx is None:
            continue
        used[idx] = True
        matched += 1
        s = sense_segments[idx]
        if s.get("emotion"):
            seg["emotion"] = s["emotion"]
        if s.get("events"):
            seg["events"] = s["events"]

    merged = dict(nano_json)
    merged["emotion_source"] = {
        "model": sense_json.get("model"),
        "model_id": sense_json.get("model_id"),
        "file": sense_json.get("file"),
        "track": sense_json.get("track"),
        "matched_segments": matched,
        "total_nano_segments": len(nano_segments),
        "total_sense_segments": len(sense_segments),
    }
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="merge-emotion",
        description="Merge SenseVoice emotion/event labels into a Nano transcription JSON.",
    )
    parser.add_argument("nano_json", type=Path, help="Nano transcription JSON (accurate text)")
    parser.add_argument("sense_json", type=Path, help="SenseVoice transcription JSON (carries emotion/event labels)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output path; defaults to <nano_stem>_with_emotion.json",
    )
    args = parser.parse_args()

    nano_json = load_json(args.nano_json)
    sense_json = load_json(args.sense_json)
    merged = merge(nano_json, sense_json)

    output = args.output or args.nano_json.with_name(f"{args.nano_json.stem}_with_emotion.json")
    output.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    src = merged["emotion_source"]
    print(f"merged: {output}")
    print(
        f"matched segments: {src['matched_segments']}/{src['total_nano_segments']} "
        f"(Nano segments), SenseVoice segments: {src['total_sense_segments']}"
    )


if __name__ == "__main__":
    main()
