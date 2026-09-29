"""Tests for advanced error mitigation techniques."""

from __future__ import annotations

import numpy as np
import pytest

from qspn.mitigation import (
    MitigationPipeline,
    cdr_mitigate,
    negative_mass,
    pec_mitigate,
    virtual_distillation,
    zne_extrapolate,
)


class TestZNE:
    """Tests for zero-noise extrapolation."""

    def test_linear_extrapolation(self):
        # y = 1 - 0.1*x
        scale_factors = [1.0, 2.0, 3.0]
        noisy_values = [0.9, 0.8, 0.7]
        result = zne_extrapolate(scale_factors, noisy_values, method="linear")
        assert abs(result["zero_noise_estimate"] - 1.0) < 0.01

    def test_richardson_extrapolation(self):
        scale_factors = [1.0, 2.0, 3.0]
        noisy_values = [0.9, 0.8, 0.7]
        result = zne_extrapolate(scale_factors, noisy_values, method="richardson")
        assert "zero_noise_estimate" in result

    def test_exponential_extrapolation(self):
        scale_factors = [1.0, 2.0, 3.0]
        noisy_values = [0.9, 0.81, 0.729]  # 0.9^x
        result = zne_extrapolate(scale_factors, noisy_values, method="exponential")
        assert result["zero_noise_estimate"] > 0

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            zne_extrapolate([1.0, 2.0], [0.9])

    def test_insufficient_points_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            zne_extrapolate([1.0], [0.9])


class TestPEC:
    """Tests for probabilistic error cancellation."""

    def test_pec_returns_result(self):
        ideal = np.array([0.25, 0.25, 0.25, 0.25])
        result = pec_mitigate(ideal, None)
        assert "mitigated_distribution" in result
        assert "method" in result


class TestCDR:
    """Tests for Clifford data regression."""

    def test_cdr_with_data(self):
        noisy = np.array([0.1, 0.2, 0.3, 0.4])
        clifford_data = [
            (np.array([0.1, 0.2, 0.3, 0.4]), np.array([0.2, 0.2, 0.2, 0.2])),
            (np.array([0.15, 0.25, 0.35, 0.25]), np.array([0.2, 0.2, 0.2, 0.2])),
        ]
        result = cdr_mitigate(noisy, clifford_data)
        assert "mitigated_distribution" in result

    def test_cdr_without_data(self):
        noisy = np.array([0.1, 0.2, 0.3, 0.4])
        result = cdr_mitigate(noisy, [])
        assert result["mitigated_distribution"] is noisy


class TestVirtualDistillation:
    """Tests for virtual distillation."""

    def test_vd_returns_result(self):
        from qiskit import QuantumCircuit
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        result = virtual_distillation(qc, num_copies=2)
        assert "method" in result
        assert result["method"] == "virtual_distillation"


class TestMitigationPipeline:
    """Tests for unified mitigation pipeline."""

    def test_empty_pipeline(self):
        pipeline = MitigationPipeline()
        counts = {"0000": 256, "0001": 256, "0010": 256, "0011": 256}
        result = pipeline.apply(counts, num_qubits=4)
        assert "raw" in result
        assert "final" in result

    def test_pipeline_with_readout_mitigation(self):
        pipeline = MitigationPipeline()
        matrix = np.eye(4)
        pipeline.add_readout_mitigation(matrix)
        counts = {"00": 256, "01": 256, "10": 256, "11": 256}
        result = pipeline.apply(counts, num_qubits=2)
        assert "after_readout_mitigation" in result

    def test_pipeline_with_zne(self):
        pipeline = MitigationPipeline()
        pipeline.add_zne([1.0, 2.0, 3.0], [0.9, 0.8, 0.7])
        counts = {"0000": 256, "0001": 256, "0010": 256, "0011": 256}
        result = pipeline.apply(counts, num_qubits=4)
        assert "zne_estimate" in result


class TestNegativeMass:
    """Tests for negative mass calculation."""

    def test_no_negative_mass(self):
        vec = np.array([0.25, 0.25, 0.25, 0.25])
        assert negative_mass(vec) == 0.0

    def test_with_negative_mass(self):
        vec = np.array([0.5, -0.1, 0.3, 0.3])
        assert negative_mass(vec) == 0.1

    def test_all_negative(self):
        vec = np.array([-0.5, -0.5])
        assert negative_mass(vec) == 1.0
