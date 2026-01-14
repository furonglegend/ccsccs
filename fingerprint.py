"""
fingerprint.py

Small utilities to produce deterministic fingerprints for constraints or
sets of variables. Fingerprints are useful for de-duplication and quick
comparison.

We use SHA-256 and provide an option to truncate the hex digest for compactness.
"""

import hashlib
from typing import Dict, Iterable, Set


def _normalize_constraint_representation(constraint: Dict) -> str:
    """
    Build a canonical string representation for the given constraint dict.
    The representation sorts variable names and parts to be stable across runs.
    """
    parts = []
    for part in ("A", "B", "C"):
        entries = constraint.get(part, {})
        # sort by var name for deterministic representation
        sorted_items = sorted(entries.items(), key=lambda kv: kv[0])
        parts.append(part + ":" + ",".join(f"{name}={float(coeff):.12g}" for name, coeff in sorted_items))
    if "source" in constraint:
        parts.append("src:" + str(constraint["source"]))
    return "|".join(parts)


def fingerprint_constraint(constraint: Dict, truncate: int = 16) -> str:
    """
    Compute a hex fingerprint for a constraint. The output is a hex string truncated to `truncate` characters.
    Default truncation 16 chars (64 bits hex = 8 bytes), adjustable for collision tradeoff.
    """
    rep = _normalize_constraint_representation(constraint)
    h = hashlib.sha256(rep.encode("utf-8")).hexdigest()
    if truncate is None:
        return h
    return h[:truncate]


def fingerprint_varset(varset: Iterable[str], truncate: int = 12) -> str:
    """
    Compute a fingerprint for an iterable of variable names (e.g. support set).
    Deterministic: sorts the names.
    """
    s = ",".join(sorted(list(varset)))
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return h[:truncate]


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """
    Simple Jaccard similarity between two sets of variable names.
    """
    if not set_a and not set_b:
        return 1.0
    inter = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return inter / union if union > 0 else 0.0
