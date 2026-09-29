"""Complexity and noise-resilience of quantum oracles for symmetric cryptanalysis.

A reproducible study of Grover-based known-plaintext key search against a toy
4-bit substitution-permutation network, under simulated NISQ noise, with
classical readout-error mitigation.

Public entry points
-------------------
:mod:`qspn.spn`
    Classical reference cipher and exhaustive-search baseline.
:mod:`qspn.oracle`
    Reversible encryption circuit and the Grover phase oracle.
:mod:`qspn.grover`
    Diffusion operator, search circuit, analytic success probability.
:mod:`qspn.noise`
    Depolarizing and readout noise models for Aer.
:mod:`qspn.mitigation`
    Assignment-matrix readout-error mitigation.
:mod:`qspn.experiments`
    Experiments A-E, each returning a JSON-serialisable result record.
"""

__version__ = "1.0.0"

from .spn import SPNParams, brute_force_keys, decrypt, encrypt, make_attack_instance

__all__ = [
    "__version__",
    "SPNParams",
    "brute_force_keys",
    "decrypt",
    "encrypt",
    "make_attack_instance",
]
