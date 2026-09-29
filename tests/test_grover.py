"""Tests for amplitude amplification and the ideal (noise-free) search."""

from __future__ import annotations

import math

import pytest

from qspn.grover import diffuser, grover_circuit, optimal_iterations, success_probability
from qspn.metrics import success_probability as measured_success
from qspn.runner import RunConfig, ideal_distribution
from qspn.spn import SPNParams, brute_force_keys, make_attack_instance


def test_optimal_iterations_matches_closed_form():
    """``floor((pi/4) sqrt(N/M))`` -- not ``sqrt(N)``; the ``pi/4`` matters."""
    assert optimal_iterations(16, 1) == 3
    assert optimal_iterations(64, 1) == 6
    assert optimal_iterations(256, 1) == 12
    assert optimal_iterations(65536, 1) == 201
    assert optimal_iterations(256, 4) == 6  # M=4 quarters the space


def test_more_iterations_than_optimal_reduces_success():
    """Over-rotation: Grover is periodic, so extra iterations *hurt*."""
    best = optimal_iterations(16, 1)
    assert success_probability(best, 16, 1) > success_probability(best + 1, 16, 1)
    assert success_probability(best, 16, 1) > success_probability(best + 2, 16, 1)


def test_success_probability_oscillates_rather_than_saturating():
    """Grover is a rotation, not a ratchet.

    Over a long run the success probability must come back *down* close to its
    starting value -- the physical content of the over-rotation warning.  The
    period ``pi / (2 theta)`` is not an integer, so we assert on the envelope
    over a full cycle rather than on exact equality at any single ``k``.
    """
    theta = math.asin(math.sqrt(1 / 16))
    period_in_k = math.pi / (2 * theta)
    curve = [success_probability(k, 16, 1) for k in range(int(2 * period_in_k) + 1)]

    assert max(curve) > 0.99, "amplification should reach near-certainty"
    assert min(curve) < 0.05, "the rotation must swing back toward zero"
    # and it is not monotonic
    assert any(curve[i + 1] < curve[i] for i in range(len(curve) - 1))


def test_diffuser_preserves_uniform_superposition():
    """``D|s> = |s>`` up to sign: ``|s>`` is the axis of the reflection."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    qc = QuantumCircuit(4)
    qc.h(range(4))
    before = Statevector.from_instruction(qc)
    after = before.evolve(diffuser(4))
    assert abs(abs(before.inner(after)) - 1.0) < 1e-9


@pytest.mark.parametrize("secret", [0b0000, 0b0101, 0b1011, 0b1111])
def test_ideal_search_finds_the_key(secret):
    """The whole pipeline, noise-free: does Grover actually recover the key?"""
    params = SPNParams(key_bits=4, rounds=2)
    pairs = make_attack_instance(secret, params)
    solutions = brute_force_keys(pairs, params)
    assert solutions == [secret]

    circuit = grover_circuit(pairs, params=params, measure=False)
    probs = ideal_distribution(circuit, params.key_bits, RunConfig())

    assert measured_success(probs, solutions) > 0.95
    assert int(probs.argmax()) == secret


def test_ideal_probability_matches_analytic_prediction():
    """Simulation must agree with ``sin^2((2k+1) theta)``, not just "be high"."""
    params = SPNParams(key_bits=4, rounds=2)
    pairs = make_attack_instance(0b1011, params)
    solutions = brute_force_keys(pairs, params)
    for iterations in range(0, 5):
        circuit = grover_circuit(pairs, iterations, params, measure=False)
        probs = ideal_distribution(circuit, params.key_bits, RunConfig())
        predicted = success_probability(iterations, params.key_space, len(solutions))
        assert measured_success(probs, solutions) == pytest.approx(predicted, abs=1e-6)


def test_zero_iterations_is_uniform():
    params = SPNParams(key_bits=4, rounds=2)
    pairs = make_attack_instance(0b1011, params)
    probs = ideal_distribution(
        grover_circuit(pairs, 0, params, measure=False), params.key_bits, RunConfig()
    )
    assert probs == pytest.approx([1 / 16] * 16, abs=1e-9)
