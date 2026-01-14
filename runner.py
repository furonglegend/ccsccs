"""
runner.py
High-level pipeline runner. Uses circom_parser to parse a file and exports
a small R1CS-like JSON summary containing variables and constraints.

This runner is intentionally minimal: it demonstrates how to wire the parser,
produce a stable JSON output, and print a compact summary for human reading.
"""

import json
from pathlib import Path
from typing import Dict, Any

from circom_parser import CircomParser
from config import DEFAULT_CONFIG


def run_pipeline(input_path: str, out_dir: str = "out", config: Dict[str, Any] = None, quiet: bool = False) -> None:
    """
    Run the parsing + export pipeline.

    :param input_path: path to .circom file
    :param out_dir: directory to write outputs
    :param config: configuration dictionary
    :param quiet: if True, suppress verbose printing
    """
    cfg = DEFAULT_CONFIG.copy()
    if config:
        cfg.update(config)

    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print(f"[runner] Parsing {input_path} ...")

    parser = CircomParser(allow_arithmetic=cfg.get("parser", {}).get("allow_arithmetic", True))
    ast = parser.parse_file(input_path)

    # Convert AST -> simple R1CS-like structure
    r1cs = parser.to_r1cs(ast, one_symbol=cfg.get("one_symbol", "ONE"))

    out_path = out_dir / cfg.get("export_r1cs_filename", "r1cs.json")
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(r1cs, fh, indent=2)

    if not quiet:
        print(f"[runner] Wrote R1CS summary to: {out_path}")
        print_summary(r1cs, cfg)


def print_summary(r1cs: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """
    Print a compact summary of parsed variables and constraints.
    """
    vars_count = len(r1cs.get("variables", {}))
    constraints_count = len(r1cs.get("constraints", []))
    top_n = cfg.get("max_top_components", 20)

    print("=== R1CS Summary ===")
    print(f"Variables: {vars_count}")
    print(f"Constraints: {constraints_count}")
    print()
    print("First constraints (up to {}):".format(top_n))
    for i, c in enumerate(r1cs.get("constraints", [])[:top_n]):
        # human-friendly render
        A = linear_dict_to_str(c["A"])
        B = linear_dict_to_str(c["B"])
        C = linear_dict_to_str(c["C"])
        print(f"  [{i}] ({A}) * ({B}) = ({C})")
    print("====================")


def linear_dict_to_str(d: Dict[str, float]) -> str:
    """
    Convert a linear combination dict {'x': 2, 'y': -1} into a string "2*x + -1*y".
    """
    if not d:
        return "0"
    parts = []
    for v, coeff in d.items():
        parts.append(f"{coeff}*{v}")
    return " + ".join(parts)
