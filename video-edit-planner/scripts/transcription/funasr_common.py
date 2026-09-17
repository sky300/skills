from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REGULAR_MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "sensevoice": {
        "model": "iic/SenseVoiceSmall",
        "vad_model": "fsmn-vad",
        "vad_kwargs": {"max_single_segment_time": 30000},
    },
    "paraformer": {
        "model": "paraformer-zh",
        "vad_model": "fsmn-vad",
        "punc_model": "ct-punc",
    },
    "paraformer-en": {
        "model": "paraformer-en",
        "vad_model": "fsmn-vad",
    },
}

NANO_MODEL_CONFIG: dict[str, Any] = {
    "model": "FunAudioLLM/Fun-ASR-Nano-2512",
    "vad_model": "fsmn-vad",
    "hub": "hf",
    "trust_remote_code": True,
}

EMOTION_TAGS = (
    "HAPPY", "SAD", "ANGRY", "NEUTRAL", "FEARFUL", "DISGUSTED", "SURPRISED", "EMO_UNKNOWN",
)
EVENT_TAGS = (
    "BGM", "Speech", "Applause", "Laughter", "Cry", "Sneeze", "Breath", "Cough",
    "Sing", "Speech_Noise", "Event_UNK",
)
EMOTION_RE = re.compile(r"<\|(" + "|".join(EMOTION_TAGS) + r")\|>")
EVENT_RE = re.compile(r"<\|(" + "|".join(EVENT_TAGS) + r")\|>")

# Literal language strings the Fun-ASR-Nano model expects for --language; keep them verbatim.
NANO_LANGUAGE_MAP: dict[str, str] = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
    "yue": "粤语",
}


@dataclass
class AudioTrack:
    index: int
    codec: str | None
    channels: int | None
    channel_layout: str | None
    language: str | None
    title: str | None


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"missing required command: {name}")


def run_command(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def list_audio_tracks(media_path: Path) -> list[AudioTrack]:
    require_command("ffprobe")
    proc = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index,codec_name,channels,channel_layout:stream_tags=language,title",
            "-of",
            "json",
            str(media_path),
        ]
    )
    data = json.loads(proc.stdout)
    tracks: list[AudioTrack] = []
    for stream in data.get("streams", []):
        tags = stream.get("tags") or {}
        tracks.append(
            AudioTrack(
                index=int(stream["index"]),
                codec=stream.get("codec_name"),
                channels=stream.get("channels"),
                channel_layout=stream.get("channel_layout"),
                language=tags.get("language"),
                title=tags.get("title"),
            )
        )
    return tracks


def print_audio_tracks(media_path: Path) -> None:
    tracks = list_audio_tracks(media_path)
    if not tracks:
        print("no audio track found")
        return
    for i, track in enumerate(tracks, 1):
        parts = [
            f"#{i}",
            f"stream_index={track.index}",
            f"codec={track.codec or '?'}",
            f"channels={track.channels or '?'}",
        ]
        if track.channel_layout:
            parts.append(f"layout={track.channel_layout}")
        if track.language:
            parts.append(f"lang={track.language}")
        if track.title:
            parts.append(f"title={track.title}")
        print("  ".join(parts))


def resolve_track(media_path: Path, requested: int | None) -> int:
    tracks = list_audio_tracks(media_path)
    if not tracks:
        raise SystemExit(f"no audio track found: {media_path}")
    if requested is None:
        return tracks[0].index
    valid_indexes = {track.index for track in tracks}
    if requested in valid_indexes:
        return requested
    raise SystemExit(
        f"audio stream index does not exist: {requested}\n"
        f"available audio streams: {', '.join(str(t.index) for t in tracks)}\n"
        "hint: --track takes the ffprobe/ffmpeg stream index, not the ordinal position of an audio track."
    )


def extract_audio(media_path: Path, wav_path: Path, track_index: int) -> None:
    require_command("ffmpeg")
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(media_path),
        "-map",
        f"0:{track_index}",
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(wav_path),
    ]
    subprocess.run(cmd, check=True)


def clean_text(text: str, *, sensevoice: bool) -> str:
    # Strip every <|...|> tag here; emotion/event labels are extracted separately in normalize_result.
    # Deliberately not using rich_transcription_postprocess, whose emoji conversion pollutes the text.
    del sensevoice  # kept for call-site compatibility; SenseVoice is cleaned like any other model
    return re.sub(r"<\|[^|]*\|>", "", text).strip()


