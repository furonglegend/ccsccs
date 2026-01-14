"""
commitment.py

Simple hash-based commitment backend for prototyping.

NOT FOR PRODUCTION: uses SHA-256 over a canonical JSON representation
of a mapping and a random nonce. This is useful for testing protocol logic.

API:
 - commit_map(mapping: Dict[str, float]) -> (commitment_hex, nonce)
 - open_map(mapping, nonce) -> opening (mapping, nonce)
 - verify_commit(commitment_hex, opening) -> bool
"""

import json
import hashlib
import secrets
from typing import Dict, Tuple, Any


def _canonical_serialize_map(m: Dict[str, Any]) -> str:
    """
    Serialize a mapping in canonical order to bytes-safe string (deterministic).
    """
    # sort keys for deterministic ordering
    return json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def commit_map(mapping: Dict[str, Any]) -> Tuple[str, str]:
    """
    Commit to a mapping (e.g., var_name -> numeric value).
    Returns (commitment_hex, nonce).
    """
    nonce = secrets.token_hex(16)
    serial = _canonical_serialize_map(mapping)
    blob = f"{serial}|{nonce}".encode("utf-8")
    h = hashlib.sha256(blob).hexdigest()
    return h, nonce


def open_map(mapping: Dict[str, Any], nonce: str) -> Dict[str, Any]:
    """
    Build an 'opening' object combining the mapping and nonce.
    """
    # In a real commitment scheme the opening may contain proofs; here it's just the data.
    return {"mapping": mapping, "nonce": nonce}


def verify_commit(commitment_hex: str, opening: Dict[str, Any]) -> bool:
    """
    Verify that opening corresponds to commitment_hex.
    """
    mapping = opening.get("mapping")
    nonce = opening.get("nonce")
    if mapping is None or nonce is None:
        return False
    serial = _canonical_serialize_map(mapping)
    blob = f"{serial}|{nonce}".encode("utf-8")
    h = hashlib.sha256(blob).hexdigest()
    return h == commitment_hex


# Optional helper: commit a single variable value (name->value)
def commit_single_var(var_name: str, value: Any) -> Tuple[str, str]:
    return commit_map({var_name: value})


# Demo
if __name__ == "__main__":
    demo_map = {"a": 3.0, "b": 5.0, "ONE": 1.0}
    commit, nonce = commit_map(demo_map)
    print("commit:", commit)
    opening = open_map(demo_map, nonce)
    ok = verify_commit(commit, opening)
    print("verify:", ok)
