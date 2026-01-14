"""
violation_iop.py

Small transcript builder/serializer for violation proofs.

The ViolationIOP collects:
  - witness commitments (per-commitment hex)
  - a list of candidate constraint entries, each containing:
      - constraint index
      - residual (numeric)
      - the opening for the variables in the constraint (var->value) and nonce
  - a top-level digest for transcript integrity (sha256)

This module is intentionally small and works with the 'commitment' module
and the 'Prover' implementation below.
"""

from typing import Dict, Any, List
import hashlib
import json


def _transcript_digest(transcript: Dict[str, Any]) -> str:
    """
    Deterministic digest over the transcript for tamper-evidence.
    """
    s = json.dumps(transcript, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def make_transcript(witness_commitments: Dict[str, str],
                    violation_entries: List[Dict[str, Any]],
                    meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Build a canonical transcript structure.

    :param witness_commitments: mapping var_name -> commitment_hex (strings)
    :param violation_entries: list of dicts with keys:
                - idx: constraint index (int)
                - residual: numeric residual value
                - opening: {"mapping": {var->val}, "nonce": str}
                - source: optional source string (constraint source text)
    :param meta: optional metadata dictionary
    :return: transcript dict with an added 'digest' field
    """
    meta = meta or {}
    tx = {
        "witness_commitments": witness_commitments,
        "violations": violation_entries,
        "meta": meta
    }
    tx["digest"] = _transcript_digest(tx)
    return tx


def serialize_transcript(transcript: Dict[str, Any]) -> str:
    """
    Deterministic JSON serialization of transcript.
    """
    return json.dumps(transcript, sort_keys=True, indent=2, separators=(",", ":"), ensure_ascii=False)


def validate_transcript_digest(transcript: Dict[str, Any]) -> bool:
    """
    Validate digest is consistent with transcript content.
    """
    expected = transcript.get("digest")
    if not expected:
        return False
    # compute digest of transcript without 'digest' field
    copy = {k: v for k, v in transcript.items() if k != "digest"}
    actual = _transcript_digest(copy)
    return actual == expected


# Demo small self-check
if __name__ == "__main__":
    wc = {"a": "deadbeef", "b": "cafebabe"}
    ve = [{"idx": 0, "residual": 1.23, "opening": {"mapping": {"a": 2.0}, "nonce": "abcd"}, "source": "c <== a*b;"}]
    tx = make_transcript(wc, ve, meta={"note": "demo"})
    s = serialize_transcript(tx)
    print(s)
    print("digest ok:", validate_transcript_digest(tx))
