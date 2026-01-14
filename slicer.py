"""
slicer.py

A small 'slicer' that consumes a parsed R1CS-like dictionary and selects
a set of suspicious constraints for further processing.

Selection heuristic (simple prototype):
 - compute constraint 'score' = nz_count * log(1 + support_size)
 - optionally de-duplicate using fingerprint
 - return top-K candidate constraints with metadata (index, score, fingerprint, summary)

This file depends on r1cs_utils and fingerprint modules.
"""

from typing import Dict, Any, List, Tuple
import math

from r1cs_utils import constraint_summary, constraint_support, constraint_nz_count
from fingerprint import fingerprint_constraint


def score_constraint(constraint: Dict[str, Any]) -> float:
    """
    Compute a lightweight heuristic score for how 'suspicious' a constraint is.
    Larger values mean the constraint is more complex / more likely important.

    Heuristic: nz_count * (1 + log(1 + support_size))
    """
    nz = constraint_nz_count(constraint)
    supp = len(constraint_support(constraint))
    return float(nz) * (1.0 + math.log1p(supp))


def slice_r1cs(r1cs: Dict[str, Any], top_k: int = 10, deduplicate: bool = True) -> List[Dict[str, Any]]:
    """
    Produce a ranked list of candidate constraints.

    Returns a list of dicts:
      {
        "idx": int,
        "score": float,
        "fingerprint": str,
        "summary": {...},   # from constraint_summary
        "constraint": {...} # original constraint dict (reference)
      }
    """
    candidates = []
    seen_fps = set()

    for i, c in enumerate(r1cs.get("constraints", [])):
        score = score_constraint(c)
        fp = fingerprint_constraint(c)
        if deduplicate and fp in seen_fps:
            # skip duplicate constraint by fingerprint
            continue
        seen_fps.add(fp)
        candidates.append({
            "idx": i,
            "score": score,
            "fingerprint": fp,
            "summary": constraint_summary(c),
            "constraint": c
        })

    # sort descending by score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


# Convenience CLI-style function (for quick scripts)
def slice_and_print(r1cs: Dict[str, Any], top_k: int = 10) -> None:
    """
    Print a short human-readable ranking of top_k constraints.
    """
    cand = slice_r1cs(r1cs, top_k=top_k)
    print(f"Top {len(cand)} candidate constraints:")
    for item in cand:
        idx = item["idx"]
        score = item["score"]
        fp = item["fingerprint"]
        src = item["summary"].get("source", "")
        supp = item["summary"].get("support_size", 0)
        nz = item["summary"].get("nz_count", 0)
        print(f"  [{idx}] score={score:.4f} nz={nz} supp={supp} fp={fp} src={src}")
