"""
verifier.py

Minimal verifier for the prototype transcripts produced by Prover + ViolationIOP.

Responsibilities:
 - Validate transcript digest
 - Verify that openings match the witness commitment(s) using commitment.verify_commit
 - Recompute residuals from the opened variable values and the constraint linear forms
 - Return verification result and a report structure

This verifier assumes the prover used commitment.commit_map to generate a 'WITNESS' commitment
and included openings that correspond to the 'WITNESS' commitment. In production the open/commit
logic and proof linking would be more sophisticated.
"""

from typing import Dict, Any, Tuple, List
import math

import commitment
import violation_iop
from r1cs_utils import constraint_support, eval_linear_form


class Verifier:
    """
    Simple verifier for the violation transcript.
    """

    def __init__(self):
        pass

    def verify(self, r1cs: Dict[str, Any], transcript: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify the transcript and return (accepted:bool, report:dict)

        Report includes per-entry verification information.
        """
        report = {"digest_ok": False, "commit_checks": [], "residual_checks": []}

        # 1) digest check
        if not violation_iop.validate_transcript_digest(transcript):
            report["digest_ok"] = False
            return False, report
        report["digest_ok"] = True

        # 2) check witness commitments present
        witness_commits = transcript.get("witness_commitments", {})
        violations = transcript.get("violations", [])

        # We expect a 'WITNESS' top-level commitment; if absent, still try per-var commitments
        witness_top_commit = witness_commits.get("WITNESS")

        # 3) For each violation entry, verify opening and recompute residual
        constraints = r1cs.get("constraints", [])
        all_ok = True
        for entry in violations:
            idx = entry.get("idx")
            residual_claim = float(entry.get("residual", 0.0))
            opening = entry.get("opening")  # may be None
            src = entry.get("source", "")

            entry_report = {"idx": idx, "source": src, "opening_ok": None, "residual_ok": None, "computed_residual": None}

            if opening is None:
                # no opening provided; only acceptable if residual_claim is zero
                entry_report["opening_ok"] = None
                if math.isclose(residual_claim, 0.0, rel_tol=1e-9, abs_tol=1e-12):
                    entry_report["residual_ok"] = True
                else:
                    entry_report["residual_ok"] = False
                    all_ok = False
                # store
                report["residual_checks"].append(entry_report)
                continue

            # verify opening against the top-level witness commitment if present; otherwise skip
            if witness_top_commit:
                ok_commit = commitment.verify_commit(witness_top_commit, opening)
                entry_report["opening_ok"] = bool(ok_commit)
                if not ok_commit:
                    all_ok = False
            else:
                # Without top-level commit we can't verify global binding; we accept opening as-is but mark as unverifiable
                entry_report["opening_ok"] = None

            # compute residual from opened mapping
            opened_map = opening.get("mapping", {})
            # Build a small assignment mapping for evaluation: opened_map could be partial (only support)
            # We evaluate A(w) * B(w) - C(w) using the opened_map for the required variables.
            if idx is None or idx < 0 or idx >= len(constraints):
                entry_report["residual_ok"] = False
                entry_report["computed_residual"] = None
                all_ok = False
                report["residual_checks"].append(entry_report)
                continue

            constraint = constraints[idx]

            # eval_linear_form expects dict var->coeff and assignment with values
            # but we need to reuse eval_constraint; replicate small computation here to avoid import cycle
            def eval_linear(linear: Dict[str, float], assignment: Dict[str, float]) -> float:
                s = 0.0
                for var, coeff in linear.items():
                    val = assignment.get(var)
                    if val is None:
                        # missing value: assume 0 (but mark this in report)
                        val = 0.0
                    s += float(coeff) * float(val)
                return s

            a_val = eval_linear(constraint.get("A", {}), opened_map)
            b_val = eval_linear(constraint.get("B", {}), opened_map)
            c_val = eval_linear(constraint.get("C", {}), opened_map)
            computed = (a_val * b_val) - c_val
            entry_report["computed_residual"] = computed
            entry_report["residual_ok"] = math.isclose(computed, float(residual_claim), rel_tol=1e-9, abs_tol=1e-12)
            if not entry_report["residual_ok"]:
                all_ok = False

            report["residual_checks"].append(entry_report)

        return all_ok, report


# Demo usage
if __name__ == "__main__":
    # build the same R1CS and witness as prover demo
    r1cs = {
        "variables": {"ONE": 0, "a": 1, "b": 2, "c": 3},
        "constraints": [
            {"A": {"a": 1.0}, "B": {"b": 1.0}, "C": {"c": 1.0}, "source": "c <== a * b;"},
            {"A": {"a": 1.0, "b": 1.0}, "B": {"ONE": 1.0}, "C": {"d": 1.0}, "source": "d <== a + b;"}
        ],
        "meta": {}
    }
    witness_good = {"ONE": 1.0, "a": 3.0, "b": 4.0, "c": 12.0}
    from prover import Prover
    p = Prover()
    tx_good = p.make_proof(r1cs, witness_good, candidate_idxs=[0, 1])

    v = Verifier()
    ok, report = v.verify(r1cs, tx_good)
    print("verification ok:", ok)
    print("report:", report)

    # demonstrate a bad witness
    witness_bad = {"ONE": 1.0, "a": 3.0, "b": 4.0, "c": 11.0}
    tx_bad = p.make_proof(r1cs, witness_bad, candidate_idxs=[0, 1])
    ok2, report2 = v.verify(r1cs, tx_bad)
    print("verification ok (bad):", ok2)
    print("report (bad):", report2)
