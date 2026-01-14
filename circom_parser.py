"""
circom_parser.py

A small, pragmatic Circom .circom parser tailored for the prototype:
- parses templates, signals (input/output/var), simple assignment statements using '<=='
- supports binary multiplication (a * b) and simple linear arithmetic (a + b - c)
- builds a small AST and can produce a basic R1CS-like list of constraints

Limitations:
- This is NOT a full Circom parser. It is intended as a practical starting point.
- Complex expressions, array signals, templates with parameters, and control-flow
  constructs are not fully supported.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path

# ----------------------------
# Data classes for a tiny AST
# ----------------------------

@dataclass
class SignalDecl:
    name: str
    kind: str  # "input", "output", or "signal" (internal)
    raw: str = ""


@dataclass
class Assignment:
    left: str
    expr: str
    raw: str = ""


@dataclass
class Template:
    name: str
    signals: List[SignalDecl] = field(default_factory=list)
    assignments: List[Assignment] = field(default_factory=list)
    raw: str = ""


@dataclass
class ComponentInst:
    name: str
    template: str
    raw: str = ""


@dataclass
class ParsedFile:
    templates: Dict[str, Template] = field(default_factory=dict)
    components: List[ComponentInst] = field(default_factory=list)
    top_template: Optional[str] = None
    raw: str = ""


# ----------------------------
# Parsing utilities
# ----------------------------

RE_TEMPLATE = re.compile(r"template\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)\s*\{", re.IGNORECASE)
RE_SIGNAL = re.compile(r"signal\s+(input|output)?\s*([A-Za-z_][A-Za-z0-9_]*)\s*;", re.IGNORECASE)
RE_ASSIGN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*<==\s*(.+?)\s*;", re.IGNORECASE)
RE_COMPONENT = re.compile(r"component\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)\s*;", re.IGNORECASE)


class CircomParser:
    """
    Minimal parser for Circom-like files.
    """

    def __init__(self, allow_arithmetic: bool = True):
        self.allow_arithmetic = allow_arithmetic

    def parse_file(self, path: Union[str, Path]) -> ParsedFile:
        """
        Parse a .circom file and return a ParsedFile structure.
        """
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        return self.parse_text(text)

    def parse_text(self, text: str) -> ParsedFile:
        """
        Parse the file content string into templates and components.
        """
        pf = ParsedFile(raw=text)
        # Naive splitting: find template blocks
        idx = 0
        while True:
            m = RE_TEMPLATE.search(text, idx)
            if not m:
                break
            tname = m.group(1)
            start = m.end()
            # find matching closing brace for this template (simple counting)
            brace = 1
            j = start
            while j < len(text) and brace > 0:
                if text[j] == "{":
                    brace += 1
                elif text[j] == "}":
                    brace -= 1
                j += 1
            block = text[start:j-1].strip()
            tpl = self._parse_template_block(tname, block)
            tpl.raw = block
            pf.templates[tname] = tpl
            idx = j

        # find component instantiations (top-level)
        for m in RE_COMPONENT.finditer(text):
            name, template = m.group(1), m.group(2)
            inst = ComponentInst(name=name, template=template, raw=m.group(0))
            pf.components.append(inst)

        # heuristic: if a component named "main" or "Main" exists, set top_template
        for c in pf.components:
            if c.name.lower() == "main":
                pf.top_template = c.template
                break
        # otherwise, set the first defined template as top if any
        if pf.top_template is None and pf.templates:
            pf.top_template = next(iter(pf.templates.keys()))

        return pf

    def _parse_template_block(self, name: str, block: str) -> Template:
        """
        Parse body of a template into signal declarations and assignments.
        """
        tpl = Template(name=name)
        # iterate line by line (very naive)
        lines = [ln.strip() for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("//")]
        for ln in lines:
            # signal declarations
            m_sig = RE_SIGNAL.match(ln)
            if m_sig:
                kind = m_sig.group(1) or "signal"
                sname = m_sig.group(2)
                tpl.signals.append(SignalDecl(name=sname, kind=kind, raw=ln))
                continue
            # assignments of form `a <== expr;`
            m_as = RE_ASSIGN.match(ln)
            if m_as:
                left = m_as.group(1)
                expr = m_as.group(2).strip()
                tpl.assignments.append(Assignment(left=left, expr=expr, raw=ln))
                continue
            # ignore other lines for now
        return tpl

    # ----------------------------
    # Convert AST -> R1CS-like
    # ----------------------------

    def to_r1cs(self, parsed: ParsedFile, one_symbol: str = "ONE") -> Dict[str, Any]:
        """
        Convert the parsed AST into a very small R1CS-like structure:
          {
            "variables": {"x": idx, ...},
            "constraints": [{"A": {...}, "B": {...}, "C": {...}}, ...],
            "meta": {...}
          }

        The constraints are constructed from assignments:
          - binary multiplication `c <== a * b;` -> (A=a) * (B=b) = (C=c)
          - linear assignment `d <== a + b - e;` -> (A = a + b - e) * (B = ONE) = (C = d)
        """
        variables: Dict[str, int] = {}
        next_var_idx = 0

        def ensure_var(v: str) -> int:
            nonlocal next_var_idx
            if v not in variables:
                variables[v] = next_var_idx
                next_var_idx += 1
            return variables[v]

        # always register ONE constant
        ensure_var(one_symbol)

        constraints: List[Dict[str, Any]] = []

        # We only convert assignments found in the top template by default.
        tpl_name = parsed.top_template
        if tpl_name is None:
            return {"variables": variables, "constraints": constraints, "meta": {"note": "no template found"}}

        tpl = parsed.templates.get(tpl_name)
        if tpl is None:
            return {"variables": variables, "constraints": constraints, "meta": {"note": f"top template {tpl_name} not found"}}

        # register signals
        for s in tpl.signals:
            ensure_var(s.name)

        # process assignments
        for a in tpl.assignments:
            left = a.left
            expr = a.expr
            ensure_var(left)

            # try to detect multiplication pattern: "<var> * <var>"
            m_mul = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)\s*", expr)
            if m_mul:
                v1, v2 = m_mul.group(1), m_mul.group(2)
                ensure_var(v1); ensure_var(v2)
                constraint = {
                    "A": {v1: 1.0},
                    "B": {v2: 1.0},
                    "C": {left: 1.0},
                    "source": a.raw
                }
                constraints.append(constraint)
                continue

            # handle simple linear expressions (sum/sub of vars and constants)
            # very naive tokenization: split by + and -, preserve signs
            if self.allow_arithmetic:
                lin = self._parse_linear_expression(expr)
                if lin is not None:
                    # linear expression supported: produce (lin) * ONE = left
                    # lin is dict var->coeff (floats)
                    for v in list(lin.keys()):
                        ensure_var(v)
                    constraint = {
                        "A": lin,
                        "B": {one_symbol: 1.0},
                        "C": {left: 1.0},
                        "source": a.raw
                    }
                    constraints.append(constraint)
                    continue

            # fallback: treat entire expression as a single reference (wire copy)
            # e.g., c <== someVar;
            m_copy = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*", expr)
            if m_copy:
                src = m_copy.group(1)
                ensure_var(src)
                constraint = {
                    "A": {src: 1.0},
                    "B": {one_symbol: 1.0},
                    "C": {left: 1.0},
                    "source": a.raw
                }
                constraints.append(constraint)
                continue

            # otherwise, we cannot interpret the rhs: include as a comment constraint
            constraint = {
                "A": {},
                "B": {},
                "C": {},
                "source": a.raw,
                "note": "unparsed expression"
            }
            constraints.append(constraint)

        # finalize variables -> stable ordering
        vars_map = {name: idx for name, idx in sorted(variables.items(), key=lambda kv: kv[1])}

        return {
            "variables": vars_map,
            "constraints": constraints,
            "meta": {
                "top_template": tpl_name,
                "template_signal_count": len(tpl.signals),
                "assignment_count": len(tpl.assignments),
            }
        }

    def _parse_linear_expression(self, expr: str) -> Optional[Dict[str, float]]:
        """
        Attempt to parse expressions like:
            "a + b - c"
            "2*a + 3*b - c"   (coefficients integers)
        Return a dict var->coeff or None if not a supported linear form.

        This parser is intentionally small and permissive for common simple cases.
        """
        # normalize: replace '-' with '+-' to split by '+'
        s = expr.replace("-", "+-")
        parts = [p.strip() for p in s.split("+") if p.strip()]

        linear: Dict[str, float] = {}
        for part in parts:
            # match coefficient * var or plain var or signed int constant
            m_coeff = re.fullmatch(r"([+-]?\d+)\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)", part)
            if m_coeff:
                coeff = float(m_coeff.group(1))
                var = m_coeff.group(2)
                linear[var] = linear.get(var, 0.0) + coeff
                continue
            m_var = re.fullmatch(r"([+-]?\d*)\s*([A-Za-z_][A-Za-z0-9_]*)", part)
            if m_var:
                sign_str = m_var.group(1)
                var = m_var.group(2)
                coeff = 1.0
                if sign_str and sign_str not in ("+", "-"):
                    try:
                        coeff = float(sign_str)
                    except ValueError:
                        return None
                elif sign_str == "-":
                    coeff = -1.0
                linear[var] = linear.get(var, 0.0) + coeff
                continue
            # constants like "+3" or "-2" are currently ignored (could be folded into ONE)
            m_const = re.fullmatch(r"([+-]?\d+)", part)
            if m_const:
                # fold constants into special ONE variable (caller must set ONE)
                linear["_CONSTANT_TERM"] = linear.get("_CONSTANT_TERM", 0.0) + float(m_const.group(1))
                continue
            # unknown term
            return None

        # If we saw only a constant, convert it to a ONE-term
        if not linear:
            return None

        # If we captured a constant term, remap to ONE (caller will ensure ONE variable exists)
        if "_CONSTANT_TERM" in linear:
            const_val = linear.pop("_CONSTANT_TERM")
            linear["ONE"] = linear.get("ONE", 0.0) + const_val

        return linear
