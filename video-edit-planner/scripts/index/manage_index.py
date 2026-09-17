#!/usr/bin/env python3
"""Manage the video-edit-planner JSON index.

The index file lives next to the video as <video_stem>.vedit.json.
It tracks transcriptions, clips, and frames to avoid duplicate processing.
All file paths are stored as relative paths (relative to the video directory)
so that moving the entire directory does not break references.

Usage:
    python manage_index.py init --video VIDEO_PATH
    python manage_index.py add-transcription --json-path PATH --track-index N --duration S
    python manage_index.py get-transcription
    python manage_index.py add-clip --start S --end E --path PATH --reason "..."
    python manage_index.py add-frames --clip-id N --frames-dir DIR --method scene
    python manage_index.py list
    python manage_index.py check-range --start S --end E
    python manage_index.py clean
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def index_path_for_video(video_path: Path) -> Path:
    """Return the index file path for a given video file."""
    return video_path.parent / f"{video_path.stem}.vedit.json"


def to_rel(path: str | Path, video_dir: Path) -> str:
    """Convert an absolute path to a path relative to the video directory."""
    p = Path(path).expanduser().resolve()
    try:
        return str(p.relative_to(video_dir))
    except ValueError:
        # Path is outside the video directory; store as absolute
        return str(p)


def to_abs(rel_path: str, video_dir: Path) -> Path:
    """Resolve a stored path (relative or absolute) to an absolute path."""
    p = Path(rel_path)
    if p.is_absolute():
        return p
    return (video_dir / p).resolve()


def load_index(video_path: Path) -> dict[str, Any]:
    """Load the index file. Returns the full index dict."""
    idx_path = index_path_for_video(video_path)
    if not idx_path.exists():
        sys.exit(f"Index not found: {idx_path}. Run 'init' first.")
    return json.loads(idx_path.read_text(encoding="utf-8"))


def save_index(video_path: Path, data: dict[str, Any]) -> None:
    """Write the index file."""
    idx_path = index_path_for_video(video_path)
    idx_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def next_id(items: list[dict[str, Any]]) -> int:
    """Get the next ID for a list of records."""
    if not items:
        return 1
    return max(r["id"] for r in items) + 1


def cmd_init(args: argparse.Namespace) -> None:
    video = Path(args.video).expanduser().resolve()
    idx_path = index_path_for_video(video)
    if idx_path.exists():
        print(json.dumps({"status": "ok", "index_path": str(idx_path), "message": "already exists"}))
        return
    data = {"transcriptions": [], "clips": [], "frames": []}
    save_index(video, data)
    print(json.dumps({"status": "ok", "index_path": str(idx_path)}))


def cmd_add_transcription(args: argparse.Namespace) -> None:
    video = Path(args.video).expanduser().resolve()
    data = load_index(video)
    new_id = next_id(data["transcriptions"])
    record = {
        "id": new_id,
        "json_path": to_rel(args.json_path, video.parent),
        "track_index": args.track_index,
        "created_at": time.time(),
        "duration_s": args.duration,
    }
    data["transcriptions"].append(record)
    save_index(video, data)
    print(json.dumps({"status": "ok", "id": new_id}))


def cmd_get_transcription(args: argparse.Namespace) -> None:
    video = Path(args.video).expanduser().resolve()
    data = load_index(video)
    records = data["transcriptions"]
    if args.track is not None:
        records = [r for r in records if r["track_index"] == args.track]
    records.sort(key=lambda r: r["created_at"], reverse=True)
    if not records:
        print(json.dumps({"found": False}))
        return
    print(json.dumps({"found": True, "records": records}, ensure_ascii=False))


def cmd_add_clip(args: argparse.Namespace) -> None:
    video = Path(args.video).expanduser().resolve()
    data = load_index(video)
    new_id = next_id(data["clips"])
    record = {
        "id": new_id,
        "start_time": args.start,
        "end_time": args.end,
        "path": to_rel(args.path, video.parent),
        "created_at": time.time(),
        "reason": args.reason,
    }
    data["clips"].append(record)
    save_index(video, data)
    print(json.dumps({"status": "ok", "clip_id": new_id}))


def cmd_add_frames(args: argparse.Namespace) -> None:
    """Add frame records for all images in a directory, associating with a clip."""
    video = Path(args.video).expanduser().resolve()
    frames_dir = Path(args.frames_dir).expanduser().resolve()
    if not frames_dir.is_dir():
        sys.exit(f"Frames directory not found: {frames_dir}")

    data = load_index(video)

    # Read scene scores from showinfo log if available
    scene_scores: dict[str, float] = {}
    log_file = frames_dir / "showinfo.log"
    if log_file.exists():
        for line in log_file.read_text(errors="replace").splitlines():
            score = None
            t = None
            for part in line.split():
                if part.startswith("score:"):
                    score = float(part.split(":")[1])
                elif part.startswith("pts_time:"):
                    t = float(part.split(":")[1])
            if score is not None and t is not None:
                scene_scores[f"{t:.3f}"] = score

    fps = args.fps if args.fps else 0.5
    start_offset = args.start if args.start else 0.0

    frame_files = sorted(frames_dir.glob("frame_*.jpg"))
    if not frame_files:
        frame_files = sorted(frames_dir.glob("frame_*.png"))

    if not frame_files:
        sys.exit(f"No frame files found in {frames_dir}")

    new_id = next_id(data["frames"])
    count = 0
    for i, frame_path in enumerate(frame_files):
        timestamp = start_offset + (i / fps)
        scene_score = scene_scores.get(f"{timestamp:.3f}")

        record = {
            "id": new_id + count,
            "clip_id": args.clip_id,
            "timestamp": timestamp,
            "path": to_rel(frame_path, video.parent),
            "scene_score": scene_score,
            "method": args.method,
            "created_at": time.time(),
        }
        data["frames"].append(record)
        count += 1

    save_index(video, data)
    print(json.dumps({"status": "ok", "frames_added": count}))


def cmd_list(args: argparse.Namespace) -> None:
    video = Path(args.video).expanduser().resolve()
    data = load_index(video)

    result = {
        "transcriptions": sorted(data["transcriptions"], key=lambda r: r["created_at"], reverse=True),
        "clips": [],
    }
    clips = sorted(data["clips"], key=lambda r: r["start_time"])
    for clip in clips:
        clip_dict = dict(clip)
        frames = [f for f in data["frames"] if f["clip_id"] == clip["id"]]
        frames.sort(key=lambda f: f["timestamp"])
        clip_dict["frames"] = frames
        result["clips"].append(clip_dict)

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_check_range(args: argparse.Namespace) -> None:
    """Check if a time range overlaps with any existing clips."""
    video = Path(args.video).expanduser().resolve()
    data = load_index(video)
    # Find clips that overlap with the requested range
    overlapping = [
        c for c in data["clips"]
        if c["start_time"] < args.end and c["end_time"] > args.start
    ]
    overlapping.sort(key=lambda c: c["start_time"])
    if not overlapping:
        print(json.dumps({"found": False}))
    else:
        print(json.dumps({"found": True, "clips": overlapping}, ensure_ascii=False))


def cmd_clean(args: argparse.Namespace) -> None:
    """Remove frame and clip records for files that no longer exist on disk."""
    video = Path(args.video).expanduser().resolve()
    data = load_index(video)
    video_dir = video.parent

    # Check frames
    frames_removed = 0
    remaining_frames = []
    for f in data["frames"]:
        if to_abs(f["path"], video_dir).exists():
            remaining_frames.append(f)
        else:
            frames_removed += 1
    data["frames"] = remaining_frames

    # Check clips
    clips_removed = 0
    remaining_clip_ids = set()
    remaining_clips = []
    for c in data["clips"]:
        if to_abs(c["path"], video_dir).exists():
            remaining_clips.append(c)
            remaining_clip_ids.add(c["id"])
        else:
            clips_removed += 1
    data["clips"] = remaining_clips

    # Remove frames whose clip was removed
    data["frames"] = [f for f in data["frames"] if f["clip_id"] in remaining_clip_ids]

    save_index(video, data)
    print(json.dumps({
        "status": "ok",
        "frames_removed": frames_removed,
        "clips_removed": clips_removed,
    }))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage video-edit-planner index file.")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize index file")
    p_init.add_argument("--video", required=True, help="Path to the video file")

    # add-transcription
    p_at = sub.add_parser("add-transcription", help="Add a transcription record")
    p_at.add_argument("--video", required=True)
    p_at.add_argument("--json-path", required=True)
    p_at.add_argument("--track-index", required=True, type=int)
    p_at.add_argument("--duration", type=float, default=None)

    # get-transcription
    p_gt = sub.add_parser("get-transcription", help="Get transcription records (all or by track)")
    p_gt.add_argument("--video", required=True)
    p_gt.add_argument("--track", type=int, default=None, help="Filter by track index (omit to get all)")

    # add-clip
    p_ac = sub.add_parser("add-clip", help="Add a clip record")
    p_ac.add_argument("--video", required=True)
    p_ac.add_argument("--start", required=True, type=float, help="Start time in seconds")
    p_ac.add_argument("--end", required=True, type=float, help="End time in seconds")
    p_ac.add_argument("--path", required=True, help="Path to the clip file")
    p_ac.add_argument("--reason", default=None)

    # add-frames
    p_af = sub.add_parser("add-frames", help="Add frame records from a directory")
    p_af.add_argument("--video", required=True)
    p_af.add_argument("--clip-id", required=True, type=int)
    p_af.add_argument("--frames-dir", required=True)
    p_af.add_argument("--method", required=True, choices=["scene", "sample", "both"])
    p_af.add_argument("--fps", type=float, default=0.5, help="Sampling fps for timestamp estimation")
    p_af.add_argument("--start", type=float, default=0.0, help="Start offset in seconds")

    # list
    p_list = sub.add_parser("list", help="List all records")
    p_list.add_argument("--video", required=True)

    # check-range
    p_cr = sub.add_parser("check-range", help="Check if a time range has existing clips")
    p_cr.add_argument("--video", required=True)
    p_cr.add_argument("--start", required=True, type=float)
    p_cr.add_argument("--end", required=True, type=float)

    # clean
    p_clean = sub.add_parser("clean", help="Remove records for files that no longer exist")
    p_clean.add_argument("--video", required=True)

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "add-transcription": cmd_add_transcription,
        "get-transcription": cmd_get_transcription,
        "add-clip": cmd_add_clip,
        "add-frames": cmd_add_frames,
        "list": cmd_list,
        "check-range": cmd_check_range,
        "clean": cmd_clean,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()