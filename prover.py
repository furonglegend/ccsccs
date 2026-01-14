"""
prover.py

A minimal Prover implementation for the prototype pipeline.

Responsibilities:
 - Accept an R1CS-like structure and a witness (mapping var->value).
 - Produce commitments to the witness mapping (using commitment.commit_map).
 - For a set of candidate constraint indices, compute residuals and when
   residual != 0 include an opening for the variables involved in that constraint.
 - Return a transcript (via violation_iop.make_transcript).

This is intentionally simple and uses the lightweight commitment module.
"""

from typing import Dict, Any, List
import math

import commitment
import violation_iop
from r1cs_utils import constraint_support, eval_constraint


class Prover:
    """
    Prover that can commit to a witness and produce a simple violation transcript.
    """

    def __init__(self):
        # placeholder for configuration; in a real system we might pass a crypto backend
        pass

    def _ensure_one(self, witness: Dict[str, float]) -> None:
        """
        Ensure the special ONE variable (constant 1) is present in the witness.
        """
        if "ONE" not in witness:
            witness["ONE"] = 1.0

    def commit_witness(self, witness: Dict[str, float]) -> Dict[str, str]:
        """
        Commit to the entire witness mapping by committing to the map as a whole.
        Returns a dict mapping a label (we use "WITNESS") or each variable name to commitment hex.
        For flexibility we commit to the full mapping under a single commitment,
        and also include per-variable single commits (useful in tests).
        """
        self._ensure_one(witness)
        # commit full mapping
        full_commit, full_nonce = commitment.commit_map(witness)
        # store the nonce in an opening map for later use by prover
        # (in production this would be secret and only revealed when opening)
        self._full_opening_nonce = full_nonce
        self._full_commitment = full_commit
        # also compute per-variable commitments (useful for per-var opening)
        per_var = {}
        for var, val in sorted(witness.items()):
            c, n = commitment.commit_map({var: val})
            per_var[var] = {"commit": c, "nonce": n}
        # store per-var openings (only the prover has the nonces)
        self._per_var_openings = {v: {"mapping": {v: witness[v]}, "nonce": per_var[v]["nonce"]} for v in per_var}
        return {"WITNESS": full_commit, **{v: per_var[v]["commit"] for v in per_var}}

    def make_proof(self,
                   r1cs: Dict[str, Any],
                   witness: Dict[str, float],
                   candidate_idxs: List[int]) -> Dict[str, Any]:
        """
        Produce a transcript for the given candidate constraint indices.

        :param r1cs: R1CS-like dict (variables, constraints)
        :param witness: mapping var_name->numeric value
        :param candidate_idxs: list of constraint indices to check and possibly open
        :return: transcript dict (violation_iop.make_transcript)
        """
        # ensure ONE is present
        self._ensure_one(witness)

        # produce witness commitments
        witness_commits = self.commit_witness(witness)

        # build violation entries
        entries = []
        constraints = r1cs.get("constraints", [])
        for idx in candidate_idxs:
            if idx < 0 or idx >= len(constraints):
                continue
            c = constraints[idx]
            # compute residual under witness: (A(w) * B(w) - C(w))
            residual = eval_constraint(c, witness)
            # small numerical zero tolerance
            is_zero = math.isclose(residual, 0.0, rel_tol=1e-9, abs_tol=1e-12)
            if not is_zero:
                # prepare opening: only reveal variables that appear in the constraint
                supp = constraint_support(c)
                opening_map = {v: witness.get(v) for v in supp}
                # For demo we either reuse per-variable openings (if available) or create fresh opening
                # Use commitment.open_map (map + nonce must match the committed per-variable entries if we included them)
                # Here we reuse the per-var openings stored earlier when committing
                # Build opening object mapping -> nonce (if found) else compute a fresh nonce commit (less realistic)
                # For consistency we will use commitment.open_map with the existing nonce stored in self._per_var_openings if present
                opening_nonce = None
                opening_obj = None
                # If all variables were individually committed earlier, build a joint opening using those nonces (not cryptographically combined)
                # For prototype we just provide one combined opening (mapping + new nonce) which the verifier will check against the 'WITNESS' commit.
                # Create combined opening that pairs with the 'WITNESS' commitment: use stored full_nonce
                opening_obj = commitment.open_map(opening_map, self._full_opening_nonce)
                entries.append({
                    "idx": idx,
                    "residual": residual,
                    "opening": opening_obj,
                    "source": c.get("source", "")
                })
            else:
                # if satisfied, we still can include a short note (verifier doesn't need openings)
                entries.append({
                    "idx": idx,
                    "residual": 0.0,
                    "opening": None,
                    "source": c.get("source", "")
                })

        # assemble transcript
        meta = {"candidate_count": len(candidate_idxs)}
        tx = violation_iop.make_transcript(witness_commitments, entries, meta=meta)
        # Prover might serialize and sign tx in a real system; we skip that here.
        return tx


# Demo usage
if __name__ == "__main__":
    # tiny R1CS: c = a * b
    r1cs = {
        "variables": {"ONE": 0, "a": 1, "b": 2, "c": 3},
        "constraints": [
            {"A": {"a": 1.0}, "B": {"b": 1.0}, "C": {"c": 1.0}, "source": "c <== a * b;"},
            {"A": {"a": 1.0, "b": 1.0}, "B": {"ONE": 1.0}, "C": {"d": 1.0}, "source": "d <== a + b;"}
        ],
        "meta": {}
    }
    witness = {"ONE": 1.0, "a": 3.0, "b": 4.0, "c": 12.0}
    p = Prover()
    tx = p.make_proof(r1cs, witness, candidate_idxs=[0, 1])
    print(violation_iop.serialize_transcript(tx))
