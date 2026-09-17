from __future__ import annotations

import argparse

from funasr_common import REGULAR_MODEL_CONFIGS, add_common_args, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="funasr-fast",
        description="Extract the given audio track and transcribe it quickly with SenseVoice.",
    )
    add_common_args(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_pipeline(
        args,
        model_name="sensevoice",
        config=REGULAR_MODEL_CONFIGS["sensevoice"],
        suffix="sensevoice",
        use_itn=True,
        sensevoice=True,
    )


if __name__ == "__main__":
    main()
