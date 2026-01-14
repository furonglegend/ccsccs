"""
mutation_templates.py

Utilities to validate and post-process mutation templates (strings) returned by an LLM oracle.

Responsibilities:
 - validate_candidate(candidate: str, allowed_signals: Optional[List[str]]) -> bool
 - normalize_candidates(candidates: List[str]) -> List[str]  (dedupe + trim)
 - sanitize_and_filter(candidates, allowed_signals, max_items) -> List[str]
 - fallback_candidates(allowed_signals, include_constants=True) -> List[str]

Validation rules (prototype):
 - candidate must be a short string (< 120 chars)
 - allowed characters: alphanumerics, whitespace, basic operators '+-*/()', and underscores
 - if allowed_signals provided, prefer candidates that only reference allowed_signals or integer constants
 - try to parse as either:
    * integer literal (e.g., "3" or "-1")
    * single variable name (e.g., "a")
    * simple linear expression using allowed signals (a + b - 1)
 - The parser is conservative: if parsing fails the candidate is rejected.
"""

from typing import List, Optional, Dict, Any
import re

_VALID_CHARS_RE = re.compile(r"^[A-Za-z0-9_\s\+\-\*\/\(\)]+$")

_INT_RE = re.compile(r"^[+-]?\d+$")
_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def normalize_candidates(candidates: List[str]) -> List[str]:
    """
    Trim whitespace, normalize internal spaces, and deduplicate while preserving order.
    """
    seen = set()
    out = []
    for c in candidates:
        s = " ".join(c.strip().split())
        if s not in seen and s != "":
            seen.add(s)
            out.append(s)
    return out


def _extract_identifiers(expr: str) -> List[str]:
    """
    Extract variable-like tokens from the expression.
    """
    # simplistic scanning for var tokens
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr)


def validate_candidate(candidate: str, allowed_signals: Optional[List[str]] = None) -> bool:
    """
    Conservative validation. Returns True if candidate passes basic checks.
    """
    if not candidate or len(candidate) > 120:
        return False
    if not _VALID_CHARS_RE.match(candidate):
        return False
    c = candidate.strip()
    # integer literal allowed
    if _INT_RE.match(c):
        return True
    # single variable
    if _VAR_RE.match(c):
        if allowed_signals is None or c in allowed_signals:
            return True
        else:
            return False
    # more complex: attempt simple parse of + and - and * by constants or allowed signals
    # We accept expressions built by tokens like VAR, INT, and operators + - * /
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[+-]?\d+|[+\-*/()]", c)
    # ensure tokens reconstruct the string (conservative)
    if "".join(tokens).replace(" ", "") != c.replace(" ", ""):
        return False
    # check identifiers against allowed_signals if provided
    ids = _extract_identifiers(c)
    if allowed_signals is not None:
        for ident in ids:
            if ident not in allowed_signals:
                return False
    # final sanity: don't allow expressions like "a a" (two identifiers adjacent) — require operators between identifiers
    if re.search(r"[A-Za-z0-9_]\s+[A-Za-z0-9_]", c):
        return False
    return True


def sanitize_and_filter(candidates: List[str],
                        allowed_signals: Optional[List[str]] = None,
                        max_items: int = 10) -> List[str]:
    """
    Normalize, validate, and return up to max_items valid candidates.
    If none valid, returns an empty list (caller may ask fallback_candidates).
    """
    normed = normalize_candidates(candidates)
    valid = []
    for c in normed:
        if validate_candidate(c, allowed_signals):
            valid.append(c)
        if len(valid) >= max_items:
            break
    return valid


def fallback_candidates(allowed_signals: Optional[List[str]] = None, include_constants: bool = True, max_items: int = 8) -> List[str]:
    """
    Produce a small set of conservative fallback candidates.
    """
    out = []
    if include_constants:
        for i in [0, 1, -1, 2, 3]:
            out.append(str(i))
    if allowed_signals:
        # include each signal as a candidate (up to a limit)
        for s in allowed_signals[: max(0, max_items - len(out))]:
            out.append(s)
    # dedupe and trim
    return normalize_candidates(out)[:max_items]


# small demo
if __name__ == "__main__":
    cands = ["  3  ", "a + b", "junk@@", "verylong" * 20, "x*y", "a b"]
    print("normalize:", normalize_candidates(cands))
    print("validate a+b (allowed a,b):", validate_candidate("a + b", ["a", "b", "c"]))
    print("sanitize:", sanitize_and_filter(cands, allowed_signals=["a","b","c","x","y"]))
    print("fallback:", fallback_candidates(["a","b","c"]))
