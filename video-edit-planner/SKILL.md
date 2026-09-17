---
name: video-edit-planner
description: "Use when planning video edits: transcribe audio (FunASR-Nano), extract emotion/event labels (SenseVoice) and key frames, analyze visuals, and produce cut/transition/assembly plans. Supports subtractive (long-form) and additive (short-form highlight) editing."
license: MIT
tags:
  [
    video-editing,
    transcription,
    funasr,
    frame-extraction,
    vision,
    planning,
    ffmpeg,
  ]
---

# Video Edit Planner

## Overview

A conversational video-editing planning assistant. The user provides a video file and an audio track index; the skill transcribes the audio, extracts key frames on demand, analyzes them visually, and produces an iterative Markdown-table edit plan (timecodes, segment descriptions, transitions, notes).

The skill is **agent-driven, not scripted**: it provides tools (transcription, clipping, frame extraction, index management) and guidance for the agent to autonomously decide when and what to extract based on user needs.

## Editing Strategy

The skill supports **both subtractive and additive editing**, chosen by the **target output format** — not by the source recording length:

- **Long-form target (subtractive, default for videos >3–4 min):** Load the full recording onto the NLE timeline and delete boring parts. What remains is a continuous, naturally flowing video. The transcript is used to **identify what to cut** (sparse dialogue, repetitive actions, dead air), not what to extract. Best for: story-driven content, medium-length videos (5–15 min), gameplay with narrative arcs.

- **Short-form target (additive / highlight extraction, for Shorts or highlight reels <3 min):** Extract individual highlights and assemble them. This is the inverse of subtractive — the transcript is used to **identify what to keep** (emotional peaks, funny moments, action climaxes), not what to cut. Best for: Shorts/TikTok, pure highlight reels, very short videos (<3 min).

- **Hybrid:** Subtractive backbone with optional inserts from elsewhere in the recording.

A long source recording can be edited either way — a 2-hour gameplay session can become a 10-minute story video (subtractive) or a 60-second highlight clip (additive). Always ask which **target format** the user wants before choosing a strategy.

When the user asks for a full edit plan, ask which strategy they prefer. Default to subtractive for long-form targets, additive for short-form/Shorts/highlight-reel targets.

## When to Use

- User provides a video path and wants help planning cuts, transitions, or assembly.
- User asks "help me edit this video" or "what parts should I cut from this recording."
- User needs to understand video content beyond what the transcript alone reveals.
- User wants an iterative dialogue to refine an edit plan over multiple turns.
- User only needs audio transcription from a video file.
- User needs to extract and analyze specific video segments visually.
- User needs help finding stock materials (stickers, GIFs, meme clips) for editing.

Any subset of these capabilities is a valid use case — not every session requires the full workflow.

**Don't use for:** actual video editing/rendering (this skill plans and transcribes, it does not produce rendered video files).

## Workflow

**Every step is optional.** The steps below describe the full end-to-end workflow, but the agent should only execute the steps relevant to the user's request. Users may need any subset of these capabilities — transcription only, frame extraction only, material search only, or a full planning session. Use the user's request to determine which steps apply; do not force the full pipeline when it is not needed.

### Step 1 — Check dependencies

Before any processing, verify the environment. Missing dependencies must be **installed only with explicit user consent**.

| Dependency           | Check command          | Install (prefer OS package manager; fallback to pip)                                                                                         |
| -------------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `ffmpeg` + `ffprobe` | `which ffmpeg ffprobe` | Linux: `sudo pacman -S ffmpeg` / `sudo apt install ffmpeg`; Windows: `winget install Gyan.FFmpeg`; macOS: `brew install ffmpeg`              |
| `uv`                 | `which uv`             | Linux: `sudo pacman -S uv` / `sudo apt install uv` (if available); macOS: `brew install uv`; Windows: `winget install astral-sh.uv`; fallback: `pip install uv` |
| `python3` / Python 3.12 for transcription | `python --version` / `python3 --version` | Use Python 3.12 for the bundled FunASR project, especially on Windows. Linux: `sudo pacman -S python` / `sudo apt install python3`; Windows: `winget install Python.Python.3.12`; macOS: `brew install python@3.12` |

**Completion criteria:** all three dependencies confirmed present, or user has explicitly declined installation (in which case stop — the skill cannot proceed).

### Step 2 — Gather inputs

Ask the user for:

1. **Video file path** (absolute path; translate Windows paths like `C:\Users\<user>\x.mkv` to `/mnt/c/Users/<user>/x.mkv` on WSL).
2. **Audio track index(es)** — the ffmpeg stream index, not ordinal. The user may provide **multiple tracks** (e.g., track 1 = own mic, track 2 = Discord audio). Each track is transcribed separately and saved as a separate JSON file. If unknown, list tracks:
   ```bash
   ffprobe -v error -select_streams a -show_entries stream=index,codec_name,channels,channel_layout:stream_tags=language,title -of json VIDEO_PATH
   ```

**Completion criteria:** video path and at least one track index confirmed.

### Step 3 — Ask editing requirements

Before transcribing, ask the user what they want to do with the video. User requirements are often vague in the first pass — that's expected. The plan is refined iteratively.

For full video-edit planning requests, ask early whether the user wants **one focused recommended cut** or **multiple alternative editing strategies**. If they want alternatives, analyze a wider set of candidate segments and present modular options the user can freely combine into their own final cut. Do not force the plan into a rigid one-path timeline where every section has only one fixed choice.

Also ask which editing strategy the user prefers:
- **Subtractive:** Delete boring parts from the full recording, keeping continuous segments. Best for long-form targets (>3–4 min), coherence and flow.
- **Additive (highlight extraction):** Extract individual highlights and assemble them. Best for short-form targets (Shorts/highlight reels).
- **Hybrid:** Subtractive backbone with optional inserts from elsewhere.
If the user doesn't specify, default by target: subtractive for long-form videos, additive for Shorts/highlight reels.

If the agent's runtime supports structured questioning (e.g. a `clarify` tool or another structured-questioning capability in your runtime), use it to gather requirements systematically. Ask questions one at a time with multiple-choice options — this is much more effective than a free-text wall of questions.

**The requirements questionnaire below covers the key axes for gameplay/creator video editing.** Not every question applies to every session — pick the relevant ones based on the user's initial request. See `references/editing-requirements-questionnaire.md` for the full questionnaire with choices.

