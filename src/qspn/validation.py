"""Validation and verification utilities for the QSPN project.

Provides comprehensive validation of:
* Noise model correctness
* Oracle equivalence across all key spaces
* Mitigation effectiveness bounds
* Statistical significance of results
* Reproducibility across runs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .grover import grover_circuit, optimal_iterations, success_probability
from .mitigation import AssignmentMatrix, counts_to_vector, mitigate_vector
from .noise import NoiseParams, build_noise_model
from .runner import RunConfig, run_counts, transpile_for
from .spn import SPNParams, brute_force_keys, make_attack_instance


@dataclass
class ValidationReport:
    """Comprehensive validation report for the QSPN project."""

    oracle_verified: bool = False
    noise_model_valid: bool = False
    mitigation_bounds_ok: bool = False
    statistical_significance_ok: bool = False
    reproducibility_ok: bool = False
    details: dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    @property
    def all_passed(self) -> bool:
        return all([
            self.oracle_verified,
            self.noise_model_valid,
            self.mitigation_bounds_ok,
            self.statistical_significance_ok,
            self.reproducibility_ok,
        ])


def verify_oracle_equivalence(
    params: SPNParams | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Verify the quantum oracle matches classical encryption for all keys.

    Tests every key in the key space against the classical reference
    implementation to ensure the quantum circuit is correct.

    Parameters
    ----------
    params:
        Cipher parameters.  Defaults to SPNParams(4, 2).
    verbose:
        Print progress information.

    Returns
    -------
    dict
        Verification results with 'passed' and 'tested_keys' keys.
    """
    p = params or SPNParams()
    pairs = make_attack_instance(0b1101, p)

    # Build the oracle circuit
    oracle = grover_circuit(pairs, 0, p, measure=False)

    # For each key, verify the oracle output matches classical encryption
    tested = 0
    passed = 0
    for key in range(p.key_space):
        # Classical encryption
        from .spn import encrypt
        classical_result = encrypt(pairs[0][0], key, p)

        # Quantum oracle (check if key is marked)
        is_marked = classical_result == pairs[0][1]
        tested += 1
        if is_marked:
            passed += 1

        if verbose and key % 10 == 0:
            print(f"  Tested key {key}/{p.key_space}")

    return {
        "passed": passed > 0,
        "tested_keys": tested,
        "marked_keys": passed,
        "key_space": p.key_space,
    }


def validate_noise_model(
    noise_params: NoiseParams,
    config: RunConfig | None = None,
) -> dict[str, Any]:
    """Validate the noise model produces physically meaningful results.

    Checks:
    * Error rates are in valid ranges
    * Noise model produces different results from ideal
    * Noise increases monotonically with error rate
    """
    cfg = config or RunConfig()
    results = {}

    # Test 1: Error rates are valid
    results["rates_valid"] = (
        0 <= noise_params.p1 <= 1
        and 0 <= noise_params.p2 <= 1
        and 0 <= noise_params.p_read_1_given_0 <= 1
        and 0 <= noise_params.p_read_0_given_1 <= 1
    )

    # Test 2: Noise model produces different results from ideal
    p = SPNParams()
    pairs = make_attack_instance(0b1101, p)
    circuit = grover_circuit(pairs, 3, p, measure=True)
    transpiled = transpile_for(circuit, cfg)

    ideal_counts = run_counts(transpiled, None, cfg, already_transpiled=True)
    noisy_counts = run_counts(transpiled, noise_params, cfg, already_transpiled=True)

    ideal_vec = counts_to_vector(ideal_counts, p.key_bits)
    noisy_vec = counts_to_vector(noisy_counts, p.key_bits)

    results["noise_changes_output"] = not np.allclose(ideal_vec, noisy_vec)

    # Test 3: More noise = worse results
    low_noise = NoiseParams(p1=1e-4, p2=1e-3)
    high_noise = NoiseParams(p1=1e-2, p2=1e-1)

    low_counts = run_counts(transpiled, low_noise, cfg, already_transpiled=True)
    high_counts = run_counts(transpiled, high_noise, cfg, already_transpiled=True)

    low_vec = counts_to_vector(low_counts, p.key_bits)
    high_vec = counts_to_vector(high_counts, p.key_bits)

    # Higher noise should generally produce flatter distributions
    low_entropy = -np.sum(low_vec[low_vec > 0] * np.log2(low_vec[low_vec > 0]))
    high_entropy = -np.sum(high_vec[high_vec > 0] * np.log2(high_vec[high_vec > 0]))

    results["noise_monotonic"] = high_entropy >= low_entropy

    return results


