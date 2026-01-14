"""
synthesizer.py

Produce a simple textual Circom "patch" or a tiny replay circuit from an extracted witness.

Two helper functions:
 - synthesize_circom_patch(witness, template_name, out_path)
     produce a minimal patch file listing assignment lines that can be applied by inspection.
 - produce_replay_circom(witness, out_path, module_name="Replay", include_one=True)
     produce a tiny .circom file that sets signals to the recovered witness values for quick testing.

These functions are intentionally conservative textual outputs to help manual inspection and reproduction.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json


def synthesize_circom_patch(witness: Dict[str, float], template_name: Optional[str] = None, out_path: str = "recovered.patch") -> str:
    """
    Write a small textual patch mapping variables to constant assignments.

    Format (simple):
      # patch for template: <template_name>
      a <== 3.0;
      b <== 4.0;

    Returns path to written file.
    """
    p = Path(out_path)
    lines = []
    if template_name:
        lines.append(f"# patch for template: {template_name}")
    for var, val in sorted(witness.items()):
        # skip internal ONE unless explicitly requested
        lines.append(f"{var} <== {float(val)};")
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def produce_replay_circom(witness: Dict[str, float], out_path: str = "replay.circom", module_name: str = "Replay", include_one: bool = True) -> str:
    """
    Produce a minimal .circom file that contains a template which assigns the recovered witness
    values to signals, then instantiates it as main. Useful for quick local replay.

    Example output:

    template Replay() {
      signal input dummy;
      signal a;
      signal b;
      a <== 3;
      b <== 4;
    }
    component main = Replay();

    Returns path to written file.
    """
    p = Path(out_path)
    lines = []
    lines.append(f"template {module_name}() {{")
    # If there is no input, add a dummy input to make circom parser happier in some contexts
    lines.append("  signal input dummy;")
    for var, val in sorted(witness.items()):
        if var == "ONE" and not include_one:
            continue
        # signal declaration (we declare everything as plain signal for minimal replay)
        lines.append(f"  signal {var};")
    lines.append("")
    # assignments
    for var, val in sorted(witness.items()):
        if var == "ONE" and not include_one:
            continue
        # prefer integer literals when close to integer
        v = float(val)
        if abs(v - round(v)) < 1e-9:
            lit = str(int(round(v)))
        else:
            lit = repr(v)
        lines.append(f"  {var} <== {lit};")
    lines.append("}")
    lines.append(f"component main = {module_name}();")
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


# Demo
if __name__ == "__main__":
    w = {"ONE": 1.0, "a": 3.0, "b": 4.0, "c": 12.0}
    p1 = synthesize_circom_patch(w, template_name="Demo", out_path="demo.patch")
    p2 = produce_replay_circom(w, out_path="replay_demo.circom")
    print("wrote", p1, p2)
