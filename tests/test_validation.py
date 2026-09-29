"""Tests for the validation framework."""

from __future__ import annotations

import numpy as np

from qspn.noise import NoiseParams
from qspn.runner import RunConfig
from qspn.spn import SPNParams
from qspn.validation import (
    validate_mitigation_bounds,
    validate_noise_model,
    validate_statistical_significance,
    verify_oracle_equivalence,
)


class TestVerifyOracleEquivalence:
    """Tests for oracle equivalence verification."""

    def test_verify_default_params(self):
        result = verify_oracle_equivalence()
        assert result["passed"]
        assert result["tested_keys"] == 16

    def test_verify_custom_params(self):
        params = SPNParams(key_bits=5, rounds=2)
        result = verify_oracle_equivalence(params)
        assert result["passed"]
        assert result["tested_keys"] == 32


class TestValidateNoiseModel:
    """Tests for noise model validation."""

    def test_default_noise_params(self):
        p = NoiseParams()
        result = validate_noise_model(p)
        assert result["rates_valid"]
        assert result["noise_changes_output"]

    def test_noiseless_params(self):
        p = NoiseParams(p1=0, p2=0, p_read_1_given_0=0, p_read_0_given_1=0)
        result = validate_noise_model(p)
        assert result["rates_valid"]


class TestValidateMitigationBounds:
    """Tests for mitigation bounds validation."""

    def test_default_noise(self):
        p = NoiseParams()
        result = validate_mitigation_bounds(p)
        assert "pinv" in result
        assert "clip" in result
        assert "nnls" in result

    def test_nnls_produces_valid_distribution(self):
        p = NoiseParams()
        result = validate_mitigation_bounds(p)
        assert result["nnls"]["valid"]


class TestValidateStatisticalSignificance:
    """Tests for statistical significance validation."""

    def test_significant_result(self):
        result = validate_statistical_significance(
            p_success=0.96,
            shots=4096,
            baseline=0.0625,
        )
        assert result["significant"]
        assert result["sigma"] > 2.0

    def test_not_significant(self):
        result = validate_statistical_significance(
            p_success=0.07,
            shots=4096,
            baseline=0.0625,
        )
        assert not result["significant"]

    def test_zero_stderr(self):
        result = validate_statistical_significance(
            p_success=0.0,
            shots=4096,
            baseline=0.0625,
        )
        assert not result["significant"]
