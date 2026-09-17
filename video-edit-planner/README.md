# Video Edit Planner

[English](./README.md) | [简体中文](./README.zh-CN.md)

An agent skill that helps plan video edits through iterative dialogue — transcribe audio, extract key frames on demand, analyze visuals, and produce a structured edit plan.

**Repository**: https://git.nite07.com/nite/skills (subdirectory: `video-edit-planner/`)

## Features

- **Audio transcription** — bundled [funasr-script](https://github.com/modelscope/FunASR) with Fun-ASR-Nano (primary, high quality, Chinese-optimized) and SenseVoice (emotion/event labels) models
- **SRT subtitle generation** — convert transcription JSON to `.srt` with a pure-stdlib script (no venv needed): long-segment splitting on punctuation, optional speaker prefixes, UTF-8 BOM output
- **On-demand frame extraction** — ffmpeg-based clip cutting (`-c copy`) + scene-change detection + uniform sampling, with hardware acceleration (CUDA/NVDEC preferred)
- **Artifact indexing** — JSON file tracks all transcriptions, clips, and frames with relative paths to avoid duplicate processing across sessions
- **Vision analysis guidance** — binary-search-style frame sampling strategy; works with any vision-capable model the agent's runtime provides
- **Iterative edit plans** — Markdown-table output (timecodes, segment descriptions, actions, transitions, notes) refined through follow-up questions
- **Dual-mode editing** — subtractive (delete boring parts) for long-form targets, additive (highlight extraction) for Shorts/highlight reels; hybrid supported
- **Agent-agnostic** — no platform-specific tool names; works with any agent framework (Hermes, Claude Code, Codex, etc.)

## Quick Start

### Prerequisites

| Dependency | Install |
|---|---|
| `ffmpeg` + `ffprobe` | Linux: `pacman -S ffmpeg` / `apt install ffmpeg`; macOS: `brew install ffmpeg`; Windows: `winget install Gyan.FFmpeg` |
| `uv` | Linux: `pacman -S uv`; macOS: `brew install uv`; Windows: `winget install astral-sh.uv`; fallback: `pip install uv` |
| `python3` / Python 3.12 | Linux: `pacman -S python`; macOS: `brew install python@3.12`; Windows: `winget install Python.Python.3.12` |

### Install the skill

**Option 1: `npx skills add` (recommended)**

This skill is compatible with the [open agent skills ecosystem](https://www.npmjs.com/package/skills). You can install it directly:

```bash
# Install globally (available across all projects)
npx skills add https://git.nite07.com/nite/skills.git -g -s video-edit-planner -y

# Install to specific agents
npx skills add https://git.nite07.com/nite/skills.git -g -s video-edit-planner -a claude-code -y

# List available skills without installing
npx skills add https://git.nite07.com/nite/skills.git --list
```

Supports 73+ agent frameworks including Claude Code, Codex, Cursor, OpenCode, and more.

**Option 2: `git clone` (manual)**

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/video-edit-planner <your agent's skills directory>
```

Copy the `video-edit-planner/` subdirectory into whatever directory your agent
loads skills from. That location is your environment's decision, not the skill's
— check your agent's documentation instead of assuming a fixed path.

## Workflow

```
1. Check dependencies (ffmpeg, uv, python3)
2. Gather inputs (video path + audio track index)
3. Ask editing requirements (including subtractive vs additive strategy)
4. Transcribe audio (skip if cached in index)
5. Extract clips & frames on demand (agent decides when transcript is insufficient)
6. Analyze frames with vision model (binary-search-style sampling)
7. Produce Markdown-table edit plan + overall recommendation
8. Iterate — user asks follow-ups, plan is refined
```

## Generate SRT Subtitles

After transcription, convert the JSON transcript to a subtitle file with one command (pure Python stdlib — works with any Python 3, no `uv sync` needed):

```powershell
# Windows (PowerShell)
$SkillDir = "<path where this skill is installed>"
$VideoJson = "<video directory>\clip_track1_fun-asr-nano.json"
python "$SkillDir\scripts\transcription\convert_srt.py" $VideoJson
```

```bash
# Linux / WSL
SKILL_DIR="<path where this skill is installed>"
VIDEO_JSON="<video directory>/clip_track1_fun-asr-nano.json"
python "$SKILL_DIR/scripts/transcription/convert_srt.py" "$VIDEO_JSON"
```

Both placeholders are deliberate: where this skill is installed and where your video lives are your environment's decisions, so resolve them at runtime.

The SRT is written next to the JSON (same name, `.srt` extension). Long segments (multi-sentence runs) are split on Chinese/English terminal punctuation with time distributed by character ratio, so entries stay readable; tune with `--max-duration`, `--max-chars`, or disable with `--no-split`. Other options: `--speaker-prefix` (adds `[SPK{n}]`), `--bom` (UTF-8 BOM for legacy players), `--min-duration`.

> ASR text is a locator, not final copy — proofread subtitles against the audio before publishing.

## Project Structure

```
video-edit-planner/
├── SKILL.md                          # Skill definition (workflow, guidance, pitfalls)
├── README.md                         # This file (English)
├── README.zh-CN.md                   # Chinese README
├── scripts/
│   ├── transcription/                # Bundled funasr-script (self-contained uv project)
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── .python-version           # Pinned to 3.12 (funasr's editdistance wheel)
│   │   ├── README.md                 # Notes on the bundled uv project (see pyproject readme)
│   │   ├── funasr_common.py          # Shared: ffprobe, audio extraction, model runner
│   │   ├── funasr_nano.py            # Fun-ASR-Nano entry point (default, high quality)
│   │   ├── funasr_fast.py            # SenseVoice entry point (emotion/event labels)
│   │   ├── funasr_regular.py         # Paraformer entry point (comparison)
│   │   ├── merge_emotion.py          # Merge SenseVoice labels onto the Nano transcript
│   │   ├── main.py                   # Default module entry point (delegates to funasr_nano)
│   │   └── convert_srt.py            # JSON → SRT conversion (pure stdlib, no venv)
│   ├── frames/
│   │   └── extract_frames.py         # Clip extraction + frame sampling (ffmpeg wrapper)
│   └── index/
│       └── manage_index.py           # JSON index management (8 subcommands)
└── references/
    ├── wsl-windows-uv-transcription.md       # WSL vs Windows execution, uv UNC constraint
    ├── windows-funasr-uv-setup.md            # Windows host setup, PyTorch/wheel pitfalls
    ├── frame-extraction-guide.md             # Vision token costs, resolution/batch guidance
    ├── spot-verification-workflow.md         # Verifying ASR claims against single frames
    └── editing-requirements-questionnaire.md # Full question set with answer choices
```

## Index File

All processing artifacts are tracked in a JSON file (`<video_stem>.vedit.json`) stored next to the video file:

- **transcriptions** — JSON path, track index, duration
- **clips** — start/end time, file path, extraction reason
- **frames** — timestamp, file path, scene score, extraction method

All paths are stored as **relative paths** (relative to the video directory), so moving the entire directory does not break references. The JSON file is human-readable and editable with any text editor.

## License

MIT