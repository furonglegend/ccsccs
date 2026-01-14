"""
smt_interface.py

Thin wrapper for interacting with an SMT solver (Z3). Two modes:
 1) Python Z3 API (preferred) if `z3` package is importable.
 2) Offline z3 executable via subprocess with SMT-LIB2 encoding (fallback).
If neither is available the interface will gracefully report unavailability.

Primary function:
  - solve_integer_constraints(r1cs, partial_assignment, unknown_vars, timeout_s)

Limitations:
  - Only supports integer domains.
  - Multiplication constraints are supported best-effort (Z3's non-linear solver).
  - For heavy or production use, replace with robust model and careful encoding.
"""

from typing import Dict, Any, List, Optional
import shutil
import subprocess
import tempfile
import os
import json

_HAS_Z3 = False
try:
    import z3  # type: ignore
    _HAS_Z3 = True
except Exception:
    _HAS_Z3 = False

class SMTInterface:
    """
    SMT wrapper.
    """

    def __init__(self):
        # check for z3 binary presence
        self.z3_bin = shutil.which("z3")
        self.has_z3_py = _HAS_Z3

    def _supports_execution(self) -> bool:
        return self.has_z3_py or (self.z3_bin is not None)

    def solve_integer_constraints(self,
                                  r1cs: Dict[str, Any],
                                  partial_assignment: Dict[str, float],
                                  unknown_vars: List[str],
                                  timeout_s: int = 5) -> Optional[Dict[str, int]]:
        """
        Try to solve for integer values for unknown_vars satisfying all constraints,
        using partial_assignment as fixed values for some variables.

        Returns mapping var -> int if successful, else None.

        Strategy:
         - Prefer Python z3 API if available.
         - Else, build an SMT-LIB2 script and call `z3 -in`.
        """
        if not self._supports_execution():
            return None

        # build expressions for constraints: each constraint is (A(vars) * B(vars) == C(vars))
        # We'll declare all vars as Int
        if self.has_z3_py:
            return self._solve_with_z3py(r1cs, partial_assignment, unknown_vars, timeout_s)
        else:
            return self._solve_with_z3bin(r1cs, partial_assignment, unknown_vars, timeout_s)

    def _solve_with_z3py(self, r1cs, partial, unknowns, timeout_s):
        import z3  # type: ignore
        s = z3.Solver()
        s.set("timeout", int(timeout_s * 1000))
        # declare Int vars
        z3_vars = {}
        for v in r1cs.get("variables", {}).keys():
            z3_vars[v] = z3.Int(v)
        # assert partial assignments
        for k, val in partial.items():
            if k not in z3_vars:
                continue
            # require partial to be integer
            s.add(z3_vars[k] == int(round(float(val))))
        # build constraints
        for c in r1cs.get("constraints", []):
            A = c.get("A", {})
            B = c.get("B", {})
            C = c.get("C", {})
            # build linear expressions sum(coeff * var)
            def mk_lin(m):
                expr = None
                for var, coeff in m.items():
                    if var not in z3_vars:
                        continue
                    term = z3_vars[var] * int(round(float(coeff)))
                    expr = term if expr is None else expr + term
                return expr if expr is not None else z3.IntVal(0)
            a_expr = mk_lin(A)
            b_expr = mk_lin(B)
            c_expr = mk_lin(C)
            # form multiplication equality
            s.add(a_expr * b_expr == c_expr)
        # check
        if s.check() == z3.sat:
            m = s.model()
            result = {}
            for v in unknowns:
                if v in z3_vars:
                    val = m.eval(z3_vars[v], model_completion=True)
                    try:
                        result[v] = int(val.as_long())
                    except Exception:
                        # fallback: try to coerce
                        try:
                            result[v] = int(str(val))
                        except Exception:
                            result[v] = 0
            return result
        return None

    def _solve_with_z3bin(self, r1cs, partial, unknowns, timeout_s):
        # Build an SMT-LIB2 script into a temp file and call z3 -smt2 -in
        decls = []
        asserts = []
        for v in r1cs.get("variables", {}).keys():
            decls.append(f"(declare-const {v} Int)")
        # partials
        for k, val in partial.items():
            asserts.append(f"(assert (= {k} {int(round(float(val)))}) )")
        # constraints
        def lin_to_smt(m):
            terms = []
            for var, coeff in m.items():
                terms.append(f"(* {int(round(float(coeff)))} {var})")
            if not terms:
                return "0"
            if len(terms) == 1:
                return terms[0]
            return f"(+ {' '.join(terms)})"
        for c in r1cs.get("constraints", []):
            A = c.get("A", {})
            B = c.get("B", {})
            C = c.get("C", {})
            a_smt = lin_to_smt(A)
            b_smt = lin_to_smt(B)
            c_smt = lin_to_smt(C)
            asserts.append(f"(assert (= (* {a_smt} {b_smt}) {c_smt}) )")
        # ask for check-sat and get-model
        script = "\n".join(decls + asserts + [f"(check-sat)", "(get-model)"])
        # call z3
        try:
            proc = subprocess.Popen([self.z3_bin, "-in"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, err = proc.communicate(script, timeout=timeout_s)
        except Exception:
            return None
        if not out:
            return None
        # parse model (very naive): look for lines like (define-fun x () Int 3)
        res = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("(define-fun"):
                # try to parse
                parts = line.split()
                if len(parts) >= 5:
                    name = parts[1]
                    # value is last token before ')'
                    try:
                        val_token = parts[-1].rstrip(")")
                        val = int(val_token)
                        if name in unknowns:
                            res[name] = val
                    except Exception:
                        continue
        return res if res else None
