"""Tests for the noise models and readout-error mitigation.

The important property is not "mitigation improves things" -- it is that
mitigation inverts the *measurement* channel specifically.  So the decisive test
uses an analytically known assignment matrix and checks the recovered
distribution against the exact answer, rather than just checking it got closer.
"""

from __future__ import annotations

import numpy as np
import pytest

from qspn.mitigation import (
    AssignmentMatrix,
    calibration_circuits,
    counts_to_vector,
    mitigate_vector,
    negative_mass,
)
from qspn.noise import (
    BASIS_GATES,
    NoiseParams,
    build_noise_model,
    readout_only_noise_model,
)
from qspn.runner import RunConfig, run_calibration


def test_calibration_circuit_count_and_preparation():
    circuits = calibration_circuits(3)
    assert len(circuits) == 8
    # circuit j must contain exactly popcount(j) X gates
    for j, circuit in enumerate(circuits):
        assert circuit.count_ops().get("x", 0) == bin(j).count("1")


def test_counts_to_vector_normalises_and_orders():
    vec = counts_to_vector({"00": 25, "01": 25, "10": 50}, 2)
    assert vec.tolist() == [0.25, 0.25, 0.5, 0.0]
    assert vec.sum() == pytest.approx(1.0)


def test_counts_to_vector_handles_empty():
    assert counts_to_vector({}, 2).tolist() == [0.0, 0.0, 0.0, 0.0]


def _tensored_assignment(p01: float, p10: float, num_qubits: int) -> np.ndarray:
    """Exact assignment matrix for independent, identical per-qubit bit flips."""
    single = np.array([[1 - p01, p10], [p01, 1 - p10]])
    matrix = np.array([[1.0]])
    for _ in range(num_qubits):
        matrix = np.kron(matrix, single)
    return matrix


@pytest.mark.parametrize("method", ["pinv", "clip", "nnls"])
def test_mitigation_inverts_a_known_channel_exactly(method):
    """With exact ``A`` and exact ``y = A x``, every method must recover ``x``."""
    rng = np.random.default_rng(0)
    matrix = _tensored_assignment(0.02, 0.04, 3)
    truth = rng.dirichlet(np.ones(8))
    observed = matrix @ truth

    recovered = mitigate_vector(matrix, observed, method)
    assert recovered == pytest.approx(truth, abs=1e-6)


def test_pinv_can_produce_negative_probabilities():
    """The documented pathology: raw inversion of shot-noisy data leaves the simplex."""
    matrix = _tensored_assignment(0.08, 0.12, 2)
    truth = np.array([1.0, 0.0, 0.0, 0.0])
    observed = matrix @ truth
    # perturb as finite sampling would
    observed = np.clip(observed + np.array([0.0, -0.02, 0.03, -0.01]), 0, None)
    observed /= observed.sum()

    raw = mitigate_vector(matrix, observed, "pinv")
    constrained = mitigate_vector(matrix, observed, "nnls")

    assert negative_mass(raw) > 0, "expected raw inversion to go negative here"
    assert negative_mass(constrained) == pytest.approx(0.0)
    assert constrained.sum() == pytest.approx(1.0)
    assert np.all(constrained >= -1e-12)


def test_nnls_always_returns_a_valid_distribution():
    rng = np.random.default_rng(7)
    matrix = _tensored_assignment(0.10, 0.15, 3)
    for _ in range(20):
        observed = rng.dirichlet(np.ones(8))
        recovered = mitigate_vector(matrix, observed, "nnls")
        assert np.all(recovered >= -1e-12)
        assert recovered.sum() == pytest.approx(1.0)


def test_unknown_mitigation_method_is_rejected():
    with pytest.raises(ValueError, match="unknown mitigation method"):
        mitigate_vector(np.eye(2), np.array([1.0, 0.0]), "magic")


def test_assignment_matrix_from_simulated_calibration():
    """End-to-end: characterise Aer's readout error and check it matches the model."""
    params = NoiseParams(p1=0.0, p2=0.0, p_read_1_given_0=0.03, p_read_0_given_1=0.06)
    config = RunConfig(shots=8192, seed=11)
    counts = run_calibration(
        3, None, config, noise_model=readout_only_noise_model(params)
    )
    assignment = AssignmentMatrix.from_calibration_counts(counts, 3, config.shots)

    expected = _tensored_assignment(0.03, 0.06, 3)
    assert assignment.matrix == pytest.approx(expected, abs=0.02)
    # columns are probability distributions
    assert assignment.matrix.sum(axis=0) == pytest.approx(np.ones(8))
    # P(read 000 | prepared 000) = (1 - 0.03)^3
    assert assignment.mean_readout_fidelity > 0.80
    assert assignment.condition_number > 1.0


def test_noise_model_covers_the_basis_gates():
    model = build_noise_model(NoiseParams())
    noisy = set(model.noise_instructions)
    assert {"cx", "sx", "x"} <= noisy
    assert "rz" not in noisy, "rz is a virtual frame change and must stay noiseless"
    assert set(BASIS_GATES) >= noisy - {"measure"}


def test_readout_only_model_has_no_gate_errors():
    model = readout_only_noise_model(NoiseParams())
    assert set(model.noise_instructions) <= {"measure"}


def test_noise_params_scaling_is_linear_and_clipped():
    base = NoiseParams(p1=1e-3, p2=1e-2, p_read_1_given_0=0.02, p_read_0_given_1=0.04)
    assert base.scaled(0.1).p2 == pytest.approx(1e-3)
    assert base.scaled(10).p2 == pytest.approx(0.1)
    # readout rates are capped at 0.5: beyond that the channel is not invertible
    assert base.scaled(1000).p_read_1_given_0 == 0.5
    assert base.scaled(0).is_noiseless


def test_zero_noise_model_is_empty():
    model = build_noise_model(NoiseParams(0.0, 0.0, 0.0, 0.0))
    assert not model.noise_instructions