| Axis | Why it matters |
|---|---|
| Target platform (Bilibili / Douyin / YouTube / Shorts) | Determines aspect ratio, pacing, subtitle density, meme density |
| Narrative style (funny compilation / story + comedy / highlights montage) | Determines structure: pure clip reel vs. narrative arc |
| Planning mode (single recommended cut / multiple alternatives) | Determines whether to produce one focused timeline or modular strategy options the user can mix and match |
| Editing strategy (subtractive / additive / hybrid) | Determines whether to plan by deleting boring parts from a continuous timeline (long-form) or by extracting and assembling highlights (short-form) |
| Role distribution (main POV / equal co-op / host / commentator) | Determines whose voice/reactions to prioritize in cuts |
| Effect density (minimal / medium / high) | Determines how many stickers, overlays, and effects to search for and apply |
| Editor tool (Premiere Pro / CapCut / DaVinci / other) | Determines how specific transition/effect instructions are phrased |
| First edit or existing draft | Determines whether to plan from scratch or optimize existing cuts |
| BGM style preference | Determines BGM search/recommendation direction |
| Number of participants | Determines how to handle multi-person interaction and voice allocation |
| Audio handling (keep original + subtitles / voice-over / mixed) | Determines subtitle work, BGM vs voice balance, and narration needs |
| Privacy (face + voice OK / no face / need masking) | Determines face-cam handling and any masking needs |
| Output format (timestamp notes / script table / storyboard plan) | Determines deliverable detail level |
| Target duration | Determines how aggressively to cut and pace the content |

**Completion criteria:** user has described at least a rough editing goal, and the agent has probed the relevant axes above.

**Long requirement summaries:** if the synthesized requirements, transcript-derived notes, or edit-planning response will be long, do not dump the whole thing into chat by default. Ask the user whether to save it as a file instead. Markdown (`.md`) is the default format for requirement summaries and edit plans; if the user requests another format (JSON, CSV, DOCX, etc.), use the requested format when practical.

### Step 4 — Transcribe audio

Use the bundled scripts in `scripts/transcription/`. **Fun-ASR-Nano** is the primary transcription model (higher accuracy and sensitivity on Chinese audio). **SenseVoice** is run as a **second pass to extract emotion and audio-event labels** — a secondary signal for highlight mining, not the primary text source.

**First run** requires `uv sync` (installs funasr + torch, may take several minutes). Subsequent runs reuse the cached venv.

**All output files (transcription JSON, clips, frames) go in the same directory as the video file.** Never use `~/whisperx_output/` or any other separate output directory — the `--output-dir` flag should point to the video's own directory. This keeps all artifacts co-located and portable.

**Choose the execution environment based on where the video file lives and where the command will run.** Keep heavy media I/O local to the filesystem that stores the video:

- If the video is on the Windows host filesystem (for example a WSL path under `/mnt/c/...`, `/mnt/d/...`, or a native Windows path like `C:\...`, `D:\...`), prefer running transcription on the Windows host. Give **PowerShell commands** with Windows paths. Do not hand the user `wsl ...` commands for the long transcription in this case; using WSL to read `/mnt/c` or `/mnt/d` defeats the storage-locality rule.
- If the video is inside the WSL/Linux filesystem (for example `/home/...`, `/var/...`, or another Linux mount), prefer running transcription in WSL/Linux. Give **Linux shell commands** with Linux paths.
- If the location is ambiguous, ask the user where the video is stored and where they want the workload to run.

**Agent should do the lightweight setup work.** Installing/checking `uv`, copying `scripts/transcription/` to a Windows-local directory, and running `uv sync` are setup tasks. If the agent can execute them through its available command interface, it should do them itself after getting any needed consent for dependency installation. Only the actual long-running transcription command should be handed to the user to execute manually.

**If the agent runs in WSL and Windows execution is chosen**, the agent can invoke the Windows host via `powershell.exe`. It should copy or clone the transcription project to a Windows-local path (for example `$env:LOCALAPPDATA\Temp\vedit-transcription` — any Windows-local writable directory works) and run setup there. Do not ask the user to manually copy files or run `uv sync` unless the agent cannot access the host command line or lacks permission.

**Windows `uv` constraint:** Windows `uv` should not operate on WSL UNC paths like `\\wsl.localhost\...` or `\\wsl$\...`; it can fail while managing `.venv` directories. Therefore, when the chosen execution environment is Windows, the transcription project itself must also be available under a Windows-local path. Follow `references/wsl-windows-uv-transcription.md`.

**Transcription can be long-running.** After setup is complete, generate the final transcription command and give it to the user to execute manually. Use PowerShell syntax for Windows execution and Linux shell syntax for WSL/Linux execution.

**Critical: when you tell the user you will provide a command, include it immediately in the same response.** Do not say "I'll give you the transcription command" and then move on to other topics without actually printing the command. The user should never have to ask "you said you'd give me the command but didn't."

