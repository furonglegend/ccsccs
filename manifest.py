"""
manifest.py

Simple manifest manager for recording run metadata to disk (JSON).
Provides atomic write and basic validation.

Manifest example fields:
{
  "run_id": "20260114T123456_abcd",
  "input": "circuit.circom",
  "backend": "hyperplonk",
  "degree": 1024,
  "domain_size": 65536,
  "timestamp": "...",
  "notes": "..."
}

API:
 - ManifestManager(path).write(manifest_dict)
 - ManifestManager(path).read() -> dict
 - validate_manifest(manifest) -> (ok, issues_list)
"""

from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path
import json
import tempfile
import os
from datetime import datetime
from utils import write_json_atomic, timestamp_iso


class ManifestManager:
    def __init__(self, path: str):
        self.path = Path(path)

    def write(self, manifest: Dict[str, Any]) -> None:
        """
        Atomically write manifest to self.path (JSON).
        """
        # set timestamp if missing
        manifest = dict(manifest)
        if "timestamp" not in manifest:
            manifest["timestamp"] = timestamp_iso()
        write_json_atomic(str(self.path), manifest)

    def read(self) -> Optional[Dict[str, Any]]:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def ensure_and_merge(self, base: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read existing manifest, merge with base (base overwrites), write back, and return merged manifest.
        """
        existing = self.read() or {}
        merged = dict(existing)
        merged.update(base)
        if "timestamp" not in merged:
            merged["timestamp"] = timestamp_iso()
        self.write(merged)
        return merged


def validate_manifest(manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Simple checks on manifest content.
    """
    issues: List[str] = []
    if "run_id" not in manifest:
        issues.append("missing run_id")
    if "backend" not in manifest:
        issues.append("missing backend")
    if "timestamp" in manifest:
        try:
            datetime.fromisoformat(manifest["timestamp"])
        except Exception:
            issues.append("timestamp not ISO format")
    return (len(issues) == 0, issues)


# demo
if __name__ == "__main__":
    mgr = ManifestManager("demo.manifest.json")
    m = {"run_id": "demo123", "input": "c1.circom", "backend": "fallback-smt", "degree": 1024}
    mgr.write(m)
    r = mgr.read()
    print("Read manifest:", r)
    ok, issues = validate_manifest(r)
    print("Validate:", ok, issues)
