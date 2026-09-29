"""Configuration management for quantum computing experiments.

Provides a unified configuration system for:
* Experiment parameters
* Noise model settings
* Backend selection
* Mitigation strategies
* Output formatting

Supports loading from YAML/JSON files and environment variables,
making it easy to manage configurations across different environments.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from .noise import NoiseParams
from .runner import RunConfig
from .spn import SPNParams


@dataclass
class ExperimentConfig:
    """Complete configuration for a quantum computing experiment.

    Attributes
    ----------
    name:
        Experiment name.
    description:
        Human-readable description.
    spn_params:
        SPN cipher parameters.
    noise_params:
    run_config:
        Run configuration.
    mitigation_methods:
        List of mitigation methods to apply.
    tags:
        User-defined tags.
    output_dir:
        Directory to save results.
    """

    name: str = "default"
    description: str = ""
    spn_params: SPNParams = field(default_factory=SPNParams)
    noise_params: NoiseParams = field(default_factory=NoiseParams)
    run_config: RunConfig = field(default_factory=RunConfig)
    mitigation_methods: list[str] = field(default_factory=lambda: ["nnls"])
    tags: list[str] = field(default_factory=list)
    output_dir: str = "results/"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        """Save configuration to a YAML or JSON file."""
        path = Path(path)
        data = self.to_dict()

        if path.suffix == ".json":
            path.write_text(json.dumps(data, indent=2))
        else:
            path.write_text(yaml.dump(data, default_flow_style=False))

    @classmethod
    def load(cls, path: str | Path) -> "ExperimentConfig":
        """Load configuration from a YAML or JSON file."""
        path = Path(path)

        if path.suffix == ".json":
            data = json.loads(path.read_text())
        else:
            data = yaml.safe_load(path.read_text())

        # Reconstruct nested dataclasses
        if "spn_params" in data:
            data["spn_params"] = SPNParams(**data["spn_params"])
        if "noise_params" in data:
            data["noise_params"] = NoiseParams(**data["noise_params"])
        if "run_config" in data:
            data["run_config"] = RunConfig(**data["run_config"])

        return cls(**data)

    @classmethod
    def from_env(cls) -> "ExperimentConfig":
        """Load configuration from environment variables.

        Environment variables:
        - QSPN_NAME: Experiment name
        - QSPN_SHOTS: Number of shots
        - QSPN_SEED: Random seed
        - QSPN_P1: Single-qubit error rate
        - QSPN_P2: Two-qubit error rate
        - QSPN_KEY_BITS: Key width
        - QSPN_ROUNDS: Number of rounds
        """
        config = cls()

        if "QSPN_NAME" in os.environ:
            config.name = os.environ["QSPN_NAME"]
        if "QSPN_SHOTS" in os.environ:
            config.run_config.shots = int(os.environ["QSPN_SHOTS"])
        if "QSPN_SEED" in os.environ:
            config.run_config.seed = int(os.environ["QSPN_SEED"])
        if "QSPN_P1" in os.environ:
            config.noise_params.p1 = float(os.environ["QSPN_P1"])
        if "QSPN_P2" in os.environ:
            config.noise_params.p2 = float(os.environ["QSPN_P2"])
        if "QSPN_KEY_BITS" in os.environ:
            config.spn_params.key_bits = int(os.environ["QSPN_KEY_BITS"])
        if "QSPN_ROUNDS" in os.environ:
            config.spn_params.rounds = int(os.environ["QSPN_ROUNDS"])

        return config


def load_config(path: str | Path | None = None) -> ExperimentConfig:
    """Load configuration from file or environment.

    Parameters
    ----------
    path:
        Path to configuration file. If None, loads from environment.

    Returns
    -------
    ExperimentConfig
    """
    if path is None:
        return ExperimentConfig.from_env()
    return ExperimentConfig.load(path)


def save_config(config: ExperimentConfig, path: str | Path) -> None:
    """Save configuration to file."""
    config.save(path)


# Example configurations for common use cases

def quick_config() -> ExperimentConfig:
    """Fast configuration for testing."""
    return ExperimentConfig(
        name="quick_test",
        spn_params=SPNParams(key_bits=4, rounds=2),
        run_config=RunConfig(shots=1024, seed=42),
        tags=["test", "quick"],
    )


def production_config() -> ExperimentConfig:
    """Production configuration for publication-quality results."""
    return ExperimentConfig(
        name="production",
        spn_params=SPNParams(key_bits=4, rounds=2),
        noise_params=NoiseParams(
            p1=1e-3,
            p2=1e-2,
            p_read_1_given_0=0.02,
            p_read_0_given_1=0.04,
        ),
        run_config=RunConfig(shots=10000, seed=20260902),
        mitigation_methods=["nnls", "zne"],
        tags=["production", "publication"],
    )


def hardware_config(backend_name: str = "ibmq_quito") -> ExperimentConfig:
    """Configuration for running on real hardware."""
    return ExperimentConfig(
        name=f"hardware_{backend_name}",
        spn_params=SPNParams(key_bits=4, rounds=2),
        run_config=RunConfig(shots=4096, seed=20260902),
        mitigation_methods=["nnls"],
        tags=["hardware", backend_name],
    )
