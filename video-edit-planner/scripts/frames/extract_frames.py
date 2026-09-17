#!/usr/bin/env python3
"""Extract clips and frames from a video for visual analysis.

This script wraps ffmpeg to:
1. Extract a time range as a clip (keyframe-accurate, -c copy).
2. Extract frames from that clip (scene detection + uniform sampling).

It is designed to be called by the agent, not directly by the user.
The agent decides parameters based on clip length, content type, and user needs.

Usage:
    # Extract a clip
    python extract_frames.py clip --video VIDEO --start 60 --end 90 --output clip.mkv

    # Extract frames from a clip (or full video)
    python extract_frames.py frames --input clip.mkv --output-dir frames/ \
        --width 1280 --threshold 0.3 --fps 0.5 --quality 3

Hardware acceleration is passed straight through to ffmpeg (--hwaccel cuda|vaapi|qsv|none).
Which method a machine supports is the agent's call, not this script's: read
`ffmpeg -hwaccels` (or ffmpeg's own error output) and pick accordingly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def cmd_clip(args: argparse.Namespace) -> None:
    """Extract a clip using -c copy (keyframe-accurate)."""
    video = Path(args.video).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    if not video.exists():
        sys.exit(f"Video not found: {video}")

    # Build stream mapping: video-only for frame extraction, or all streams for editor use
    if args.all_streams:
        stream_map = ["-map", "0"]  # all streams (video + all audio + subtitles)
    else:
        stream_map = ["-map", "0:v:0"]  # video only (faster, smaller for frame extraction)

    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-ss", str(args.start),
        "-to", str(args.end),
        "-i", str(video),
        "-c", "copy",
        *stream_map,
        str(output),
    ]

    try:
        run_command(cmd)
        print(json.dumps({
            "status": "ok",
            "clip_path": str(output),
            "start": args.start,
            "end": args.end,
            "duration": args.end - args.start,
        }))
    except subprocess.CalledProcessError as e:
        print(json.dumps({"status": "error", "stderr": e.stderr}))
        sys.exit(1)


def cmd_frames(args: argparse.Namespace) -> None:
    """Extract frames from a video/clip with scene detection + uniform sampling."""
    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        sys.exit(f"Input not found: {input_path}")

    # Build the scale filter
    scale_filter = f"scale={args.width}:-2"

    # Build the select filter: scene change OR uniform sampling
    # fps filter handles uniform sampling; select filter handles scene detection
    # We use fps for uniform sampling and select for scene changes, combined
    select_filter = f"select='gt(scene\\,{args.threshold})'"
    vf_parts = [scale_filter]

    if args.fps > 0:
        # fps filter for uniform sampling
        vf_parts.append(f"fps={args.fps}")

    # Add scene detection select filter
    vf_parts.append(select_filter)

    # Add showinfo for scene score logging
    if args.showinfo:
        vf_parts.append("showinfo")

    vf = ",".join(vf_parts)

    # Build command
    cmd = ["ffmpeg", "-hide_banner", "-y"]

    # Hardware acceleration
    # Pass the requested method through unchanged: which one this machine supports is
    # the caller's decision (ffmpeg -hwaccels), not something this script should guess.
    if args.hwaccel and args.hwaccel != "none":
        cmd.extend(["-hwaccel", args.hwaccel])

    cmd.extend(["-i", str(input_path)])
    cmd.extend(["-vf", vf])
    cmd.extend(["-vsync", "vfr"])
    cmd.extend(["-q:v", str(args.quality)])

    frame_pattern = str(output_dir / "frame_%04d.jpg")
    cmd.append(frame_pattern)

    # Capture showinfo log
    if args.showinfo:
        log_file = output_dir / "showinfo.log"
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            log_file.write_text(result.stderr)
            if result.returncode != 0:
                print(json.dumps({"status": "error", "stderr": result.stderr[-2000:]}))
                sys.exit(1)
        except Exception as e:
            print(json.dumps({"status": "error", "error": str(e)}))
            sys.exit(1)
    else:
        try:
            run_command(cmd)
        except subprocess.CalledProcessError as e:
            print(json.dumps({"status": "error", "stderr": e.stderr[-2000:] if e.stderr else ""}))
            sys.exit(1)

    # Count extracted frames
    frame_files = sorted(output_dir.glob("frame_*.jpg"))
    print(json.dumps({
        "status": "ok",
        "frames_dir": str(output_dir),
        "frame_count": len(frame_files),
        "width": args.width,
        "threshold": args.threshold,
        "fps": args.fps,
        "quality": args.quality,
    }))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract clips and frames for video edit planning.")
    sub = parser.add_subparsers(dest="command", required=True)

    # clip
    p_clip = sub.add_parser("clip", help="Extract a time range as a clip")
    p_clip.add_argument("--video", required=True, help="Source video path")
    p_clip.add_argument("--start", required=True, type=float, help="Start time in seconds")
    p_clip.add_argument("--end", required=True, type=float, help="End time in seconds")
    p_clip.add_argument("--output", required=True, help="Output clip path")
    p_clip.add_argument("--all-streams", action="store_true", default=False,
                        help="Preserve all streams (video + all audio tracks + subtitles). Default: video only (for frame extraction)")

    # frames
    p_frames = sub.add_parser("frames", help="Extract frames from a video/clip")
    p_frames.add_argument("--input", required=True, help="Input video/clip path")
    p_frames.add_argument("--output-dir", required=True, help="Output directory for frames")
    p_frames.add_argument("--width", type=int, default=1280, help="Output width in pixels (height auto-scaled)")
    p_frames.add_argument("--threshold", type=float, default=0.3, help="Scene change threshold (0-1)")
    p_frames.add_argument("--fps", type=float, default=0.5, help="Uniform sampling fps (0 = scene-only)")
    p_frames.add_argument("--quality", type=int, default=3, help="JPEG quality (2-31, lower=better)")
    p_frames.add_argument("--hwaccel", default="cuda",
                        help="Hardware acceleration passed to ffmpeg (cuda/vaapi/qsv/none); use none where no usable one exists")
    p_frames.add_argument("--showinfo", action="store_true", default=True, help="Log scene scores to showinfo.log")

    args = parser.parse_args()

    commands = {
        "clip": cmd_clip,
        "frames": cmd_frames,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()