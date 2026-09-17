# Choosing Windows vs WSL for `uv` transcription

Use this reference when the user has both a Windows host and a WSL/Linux environment.

## Core rule: follow the video file and the execution environment

Every example below uses placeholders (`<path where this skill is installed>`, `<path to the video>`, `<any writable directory>`, `/mnt/c/Users/<user>/...`); none of them is a fixed location, and none of them should be copied verbatim without resolving it in the target environment.

Choose the execution environment based on **where the video file is stored** and therefore where heavy media I/O should happen.

| Video location | Preferred execution | Command syntax | Why |
|---|---|---|---|
| Windows host filesystem (`C:\...`, `D:\...`, or WSL paths like `/mnt/c/...`, `/mnt/d/...`) | Windows host | PowerShell + Windows paths | Keeps heavy video reads local to Windows; usually better host/GPU access |
| WSL/Linux filesystem (`/home/...`, `/var/...`, Linux project directories) | WSL/Linux shell | Linux shell + Linux paths | Keeps heavy video reads local to Linux; avoids Windows reading through WSL UNC |
| Ambiguous / network / external drive | Ask the user | Depends on answer | Storage locality and GPU/tool availability may differ |

Do **not** assume Windows execution just because the agent itself runs in WSL. If the video is genuinely inside the WSL filesystem, running the Linux transcription project in WSL is the correct choice.

## What the agent should do vs what the user should do

The agent should do lightweight setup work when it has the capability:

- Check whether `uv`, Python 3.12, and ffmpeg are available in the chosen execution environment.
- Ask for consent before installing missing system dependencies, then install them if possible.
- If Windows execution is chosen and the agent is running in WSL, use `powershell.exe` to access the Windows host.
- Copy or clone the transcription project to a Windows-local directory when needed.
- Run `uv sync` during setup when possible.

The user should only be asked to run the **long-running transcription command** (or other long-running media processing commands), because those may take a long time and should not block the conversation.

## Windows `uv` constraint

When Windows execution is chosen, do **not** ask Windows `uv` to operate on the skill's WSL filesystem path (`\\wsl.localhost\...` / `\\wsl$\...`). Windows `uv` can fail while creating or removing `.venv` directories on UNC-backed WSL paths.

Instead, make the transcription project available under a Windows-local path and run `uv` there.

### Windows setup from a WSL agent

If the agent runs in WSL, it can use `powershell.exe` to run Windows host setup commands. Example pattern:

```bash
# From WSL: copy bundled transcription project to a Windows-local path.
SRC="<path where this skill is installed>/scripts/transcription"
# <user> is a placeholder for your own Windows profile directory; any
# Windows-local writable directory works, as long as Windows uv can reach it locally.
DST="/mnt/c/Users/<user>/AppData/Local/Temp/vedit-transcription"
mkdir -p "$DST"
cp -a "$SRC"/. "$DST"/

# From WSL: run Windows uv setup through PowerShell.
powershell.exe -NoProfile -Command '
  $TransDir = "$env:LOCALAPPDATA\Temp\vedit-transcription"
  Set-Location $TransDir
  uv sync
'
```

If copying from WSL is not possible, clone the full repo on Windows instead:

```powershell
$Repo = "<any writable directory>"   # the clone destination is your choice, not fixed
git clone https://git.nite07.com/nite/skills.git $Repo
Set-Location "$Repo\video-edit-planner\scripts\transcription"
uv sync
```

## Windows transcription command shape

Use this when the video is stored on the Windows host filesystem. Give this kind of command to the user after setup is complete:

```powershell
$SkillTranscription = "$env:LOCALAPPDATA\Temp\vedit-transcription"   # the Windows-local copy made above
$Video = "<path to the video>"
$VideoDir = Split-Path -Parent $Video
uv run --directory $SkillTranscription funasr-nano $Video --track 2 --language AUDIO_LANGUAGE_CODE --output-dir $VideoDir
```

For multiple tracks, run once per track and record each resulting JSON in the index.

## WSL/Linux setup and transcription command shape

Use this when the video is stored inside the WSL/Linux filesystem. The agent can run setup directly in WSL:

```bash
SKILL_TRANSCRIPTION="<path where this skill is installed>/scripts/transcription"
cd "$SKILL_TRANSCRIPTION" && uv sync
```

Then give the user a Linux shell command for the long transcription step:

```bash
SKILL_TRANSCRIPTION="<path where this skill is installed>/scripts/transcription"
VIDEO="<path to the video>"
VIDEO_DIR="$(dirname "$VIDEO")"
uv run --directory "$SKILL_TRANSCRIPTION" funasr-nano "$VIDEO" --track 2 --language AUDIO_LANGUAGE_CODE --output-dir "$VIDEO_DIR"
```

`SKILL_TRANSCRIPTION` and `SKILL_DIR` are placeholders on purpose: where a skill is installed is the user's decision, so resolve the path from wherever this `SKILL.md` actually lives in that environment.

## Notes for agents

- Prefer Fun-ASR-Nano unless the user explicitly wants a fast preview.
- Give the transcription command immediately when promising a command.
- Keep all outputs next to the video file.
- Avoid separate output directories such as `~/whisperx_output/`; transcription JSON, clips, frames, and the index should stay with the video.
- Use PowerShell commands for Windows execution; use Linux shell commands for WSL/Linux execution.
- Do lightweight setup yourself when possible; hand off only long-running media processing to the user.