LANG_TAG_RE = re.compile(r"<\|(?:zh|en|yue|ja|ko|nospeech)\|>")


def extract_sensevoice_labels_per_segment(raw_full_text: str) -> list[tuple[list[str], list[str]]]:
    """Split SenseVoice's top-level tagged text on language tags; return (emotions, events) per segment.

    Since FunASR 1.4.x the text in sentence_info is already stripped to clean text, and the tags
    survive only in the top-level text, shaped like:
        <|zh|><|NEUTRAL|><|Speech|><|withitn|>first utterance <|zh|><|HAPPY|><|Laughter|>second utterance ...
    After splitting on the language tags, each chunk maps to one VAD segment, in sentence_info order.
    """
    parts = [p for p in LANG_TAG_RE.split(raw_full_text) if p.strip()]
    return [(EMOTION_RE.findall(p), EVENT_RE.findall(p)) for p in parts]


def get_audio_duration(audio_path: Path) -> float | None:
    try:
        import soundfile as sf

        return round(float(sf.info(str(audio_path)).duration), 3)
    except Exception:
        return None


def normalize_result(
    raw_result: list[dict[str, Any]],
    *,
    audio_path: Path,
    source_media: Path,
    track_index: int,
    model_name: str,
    model_id: str,
    language: str | None,
    diarize: bool,
    elapsed: float,
    sensevoice: bool,
) -> dict[str, Any]:
    first = raw_result[0] if raw_result else {}
    text = clean_text(str(first.get("text", "")), sensevoice=sensevoice)
    segments: list[dict[str, Any]] = []
    for seg in first.get("sentence_info") or []:
        raw_sentence = str(seg.get("sentence") or seg.get("text") or "")
        item: dict[str, Any] = {
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "text": clean_text(raw_sentence, sensevoice=sensevoice),
        }
        if diarize and "spk" in seg:
            item["speaker"] = seg["spk"]
        segments.append(item)

    if sensevoice:
        # Tags survive only in the top-level text: split on language tags and refill the segments in order.
        labels = extract_sensevoice_labels_per_segment(str(first.get("text", "")))
        for i, item in enumerate(segments):
            if i < len(labels):
                emotions, events = labels[i]
                if emotions:
                    item["emotion"] = emotions[0]
                if events:
                    item["events"] = events

    output: dict[str, Any] = {
        "text": text,
        "segments": segments,
        "file": source_media.name,
        "audio_file": audio_path.name,
        "track": track_index,
        "model": model_name,
        "model_id": model_id,
        "language": language or "auto",
        "audio_duration_s": get_audio_duration(audio_path),
        "processing_s": round(elapsed, 3),
    }
    for key in ("timestamps", "timestamp"):
        if key in first:
            output[key] = first[key]
    return output


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_output_path(output_dir: Path, media_path: Path, track_index: int, suffix: str) -> Path:
    return output_dir / f"{media_path.stem}_track{track_index}_{suffix}.json"


