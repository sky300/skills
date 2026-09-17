from __future__ import annotations

import argparse

from funasr_common import REGULAR_MODEL_CONFIGS, add_common_args, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="funasr-regular",
        description="Extract the given audio track and transcribe it with the regular FunASR pipeline (SenseVoice/Paraformer).",
    )
    add_common_args(parser)
    parser.add_argument(
        "--model",
        choices=sorted(REGULAR_MODEL_CONFIGS),
        default="sensevoice",
        help="regular FunASR model, sensevoice by default",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = REGULAR_MODEL_CONFIGS[args.model]
    run_pipeline(
        args,
        model_name=args.model,
        config=config,
        suffix=args.model,
        use_itn=args.model == "sensevoice",
        sensevoice=args.model == "sensevoice",
    )


if __name__ == "__main__":
    main()
