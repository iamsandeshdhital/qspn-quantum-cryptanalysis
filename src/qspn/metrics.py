"""Figures of merit for comparing measured, noisy and mitigated distributions."""

from __future__ import annotations

import math

import numpy as np

Counts = dict[str, int]


def success_probability(vec: np.ndarray, solutions: list[int]) -> float:
    """Total probability mass on the marked keys.

    With ``M > 1`` marked keys, *any* of them is a valid attack outcome (each
    satisfies the known plaintext/ciphertext relation), so the mass is summed.
    """
    return float(sum(vec[k] for k in solutions))


def total_variation_distance(p: np.ndarray, q: np.ndarray) -> float:
    """``TVD(p, q) = 0.5 * sum |p_i - q_i|``, in ``[0, 1]``.

    Interpretable as the largest possible difference in the probability the two
    distributions assign to any single event.
    """
    return float(0.5 * np.sum(np.abs(p - q)))


def hellinger_fidelity(p: np.ndarray, q: np.ndarray) -> float:
    """``(sum sqrt(p_i q_i))**2``, in ``[0, 1]``; 1 iff the distributions match.

    Matches the convention used by ``qiskit.quantum_info.hellinger_fidelity``.
    """
    return float(np.sum(np.sqrt(np.clip(p, 0, None) * np.clip(q, 0, None))) ** 2)


def shannon_entropy(vec: np.ndarray) -> float:
    """Entropy in bits.  A flat distribution over ``N`` keys gives ``log2 N``.

    Useful as a single number for "how far has noise pushed us back toward
    uniform" -- the failure mode of a decohered Grover run.
    """
    nz = vec[vec > 0]
    return float(-np.sum(nz * np.log2(nz)))


def rank_of_target(vec: np.ndarray, target: int) -> int:
    """1-based rank of ``target`` when candidates are sorted by probability.

    The operationally honest metric for an attacker: even if the correct key is
    not the single most likely outcome, a rank of 2 or 3 still means very few
    classical verification attempts.
    """
    order = np.argsort(-vec, kind="stable")
    return int(np.where(order == target)[0][0]) + 1


def expected_classical_checks(vec: np.ndarray, solutions: list[int]) -> float:
    """Expected number of classical trial encryptions to confirm the key.

    Assumes the attacker verifies candidates in descending probability order
    until a marked key is found -- the natural hybrid strategy.  This is the
    metric that makes "did mitigation actually help the attack?" answerable.
    """
    order = np.argsort(-vec, kind="stable")
    solution_set = set(solutions)
    for position, candidate in enumerate(order, start=1):
        if int(candidate) in solution_set:
            return float(position)
    return float(vec.size)


def counts_std_error(probability: float, shots: int) -> float:
    """Binomial standard error on a measured probability.

    Every reported probability is an estimate from ``shots`` samples; quoting it
    without this error bar overstates the precision of the result.
    """
    if shots <= 0:
        return float("nan")
    return math.sqrt(max(0.0, probability * (1.0 - probability)) / shots)


def circuit_resources(circuit) -> dict[str, int]:
    """Gate/depth resource summary of a transpiled circuit.

    ``cx`` count and depth are the meaningful NISQ cost drivers: two-qubit gate
    error dominates, and depth drives decoherence.
    """
    ops = circuit.count_ops()
    return {
        "num_qubits": circuit.num_qubits,
        "depth": circuit.depth(),
        "size": sum(ops.values()),
        "cx": int(ops.get("cx", 0)),
        "sx": int(ops.get("sx", 0)),
        "x": int(ops.get("x", 0)),
        "rz": int(ops.get("rz", 0)),
    }
