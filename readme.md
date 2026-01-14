# ZK-Prototype — Minimal Circom → R1CS & Extraction Toolkit

A lightweight **research / prototyping** Python toolkit that:
- parses a small subset of Circom,
- exports a tiny R1CS-like JSON,
- provides prototype pieces for commitments, a simple Violation IOP, prover/verifier flow,
- supports extractor + solver fallbacks, an LLM mutation stub, and small utilities.

**IMPORTANT:** This repository is a learning/prototyping artifact — it is **not** cryptographically secure and must **not** be used for production zero-knowledge systems.

---

# Table of Contents

- [Quick Summary](#quick-summary)  
- [Requirements](#requirements)  
- [Project Layout](#project-layout)  
- [Quick Start](#quick-start)  
- [Programmatic Example](#programmatic-example)  
- [Module Map & Purpose](#module-map--purpose)  
- [Limitations & Security Disclaimer](#limitations--security-disclaimer)  
- [Development & Testing](#development--testing)  
- [Extensions & Next Steps](#extensions--next-steps)  
- [License](#license)  
- [Contact](#contact)

---

# Quick Summary

This repo implements a practical minimal pipeline to explore ideas around circuit parsing, witness commitments, selective openings, transcripts and extraction strategies. It is designed to be readable, easy to extend, and useful for experimentation.

Key features:
- Minimal Circom parser (subset) → R1CS JSON export.
- R1CS helpers: conversion, inspection, slicing heuristics, fingerprints.
- Prototype commitment (SHA-256 over canonical JSON), Violation IOP transcript format.
- Prover & Verifier prototypes for the simplified protocol.
- Extractor that merges openings and attempts linear / brute-force recovery.
- Optional SMT fallback and deterministic LLM oracle stub.
- Utilities: Row-Vortex Vandermonde prototype, manifest manager, backend selector, Rust sampler generator.

---

# Requirements

- Python 3.9+ recommended.
- Core functionality uses only Python standard library.
- Optional (recommended for better numeric and SMT behavior):
  - `numpy` — for linear algebra and Vandermonde operations.
  - `z3-solver` (Python package) or a local `z3` binary — SMT solving.
  - `openai` — optional if you want real LLM calls (the code falls back to a deterministic stub).

Install optional libs:
```bash
python -m pip install numpy
# optionally:
python -m pip install z3-solver openai