Command templates (adjust paths for the user's environment):

Always include an explicit transcription language in commands that run ASR. Use a neutral placeholder such as `AUDIO_LANGUAGE_CODE` in templates, then replace it with the language actually spoken in the audio (`zh`, `en`, `ja`, `ko`, `yue`, etc.). Do **not** infer the audio language solely from the user's chat language. If uncertain, ask; if the user wants automatic detection, explicitly pass `--language auto` rather than omitting the flag.

```bash
# 1) Primary transcription: Fun-ASR-Nano (high quality, Chinese-optimized)
uv run --directory SKILL_DIR/scripts/transcription funasr-nano VIDEO_PATH --track TRACK_INDEX --language AUDIO_LANGUAGE_CODE --output-dir VIDEO_DIR

# 2) Emotion/event labels: SenseVoice (second pass, same track)
uv run --directory SKILL_DIR/scripts/transcription funasr-fast VIDEO_PATH --track TRACK_INDEX --language AUDIO_LANGUAGE_CODE --output-dir VIDEO_DIR

# 3) Merge SenseVoice emotion/events into the Nano transcript (per segment, by time)
uv run --directory SKILL_DIR/scripts/transcription merge-emotion NANO_JSON SENSEVOICE_JSON

# List tracks (no ASR is run, so no language flag is needed)
uv run --directory SKILL_DIR/scripts/transcription funasr-nano VIDEO_PATH --list-tracks
```

Where `VIDEO_DIR` is the directory containing the video file, `SKILL_DIR` is the directory this skill is installed in, and `AUDIO_LANGUAGE_CODE` is the explicit transcription language (for example `zh` for Mandarin Chinese). `SKILL_DIR` is a placeholder on purpose: where a skill is installed is the user's/environment's decision, so resolve it in the running environment (whatever directory this `SKILL.md` was loaded from) instead of assuming a fixed path.


**Multi-track recordings — do not assume a layout.** A multi-track OBS recording may have several dialogue tracks (e.g. own mic + another player's voice) separated by the game-audio track, and the ordering varies. Example layouts:

| Example A (common) | Example B (real-world) |
|---|---|
| index 1 = game audio | index 1 = player A voice |
| index 2 = microphone | index 2 = game audio |
| index 3 = Discord/voice chat | index 3 = player B voice |

**Always verify with `ffprobe` AND ask the user** which track is which — never guess. Multiple dialogue tracks are transcribed separately, each to its own JSON; when each speaker is on their own track, speaker diarization is unnecessary.

**Multi-track transcription:** when the user provides multiple track indexes (e.g., track 1 = mic, track 2 = Discord), run the transcription command **once per track**. Each run produces a separate JSON file named `<video_stem>_track<INDEX>_<model>.json`. Record each transcription in the index (Step 5) with its corresponding track index. When answering user questions, the agent should cross-reference all available transcripts to understand the full conversation context.

**Note on Discord audio quality:** Discord tracks may contain noise, crosstalk, or non-participant chatter. This is normal — the ASR transcript will be noisier. When cross-referencing transcripts, treat Discord track content as supplementary context, not as the primary narrative source.

**ASR transcript reliability:** FunASR transcripts are useful for locating material, understanding the rough plot, and finding candidate time ranges, but they are not an authoritative text source for final deliverables. Misrecognized words are common when the original track has unclear pronunciation, overlap, noise, or background audio. Similar-sounding words may be substituted. Before using transcript text as final copy, subtitles, quotes, captions, or narration, re-listen to the original audio around that time range and correct the text manually. When uncertain, mark the wording as uncertain rather than treating the ASR output as exact.

**ASR JSON format:** FunASR output JSON files contain a `segments` array where each segment has `start` and `end` timestamps in **milliseconds** (not seconds), plus `text` and optionally `speaker` fields. The SenseVoice pass adds `emotion` (one of HAPPY/SAD/ANGRY/NEUTRAL/FEARFUL/DISGUSTED/SURPRISED) and `events` (e.g. Speech/Laughter/Applause/BGM) per segment; after `merge-emotion`, these fields are attached to the Nano transcript's segments. When filtering segments by time range, convert `mm:ss` to milliseconds first (e.g., `49:30` = `2970000` ms). The top-level `audio_duration_s` field is in seconds. Always verify units before using timestamps for frame extraction.

**Emotion/event labels are a weak signal, not ground truth.** SenseVoice labels each VAD segment with a dominant emotion and audio events. These are useful for surfacing emotional peaks and laughter, but they do **not** capture humor, sarcasm, or tone — a segment whose text reads "笑死了" may still be labeled NEUTRAL. Treat labels as one clue among many (transcript semantics, cross-track reactions, visual frames), never as the sole basis for calling a segment "funny" or "exciting".

**Skip if cached:** check the index file (Step 5) for existing transcription entries. If a record exists for the same track index and the video file hasn't changed, reuse it.

**Completion criteria:** a transcription JSON exists for every requested track, and each is recorded in the index. Each JSON contains `segments` with timestamps and text.

### Step 4b — Generate SRT subtitles (on demand)

When the user wants **subtitle files** (to drop into an NLE timeline) rather than an edit plan, convert the transcription JSON to SRT with the bundled `scripts/transcription/convert_srt.py`. It is **pure Python stdlib** — no project venv or `uv run` needed, runs with any Python 3, and can be executed on either the Windows host or WSL regardless of where the transcription ran (conversion is lightweight I/O, so the storage-locality rule does not apply here).

```powershell
# Windows host
$SkillDir = "<path where this skill is installed>"
$VideoJson = "<video directory>\clip_track1_fun-asr-nano.json"
python "$SkillDir\scripts\transcription\convert_srt.py" $VideoJson
```

```bash
# Linux/WSL
SKILL_DIR="<path where this skill is installed>"
VIDEO_JSON="<video directory>/clip_track1_fun-asr-nano.json"
python "$SKILL_DIR/scripts/transcription/convert_srt.py" "$VIDEO_JSON"
```

Both placeholder values are deliberate: where this skill is installed and where the video
lives are your environment's decisions, so resolve them at runtime rather than assuming them.

Defaults: output written next to the input JSON (same stem, `.srt` extension, UTF-8), empty segments dropped, and **long segments split on terminal punctuation** (`。！？!?；;…` — the literal characters the script matches, kept verbatim so Chinese and English periods, question marks, exclamation marks and semicolons all split) with time distributed by character ratio. Options:

| Option | Effect |
|---|---|
| `-o, --output <path>` | Explicit output path |
| `--max-duration <sec>` / `--max-chars <n>` | Split threshold (defaults 8s / 50 chars) |
| `--no-split` | Output one entry per transcription segment, no splitting |
| `--speaker-prefix` | Prefix each entry with `[SPK{n}]` when the JSON has `speaker` fields |
| `--bom` | UTF-8 BOM output (legacy Windows players) |
| `--min-duration <ms>` | Drop segments shorter than this |

Pitfalls:
- FunASR timestamps are **milliseconds**; SRT needs `HH:MM:SS,mmm` — the script converts units.
- ASR text is a locator, not final copy: tell the user to proofread subtitles against the audio before publishing.
- Split timestamps are proportional estimates (interpolated by character ratio). They are close enough for timeline placement; entries remain individually draggable in the NLE for fine adjustment.
- Output belongs next to the video file (artifact co-location rule), never in agent directories.

### Step 5 — Manage index file

A JSON file tracks all processing artifacts to avoid duplicate work. It lives **next to the video file** and is human-readable and editable.

```
<video_dir>/<video_stem>.vedit.json
```

**All file paths are stored as relative paths** (relative to the video directory). Moving the entire directory does not break any references. If files are split across directories, paths outside the video directory are stored as absolute paths — the user can edit the JSON directly with a text editor to fix them.

Structure (managed by `scripts/index/manage_index.py`):

```json
{
  "transcriptions": [
    {
      "id": 1,
      "json_path": "video_track1_fun-asr-nano.json",
      "track_index": 1,
      "created_at": 1783997794.78,
      "duration_s": 120.5
    }
  ],
  "clips": [
    {
      "id": 1,
      "start_time": 30.0,
      "end_time": 60.0,
      "path": "video_clips/clip_30-60.mkv",
      "created_at": 1783997794.85,
      "reason": "user asked about this segment"
    }
  ],
  "frames": [
    {
      "id": 1,
      "clip_id": 1,
      "timestamp": 32.0,
      "path": "video_frames/frame_0001.jpg",
      "scene_score": 0.45,
      "method": "scene",
      "created_at": 1783997795.0
    }
  ]
}
```

Use `scripts/index/manage_index.py` for all CRUD operations:

```bash
# Initialize index file (idempotent)
uv run --directory SKILL_DIR python scripts/index/manage_index.py init --video VIDEO_PATH

# Add transcription record (requires --video to locate the index file)
uv run --directory SKILL_DIR python scripts/index/manage_index.py add-transcription --video VIDEO_PATH --json-path PATH --track-index N --duration S

# Query existing transcription (all tracks)
uv run --directory SKILL_DIR python scripts/index/manage_index.py get-transcription

# Query specific track
uv run --directory SKILL_DIR python scripts/index/manage_index.py get-transcription --track 1

# Add a clip record (requires --video)
uv run --directory SKILL_DIR python scripts/index/manage_index.py add-clip --video VIDEO_PATH --start S --end E --path PATH --reason "user asked about this segment"

# Add frame records (batch from a directory, requires --video)
uv run --directory SKILL_DIR python scripts/index/manage_index.py add-frames --video VIDEO_PATH --clip-id N --frames-dir DIR --method scene

# List all clips and frames
uv run --directory SKILL_DIR python scripts/index/manage_index.py list

# Check if a time range has already been extracted
uv run --directory SKILL_DIR python scripts/index/manage_index.py check-range --start S --end E

# Remove records for files that no longer exist on disk
uv run --directory SKILL_DIR python scripts/index/manage_index.py clean
```

**Completion criteria:** index file exists and all produced artifacts are recorded in it.

### Step 6 — Extract clips and frames (on demand)

**When to extract:** the agent autonomously decides based on user needs. If the transcript alone is insufficient to answer (e.g., user asks about visual content, or a transcript segment is sparse/empty for a time range the user cares about), extract frames for that range.

**Binary-search-style frame analysis:**

1. Extract a clip for the target time range.
2. Extract scene-change frames + uniform samples from the clip.
3. Send a few representative frames to vision analysis.
4. If a sub-range needs deeper understanding, extract more frames from that sub-range.
5. Once the relevant range is identified, send all frames in that range (in batches if needed) to vision.

**Spot-verification at ASR-mentioned timestamps:**

When verifying specific transcript claims (e.g., "is there really a boss fight at 49:30?"), skip clip extraction and directly extract single frames at the exact ASR-mentioned timestamps:

```bash
# Extract one frame at a specific timestamp (seconds)
ffmpeg -y -ss TIMESTAMP -i VIDEO_PATH -frames:v 1 -q:v 3 OUTPUT.jpg
```

This is much faster than clip+scene-detection for verifying a handful of specific points. Send each frame to vision analysis with a targeted question about what the transcript claims is happening at that moment (e.g., "The transcript says the boss entered phase 2 — can you see a boss with a phase indicator?").

Key lessons from spot-verification:
- **ASR timestamps can be off by several seconds** from the visual event they describe. If a frame at the ASR timestamp doesn't show the claimed content, try ±5–10 seconds before concluding the claim is wrong.
- **ASR proper nouns are unreliable.** Boss names, item names, and location names may be homophone errors. Treat proper nouns in transcripts as phonetic hints, not authoritative labels.
- **Visual confirmation can upgrade or downgrade segment priority.** A segment with confirmed visuals becomes higher priority; a segment where the transcript claims action but frames show only menus/UI should be downgraded.

**Clip extraction** (keyframe-accurate, `-c copy`):

For frame extraction purposes, only the video stream is needed:

```bash
ffmpeg -hide_banner -y -ss START -to END -i VIDEO_PATH -c copy -map 0:v:0 CLIP_PATH
```

For clips that the user may want to import into a video editor or play back, **preserve all audio tracks** by mapping all streams instead of only the video:

```bash
ffmpeg -hide_banner -y -ss START -to END -i VIDEO_PATH -c copy -map 0 CLIP_PATH
```

`-map 0` copies all streams (video + all audio tracks + subtitles). The agent should ask the user whether they need a full-multitrack clip or a video-only clip for frame extraction. When in doubt, produce both: a video-only clip for fast frame extraction, and a full-multitrack clip if the user plans to use it in an editor.

**Note:** When using `-c copy` with `-ss` before `-i`, seek accuracy is keyframe-level. If the user needs frame-exact cuts, re-encode is required (significantly slower). Keyframe accuracy is sufficient for planning purposes.

**Frame extraction** (scene detection + uniform sampling, hardware-accelerated, downsampled):

```bash
# Hardware-accelerated (CUDA/NVDEC preferred)
ffmpeg -hide_banner -y -hwaccel cuda -i CLIP_PATH \
  -vf "scale=1280:-2,fps=1/2,select='gt(scene,THRESHOLD)+gte(n,0)',showinfo" \
  -vsync vfr -q:v 3 FRAMES_DIR/frame_%04d.jpg

# CPU fallback
ffmpeg -hide_banner -y -i CLIP_PATH \
  -vf "scale=1280:-2,fps=1/2,select='gt(scene,THRESHOLD)',showinfo" \
  -vsync vfr -q:v 3 FRAMES_DIR/frame_%04d.jpg
```

**Parameters the agent chooses:**

| Parameter             | Default                | Guidance                                                                                                          |
| --------------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `scale` width         | `1280`                 | Raise to `1920` for short clips (<30s) where detail matters; lower to `854` for long clips (>120s) to save tokens |
| `THRESHOLD`           | `0.3`                  | Lower to `0.1`–`0.2` for gameplay footage (subtle scene changes); raise to `0.4` for dynamic content              |
| `fps` sample rate     | `1/2` (1 frame per 2s) | Raise to `1` (1fps) for short clips; lower to `1/5` for long clips                                                |
| `-q:v` (JPEG quality) | `3`                    | Range 2–31, lower = higher quality. 3 is high quality; 5 is a good balance                                        |

**All clips and frames are saved next to the video file** (e.g., `<video_stem>_clips/` and `<video_stem>_frames/`). The user manages cleanup.

**Record every extracted clip and frame in the index** before proceeding.

**Spot-verification frames** (single frames extracted at ASR timestamps to verify transcript claims) are lightweight probes, not durable artifacts. They do **not** need to be recorded in the index unless the agent determines they will be reused in later turns. If the verification is a one-pass check, skip the index to avoid clutter. If the agent expects to revisit the same timestamps, record them so subsequent turns can find them.

**Completion criteria:** clips and frames exist on disk and are recorded in the index.

### Step 7 — Vision analysis

Use whatever vision capability the agent's runtime provides to analyze extracted frames. The agent chooses:

- **Which model** to use (depends on the agent's runtime and available vision capabilities).
- **Batch size** — depends on the model's context window. See `references/frame-extraction-guide.md` for token cost estimates at different resolutions.
- **Windows setup troubleshooting** — see `references/windows-funasr-uv-setup.md` for Windows-host PowerShell transcription commands, Python wheel issues such as `editdistance` source builds, and PyTorch CUDA-vs-CPU build checks.
- **How many frames** per analysis pass — use the binary-search approach from Step 6.
- **Spot-verification** — when verifying specific transcript claims, see `references/spot-verification-workflow.md` for the single-frame extraction protocol.

**Completion criteria:** the agent has enough visual understanding to answer the user's question or produce the requested edit plan.

### Step 8 — Produce edit plan

#### Narrative skeleton — setup / development / turn / resolution (起承转合) — a soft guide, not a rigid schema

Before producing the plan, extract a **narrative skeleton**: a timeline labeling each segment's role in the story arc — setup / development / turn (climax) / resolution (reaction). Chinese-platform editing convention names those four beats 起 (setup) / 承 (development) / 转 (turn) / 合 (resolution); use that labeling when the user edits for Chinese platforms, and plain English labels otherwise. This skeleton serves both strategies: in subtractive mode the development/transition segments are cut candidates; in additive mode the turn/climax and emotional peaks are highlight candidates.

**The four-beat skeleton is a soft constraint, not a rigid schema.** Real recordings rarely follow the four beats strictly, in order, or completely — some stories skip the resolution, some are mostly development with a brief turn, and the user's own narration often follows a preview → execution → debrief pattern instead. Use the skeleton to *understand the arc*, then relax it to fit the actual material. Do not force every segment into one of four labels.

#### Highlight types — what counts as "interesting"

Highlights are not only fast-paced combat. Consider multiple kinds when mining candidates:

| Type | Signals | Example |
|---|---|---|
| Action climax | dense combat, tension, callouts | boss phase change, clutch play |
| Emotional peak | non-NEUTRAL emotion labels, surprise/anger/fear, screams | team wipe, rage, screams |
| Humor | semantic humor in transcript (puns, absurdity, playing it straight), Laughter events, cross-track reaction | deadpan jokes, trading jabs |
| Story turn | plot reversal, setup→payoff, debrief | a called shot that lands, plot reversal |
| Reaction | dense cross-track overlap, laughter, debrief | the whole group laughing |

**The agent cannot perceive tone or delivery.** Humor that lives in *how* something is said (deadpan, 阴阳怪气, rhythm) is invisible in the transcript and emotion labels. When a segment looks like it might be tone-based humor, mark it **tone uncertain — needs a human re-listen** (write the marker in the user's own language) instead of asserting it is funny. Never claim a segment is funny based on tone you cannot hear.

#### Transcript-first candidate mining for a bounded review window

When the user asks for **clip candidates from a specific time range** of an already-transcribed video (for example, `22:00–45:00`) rather than a full edit plan for the whole recording, do a lightweight **transcript-first mining pass** before any heavy extraction:

**Subtractive framing:** When using a subtractive strategy, the transcript mining pass identifies BORING ranges to cut, not just interesting ranges to keep. A range with sparse dialogue, repetitive actions, or no reactions is a cut candidate. A range with dense dialogue, reactions, or story progression is a keep candidate.

1. Load every relevant transcript track covering that window and slice to the requested range.
2. Compute simple density signals per minute or rolling window (segment count, character count, keyword hits, overlapping reactions across tracks).
3. Print and review the top windows plus manually chosen story pivots (setup / escalation / payoff), not just the numerically densest span.
4. Cross-read the main mic track with secondary chat/Discord tracks — use side tracks as corroboration and reaction context, not as the sole source of truth.
5. For the shortlisted windows, do a **spot visual check** with a few representative frames (for example 3–4 timestamps per candidate, optionally stitched into a contact sheet) instead of extracting long clips immediately.
6. Only extract full clips if the transcript and spot frames are still insufficient.

For multi-track recordings with crosstalk or duplicated speech, treat ASR as a **locator index**. Merge tracks by time, de-duplicate repeated lines mentally, and prefer moments where both dialogue and visuals support a self-contained mini-story. Secondary tracks may contain unrelated chatter; they are useful for reactions but should not dominate the narrative. When presenting the plan, call out which suggestions are transcript-grounded and which were visually spot-checked.

For fast-paced story + comedy gameplay videos, cull hard: keep combat, danger, reactions, relationship banter, and short setup/payoff beats; compress crafting, shopping, and inventory UI into 0.5–2 second bridge shots unless the item/choice itself is the punchline. A 7–8 minute plan should usually be a chaptered structure, not a flat list of every candidate.

This workflow is especially effective for requests like **“find fast-paced funny + story-driven candidate segments”**. It keeps token/runtime cost low while still verifying whether a transcript-highlighted moment actually has usable on-screen action.

Output a Markdown table with overall recommendations, then let the user iterate. **Respond in the same language the user is using.** If the user requested multiple alternative strategies, structure the plan as modular options rather than a single rigid timeline: offer alternative openings, narrative arcs, pacing choices, candidate segments, transitions, BGM/effect directions, and optional inserts the user can mix and match. In this mode, analyze more candidate segments than strictly needed for one final cut, and clearly label tradeoffs (e.g., funniest, clearest story, fastest pacing, most emotional, best visual action). If the plan is likely to be long (large tables, detailed scripts, full requirement summaries, or multi-section recommendations), ask whether the user wants it saved as a file instead of pasted into chat. Default to Markdown (`.md`) for saved plans unless the user requests another format.

```markdown
## Edit Plan

### Overall Recommendation

<1-3 sentences of high-level recommendation addressing the user's goal>

### Editing strategy

<Subtractive / Hybrid / Additive — one sentence explaining why>

### Timeline (grouped by story unit)

Group segments into **story units** — each unit is one self-contained mini-story (setup → development → climax → reaction). A highlight is often several segments stitched together (setup + climax + reaction), not a single contiguous range; keep them grouped so they aren't split into disconnected fragments. In subtractive mode the Action column drives the cuts (development/transition segments deleted); in additive mode the turn/climax and resolution/reaction segments are the extracted highlights.

The template below is English (this file is English-only): render the heading, column names, and every cell in the user's own language, and use the four-beat labels that fit that language (see pitfall 10).

#### Story 1 — <short title>

| Role | Timecode | Action | Notes |
|---|---|---|---|
| Setup | 00:00:30–00:01:23 | Keep | Accept the quest; the goal is stated |
| Development | 00:01:23–00:03:45 | Keep | Multi-phase boss fight, callouts included |
| Turn | 00:03:45–00:04:10 | Keep | Team-wipe reversal; the called shot lands |
| Resolution | 00:04:10–00:04:50 | Keep | Debrief and the laughing fit |

> Turn segment: zoom-in on the wipe; impact sound effect; cut the BGM to a tense track.
> Resolution segment: laughing meme sticker; keep the original laughter audio.

#### Story 2 — <short title> (development segment, safe to cut)

| Role | Timecode | Action | Notes |
|---|---|---|---|
| Development | 00:04:50–00:08:20 | Cut | Running the route; no dialogue, no events |

#### Insert (optional, hybrid mode) — <short title>

| Field | Value |
|---|---|
| Source timecode | 00:45:10–00:45:25 |
| Suggested duration | ~15s |
| Content / reason | Funny reaction from later in the recording, works as a cutaway |
| Insert at | After the first story unit |
| Edit technique | Cutaway, audio dip under BGM |
| Visual materials | Reaction sticker; search: shocked / laughing meme |
| Sound effects | Record scratch on cutaway; search: record scratch |

### Alternative Strategy Options (if requested)

| Module | Option | Best for | Candidate segments | Tradeoffs |
| ------ | ------ | -------- | ------------------ | --------- |
| Opening | Cold open with funniest quote | Fast hook | 00:03:10–00:03:24 | Strong hook, weaker story setup |
| ... | ... | ... | ... | ... |
```

**Completion criteria:** user receives a Markdown table addressing their stated goal, and is invited to ask follow-up questions.

### Step 9 — Iterate

The user will likely ask follow-ups: "what about this section?", "add a transition here", "can you check what's happening at 5:30?". For each:

1. Check if the answer can be derived from existing transcript + frames (check index first).
2. If not, extract new clips/frames for the requested range (Step 6).
3. Analyze and update the plan.

**Completion criteria:** user is satisfied with the plan or explicitly ends the session.

## Resuming a previous editing session

When the user says "continue editing" or resumes a prior session, the agent should recover state before doing new work:

1. **Search for the previous session** in your runtime's session history (a session-search tool, when you have one) using the video filename and relevant keywords (e.g., video name, "edit plan", "transcription").
2. **Check for existing artifacts** next to the video file:
   - Transcription JSON files (`<video_stem>_track*_*.json`)
   - Edit plan files (`*edit_plan*.md` or similar)
   - Index file (`<video_stem>.vedit.json`)
3. **Read the existing plan** to understand where the user left off and what was pending.
4. **Ask the user what to continue with** — do not assume the next step. The user may want to verify segments, add optional clips, revise the structure, or start a fresh pass.
5. **Reuse existing transcriptions** — do not re-transcribe unless the user explicitly asks or the video file has changed.

Common resume patterns:
- "Continue editing [video]" → check session history, find plan file, ask what to work on next.
- "Update the plan" → read existing plan, apply user's feedback, write updated version.
- "I selected some clips from the optional library" → read plan + optional library, integrate user's selections into the main timeline.

## Finding stock materials (optional, on demand)

When the user needs editing materials — stickers, GIFs, meme video clips, B-roll — the agent can help search or provide links for the user to search themselves. This section is **only triggered when the user asks for materials**; it is never a mandatory step.

### Material sources

| Source | URL | Content | Best for |
|---|---|---|---|
| Aigei | https://www.aigei.com/ | Chinese meme video clips, free download | Chinese-language creators (Bilibili / Douyin) |
| Bilibili Material Hub | https://cool.bilibili.com/ | Bilibili platform-native assets (video, audio, BGM, templates, stickers) | Bilibili creators; large Chinese meme collection |
| Tenor | https://tenor.com/ | GIFs + stickers, 30+ languages incl. Chinese, free API | Quick GIF/sticker search |
| GIPHY | https://giphy.com/ | Largest GIF library, 30+ languages, sticker channel | English/multilingual GIF search |
| Klipy | https://klipy.com/ | Localized GIF/sticker/clip API, supports Chinese | API-integrated search, localization |

### Priority by language

If the user communicates in Chinese, **recommend Aigei and Bilibili Material Hub first** — they have the most Chinese-relevant meme and sticker content. For non-Chinese users, Tenor and GIPHY are good defaults.

### Search strategy

- **Expand search terms** based on semantic understanding of the user's request. If the user says "I want a clip of someone looking shocked", search terms might include: "shocked / surprised / stunned / wtf". Use the user's language as the base, expand with synonyms and internet slang.
- The agent can either **search directly** (using web tools or API calls) or **suggest expanded search terms** for the user to search manually.
- If the user only wants links, provide the source URLs above and let the user search themselves.

### Sound effects and audio materials

Each scene's material recommendations should include **both** visual search terms (stickers, GIFs, overlays) **and** audio/sound-effect search terms. The user needs both to execute the edit in their NLE.

Common sound-effect categories for gameplay/creator edits:

| Category | Example search terms (expand by language) |
|---|---|
| Whoosh / transition | "whoosh", "swoosh", "transition sound effect" |
| Record scratch / stop | "record scratch", "vinyl stop", "record stop" |
| Impact / hit | "impact", "punch", "slap", "hit sound effect" |
| Alert / alarm | "alert", "alarm", "siren", "warning sound" |
| Loot / pickup | "loot ping", "item pickup", "pickup sound effect" |
| Comedy / meme | "meme sound", "vine boom", "comedy sound effect" |
| Heartbeat / tension | "heartbeat", "tension", "suspense sound effect" |
| Level up / success | "level up", "fanfare", "success sound effect" |

Recommend sound effects per scene alongside visual materials, not in a separate chapter. See pitfall #23 about splitting advice into separate top-level chapters.

### Bilibili Material Hub special handling

Bilibili Material Hub (cool.bilibili.com) has no built-in search function. Two options:

1. **Recommend the userscript**: [bcut-resource-search](https://git.nite07.com/nite/bcut-resource-search) — a Tampermonkey script that adds search to the Material Hub, supporting video, sticker/image, music, sound effect, and template categories.
2. **Search via API directly**: the agent can read the userscript's source code to discover the API endpoints and make requests directly (via HTTP tools or curl). Note: the site has CORS restrictions and UA-based access control, so direct API calls may require appropriate headers. If the agent's HTTP tools are blocked, fall back to suggesting the userscript to the user.

### Anti-bot fallback

Some material sites may block automated access (anti-bot, Cloudflare, CAPTCHA). If a plain web request or HTTP tool is blocked:

1. Retry with different headers (User-Agent, Accept-Language) if the tool allows it.
2. If your runtime already gives you a browser-automation tool (a browser tool, Playwright/Puppeteer MCP, or similar), use it to open the page. You can tell whether you have one from your own toolset — do not probe the machine for a browser, do not assume any browser stack is installed, and do not hardcode an executable path.
3. If you have no browser tool, or it is blocked as well, stop automating: hand the user the direct URL for a manual search, or ask them to provide a browser tool. This is a fallback for an optional step, not a prerequisite — nothing else in this skill needs a browser.

## Long-running operations

Before any operation expected to take >1 minute (transcription of long videos, large frame extraction):

1. Do lightweight setup directly when possible: dependency checks, copying scripts, preparing a Windows-local transcription directory, and running `uv sync`.
2. Ask for consent before installing missing system dependencies (`ffmpeg`, `uv`, Python), then install them if the runtime can do so.
3. Hand off only genuinely long-running media operations to the user. Generate the command and give it to the user to execute manually.
4. Match command syntax to the chosen execution environment: PowerShell commands for Windows execution; Linux shell commands for WSL/Linux execution.
5. After the user reports completion, the agent should verify the output exists before proceeding.

## Self-contained setup

The skill bundles its own transcription project under `scripts/transcription/`. On first use, the agent should prepare the environment before handing off the transcription command.

For WSL/Linux execution, run setup in the bundled transcription directory:

```bash
cd SKILL_DIR/scripts/transcription && uv sync
```

For Windows execution, ensure the transcription project is in a Windows-local directory before running setup. If the agent itself is running in WSL, it can use `powershell.exe` to run host commands and should do this setup itself when possible:

```powershell
# Example Windows-local setup directory
$TransDir = "$env:LOCALAPPDATA\Temp\vedit-transcription"
New-Item -ItemType Directory -Force -Path $TransDir | Out-Null
# Copy or clone scripts/transcription into $TransDir before this step.
Set-Location $TransDir
uv sync
```

This creates an isolated venv with `funasr`, `torch`, `torchaudio`. If the user has previously installed these packages via uv in other projects, uv's cache will reuse them — first-time cost is often only the link step. Do not ask the user to manually copy files or run `uv sync` unless the agent cannot access the host command line or lacks permission.

## Common pitfalls

1. **Installing dependencies without consent.** Always ask the user first. If they decline, stop — the skill cannot proceed without ffmpeg, uv, and python3.
2. **Re-processing already-transcribed videos.** Always check the index file first. If a transcription record exists and the video hasn't been modified, reuse it.
3. **Extracting frames from the entire video.** This is extremely slow for long videos. Always clip the target range first with `-c copy`, then extract frames from the clip.
4. **Using full-resolution frames.** A 2560×1600 PNG can cost 2000+ vision tokens. Downsample to 1280 width with `scale=1280:-2` and use JPEG (`-q:v 3`).
5. **Forgetting to record artifacts in the index.** Every clip and frame batch must be recorded. Otherwise subsequent turns will re-extract the same content.
6. **Assuming the transcript is sufficient.** Gameplay videos often have long stretches of action with no dialogue. The agent should proactively check whether visual analysis is needed for segments the user asks about.
7. **Treating ASR text as final copy.** FunASR transcripts can contain wrong characters/words caused by unclear speech, noise, overlap, or similar-sounding terms. Use transcripts for locating material and understanding context, not as the absolute wording for final captions, quotes, narration, or published copy. Re-listen and manually correct any text that will appear in the final product.
8. **Mixing funasr-script flags.** The bundled `funasr-nano`/`funasr-fast` use `--track STREAM_INDEX`, explicit `--language AUDIO_LANGUAGE_CODE`, and `--output-dir DIR`. Do not use the flags of the separate legacy `funasr-transcribe` wrapper if one happens to be installed.
9. **Hardcoding tool names.** This skill is agent-agnostic. Do not assume specific MCP tools or APIs exist. Use whatever the runtime provides for vision analysis, background execution, and user notification.
10. **Hardcoding output language.** The edit plan table and all user-facing text must follow the user's language, not a fixed language. The English table in Step 8 is a template — translate columns and content to match the user's language at runtime.
11. **Dropping audio tracks during clip extraction.** The default clip command maps only `0:v:0` (video-only) for fast frame extraction. If the user plans to import the clip into a video editor, use `--all-streams` (or `-map 0`) to preserve all audio tracks. Always ask the user which they need.
12. **Using `~/whisperx_output/` or other separate output directories.** All artifacts (transcription JSON, clips, frames, index file) must go in the same directory as the video file. The `--output-dir` flag should always point to the video's own directory. This keeps everything co-located and portable.
13. **Choosing command syntax or execution environment solely from where the agent runs.** Choose based on where the video file lives and where the command will execute. Windows execution → PowerShell commands and Windows paths; WSL/Linux execution → Linux shell commands and Linux paths. If the agent runs in WSL but Windows execution is chosen, use `powershell.exe` to do lightweight setup (copy files, install/check dependencies, run `uv sync`) before handing only the long transcription command to the user. Never ask Windows `uv` to run from `\\wsl.localhost\...` / `\\wsl$\...`.
14. **Saying you'll provide a command but not including it.** If you mention giving the user a transcription command, include it immediately in that same response. Do not move on to other content without printing the actual command. The user should never have to ask for it.
15. **Sending a wall of free-text questions.** When gathering editing requirements, use structured one-at-a-time multiple-choice questions via the runtime's clarify/prompt tool. This is far more effective than dumping 10 questions as a paragraph.
16. **Making full edit plans too rigid.** For complete planning requests, ask whether the user wants multiple alternative strategies. If yes, provide modular options and extra candidate segments that the user can combine, rather than a single fixed linear plan where every section has exactly one prescribed choice.
17. **Assuming ASR timestamps are in seconds.** FunASR JSON segment `start`/`end` fields are in **milliseconds**. Filtering by `2970` (seconds) when the data is `2970000` (ms) silently returns zero results. Always check the first segment's timestamp magnitude before filtering.
18. **Trusting ASR timestamps as frame-exact.** ASR segment timestamps can be off by several seconds from the visual event they describe. When doing spot-verification, if the frame at the ASR timestamp doesn't match the transcript claim, try ±5–10 seconds before concluding the claim is wrong.
19. **Treating ASR proper nouns as authoritative.** Boss names, item names, location names, and character names in ASR transcripts may be homophone errors. Use transcript proper nouns as phonetic hints for searching, but verify against visual/UI evidence before using them in final copy.
20. **Assuming transcript-claimed action is visually present.** A transcript saying an action is happening (e.g., a creature chasing the player) does not guarantee the action is visible on screen at that timestamp — the player may be in a menu, or the action may have happened off-screen. Always spot-verify with frames before promising visual content in the edit plan. Distinguish "transcript-grounded" from "visually confirmed" segments in the plan.
21. **Inferring psychological state from isolated ASR sentences.** ASR transcripts capture *what was said*, not *how it was said* — tone, emotion, and situational context are invisible in the text. A phrase that looks like amusement in text might actually express frustration or speechlessness in context. A phrase that looks like blame might actually be a coordination timing issue. Inferring psychological state or intent from context IS allowed, but it must be based on surrounding dialogue and situational context, not a single sentence in isolation. When a single transcript line could be misread, check nearby segments for context, ask the user for clarification, or mark the description as uncertain.
22. **Including non-game content in a game edit plan.** If the video is a gameplay recording, the edit plan should focus on game-related content only. Off-topic segments (microphone crosstalk, refund discussions, personal banter unrelated to the game) should not be included unless the user specifically requests them. The user's chat language being Chinese does not mean they want non-game Chinese-language banter in the plan.
23. **Splitting technique/BGM/material advice into separate top-level chapters.** The edit-plan document should be organized around the script table (each scene/segment as a subsection), with BGM search terms, sound-effect search terms, visual-material search terms, technique notes (zoom-in, screen shake, quick replay), and any other per-scene guidance embedded directly under each subsection — NOT split into separate top-level sections (e.g., "Section 4: Techniques", "Section 5: Material Keywords", "Section 6: BGM Strategy"). The user reads the plan scene-by-scene; scattering technique advice across detached chapters forces them to cross-reference.
24. **Recommending optional clips that are too fragmented to use.** Optional clip candidates with timecodes of only 3–15 seconds are often too short to form a coherent, flowable segment when inserted into a video. Prefer self-contained segments of 20+ seconds. When the only interesting moment in a time range is a single 5-second quote, recommend that the user expand the selection range in Premiere (include ±30–60 seconds of surrounding context) to form a usable segment. Note this explicitly in the optional clip library. Short merchant/dialogue segments (30–60s) tend to be more self-contained and usable than short combat fragments.
25. **Recommending visual materials without corresponding audio effects.** Each scene's material recommendations should include both visual search terms (for stickers, GIFs, overlays) AND audio/sound-effect search terms (for whoosh, record scratch, alarm, loot ping, etc.). The user needs both to execute the edit in Premiere.
26. **Saving frames to `/tmp/` or other temporary directories.** All extracted frames must go in the video file's directory (e.g., `<video_stem>_frames/`). When using a code-execution tool or direct `ffmpeg` commands, always set the output path to the video directory — not `/tmp/frames/` or any other temp directory. Temporary directories are not portable, get cleaned up by the OS, and break the self-contained workflow. This applies to both spot-verification frames and full clip extraction.
27. **Using shell `&` to parallelize ffmpeg commands.** Some terminal tools reject shell-level backgrounding (`command &`) and expose their own background option instead. When extracting multiple spot-verification frames in parallel, use a sequential `for` loop (each frame takes <1s so the total is still fast), or use your terminal tool's background option if it has one. Do not use `&` inside a single terminal call.
28. **Forgetting `--video` on `manage_index.py add-transcription`.** The `add-transcription` subcommand requires `--video VIDEO_PATH` to locate the index file next to the video. Omitting it causes an argument error. The same applies to `add-clip` and `add-frames` — always pass `--video`.
29. **Defaulting to additive editing for long-form content.** For targets longer than 3–4 minutes, subtractive editing (deleting boring parts from a continuous timeline) produces more coherent results than extracting and stitching short clips. The agent should default to subtractive for long-form targets and additive for short-form/Shorts/highlight-reel targets. See "Editing Strategy" section above.
30. **Recommending keep segments that are too short for subtractive editing.** In subtractive mode, "keep" segments should be continuous ranges of 30 seconds or longer — not 5–10 second fragments. If a 10-second moment is interesting but surrounded by boring content, recommend keeping a wider range (e.g., 30–60s) that includes setup and payoff, rather than extracting just the punchline. Short fragments are for "insert" segments in hybrid mode, not for the backbone timeline.
31. **Treating emotion labels as proof of humor or excitement.** A SenseVoice `emotion` label of NEUTRAL does not mean boring, and a HAPPY label does not mean funny — a segment whose text reads "笑死了" may still be labeled NEUTRAL. Emotion labels are one weak signal; the transcript semantics and cross-track reactions matter far more for judging "interesting". Never cite an emotion label alone as the reason a segment is a highlight.
32. **Asserting humor you cannot hear.** The agent perceives text and labels, not tone, delivery, deadpan, 阴阳怪气, or rhythm. Humor that lives in *how* something is said is invisible. When a segment looks like tone-based humor, mark it **tone uncertain — needs a human re-listen** (in the user's language) rather than claiming it is funny. Overclaiming tone-based humor produces false highlights that inflate the user's review workload.
33. **Forcing every segment into a rigid four-beat schema.** The setup/development/turn/resolution skeleton (起承转合) is a soft guide, not a hard four-act requirement. Real recordings skip beats, reorder them, or stay mostly in development with a brief turn. Label the arc where it is clear and leave segments unlabeled rather than forcing a turn or a resolution onto material that has none.
34. **Assuming a fixed multi-track layout.** Dialogue tracks are not always adjacent and the game-audio track is not always first — e.g. track 1 = player A, track 2 = game audio, track 3 = player B. Never guess the layout from a template; verify with `ffprobe` AND ask the user. When each speaker is on their own track, speaker diarization is unnecessary.
35. **Using SenseVoice text as the primary transcript.** SenseVoice is the emotion/event-label pass; its Chinese text is measurably worse than Fun-ASR-Nano (e.g. 心里乱了 → 里乱了). Use Nano's text for semantics and quoting, and SenseVoice only for the `emotion`/`events` fields merged onto Nano's segments.

## Verification checklist

Check only the items relevant to the steps actually executed. Not all items apply to every session — the user may only need a subset of the skill's capabilities.

- [ ] Dependencies (ffmpeg, uv, python3) confirmed present or user declined. *(Step 1 — always required)*
- [ ] Video path and audio track index(es) confirmed. *(Step 2 — required when video processing is needed)*
- [ ] User's editing goal understood. *(Step 3 — skip if not relevant to the user's request)*
- [ ] Transcription completed for all requested tracks, or reused from cache. *(Step 4)*
- [ ] Emotion/event labels merged onto transcripts (SenseVoice + merge-emotion) when highlight mining is needed. *(Step 4)*
- [ ] Index file initialized at `<video_dir>/<video_stem>.vedit.json`. *(Step 5 — always required when any processing is done)*
- [ ] All extracted clips and frames recorded in the index. *(Step 6 — only if frames were extracted)*
- [ ] Vision analysis performed where needed. *(Step 7 — only if frames were extracted)*
- [ ] Edit plan produced as Markdown table with overall recommendation. *(Step 8 — skip if not relevant to the user's request)*
- [ ] User invited to iterate. *(Step 9)*
