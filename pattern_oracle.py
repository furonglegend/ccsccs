"""
pattern_oracle.py

Generate small "pattern" samplers (Rust function strings) from a counterexample-like mapping,
and perform lightweight validation.

This is a conservative prototype:
 - `PatternOracle.propose_sampler` creates a deterministic Rust function string that returns
   a tuple (or struct-like tuple) of input values derived from the counterexample.
 - `validate_rust_sampler` performs a minimal sanity check (presence of 'fn', balanced braces,
   and that declared identifiers look sane). This is not a compiler check.

Usage:
    oracle = PatternOracle()
    entry = oracle.propose_sampler({"a": 3, "b": 5}, signals=["a","b","c"])
    print(entry["rust_code"])
"""

from typing import Dict, Any, List, Optional, Tuple
import hashlib
import textwrap
import re


_DEF_TEMPLATE = """\
fn {fn_name}() -> ({ret_types}) {{
{body}
}}
"""

_STRUCT_TEMPLATE = """\
struct {struct_name} {{
{fields}
}}

fn {fn_name}() -> {struct_name} {{
{body}
}}
"""


_VALID_RUST_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PatternOracle:
    """
    Simple pattern oracle that proposes Rust sampler functions from a counterexample dict.

    The returned dict contains:
      - "name": sampler function name
      - "rust_code": code string
      - "signals": list of signals used
      - "desc": short description
    """

    def __init__(self, namespace: str = "generated", force_struct: bool = False):
        self.namespace = namespace
        self.force_struct = force_struct
        self._registry: Dict[str, str] = {}  # name -> code

    def _deterministic_name(self, counterexample: Dict[str, Any], prefix: str = "sample") -> str:
        """
        Make a stable name from the counterexample fingerprint.
        """
        h = hashlib.sha256(repr(sorted(counterexample.items())).encode("utf-8")).hexdigest()[:10]
        return f"{prefix}_{self.namespace}_{h}"

    def propose_sampler(self,
                        counterexample: Dict[str, Any],
                        signals: Optional[List[str]] = None,
                        fn_name: Optional[str] = None,
                        prefer_struct: bool = False) -> Dict[str, Any]:
        """
        Produce a Rust sampler function as a string.

        - counterexample: mapping var->value (values should be ints or floats or simple literals)
        - signals: optional preferred ordering of signals
        - fn_name: optional override for function name
        - prefer_struct: if True produce a small struct return instead of tuple

        Returns: dict with keys: name, rust_code, signals, desc
        """
        signals = list(signals) if signals else sorted(list(counterexample.keys()))
        ordered = [s for s in signals if s in counterexample] + [s for s in counterexample.keys() if s not in signals]

        if fn_name is None:
            fn_name = self._deterministic_name(counterexample)

        # sanitize identifiers
        safe_ordered = [self._sanitize_ident(s) for s in ordered]

        # build return types: use i128 for integers that fit, f64 for floats; for simplicity use i128 for ints else f64
        types = []
        vals = []
        for s in safe_ordered:
            v = counterexample.get(s)
            if isinstance(v, int):
                types.append("i128")
                vals.append(str(int(v)))
            else:
                # try numeric coercion
                try:
                    fv = float(v)
                    if abs(fv - round(fv)) < 1e-9:
                        types.append("i128")
                        vals.append(str(int(round(fv))))
                    else:
                        types.append("f64")
                        vals.append(repr(float(fv)))
                except Exception:
                    # fallback to integer zero
                    types.append("i128")
                    vals.append("0")

        # choose return style
        use_struct = prefer_struct or self.force_struct
        if use_struct and len(safe_ordered) > 1:
            struct_name = fn_name.capitalize() + "Input"
            fields = "\n".join([f"    pub {n}: {t}," for n, t in zip(safe_ordered, types)])
            body_lines = []
            # instantiate struct
            init_fields = "\n".join([f"    {n}: {v}," for n, v in zip(safe_ordered, vals)])
            body_lines.append(f"    {struct_name} {{")
            body_lines.append(init_fields)
            body_lines.append("    }")
            body = "\n".join(body_lines)
            code = _STRUCT_TEMPLATE.format(struct_name=struct_name, fn_name=fn_name, fields=fields, body=body)
        else:
            # tuple return
            ret_types = ", ".join(types) if types else "()"
            body_lines = []
            # create tuple literal
            tup = ", ".join(vals)
            body_lines.append(f"    // deterministic sampler generated from counterexample")
            body_lines.append(f"    ({tup})")
            body = "\n".join(body_lines)
            code = _DEF_TEMPLATE.format(fn_name=fn_name, ret_types=ret_types, body=body)

        # minimal validation
        valid = validate_rust_sampler(code)
        desc = f"Sampler for signals: {', '.join(safe_ordered)}; valid={valid}"
        # register
        self._registry[fn_name] = code
        return {"name": fn_name, "rust_code": code, "signals": safe_ordered, "desc": desc, "valid": valid}

    def _sanitize_ident(self, name: str) -> str:
        """
        Reduce non-ident characters to underscore, ensure valid Rust identifier.
        """
        if _VALID_RUST_IDENT.match(name):
            return name
        # replace invalid chars
        s = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if s and s[0].isdigit():
            s = "_" + s
        if not s:
            s = "v"
        return s

    def get_registered(self) -> Dict[str, str]:
        return dict(self._registry)


def validate_rust_sampler(code: str) -> bool:
    """
    Very small heuristic validation for generated Rust sampler code.
    Checks:
     - contains 'fn' token
     - braces balanced
     - no suspicious characters
    This is not a compiler or syntactic check.
    """
    if "fn " not in code:
        return False
    # balanced braces
    stack = []
    for ch in code:
        if ch == "{":
            stack.append("{")
        elif ch == "}":
            if not stack:
                return False
            stack.pop()
    if stack:
        return False
    # check for suspicious control characters
    if any(ord(ch) < 9 for ch in code):
        return False
    return True


# quick demo
if __name__ == "__main__":
    oracle = PatternOracle()
    ce = {"a": 3, "b": 7, "out": 21}
    res = oracle.propose_sampler(ce, signals=["a", "b"])
    print("FUNCTION NAME:", res["name"])
    print("VALID:", res["valid"])
    print(res["rust_code"])
