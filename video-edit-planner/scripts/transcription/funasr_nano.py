from __future__ import annotations

import argparse

from funasr_common import NANO_MODEL_CONFIG, add_common_args, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="funasr-nano",
        description="Extract the given audio track and transcribe it with Fun-ASR-Nano-2512.",
    )
    add_common_args(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_pipeline(
        args,
        model_name="fun-asr-nano",
        config=NANO_MODEL_CONFIG,
        suffix="fun-asr-nano",
        use_itn=True,
        sensevoice=False,
    )


if __name__ == "__main__":
    main()
