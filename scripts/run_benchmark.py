#!/usr/bin/env python3
"""Script to run the standardized quantum computing benchmark suite.

Usage:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --backend ibmq_quito
    python scripts/run_benchmark.py --output benchmark_results.json

This script runs all available benchmarks and saves results to JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qspn.benchmark import run_standard_benchmark_suite
from qspn.runner import RunConfig


def main():
    parser = argparse.ArgumentParser(
        description="Run standardized quantum computing benchmark suite"
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="IBM Quantum backend name (default: simulator)",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=4096,
        help="Number of shots per circuit",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for benchmark results",
    )
    args = parser.parse_args()

    # Get backend if specified
    backend = None
    if args.backend:
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            service = QiskitRuntimeService()
            backend = service.backend(args.backend)
            print(f"Using backend: {args.backend}")
        except Exception as e:
            print(f"Error connecting to IBM Quantum: {e}")
            print("Make sure you have configured your IBM Quantum credentials.")
            return 1
    else:
        print("Using Aer simulator")

    config = RunConfig(shots=args.shots)

    print("\nRunning benchmark suite...")
    print("=" * 60)

    report = run_standard_benchmark_suite(backend=backend, config=config)

    print("\nBenchmark Results:")
    print("=" * 60)
    for benchmark in report["benchmarks"]:
        print(f"\n{benchmark['name']}:")
        for key, value in benchmark["metrics"].items():
            print(f"  {key}: {value}")

    if args.output:
        args.output.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nResults saved to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