def resolve_output_dir(output_dir: Path | None, media_path: Path) -> Path:
    if output_dir is None:
        return media_path.parent
    return output_dir.expanduser().resolve()


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("media", type=Path, help="path to the video/audio file")
    parser.add_argument("--track", type=int, default=None, help="ffmpeg stream index; defaults to the first audio track")
    parser.add_argument("--list-tracks", action="store_true", help="list the audio tracks and exit")
    parser.add_argument("--output-dir", "-o", type=Path, default=None, help="output directory; defaults to the source media file's directory")
    parser.add_argument("--language", "-l", default="auto", help="language, e.g. auto/zh/en/ja/ko/yue; auto by default")
    parser.add_argument("--device", default=None, help="device, e.g. cuda:0/cpu; auto-detected by default")
    parser.add_argument("--no-diarize", action="store_true", help="disable the cam++ speaker-diarization model")
    parser.add_argument("--keep-wav", action="store_true", help="keep the extracted 16k wav file")
    parser.add_argument("--wav-dir", type=Path, default=None, help="directory for the temporary wav; defaults to the system temp directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="print more progress information")


def prepare_audio(args: argparse.Namespace) -> tuple[Path, int, tempfile.TemporaryDirectory[str] | None]:
    media_path: Path = args.media.expanduser().resolve()
    if not media_path.exists():
        raise SystemExit(f"file not found: {media_path}")

    if args.list_tracks:
        print_audio_tracks(media_path)
        raise SystemExit(0)

    track_index = resolve_track(media_path, args.track)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.keep_wav:
        wav_dir = args.wav_dir.expanduser().resolve() if args.wav_dir else resolve_output_dir(args.output_dir, media_path)
        wav_dir.mkdir(parents=True, exist_ok=True)
    elif args.wav_dir is not None:
        wav_dir = args.wav_dir.expanduser().resolve()
        wav_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="funasr-script-")
        wav_dir = Path(temp_dir.name)

    wav_path = wav_dir / f"{media_path.stem}_track{track_index}.wav"
    print(f"[1/2] extracting audio stream_index={track_index} -> {wav_path}", file=sys.stderr)
    extract_audio(media_path, wav_path, track_index)
    return wav_path, track_index, temp_dir


def auto_device(device: str | None) -> str:
    if device:
        return device
    import torch

    return "cuda:0" if torch.cuda.is_available() else "cpu"


def transcribe_with_config(
    *,
    wav_path: Path,
    media_path: Path,
    track_index: int,
    output_path: Path,
    model_name: str,
    config: dict[str, Any],
    language: str | None,
    device: str | None,
    diarize: bool,
    use_itn: bool,
    sensevoice: bool,
    verbose: bool,
) -> dict[str, Any]:
    from funasr import AutoModel

    if model_name in ("fun-asr-nano", "sensevoice"):
        # Nano has no native word-level timestamps; SenseVoice with spk_model loses its emotion/event tags.
        # Neither runs speaker diarization: multi-speaker audio is already separated by the per-track run.
        diarize = False
    config = config.copy()
    if diarize and "spk_model" not in config:
        config["spk_model"] = "cam++"
    resolved_device = auto_device(device)

    print(f"[2/2] loading model {model_name} ({config['model']}) on {resolved_device}", file=sys.stderr)
    load_start = time.time()
    model = AutoModel(device=resolved_device, disable_update=True, **config)
    if verbose:
        print(f"model load took: {time.time() - load_start:.1f}s", file=sys.stderr)

    gen_kw: dict[str, Any] = {
        "input": str(wav_path),
        "batch_size": 1,
        "sentence_timestamp": True,
    }
    resolved_language = language
    if model_name == "fun-asr-nano":
        resolved_language = NANO_LANGUAGE_MAP.get(language or "", language)
    if resolved_language and resolved_language != "auto":
        gen_kw["language"] = resolved_language
    if use_itn:
        gen_kw["itn" if model_name == "fun-asr-nano" else "use_itn"] = True

    start = time.time()
    raw_result = model.generate(**gen_kw)
    elapsed = time.time() - start
    output = normalize_result(
        raw_result,
        audio_path=wav_path,
        source_media=media_path,
        track_index=track_index,
        model_name=model_name,
        model_id=str(config["model"]),
        language=language,
        diarize=diarize,
        elapsed=elapsed,
        sensevoice=sensevoice,
    )
    write_json(output_path, output)
    print(f"done: {output_path}", file=sys.stderr)
    print(f"transcription took: {elapsed:.2f}s", file=sys.stderr)
    return output


def run_pipeline(args: argparse.Namespace, *, model_name: str, config: dict[str, Any], suffix: str, use_itn: bool, sensevoice: bool) -> Path:
    media_path = args.media.expanduser().resolve()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        wav_path, track_index, temp_dir = prepare_audio(args)
        output_path = make_output_path(resolve_output_dir(args.output_dir, media_path), media_path, track_index, suffix)
        transcribe_with_config(
            wav_path=wav_path,
            media_path=media_path,
            track_index=track_index,
            output_path=output_path,
            model_name=model_name,
            config=config,
            language=args.language,
            device=args.device,
            diarize=not args.no_diarize,
            use_itn=use_itn,
            sensevoice=sensevoice,
            verbose=args.verbose,
        )
        print(output_path)
        return output_path
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
