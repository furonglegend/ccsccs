"""
solver_fallback.py

Fallback solving utilities used by extractor when openings are partial.

Capabilities:
 - solve_linear_constraints(r1cs, partial_assignment)
     Attempt to solve linear constraints that have the form (A) * ONE = C (i.e. B == ONE),
     producing values for unknown variables by solving a linear system via numpy.
 - brute_force_search(r1cs, partial_assignment, unknown_vars, domain_range, max_trials)
     Exhaustively search small domains for unknowns and test constraints residuals.

The module returns a completed witness mapping (if found) or raises an exception.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import math

from r1cs_utils import constraint_support


def solve_linear_constraints(r1cs: Dict[str, Any], partial: Dict[str, float]) -> Optional[Dict[str, float]]:
    """
    Attempt to fill unknown variables by solving linear constraints of the form:
        (A) * (ONE) = (C)  --> A(vars) = C(vars)
    where B is exactly ONE (i.e., multiplication by the constant 1), so the constraint reduces to linear equality.

    The method:
      - Collect all constraints where B == {"ONE": 1.0} (or equivalent)
      - Convert each to a linear equation over unknown variables and known constants (from partial)
      - Solve the linear system with numpy.linalg.lstsq (or solve when square)

    Returns:
      completed_assignment dict if system is solvable (and residual small), else None.
    """
    vars_map = r1cs.get("variables", {})
    constraints = r1cs.get("constraints", [])

    # Build linear equations: rows * x_unknown = rhs
    eq_rows = []
    eq_rhs = []
    unknown_vars = set()
    for c in constraints:
        B = c.get("B", {})
        # require B equals ONE variable only (coefficient 1)
        if len(B) == 1 and ("ONE" in B) and float(B["ONE"]) == 1.0:
            # equation: sum_i A_i * v_i = C
            A = c.get("A", {})
            C = c.get("C", {})
            # compute numeric RHS using partial for C (if C contains variables not in partial, treat as unknown)
            # represent unknowns as variables in unknown_vars
            # We'll express the equation as sum(coeff_known * known_val) + sum(coeff_unknown * x_var) = RHS_const
            lhs_unknown = {}
            lhs_known_total = 0.0
            # A side
            for var, coeff in A.items():
                coeff = float(coeff)
                if var in partial:
                    lhs_known_total += coeff * float(partial[var])
                else:
                    lhs_unknown[var] = lhs_unknown.get(var, 0.0) + coeff
                    unknown_vars.add(var)
            # right side: C (linear)
            rhs_known_total = 0.0
            rhs_unknown = {}
            for var, coeff in C.items():
                coeff = float(coeff)
                if var in partial:
                    rhs_known_total += coeff * float(partial[var])
                else:
                    rhs_unknown[var] = rhs_unknown.get(var, 0.0) + coeff
                    unknown_vars.add(var)
            # Move all unknown terms to LHS: (lhs_unknown - rhs_unknown)*x = rhs_known_total - lhs_known_total
            combined_unknown = {}
            for v, coef in lhs_unknown.items():
                combined_unknown[v] = combined_unknown.get(v, 0.0) + coef
            for v, coef in rhs_unknown.items():
                combined_unknown[v] = combined_unknown.get(v, 0.0) - coef
            rhs_const = rhs_known_total - lhs_known_total
            if not combined_unknown:
                # no unknowns in this equation; check consistency
                if abs(rhs_const) > 1e-9:
                    # inconsistent equation -> no solution
                    return None
                else:
                    continue
            # save equation: coefficients for unknown vars in consistent ordering
            eq_rows.append((combined_unknown, rhs_const))

    if not eq_rows:
        # nothing to solve linearly
        return None

    # Determine unknown var list in deterministic order
    unknown_list = sorted(list(unknown_vars))
    m = len(eq_rows)
    n = len(unknown_list)
    A_mat = np.zeros((m, n), dtype=float)
    b_vec = np.zeros((m,), dtype=float)
    for i, (coef_map, rhs_const) in enumerate(eq_rows):
        for j, v in enumerate(unknown_list):
            A_mat[i, j] = float(coef_map.get(v, 0.0))
        b_vec[i] = float(rhs_const)

    # Attempt to solve (least squares if overdetermined)
    try:
        if m == n:
            sol = np.linalg.solve(A_mat, b_vec)
        else:
            sol, residuals, rank, s = np.linalg.lstsq(A_mat, b_vec, rcond=None)
            # check residuals small
            if residuals.size > 0 and not math.isclose(residuals.sum(), 0.0, rel_tol=1e-9, abs_tol=1e-9):
                return None
    except np.linalg.LinAlgError:
        return None

    # build completed assignment by merging partial + solved unknowns
    completed = dict(partial)
    for j, v in enumerate(unknown_list):
        completed[v] = float(sol[j])

    return completed


def _evaluate_constraint_residual(constraint: Dict[str, Any], assignment: Dict[str, float]) -> float:
    """
    Evaluate residual (A(assignment)*B(assignment) - C(assignment)).
    Missing variables are treated as zero.
    """
    def eval_lin(lin):
        s = 0.0
        for var, coef in lin.items():
            val = assignment.get(var, 0.0)
            s += float(coef) * float(val)
        return s
    a = eval_lin(constraint.get("A", {}))
    b = eval_lin(constraint.get("B", {}))
    c = eval_lin(constraint.get("C", {}))
    return (a * b) - c


def brute_force_search(r1cs: Dict[str, Any],
                       partial: Dict[str, float],
                       unknown_vars: List[str],
                       domain_range: Tuple[int, int] = (0, 5),
                       max_trials: int = 100000) -> Optional[Dict[str, float]]:
    """
    Brute-force search for small numbers of unknown variables.

    - domain_range is inclusive [low, high] integer domain for each unknown var.
    - stops when a full assignment that satisfies all constraints (residuals close to 0) is found.
    - max_trials limits the total number of assignments tested.

    Returns completed assignment dict or None if not found within limits.
    """
    low, high = domain_range
    domain = list(range(low, high + 1))
    k = len(unknown_vars)
    if k == 0:
        return partial

    # quick check: estimate number of trials
    total = len(domain) ** k
    if total > max_trials:
        # too big to search
        return None

    # iterate cartesian product (iterative nested loops)
    indices = [0] * k
    tried = 0
    while True:
        assign = dict(partial)
        for i, v in enumerate(unknown_vars):
            assign[v] = float(domain[indices[i]])
        # test all constraints
        ok = True
        for c in r1cs.get("constraints", []):
            res = _evaluate_constraint_residual(c, assign)
            if abs(res) > 1e-9:
                ok = False
                break
        if ok:
            return assign
        tried += 1
        if tried >= max_trials:
            return None
        # increment indices
        pos = k - 1
        while pos >= 0:
            indices[pos] += 1
            if indices[pos] < len(domain):
                break
            indices[pos] = 0
            pos -= 1
        if pos < 0:
            break
    return None
