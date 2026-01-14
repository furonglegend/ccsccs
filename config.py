"""
config.py
Default configuration and loader. Very small helper to override defaults via JSON files.
"""

import json
from pathlib import Path
from typing import Any, Dict

# Default constants used by the simple pipeline.
DEFAULT_CONFIG: Dict[str, Any] = {
    "one_symbol": "ONE",          # special constant symbol for 1
    "export_r1cs_filename": "r1cs.json",
    "max_top_components": 50,     # for summary printing / limiting
    "parser": {
        "allow_arithmetic": True,  # parser accepts +, -, * in assignment expressions
    },
}


def load_config(path: str, base: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Load a JSON config file and merge it into base (shallow merge).

    :param path: path to JSON config file
    :param base: base configuration dictionary to update (if None use DEFAULT_CONFIG)
    :return: merged configuration dictionary
    """
    base = base.copy() if base is not None else DEFAULT_CONFIG.copy()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    # shallow merge
    for k, v in data.items():
        base[k] = v
    return base
