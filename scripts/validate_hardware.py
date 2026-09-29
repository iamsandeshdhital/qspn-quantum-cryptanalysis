#!/usr/bin/env python3
"""Script to validate the simulated noise model against real IBM Quantum hardware.

Usage:
    python scripts/validate_hardware.py --backend ibmq_quito --qubits 4

This script:
1. Connects to IBM Quantum
2. Characterizes the readout error on the specified backend
3. Compares against the simulated noise model
4. Outputs a validation report

Note: Requires IBM Quantum credentials to be configured.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qspn.hardware import validate_against_hardware
from qspn.noise import NoiseParams


def main():
    parser = argparse.ArgumentParser(
        description="Validate simulated noise model against real hardware"
    )
    parser.add_argument(
        "--backend",
        default="ibmq_quito",
        help="IBM Quantum backend name",
    )
    parser.add_argument(
        "--qubits",
        type=int,
        default=4,
        help="Number of qubits to test",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=8192,
        help="Number of shots per circuit",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for validation report",
    )
    args = parser.parse_args()

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService()
        backend = service.backend(args.backend)
    except Exception as e:
        print(f"Error connecting to IBM Quantum: {e}")
        print("Make sure you have configured your IBM Quantum credentials.")
        return 1

    print(f"Validating against {args.backend}...")
    print(f"Qubits: {args.qubits}, Shots: {args.shots}")

    noise_params = NoiseParams()
    report = validate_against_hardware(
        noise_params=noise_params,
        backend=backend,
        num_qubits=args.qubits,
        shots=args.shots,
    )

    print("\nValidation Report:")
    print(json.dumps(report, indent=2))

    if args.output:
        args.output.write_text(json.dumps(report, indent=2))
        print(f"\nReport saved to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
