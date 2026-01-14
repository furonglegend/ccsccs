"""
finite_field.py

A tiny prime-field implementation for prototyping finite-field arithmetic.

Classes:
 - Field: represents GF(p) with prime p, provides helper to create FieldElement.
 - FieldElement: value in GF(p) with arithmetic operators.

NOT FOR CRYPTOGRAPHIC PRODUCTION: this is a convenience educational implementation.
For production-grade cryptography use a well-tested finite-field library.
"""

from typing import Optional
import random


def _is_prime(n: int) -> bool:
    """
    Simple deterministic primality check for small/medium n.
    Uses trial division up to sqrt(n). Sufficient for small primes used in testing.
    """
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


class FieldElement:
    """
    Represents an element of GF(p).
    """
    __slots__ = ("value", "p")

    def __init__(self, value: int, p: int):
        self.p = int(p)
        self.value = int(value) % self.p

    def __add__(self, other):
        if isinstance(other, FieldElement):
            assert self.p == other.p
            return FieldElement(self.value + other.value, self.p)
        return FieldElement(self.value + int(other), self.p)

    def __sub__(self, other):
        if isinstance(other, FieldElement):
            assert self.p == other.p
            return FieldElement(self.value - other.value, self.p)
        return FieldElement(self.value - int(other), self.p)

    def __mul__(self, other):
        if isinstance(other, FieldElement):
            assert self.p == other.p
            return FieldElement(self.value * other.value, self.p)
        return FieldElement(self.value * int(other), self.p)

    def __truediv__(self, other):
        if isinstance(other, FieldElement):
            assert self.p == other.p
            return self * other.inv()
        return self * FieldElement(int(other), self.p).inv()

    def __neg__(self):
        return FieldElement(-self.value, self.p)

    def __eq__(self, other):
        if isinstance(other, FieldElement):
            return self.p == other.p and self.value == other.value
        return self.value == (int(other) % self.p)

    def __repr__(self):
        return f"FieldElement({self.value} mod {self.p})"

    def inv(self):
        """
        Multiplicative inverse via extended Euclidean algorithm.
        """
        a, m = self.value, self.p
        if a == 0:
            raise ZeroDivisionError("inverse of zero")
        # extended gcd
        lm, hm = 1, 0
        low, high = a % m, m
        while low > 1:
            r = high // low
            nm = hm - lm * r
            new = high - low * r
            hm, lm = lm, nm
            high, low = low, new
        return FieldElement(lm % m, m)

    def pow(self, exponent: int):
        return FieldElement(pow(self.value, exponent, self.p), self.p)

    def to_int(self) -> int:
        return int(self.value)


class Field:
    """
    Factory/namespace for field-related helpers.
    """
    def __init__(self, p: Optional[int] = None):
        """
        If p is None, pick a default prime (near 2**61-1) for convenience.
        """
        if p is None:
            # a common Mersenne-like prime for testing: 2305843009213693951 is too big for naive trial division;
            # instead pick a moderate prime for prototyping
            p = 2**31 - 1  # 2147483647, prime
        if not _is_prime(p):
            raise ValueError("p must be prime for a proper field")
        self.p = int(p)

    def element(self, value: int) -> FieldElement:
        return FieldElement(value, self.p)

    def random_element(self) -> FieldElement:
        return FieldElement(random.randrange(0, self.p), self.p)
