#!/usr/bin/env python3
"""
cli.py
Command-line entrypoint for the simple Circom -> R1CS pipeline.
"""

import argparse
import sys
from pathlib import Path

from config import load_config, DEFAULT_CONFIG
from runner import run_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Simple Circom parser and R1CS exporter (minimal prototype)."
    )
    p.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to the .circom file to parse.",
    )
    p.add_argument(
        "--out-dir",
        "-o",
        default="out",
        help="Directory to write outputs (json summaries). Default: ./out",
    )
    p.add_argument(
        "--config",
        "-c",
        default=None,
        help="Optional JSON config file to override defaults.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Minimize console output.",
    )
    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    cfg = DEFAULT_CONFIG.copy()
    if args.config:
        cfg = load_config(args.config, base=cfg)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_pipeline(str(input_path), out_dir=str(out_dir), config=cfg, quiet=args.quiet)


if __name__ == "__main__":
    main()
