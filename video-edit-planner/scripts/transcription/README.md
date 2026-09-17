# Bundled transcription project (funasr-script)

A small, self-contained [uv](https://docs.astral.sh/uv/) project that extracts one audio
track from a media file and writes a JSON transcript. `SKILL.md` drives it; nothing here
needs to be read to use the skill.

This file is referenced by `pyproject.toml` (`readme = "README.md"`), and it is written for
someone inspecting the bundle rather than for a model.

## Entry points

| Console script | Module | Purpose |
|---|---|---|
| `funasr-nano` | `funasr_nano.py` | Fun-ASR-Nano transcription (accurate text; the default) |
| `funasr-fast` | `funasr_fast.py` | SenseVoice pass, used for its `emotion` / `events` labels |
| `funasr-regular` | `funasr_regular.py` | SenseVoice / Paraformer pipelines, for comparison |
| `merge-emotion` | `merge_emotion.py` | Merge the SenseVoice labels onto the Nano transcript by time |

Every command takes its input paths from the caller — the media file, the audio stream
index, and the output directory. None of them is baked into the code: the transcript lands
next to the video unless `--output-dir` says otherwise, so artifacts stay co-located with
the media the user already knows the location of.

## Environment

- Python is pinned to 3.12 in `.python-version` (`funasr` → `editdistance==0.8.1` ships no
  CPython 3.13 Windows wheel, so 3.13 falls back to a source build).
- `torch` / `torchaudio` come from the PyTorch `cu130` index on Linux and Windows (see
  `[tool.uv.sources]` in `pyproject.toml`). A CPU-only environment still works — slower.
- `ffmpeg` / `ffprobe` must be on `PATH`; the scripts shell out to them for track listing
  and audio extraction.
- The first `uv sync` pulls `funasr` + `torch` and can take several minutes.

## Where state lives

`uv sync` creates a `.venv` inside this directory (git-ignored). Nothing else is written
here: transcripts go next to the video file, and temporary wav files go to a temp
directory that is cleaned up on exit unless `--keep-wav` is passed.