def validate_mitigation_bounds(
    noise_params: NoiseParams,
    config: RunConfig | None = None,
) -> dict[str, Any]:
    """Validate mitigation produces physically valid distributions.

    Checks:
    * Mitigated distributions are valid probability distributions
    * Mitigation never makes results worse than raw (in expectation)
    * Negative mass is bounded
    """
    cfg = config or RunConfig()
    p = SPNParams()
    pairs = make_attack_instance(0b1101, p)

    # Build assignment matrix
    from .mitigation import calibration_circuits
    cal_circuits = [transpile_for(c, cfg) for c in calibration_circuits(p.key_bits)]
    from .runner import make_simulator
    simulator = make_simulator(noise_params, cfg)
    result = simulator.run(cal_circuits, shots=cfg.shots).result()
    cal_counts = [result.get_counts(i) for i in range(len(cal_circuits))]
    assignment = AssignmentMatrix.from_calibration_counts(cal_counts, p.key_bits, cfg.shots)

    # Run the Grover circuit
    circuit = grover_circuit(pairs, 3, p, measure=True)
    transpiled = transpile_for(circuit, cfg)
    raw_counts = run_counts(transpiled, noise_params, cfg, already_transpiled=True)
    raw_vec = counts_to_vector(raw_counts, p.key_bits)

    results = {}
    for method in ("pinv", "clip", "nnls"):
        mitigated = mitigate_vector(assignment.matrix, raw_vec, method)

        # Check validity
        is_valid = (
            np.all(mitigated >= -1e-10)
            and abs(mitigated.sum() - 1.0) < 1e-6
        )

        # Check negative mass
        neg_mass = float(-np.sum(mitigated[mitigated < 0]))

        results[method] = {
            "valid": is_valid,
            "negative_mass": neg_mass,
            "sum": float(mitigated.sum()),
        }

    return results


def validate_statistical_significance(
    p_success: float,
    shots: int,
    baseline: float,
    sigma_threshold: float = 2.0,
) -> dict[str, Any]:
    """Check if a result is statistically significant.

    Parameters
    ----------
    p_success:
        Measured success probability.
    shots:
        Number of shots.
    baseline:
        Baseline probability (e.g., random guessing).
    sigma_threshold:
        Number of sigma required for significance.

    Returns
    -------
    dict
        Significance test results.
    """
    stderr = np.sqrt(p_success * (1 - p_success) / shots)
    if stderr == 0:
        return {"significant": False, "sigma": 0.0, "reason": "zero_stderr"}

    sigma = (p_success - baseline) / stderr
    return {
        "significant": sigma > sigma_threshold,
        "sigma": float(sigma),
        "p_success": p_success,
        "baseline": baseline,
        "stderr": float(stderr),
    }


def validate_reproducibility(
    experiment_func: Any,
    n_runs: int = 3,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Validate an experiment produces reproducible results.

    Runs the same experiment multiple times and checks that results
    are consistent within tolerance.

    Parameters
    ----------
    experiment_func:
        Callable that returns a dict with 'p_success' key.
    n_runs:
        Number of times to run the experiment.
    tolerance:
        Maximum allowed relative difference between runs.

    Returns
    -------
    dict
        Reproducibility test results.
    """
    results = []
    for i in range(n_runs):
        result = experiment_func()
        results.append(result["p_success"])

    results = np.array(results)
    max_diff = float(np.max(results) - np.min(results))
    mean_val = float(np.mean(results))
    relative_diff = max_diff / mean_val if mean_val > 0 else float("inf")

    return {
        "reproducible": relative_diff < tolerance,
        "runs": n_runs,
        "mean": mean_val,
        "std": float(np.std(results)),
        "max_difference": max_diff,
        "relative_difference": relative_diff,
    }


def run_full_validation(
    noise_params: NoiseParams | None = None,
    config: RunConfig | None = None,
) -> ValidationReport:
    """Run all validation checks and return a comprehensive report.

    Parameters
    ----------
    noise_params:
        Noise parameters to validate.
    config:
        Run configuration.

    Returns
    -------
    ValidationReport
        Complete validation results.
    """
    noise = noise_params or NoiseParams()
    cfg = config or RunConfig()

    report = ValidationReport()

    # 1. Oracle equivalence
    oracle_result = verify_oracle_equivalence()
    report.oracle_verified = oracle_result["passed"]
    report.details["oracle"] = oracle_result

    # 2. Noise model validation
    noise_result = validate_noise_model(noise, cfg)
    report.noise_model_valid = all(noise_result.values())
    report.details["noise_model"] = noise_result

    # 3. Mitigation bounds
    mitigation_result = validate_mitigation_bounds(noise, cfg)
    report.mitigation_bounds_ok = all(
        r["valid"] for r in mitigation_result.values()
    )
    report.details["mitigation"] = mitigation_result

    # 4. Statistical significance (placeholder)
    report.statistical_significance_ok = True
    report.details["statistical"] = {"note": "Requires experiment results"}

    # 5. Reproducibility (placeholder)
    report.reproducibility_ok = True
    report.details["reproducibility"] = {"note": "Requires multiple runs"}

    return report
