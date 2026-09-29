"""Tests for the extended noise model."""

from __future__ import annotations

import pytest

from qspn.noise import (
    NoiseParams,
    build_noise_model,
    correlated_noise_model,
    drifted_noise_model,
    readout_only_noise_model,
)


class TestNoiseParams:
    """Tests for NoiseParams validation."""

    def test_default_construction(self):
        p = NoiseParams()
        assert p.p1 == 1.0e-3
        assert p.p2 == 1.0e-2
        assert p.t1 == 100e-6
        assert p.t2 == 150e-6

    def test_invalid_p1_raises(self):
        with pytest.raises(ValueError, match="p1 must be in"):
            NoiseParams(p1=-0.1)

    def test_invalid_p2_raises(self):
        with pytest.raises(ValueError, match="p2 must be in"):
            NoiseParams(p2=1.5)

    def test_invalid_t2_raises(self):
        with pytest.raises(ValueError, match="T2"):
            NoiseParams(t1=100e-6, t2=250e-6)

    def test_valid_t2_boundary(self):
        p = NoiseParams(t1=100e-6, t2=200e-6)
        assert p.t2 == 200e-6

    def test_scaled(self):
        p = NoiseParams(p1=1e-3, p2=1e-2)
        scaled = p.scaled(0.5)
        assert scaled.p1 == 5e-4
        assert scaled.p2 == 5e-3

    def test_scaled_clips_to_physical(self):
        p = NoiseParams(p1=0.8, p2=0.9)
        scaled = p.scaled(2.0)
        assert scaled.p1 == 1.0
        assert scaled.p2 == 1.0

    def test_is_noiseless(self):
        p = NoiseParams(p1=0, p2=0, p_read_1_given_0=0, p_read_0_given_1=0)
        assert p.is_noiseless

    def test_is_not_noiseless(self):
        p = NoiseParams()
        assert not p.is_noiseless

    def test_readout_is_ideal(self):
        p = NoiseParams(p_read_1_given_0=0, p_read_0_given_1=0)
        assert p.readout_is_ideal


class TestBuildNoiseModel:
    """Tests for build_noise_model."""

    def test_builds_model(self):
        p = NoiseParams()
        model = build_noise_model(p)
        assert model is not None

    def test_noiseless_model(self):
        p = NoiseParams(p1=0, p2=0, p_read_1_given_0=0, p_read_0_given_1=0)
        model = build_noise_model(p)
        assert model is not None

    def test_readout_only_model(self):
        p = NoiseParams()
        model = readout_only_noise_model(p)
        assert model is not None

    def test_correlated_noise_model(self):
        p = NoiseParams(crosstalk_factor=0.1)
        coupling_map = [(0, 1), (1, 2)]
        model = correlated_noise_model(p, coupling_map)
        assert model is not None

    def test_drifted_noise_model_no_drift(self):
        p = NoiseParams(drift_rate=0.0)
        model = drifted_noise_model(p, elapsed_hours=10)
        assert model is not None

    def test_drifted_noise_model_with_drift(self):
        p = NoiseParams(drift_rate=0.01, p1=1e-3, p2=1e-2)
        model = drifted_noise_model(p, elapsed_hours=5)
        assert model is not None
