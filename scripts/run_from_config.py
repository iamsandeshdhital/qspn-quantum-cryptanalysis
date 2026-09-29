#!/usr/bin/env python3
"""Script to run experiments from a configuration file.

Usage:
    python scripts/run_from_config.py --config configs/example.yaml
    python scripts/run_from_config.py --config configs/example.yaml --quick

This script loads a configuration file and runs the specified experiments.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qspn.config import load_config
from qspn.experiments import (
    Instance,
    experiment_a_ideal,
    experiment_b_noisy,
    experiment_c_mitigation,
    experiment_d_threshold,
    experiment_e_resources,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run experiments from a configuration file"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to configuration file (YAML or JSON)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run with reduced shots for quick testing",
    )
    parser.add_argument(
        "--experiments",
        default="abcde",
        help="Which experiments to run (subset of abcde)",
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    print(f"Loaded configuration: {config.name}")
    print(f"Description: {config.description}")
    print(f"Tags: {', '.join(config.tags)}")
    print()

    # Override for quick mode
    if args.quick:
        config.run_config.shots = 1024
        print("Quick mode: reduced to 1024 shots")

    # Build instance
    instance = Instance.build(
        secret_key=0b1101,
        params=config.spn_params,
    )

    print(f"Instance: {instance.num_qubits} qubits, {len(instance.pairs)} pairs")
    print(f"Shots: {config.run_config.shots}")
    print(f"Seed: {config.run_config.seed}")
    print()

    # Run selected experiments
    results = {}
    for exp in args.experiments:
        if exp == "a":
            print("Running experiment A (ideal)...")
            results["a"] = experiment_a_ideal(instance, config.run_config)
        elif exp == "b":
            print("Running experiment B (noisy)...")
            results["b"] = experiment_b_noisy(
                instance, config.noise_params, config.run_config
            )
        elif exp == "c":
            print("Running experiment C (mitigation)...")
            results["c"] = experiment_c_mitigation(
                instance, config.noise_params, config.run_config
            )
        elif exp == "d":
            print("Running experiment D (threshold)...")
            results["d"] = experiment_d_threshold(
                instance, config.noise_params, config.run_config
            )
        elif exp == "e":
            print("Running experiment E (resources)...")
            results["e"] = experiment_e_resources(config=config.run_config)
        print()

    # Save results
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, result in results.items():
        path = output_dir / f"experiment_{name}.json"
        path.write_text(json.dumps(result, indent=2, default=str))
        print(f"Saved: {path}")

    print(f"\nAll results saved to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
