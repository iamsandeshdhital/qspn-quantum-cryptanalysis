#!/usr/bin/env python3
"""Script to run full validation of the QSPN project.

Usage:
    python scripts/run_validation.py

This script runs all validation checks:
1. Oracle equivalence verification
2. Noise model validation
3. Mitigation bounds checking
4. Statistical significance tests
5. Reproducibility checks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qspn.validation import run_full_validation
from qspn.noise import NoiseParams
from qspn.runner import RunConfig


def main():
    parser = argparse.ArgumentParser(
        description="Run full validation of the QSPN project"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for validation report",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress",
    )
    args = parser.parse_args()

    print("Running full validation...")
    print()

    noise_params = NoiseParams()
    config = RunConfig()

    report = run_full_validation(noise_params, config)

    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    print()

    checks = [
        ("Oracle Equivalence", report.oracle_verified),
        ("Noise Model Valid", report.noise_model_valid),
        ("Mitigation Bounds OK", report.mitigation_bounds_ok),
        ("Statistical Significance", report.statistical_significance_ok),
        ("Reproducibility", report.reproducibility_ok),
    ]

    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    print()
    print(f"Overall: {'ALL PASSED' if report.all_passed else 'SOME FAILED'}")
    print()

    if args.verbose:
        print("Details:")
        print(json.dumps(report.details, indent=2, default=str))

    if args.output:
        args.output.write_text(
            json.dumps(
                {
                    "all_passed": report.all_passed,
                    "checks": {name: passed for name, passed in checks},
                    "details": report.details,
                },
                indent=2,
                default=str,
            )
        )
        print(f"Report saved to {args.output}")

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
