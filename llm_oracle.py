"""
llm_oracle.py

A small, pluggable "LLM Oracle" abstraction.

Design goals:
 - Deterministic stub mode (default) which produces repeatable candidates for a "weak_assignment".
 - Optional OpenAI-based mode if OPENAI_API_KEY exists and `openai` package is installed.
 - API yields a small list of candidate RHS expressions or numeric constants (strings),
   with deterministic ordering (top-1 is first).

Interface:
  LLMOracle(mode="stub"|"openai", model_name=..., max_tokens=..., debug=False)
    - mutation_oracle(weak_assignment: str, context: dict=None, top_k: int=5) -> List[str]
      returns list of candidate RHS strings (e.g., ["0", "1", "otherVar", "a + b"])

Notes:
 - The stub uses a hashing-based deterministic generator combining the weak assignment name and optional
   context to propose small integers and copies of other variable names seen in context.
 - If OpenAI paths are used, the code attempts a deterministic call (temperature=0, top_p=1)
   but gracefully falls back to the stub on any exception.
"""

from typing import List, Optional, Dict, Any
import os
import hashlib
import json

# Try to import openai if present, but do not require it
_OPENAI_AVAILABLE = False
try:
    import openai  # type: ignore
    _OPENAI_AVAILABLE = True
except Exception:
    _OPENAI_AVAILABLE = False


class LLMOracle:
    """
    LLM Oracle abstraction.
    """

    def __init__(self, mode: str = "stub", model_name: str = "gpt-4o-mini", max_tokens: int = 128, debug: bool = False):
        """
        mode: "stub" or "openai". If "openai" requested but OpenAI package or key missing,
              constructor falls back to "stub".
        """
        self.debug = debug
        self.model_name = model_name
        self.max_tokens = max_tokens
        if mode == "openai" and _OPENAI_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
            self.mode = "openai"
            openai.api_key = os.environ.get("OPENAI_API_KEY")
        else:
            if mode == "openai" and (not _OPENAI_AVAILABLE or not os.environ.get("OPENAI_API_KEY")):
                if self.debug:
                    print("[LLMOracle] OpenAI not available or OPENAI_API_KEY missing; using stub mode.")
            self.mode = "stub"

    def mutation_oracle(self, weak_assignment: str, context: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[str]:
        """
        Provide up to top_k candidate RHS expressions for the given weak_assignment.
        context: optional dict that can include "signals": list of variable names, "recent_values": mapping etc.
        """
        context = context or {}
        # If OpenAI mode and operational, try remote call
        if self.mode == "openai":
            try:
                return self._call_openai(weak_assignment, context, top_k)
            except Exception as e:
                if self.debug:
                    print("[LLMOracle] OpenAI call failed, falling back to stub:", e)
                # fall through to stub

        return self._deterministic_stub(weak_assignment, context, top_k)

    def _deterministic_stub(self, weak_assignment: str, context: Dict[str, Any], top_k: int) -> List[str]:
        """
        Deterministic candidate generation:
          - small integer constants [0,1,2,3,4,...]
          - common constants [1,0,-1]
          - copy candidates from 'signals' in context, prioritized by lexical closeness to the weak_assignment
          - simple linear combos a + b if two signals available
        Determinism achieved by hashing weak_assignment + context json.
        """
        seed_material = weak_assignment + "|" + json.dumps(context, sort_keys=True)
        h = hashlib.sha256(seed_material.encode("utf-8")).digest()
        # pick base small ints deterministically from hash bytes
        ints = []
        for i in range(8):
            ints.append((h[i] % 7) - 1)  # value range [-1,5]
        # unique and keep order
        seen = set()
        candidates = []
        for v in ints:
            if v not in seen:
                seen.add(v)
                candidates.append(str(int(v)))
        # add common constants and ONE
        for c in ["1", "0", "-1"]:
            if c not in seen:
                seen.add(c)
                candidates.append(c)
        # include signals from context (if any), sorted by name closeness
        signals = context.get("signals", []) or []
        # score by simple levenshtein-like heuristic (here: common prefix length)
        def closeness(a, b):
            # compute common prefix length
            i = 0
            while i < len(a) and i < len(b) and a[i] == b[i]:
                i += 1
            return i
        sorted_signals = sorted(signals, key=lambda s: (-closeness(s, weak_assignment), s))
        for s in sorted_signals:
            if s not in seen:
                seen.add(s)
                candidates.append(s)
        # add simple linear combos if we have at least two signals
        if len(sorted_signals) >= 2:
            a, b = sorted_signals[0], sorted_signals[1]
            combo = f"{a} + {b}"
            if combo not in seen:
                candidates.append(combo)
        # ensure deterministic truncation
        return candidates[:top_k]

    def _call_openai(self, weak_assignment: str, context: Dict[str, Any], top_k: int) -> List[str]:
        """
        Example OpenAI completion call (deterministic settings). This function is intentionally
        conservative: temperature 0, top_p 1, n=top_k, best_of=1.

        NOTE: this code will attempt a network call; caller must ensure environment and package.
        """
        if not _OPENAI_AVAILABLE:
            raise RuntimeError("OpenAI package not available")
        prompt = self._build_prompt(weak_assignment, context)
        resp = openai.ChatCompletion.create(
            model=self.model_name,
            messages=[{"role": "system", "content": "You are a deterministic assistant that proposes RHS expressions for a small circuit variable assignment."},
                      {"role": "user", "content": prompt}],
            temperature=0.0,
            top_p=1.0,
            n=1,
            max_tokens=self.max_tokens
        )
        # parse up to top_k lines from the assistant's reply
        text = resp["choices"][0]["message"]["content"]
        # split by newlines and commas, sanitize
        cand = []
        for part in [p.strip() for p in text.replace(",", "\n").splitlines() if p.strip()]:
            if part not in cand:
                cand.append(part)
            if len(cand) >= top_k:
                break
        return cand[:top_k]

    def _build_prompt(self, weak_assignment: str, context: Dict[str, Any]) -> str:
        """
        Build a concise prompt describing the weak assignment and available context.
        """
        lines = [f"Propose up to 8 plausible RHS expressions (short) for the weak assignment variable: '{weak_assignment}'.",
                 "Return only the candidate expressions, one per line, no extra commentary.",
                 ""]
        if "signals" in context:
            lines.append("Available signals: " + ", ".join(context.get("signals", [])))
        if "recent_values" in context:
            lines.append("Recent values (var:val): " + ", ".join(f"{k}:{v}" for k, v in context.get("recent_values", {}).items()))
        return "\n".join(lines)


# Demo when run as script
if __name__ == "__main__":
    oracle = LLMOracle(mode="stub", debug=True)
    print("Candidates:", oracle.mutation_oracle("weak_x", {"signals": ["a", "b", "out", "weak_x"]}, top_k=6))
