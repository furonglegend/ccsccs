"""
rowvortex.py

A small prototype implementation of the "Row-Vortex" style polynomial coding helpers.

This module provides:
 - build_vandermonde(nodes, degree) -> Vandermonde matrix (numpy)
 - encode_rows_as_evaluations(rows, nodes) -> evaluate polynomials (rows are coefficient vectors)
 - decode_evaluations_to_rows(evals, nodes) -> interpolate to recover coefficients

This is a floating-point prototype intended for testing and debugging.
For cryptographic/finite-field correctness replace numpy float operations
with finite-field arithmetic (e.g., using galois or custom field impl).
"""

from typing import List, Sequence, Tuple
import numpy as np


def build_vandermonde(nodes: Sequence[float], degree: int) -> np.ndarray:
    """
    Build a Vandermonde matrix V where V[i, j] = nodes[i]**j for j in [0..degree-1].

    Args:
        nodes: iterable of distinct evaluation points (floats)
        degree: number of polynomial coefficients (polynomial degree = degree-1)

    Returns:
        numpy array shape (len(nodes), degree)
    """
    x = np.asarray(nodes, dtype=float)
    n = x.shape[0]
    deg = int(degree)
    V = np.vander(x, N=deg, increasing=True)  # columns: x^0, x^1, ..., x^(deg-1)
    return V


def encode_rows_as_evaluations(rows: List[Sequence[float]], nodes: Sequence[float]) -> np.ndarray:
    """
    Encode rows (each row is a list of polynomial coefficients [a0, a1, ...])
    by evaluating each polynomial at every node.

    Returns:
        evals: numpy array shape (len(rows), len(nodes)) where row i contains evaluations of polynomial i.
    """
    rows_arr = np.array(rows, dtype=float)  # shape (r, deg)
    r, deg = rows_arr.shape
    V = build_vandermonde(nodes, degree=deg)  # shape (len(nodes), deg)
    # Evaluate: for each row (coeffs) compute V @ coeffs
    evals = rows_arr @ V.T  # (r, deg) @ (deg, n_nodes) -> (r, n_nodes)
    return evals


def decode_evaluations_to_rows(evals: List[Sequence[float]], nodes: Sequence[float]) -> List[List[float]]:
    """
    Given polynomial evaluations (list of evaluation-vectors for each polynomial),
    interpolate to recover coefficient vectors.

    Args:
        evals: shape (r, n_nodes)
        nodes: length n_nodes
    Returns:
        list of coefficient lists (length = degree where degree == n_nodes)
    Note:
        This uses dense Vandermonde solve. For finite-field contexts, replace
        with a field-aware interpolation routine.
    """
    evals_arr = np.array(evals, dtype=float)
    r, n_nodes = evals_arr.shape
    V = build_vandermonde(nodes, degree=n_nodes)  # square Vandermonde
    # Solve V * coeffs = y for each polynomial y (column vector of length n_nodes)
    # We want coeffs of length n_nodes (degree n_nodes-1)
    coeffs = np.linalg.solve(V, evals_arr.T)  # result shape (n_nodes, r)
    # return as list of rows
    rows = [list(coeffs[:, i]) for i in range(coeffs.shape[1])]
    return rows


class RowVortex:
    """
    Simple wrapper class to encode/decode many rows using the same node set.
    This presents a clearer interface for integration with the pipeline.
    """

    def __init__(self, nodes: Sequence[float], row_degree: int):
        """
        nodes: evaluation points (must be distinct)
        row_degree: number of coefficients per row (polynomial degree + 1)
        """
        if len(nodes) < row_degree:
            # For invertibility we generally need at least row_degree nodes.
            raise ValueError("Number of nodes must be >= row_degree for square interpolation")
        self.nodes = list(nodes)
        self.row_degree = int(row_degree)
        self.vand = build_vandermonde(self.nodes, self.row_degree)  # shape (n_nodes, deg)
        # if square, precompute inverse for faster interpolation
        if len(self.nodes) == self.row_degree:
            self.vand_inv = np.linalg.inv(self.vand)
        else:
            self.vand_inv = None

    def encode(self, rows: List[Sequence[float]]) -> np.ndarray:
        """
        Encode multiple rows (each is a coefficient vector len==row_degree)
        -> returns evaluations shape (len(rows), len(nodes))
        """
        return encode_rows_as_evaluations(rows, self.nodes)

    def decode(self, evals: List[Sequence[float]]) -> List[List[float]]:
        """
        Decode evaluations back to coefficient rows. If vand_inv is available use it.
        """
        evals_arr = np.array(evals, dtype=float)  # shape (r, n_nodes)
        r, n_nodes = evals_arr.shape
        if self.vand_inv is not None and n_nodes == self.row_degree:
            coeffs = self.vand_inv @ evals_arr.T  # (deg, deg) @ (deg, r) -> (deg, r)
            return [list(coeffs[:, i]) for i in range(coeffs.shape[1])]
        # fallback to general interpolation via solve
        return decode_evaluations_to_rows(evals_arr, self.nodes)


# Example quick demo if run as script
if __name__ == "__main__":
    # Small demo: two polynomials p(x) = 1 + 2x + 3x^2, q(x) = -1 + 0.5x
    rows = [[1.0, 2.0, 3.0], [-1.0, 0.5, 0.0]]
    nodes = [0.0, 1.0, 2.0]  # three nodes -> recover degree<=2 coefficients
    rv = RowVortex(nodes, row_degree=3)
    evals = rv.encode(rows)
    print("Evaluations:\n", evals)
    recovered = rv.decode(evals)
    print("Recovered rows:\n", recovered)
