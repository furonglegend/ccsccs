"""
r1cs_utils.py

Utility functions for manipulating and inspecting a small R1CS-like structure.

Expected R1CS format (matching the runner/parser earlier):
{
  "variables": {"ONE": 0, "a": 1, "b": 2, ...},   # variable -> index
  "constraints": [
      {"A": {"a": 1.0}, "B": {"b": 1.0}, "C": {"c": 1.0}, "source": "c <== a * b;"},
      ...
  ],
  "meta": {...}
}

This module intentionally keeps things lightweight and uses numpy for small linear algebra tasks.
"""

from typing import Dict, List, Tuple, Any, Set, Iterable
import numpy as np


def build_var_index(r1cs: Dict[str, Any]) -> Tuple[Dict[str, int], List[str]]:
    """
    Return (name_to_idx, idx_to_name_list) ensuring stable ordering.

    The parser already produces a mapping, but this function normalizes and
    produces a list ordered by index for easy iteration.
    """
    vars_map = r1cs.get("variables", {})
    # invert and sort by index to create idx->name list
    max_idx = max(vars_map.values()) if vars_map else -1
    idx_to_name = [None] * (max_idx + 1)
    for name, idx in vars_map.items():
        if idx < 0:
            raise ValueError("variable indices must be non-negative")
        if idx >= len(idx_to_name):
            # expand if sparse indices present
            extend_by = idx - len(idx_to_name) + 1
            idx_to_name.extend([None] * extend_by)
        idx_to_name[idx] = name
    # replace any None with placeholder (shouldn't generally happen)
    for i, n in enumerate(idx_to_name):
        if n is None:
            idx_to_name[i] = f"<var_{i}_missing>"
    return vars_map.copy(), idx_to_name


def constraints_to_dense_matrices(r1cs: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert sparse constraint dictionaries into dense numpy matrices A, B, C.

    Returns:
        A, B, C: numpy arrays of shape (m_constraints, n_variables)
    """
    vars_map, idx_to_name = build_var_index(r1cs)
    n = len(idx_to_name)
    constraints = r1cs.get("constraints", [])
    m = len(constraints)

    A = np.zeros((m, n), dtype=float)
    B = np.zeros((m, n), dtype=float)
    C = np.zeros((m, n), dtype=float)

    for i, c in enumerate(constraints):
        for var, coeff in c.get("A", {}).items():
            if var not in vars_map:
                # unknown var: dynamic add is not supported here; raise for visibility
                raise KeyError(f"Unknown variable '{var}' referenced in constraint A at index {i}")
            A[i, vars_map[var]] = float(coeff)
        for var, coeff in c.get("B", {}).items():
            if var not in vars_map:
                raise KeyError(f"Unknown variable '{var}' referenced in constraint B at index {i}")
            B[i, vars_map[var]] = float(coeff)
        for var, coeff in c.get("C", {}).items():
            if var not in vars_map:
                raise KeyError(f"Unknown variable '{var}' referenced in constraint C at index {i}")
            C[i, vars_map[var]] = float(coeff)

    return A, B, C


def eval_linear_form(linear: Dict[str, float], assignment: Dict[str, float], default_zero: float = 0.0) -> float:
    """
    Evaluate a linear form represented as a dict var->coeff under a variable assignment.
    assignment: mapping var_name -> numeric value
    """
    s = 0.0
    for var, coeff in linear.items():
        val = assignment.get(var, default_zero)
        s += float(coeff) * float(val)
    return s


def eval_constraint(constraint: Dict[str, Any], assignment: Dict[str, float]) -> float:
    """
    Evaluate A(assignment) * B(assignment) - C(assignment).
    Returns the residual (should be zero for a satisfied constraint).
    """
    a_val = eval_linear_form(constraint.get("A", {}), assignment)
    b_val = eval_linear_form(constraint.get("B", {}), assignment)
    c_val = eval_linear_form(constraint.get("C", {}), assignment)
    return (a_val * b_val) - c_val


def constraint_support(constraint: Dict[str, Any]) -> Set[str]:
    """
    Return the set of variable names that appear in the constraint (A or B or C).
    """
    s = set()
    for part in ("A", "B", "C"):
        s.update(constraint.get(part, {}).keys())
    return s


def constraint_nz_count(constraint: Dict[str, Any]) -> int:
    """
    Number of non-zero coefficient entries across A,B,C.
    """
    cnt = 0
    for part in ("A", "B", "C"):
        cnt += len([v for v in constraint.get(part, {}).values() if float(v) != 0.0])
    return cnt


def to_triplet_list(r1cs: Dict[str, Any]) -> List[Tuple[int, int, float, str]]:
    """
    Convert constraints into a triplet list of non-zero entries:
    returns list of tuples (constraint_idx, var_idx, coeff, part) where part in {'A','B','C'}.
    """
    vars_map, idx_to_name = build_var_index(r1cs)
    triplets = []
    for i, c in enumerate(r1cs.get("constraints", [])):
        for part in ("A", "B", "C"):
            for var, coeff in c.get(part, {}).items():
                if var not in vars_map:
                    raise KeyError(f"Unknown variable '{var}' in constraint {i} part {part}")
                triplets.append((i, vars_map[var], float(coeff), part))
    return triplets


def constraint_summary(constraint: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a small summary dict for a constraint describing its support and sparsity.
    """
    supp = constraint_support(constraint)
    return {
        "support_size": len(supp),
        "nz_count": constraint_nz_count(constraint),
        "support": sorted(list(supp)),
        "source": constraint.get("source", "")
    }


# Example quick utility: find constraints referencing a variable
def constraints_referencing_var(r1cs: Dict[str, Any], var_name: str) -> List[int]:
    """
    Return a list of constraint indices that mention var_name.
    """
    idxs = []
    for i, c in enumerate(r1cs.get("constraints", [])):
        if var_name in constraint_support(c):
            idxs.append(i)
    return idxs
