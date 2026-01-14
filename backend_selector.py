"""
backend_selector.py

Choose which proving backend to use based on simple heuristics:
  - polynomial degree (deg)
  - domain size (|D|)
  - environment flags indicating crypto libraries available

This prototype returns one of:
  - "hyperplonk" (preferred ZK-native)
  - "basefold"  (alternative ZK-native)
  - "fallback-smt" (use SMT/Solver-assisted path)
  - "noop" (no viable backend)

Configuration is passed as a small dict or via environment variables.
"""

from typing import Dict, Any, Optional
import os


DEFAULT_THRESHOLDS = {
    "max_degree_hyperplonk": 4096,   # example threshold
    "max_domain_hyperplonk": 1 << 20,  # 1M
    "max_degree_basefold": 16384,
    "max_domain_basefold": 1 << 22,  # 4M
}


class BackendSelector:
    """
    Heuristic backend selector.

    Typical usage:
        sel = BackendSelector()
        backend = sel.choose_backend(degree=1024, domain_size=65536)
    """

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None):
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    def _crypto_available(self) -> bool:
        """
        Detect presence of 'crypto' backends heuristically via environment variables.
        Users can set BACKEND_AVAILABLE=hyperplonk,basefold to override.
        """
        env = os.environ.get("BACKEND_AVAILABLE")
        if env:
            available = [s.strip().lower() for s in env.split(",") if s.strip()]
            return len(available) > 0
        # fallback: check for presence of an env var indicating kzg/kate support
        return bool(os.environ.get("KZG_AVAILABLE") or os.environ.get("HYPERPLONK_AVAILABLE"))

    def available_backends(self) -> Dict[str, bool]:
        """
        Return which backends appear available (heuristic).
        """
        available_list = (os.environ.get("BACKEND_AVAILABLE") or "").lower().split(",") if os.environ.get("BACKEND_AVAILABLE") else []
        return {
            "hyperplonk": "hyperplonk" in available_list or bool(os.environ.get("HYPERPLONK_AVAILABLE")),
            "basefold": "basefold" in available_list or bool(os.environ.get("BASEFOLD_AVAILABLE")),
            "smt": True  # solver-assisted path (assume always available)
        }

    def choose_backend(self, degree: int, domain_size: int, prefer: Optional[str] = None) -> str:
        """
        Decide which backend to use.

        Rules (prototype):
          - If prefer specified and available -> choose it.
          - If degree and domain_size within hyperplonk thresholds and hyperplonk available -> hyperplonk
          - Else if within basefold thresholds and basefold available -> basefold
          - Else fallback-smt
        """
        avail = self.available_backends()

        if prefer:
            pref = prefer.lower()
            if pref in avail and avail[pref]:
                return pref

        # try hyperplonk
        if avail.get("hyperplonk", False):
            if degree <= self.thresholds["max_degree_hyperplonk"] and domain_size <= self.thresholds["max_domain_hyperplonk"]:
                return "hyperplonk"

        # try basefold
        if avail.get("basefold", False):
            if degree <= self.thresholds["max_degree_basefold"] and domain_size <= self.thresholds["max_domain_basefold"]:
                return "basefold"

        # otherwise fallback
        return "fallback-smt"


# demo
if __name__ == "__main__":
    sel = BackendSelector()
    print("Choose for deg=1024,domain=65536 ->", sel.choose_backend(1024, 65536))
    print("Available backends (env):", sel.available_backends())
