# Windows FunASR uv setup notes

Use when preparing the bundled transcription project on the Windows host for videos stored on a Windows drive (`C:\...`, `D:\...`).

Every command below uses placeholders: `<path where this skill is installed>` is where this skill actually lives on the machine (a Windows-local path when Windows execution is chosen — see `wsl-windows-uv-transcription.md`), and `<path to the video>` is the user's file. Resolve both at runtime; neither is a fixed location.

## Execution-location rule

If the video is on the Windows host filesystem, run the long transcription on Windows with PowerShell and Windows paths. Do not give `wsl ...` transcription commands just because the agent itself runs in WSL. The agent may use `powershell.exe` from WSL for lightweight setup/debugging, but the user-facing long command should be native PowerShell.

## Correct command shape

```powershell
$TransDir = "<path where this skill is installed>\scripts\transcription"
$Video = "<path to the video>"
$VideoDir = Split-Path -Parent $Video

uv run --directory $TransDir funasr-nano $Video --list-tracks
uv run --directory $TransDir funasr-nano $Video --track 2 --language AUDIO_LANGUAGE_CODE --output-dir $VideoDir
uv run --directory $TransDir funasr-nano $Video --track 3 --language AUDIO_LANGUAGE_CODE --output-dir $VideoDir
```

Outputs should be written next to the video (`$VideoDir`).

## Debugging `uv sync` from a WSL agent

Capture real stderr/stdout to a log to avoid PowerShell's `NativeCommandError` wrapping:

```powershell
$TransDir = "<path where this skill is installed>\scripts\transcription"
$Log = Join-Path $TransDir "uv-sync-debug.log"
Set-Location $TransDir
uv sync *> $Log
$Code = $LASTEXITCODE
Write-Host "uv sync exit code: $Code"
Get-Content $Log -Tail 160
```

From WSL, wrap this in `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '...'`.

## PyTorch CUDA build pitfall

If `funasr-nano` logs `on cpu` on a Windows NVIDIA machine, check PyTorch:

```powershell
$TransDir = "<path where this skill is installed>\scripts\transcription"
Set-Location $TransDir
uv run python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

If this prints `+cpu`, `None`, and `False`, the environment has CPU-only PyTorch. Do **not** fix this with a one-off `uv pip install --torch-backend=auto` unless the project lock/config is also updated: `uv run` will sync from `uv.lock` and may immediately uninstall the CUDA build and reinstall the CPU build.

This project configures `torch` and `torchaudio` to use the PyTorch `cu130` index on Linux/Windows via `[tool.uv.sources]`. After pulling a version that includes that configuration, rebuild the environment with:

```powershell
$TransDir = "<path where this skill is installed>\scripts\transcription"
Set-Location $TransDir
git pull
uv sync --reinstall
uv run python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

Expected on an NVIDIA Windows host: `torch` version contains `+cu130`, `torch.version.cuda` is not `None`, and `torch.cuda.is_available()` is `True`.

## `editdistance` / Python version pitfall

Observed failure:

```text
Failed to build `editdistance==0.8.1`
error: Microsoft Visual C++ 14.0 or greater is required
hint: editdistance was included because funasr -> editdistance
```

Cause: the selected Windows Python version may not have a prebuilt wheel for `editdistance==0.8.1`, so uv attempts a source build. Verified: `editdistance==0.8.1` has Windows wheels for CPython 3.12, but not for CPython 3.13.

This transcription project is pinned to Python 3.12 via `.python-version` and `requires-python = ">=3.12,<3.13"`. If an older clone still selects 3.13, update it and rebuild `.venv`:

```powershell
$TransDir = "<path where this skill is installed>\scripts\transcription"
Set-Location $TransDir
Set-Content .python-version "3.12"
# Also set pyproject requires-python to a compatible range such as >=3.12,<3.13 if maintaining the project.
Remove-Item -Recurse -Force .venv
uv sync
```

Avoid defaulting to installing MSVC Build Tools unless the user explicitly prefers compiling native packages on Windows.
