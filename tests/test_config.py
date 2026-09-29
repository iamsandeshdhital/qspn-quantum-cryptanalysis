"""Tests for configuration management."""

from __future__ import annotations

import json

import pytest

from qspn.config import (
    ExperimentConfig,
    load_config,
    quick_config,
    production_config,
    hardware_config,
)
from qspn.noise import NoiseParams
from qspn.runner import RunConfig
from qspn.spn import SPNParams


class TestExperimentConfig:
    """Tests for ExperimentConfig."""

    def test_default_config(self):
        config = ExperimentConfig()
        assert config.name == "default"
        assert config.spn_params.key_bits == 4
        assert config.run_config.shots == 4096

    def test_save_and_load_yaml(self, tmp_path):
        config = ExperimentConfig(
            name="test",
            spn_params=SPNParams(key_bits=5, rounds=3),
            noise_params=NoiseParams(p1=1e-3),
            run_config=RunConfig(shots=2048),
        )
        path = tmp_path / "config.yaml"
        config.save(path)

        loaded = ExperimentConfig.load(path)
        assert loaded.name == config.name
        assert loaded.spn_params.key_bits == 5
        assert loaded.run_config.shots == 2048

    def test_save_and_load_json(self, tmp_path):
        config = ExperimentConfig(name="test")
        path = tmp_path / "config.json"
        config.save(path)

        loaded = ExperimentConfig.load(path)
        assert loaded.name == config.name

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("QSPN_NAME", "env_test")
        monkeypatch.setenv("QSPN_SHOTS", "2048")
        monkeypatch.setenv("QSPN_P1", "0.01")

        config = ExperimentConfig.from_env()
        assert config.name == "env_test"
        assert config.run_config.shots == 2048
        assert config.noise_params.p1 == 0.01


class TestPresetConfigs:
    """Tests for preset configurations."""

    def test_quick_config(self):
        config = quick_config()
        assert config.run_config.shots == 1024
        assert "quick" in config.tags

    def test_production_config(self):
        config = production_config()
        assert config.run_config.shots == 10000
        assert "production" in config.tags

    def test_hardware_config(self):
        config = hardware_config("ibmq_quito")
        assert "ibmq_quito" in config.tags
        assert "hardware" in config.tags


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_file(self, tmp_path):
        config = ExperimentConfig(name="file_test")
        path = tmp_path / "config.yaml"
        config.save(path)

        loaded = load_config(path)
        assert loaded.name == "file_test"

    def test_load_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("QSPN_NAME", "env_config")
        loaded = load_config(None)
        assert loaded.name == "env_config"
