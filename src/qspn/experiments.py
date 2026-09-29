"""Experiments A-E.  Each returns a JSON-serialisable record.

============  =========================================================
Experiment    Question it answers
============  =========================================================
A  ideal      Does the oracle work, and does the measured amplification
              curve match sin^2((2k+1) theta), including over-rotation?
B  noisy      How much does realistic NISQ noise degrade key recovery?
C  mitigation Can classical readout-error mitigation recover the signal,
              and how much of the loss is readout versus gate error?
D  threshold  At what two-qubit error rate does the attack stop working?
E  resources  How do depth, CX count and pair count scale with key width?
============  =========================================================

Experiment C is deliberately run against *two* noise models.  Readout error
alone is fully described by the assignment matrix, so inversion should recover
almost everything; gate depolarizing error is not a measurement effect at all,
so mitigation cannot touch it.  Running both turns the scope of the technique
into a measured result rather than an assumption.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .grover import grover_circuit, optimal_iterations
from .grover import success_probability as analytic_success
from .metrics import (
    circuit_resources,
    counts_std_error,
    expected_classical_checks,
    hellinger_fidelity,
    rank_of_target,
    shannon_entropy,
    success_probability,
    total_variation_distance,
)
from .mitigation import AssignmentMatrix, counts_to_vector, mitigate_vector, negative_mass
from .noise import NoiseParams, build_noise_model, readout_only_noise_model
from .runner import (
    RunConfig,
    ideal_distribution,
    run_calibration,
    run_counts,
    transpile_for,
)
from .spn import (
    BLOCK_BITS,
    SPNParams,
    brute_force_keys,
    classical_query_cost,
    make_attack_instance,
    required_pairs,
)

MITIGATION_METHODS = ("pinv", "clip", "nnls")

#: Default secret key for the simulated experiments.
#:
#: Chosen deliberately: with ``SPNParams(4, 2)`` this key is uniquely
#: determined by a *single* known plaintext/ciphertext pair, so the oracle needs
#: only one 4-bit data register and the whole search runs on 8 qubits.  Keys
#: needing two or three pairs push the circuit to 12 or 16 qubits, where noisy
#: trajectory simulation costs 16x-256x more time per shot (runtime scales as
#: ``shots * gates * 2**n``).  The attack itself is in no way weakened -- ``M``
#: is still exactly 1, verified by brute force in :meth:`Instance.build` -- the
#: choice only keeps the noise study affordable.  Experiment E reports the cost
#: of the multi-pair configurations that other keys require.
DEMO_SECRET_KEY = 0b1101


@dataclass
class Instance:
    """A concrete attack instance: cipher parameters plus the known pairs."""

    params: SPNParams
    secret_key: int
    pairs: list[tuple[int, int]]
    solutions: list[int]

    @classmethod
    def build(
        cls,
        secret_key: int = DEMO_SECRET_KEY,
        params: SPNParams | None = None,
        num_pairs: int | None = None,
    ) -> "Instance":
        p = params or SPNParams()
        pairs = make_attack_instance(secret_key, p, num_pairs)
        solutions = brute_force_keys(pairs, p)
        if secret_key not in solutions:  # pragma: no cover - guards a logic error
            raise AssertionError(
                f"secret key {secret_key} is not consistent with its own pairs"
            )
        return cls(params=p, secret_key=secret_key, pairs=pairs, solutions=solutions)

    @property
    def num_solutions(self) -> int:
        return len(self.solutions)

    @property
    def optimal_iterations(self) -> int:
        return optimal_iterations(self.params.key_space, max(1, self.num_solutions))

    @property
    def num_qubits(self) -> int:
        """``key_bits + 4r``: the oracle is ancilla-free, so this is the whole cost."""
        return self.params.key_bits + BLOCK_BITS * len(self.pairs)

    def describe(self) -> dict[str, Any]:
        return {
            "key_bits": self.params.key_bits,
            "rounds": self.params.rounds,
            "key_space": self.params.key_space,
            "secret_key": self.secret_key,
            "secret_key_bits": format(self.secret_key, f"0{self.params.key_bits}b"),
            "num_pairs": len(self.pairs),
            "pairs": [list(pair) for pair in self.pairs],
            "num_solutions": self.num_solutions,
            "solutions": self.solutions,
            "optimal_iterations": self.optimal_iterations,
            "num_qubits": self.num_qubits,
            "statevector_bytes": 2**self.num_qubits * 16,
            "density_matrix_bytes": (2**self.num_qubits) ** 2 * 16,
        }


def _distribution_record(
    vec: np.ndarray,
    instance: Instance,
    shots: int,
    reference: np.ndarray | None = None,
) -> dict[str, Any]:
    """Standard bundle of figures of merit for one output distribution."""
    p_success = success_probability(vec, instance.solutions)
    record: dict[str, Any] = {
        "p_success": p_success,
        "p_success_stderr": counts_std_error(p_success, shots),
        "p_secret_key": float(vec[instance.secret_key]),
        "top_key": int(np.argmax(vec)),
        "top_key_is_solution": int(np.argmax(vec)) in instance.solutions,
        "rank_of_secret": rank_of_target(vec, instance.secret_key),
        "expected_classical_checks": expected_classical_checks(vec, instance.solutions),
        "entropy_bits": shannon_entropy(np.clip(vec, 0, None)),
    }
    if reference is not None:
        record["tvd_vs_ideal"] = total_variation_distance(vec, reference)
        record["hellinger_fidelity_vs_ideal"] = hellinger_fidelity(vec, reference)
    return record


# --------------------------------------------------------------------------
# Experiment A -- ideal simulation
# --------------------------------------------------------------------------
def experiment_a_ideal(
    instance: Instance | None = None,
    config: RunConfig | None = None,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """Sweep the iteration count with no noise and compare against theory.

    Reports the exact statevector probability *and* a sampled result, so the
    reader can separate sampling error from any algorithmic effect.
    """
    inst = instance or Instance.build()
    cfg = config or RunConfig()
    k_max = max_iterations if max_iterations is not None else inst.optimal_iterations + 3

    sweep = []
    for iterations in range(k_max + 1):
        unmeasured = grover_circuit(inst.pairs, iterations, inst.params, measure=False)
        exact = ideal_distribution(unmeasured, inst.params.key_bits, cfg)

        measured = grover_circuit(inst.pairs, iterations, inst.params, measure=True)
        sampled = counts_to_vector(
            run_counts(measured, None, cfg), inst.params.key_bits
        )

        predicted = analytic_success(
            iterations, inst.params.key_space, max(1, inst.num_solutions)
        )
        exact_p = success_probability(exact, inst.solutions)
        sweep.append(
            {
                "iterations": iterations,
                "analytic_p_success": predicted,
                "exact_p_success": exact_p,
                "sampled_p_success": success_probability(sampled, inst.solutions),
                "sampled_stderr": counts_std_error(
                    success_probability(sampled, inst.solutions), cfg.shots
                ),
                "abs_error_exact_vs_analytic": abs(exact_p - predicted),
                "exact_distribution": exact.tolist(),
                "sampled_distribution": sampled.tolist(),
            }
        )

    best = max(sweep, key=lambda row: row["exact_p_success"])
    return {
        "experiment": "A_ideal",
        "instance": inst.describe(),
        "shots": cfg.shots,
        "seed": cfg.seed,
        "sweep": sweep,
        "best_iterations": best["iterations"],
        "best_p_success": best["exact_p_success"],
        "max_analytic_deviation": max(r["abs_error_exact_vs_analytic"] for r in sweep),
        "over_rotation_observed": (
            sweep[-1]["exact_p_success"] < best["exact_p_success"] - 1e-6
        ),
    }


# --------------------------------------------------------------------------
# Experiment B -- noisy simulation
# --------------------------------------------------------------------------
def experiment_b_noisy(
    instance: Instance | None = None,
    noise: NoiseParams | None = None,
    config: RunConfig | None = None,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """Repeat the iteration sweep under depolarizing plus readout noise."""
    inst = instance or Instance.build()
    cfg = config or RunConfig()
    noise_params = noise or NoiseParams()
    k_max = max_iterations if max_iterations is not None else inst.optimal_iterations + 3

    model = build_noise_model(noise_params)
    sweep = []
    for iterations in range(k_max + 1):
        unmeasured = grover_circuit(inst.pairs, iterations, inst.params, measure=False)
        ideal = ideal_distribution(unmeasured, inst.params.key_bits, cfg)

        transpiled = transpile_for(
            grover_circuit(inst.pairs, iterations, inst.params, measure=True), cfg
        )
        noisy = counts_to_vector(
            run_counts(transpiled, None, cfg, noise_model=model, already_transpiled=True),
            inst.params.key_bits,
        )

        row: dict[str, Any] = {
            "iterations": iterations,
            "resources": circuit_resources(transpiled),
        }
        row.update(_distribution_record(noisy, inst, cfg.shots, reference=ideal))
        row["ideal_p_success"] = success_probability(ideal, inst.solutions)
        row["degradation"] = row["ideal_p_success"] - row["p_success"]
        row["noisy_distribution"] = noisy.tolist()
        row["ideal_distribution"] = ideal.tolist()
        sweep.append(row)

    at_optimal = sweep[min(inst.optimal_iterations, len(sweep) - 1)]
    return {
        "experiment": "B_noisy",
        "instance": inst.describe(),
        "noise": asdict(noise_params),
        "shots": cfg.shots,
        "seed": cfg.seed,
        "sweep": sweep,
        "at_optimal_iterations": {
            k: v for k, v in at_optimal.items() if not k.endswith("distribution")
        },
        "uniform_baseline": 1.0 / inst.params.key_space,
        # A bare ">" comparison against 1/N is meaningless at these shot counts:
        # the estimator's own standard error is comparable to the gap.  Require a
        # two-sigma margin before claiming the attack retains any advantage.
        "beats_random_guessing": bool(
            at_optimal["p_success"]
            > 1.0 / inst.params.key_space + 2 * at_optimal["p_success_stderr"]
        ),
        "advantage_sigmas": (
            (at_optimal["p_success"] - 1.0 / inst.params.key_space)
            / at_optimal["p_success_stderr"]
            if at_optimal["p_success_stderr"] > 0
            else float("nan")
        ),
    }


# --------------------------------------------------------------------------
# Experiment C -- readout-error mitigation
# --------------------------------------------------------------------------
def experiment_c_mitigation(
    instance: Instance | None = None,
    noise: NoiseParams | None = None,
    config: RunConfig | None = None,
    iterations: int | None = None,
    reduced_gate_scale: float = 0.03,
) -> dict[str, Any]:
    """Apply assignment-matrix mitigation under three different noise models.

    ``readout_only``
        Only measurement error is present, so the assignment matrix fully
        describes the corruption and inversion should recover the ideal
        distribution up to shot noise.  This is the technique's best case.
    ``reduced_gate``
        Full-rate readout error, but gate error scaled down by
        ``reduced_gate_scale`` so that a partial signal survives the circuit.
        This is the informative middle regime: there is a real but degraded peak
        for mitigation to sharpen, so the improvement is measurable rather than
        buried in an already-flat distribution.
    ``full``
        Gate depolarizing error at the full modelled rate.  Mitigation still
        corrects the measurement channel but is structurally unable to address
        gate error; the residual gap quantifies exactly that limitation.
    """
    inst = instance or Instance.build()
    cfg = config or RunConfig()
    noise_params = noise or NoiseParams()
    iters = inst.optimal_iterations if iterations is None else iterations

    unmeasured = grover_circuit(inst.pairs, iters, inst.params, measure=False)
    ideal = ideal_distribution(unmeasured, inst.params.key_bits, cfg)
    transpiled = transpile_for(
        grover_circuit(inst.pairs, iters, inst.params, measure=True), cfg
    )

    # Readout error stays at full strength in every scenario; only the gate error
    # rate changes, so any difference between them is attributable to gate noise.
    reduced = NoiseParams(
        p1=noise_params.p1 * reduced_gate_scale,
        p2=noise_params.p2 * reduced_gate_scale,
        p_read_1_given_0=noise_params.p_read_1_given_0,
        p_read_0_given_1=noise_params.p_read_0_given_1,
    )

    scenarios: dict[str, Any] = {}
    for label, model in (
        ("readout_only", readout_only_noise_model(noise_params)),
        ("reduced_gate", build_noise_model(reduced)),
        ("full", build_noise_model(noise_params)),
    ):
        cal_counts = run_calibration(inst.params.key_bits, None, cfg, noise_model=model)
        assignment = AssignmentMatrix.from_calibration_counts(
            cal_counts, inst.params.key_bits, cfg.shots
        )
        raw = counts_to_vector(
            run_counts(transpiled, None, cfg, noise_model=model, already_transpiled=True),
            inst.params.key_bits,
        )

        entry: dict[str, Any] = {
            "assignment_matrix": {
                "mean_readout_fidelity": assignment.mean_readout_fidelity,
                "condition_number": assignment.condition_number,
                "num_calibration_circuits": 1 << inst.params.key_bits,
                "matrix": assignment.matrix.tolist(),
            },
            "raw": _distribution_record(raw, inst, cfg.shots, reference=ideal),
            "methods": {},
        }
        entry["raw"]["distribution"] = raw.tolist()

        for method in MITIGATION_METHODS:
            corrected = mitigate_vector(assignment.matrix, raw, method)
            rec = _distribution_record(
                np.clip(corrected, 0, None), inst, cfg.shots, reference=ideal
            )
            rec["negative_mass"] = negative_mass(corrected)
            rec["is_valid_distribution"] = bool(
                np.all(corrected >= -1e-12) and abs(float(corrected.sum()) - 1.0) < 1e-6
            )
            rec["improvement_over_raw"] = rec["p_success"] - entry["raw"]["p_success"]
            rec["tvd_reduction"] = entry["raw"]["tvd_vs_ideal"] - rec["tvd_vs_ideal"]
            rec["distribution"] = corrected.tolist()
            entry["methods"][method] = rec

        scenarios[label] = entry

    return {
        "experiment": "C_mitigation",
        "instance": inst.describe(),
        "noise": asdict(noise_params),
        "iterations": iters,
        "reduced_gate_scale": reduced_gate_scale,
        "reduced_gate_noise": asdict(reduced),
        "shots": cfg.shots,
        "seed": cfg.seed,
        "ideal_p_success": success_probability(ideal, inst.solutions),
        "ideal_distribution": ideal.tolist(),
        "scenarios": scenarios,
        "conclusion": {
            scenario: {
                "raw": scenarios[scenario]["raw"]["p_success"],
                "mitigated_nnls": scenarios[scenario]["methods"]["nnls"]["p_success"],
                "improvement": scenarios[scenario]["methods"]["nnls"][
                    "improvement_over_raw"
                ],
                "tvd_reduction": scenarios[scenario]["methods"]["nnls"]["tvd_reduction"],
            }
            for scenario in scenarios
        },
    }


# --------------------------------------------------------------------------
# Experiment D -- noise threshold
# --------------------------------------------------------------------------
def experiment_d_threshold(
    instance: Instance | None = None,
    noise: NoiseParams | None = None,
    config: RunConfig | None = None,
    scale_factors: list[float] | None = None,
) -> dict[str, Any]:
    """Scale every error rate and find where the attack stops working.

    "Working" is defined operationally: the correct key must remain the single
    most likely measurement outcome.  The reported threshold is the largest
    tested two-qubit error rate at which that still holds.
    """
    inst = instance or Instance.build()
    cfg = config or RunConfig()
    base = noise or NoiseParams()
    factors = scale_factors or [0.0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]

    transpiled = transpile_for(
        grover_circuit(inst.pairs, inst.optimal_iterations, inst.params, measure=True),
        cfg,
    )
    unmeasured = grover_circuit(
        inst.pairs, inst.optimal_iterations, inst.params, measure=False
    )
    ideal = ideal_distribution(unmeasured, inst.params.key_bits, cfg)

    sweep = []
    for factor in factors:
        scaled = base.scaled(factor)
        model = build_noise_model(scaled) if factor > 0 else None
        vec = counts_to_vector(
            run_counts(transpiled, None, cfg, noise_model=model, already_transpiled=True),
            inst.params.key_bits,
        )
        row: dict[str, Any] = {
            "scale_factor": factor,
            "p1": scaled.p1 if factor > 0 else 0.0,
            "p2": scaled.p2 if factor > 0 else 0.0,
            "p_readout_mean": (
                (scaled.p_read_1_given_0 + scaled.p_read_0_given_1) / 2
                if factor > 0
                else 0.0
            ),
        }
        row.update(_distribution_record(vec, inst, cfg.shots, reference=ideal))
        sweep.append(row)

    working = [r for r in sweep if r["top_key_is_solution"] and r["scale_factor"] > 0]
    return {
        "experiment": "D_threshold",
        "instance": inst.describe(),
        "base_noise": asdict(base),
        "shots": cfg.shots,
        "seed": cfg.seed,
        "resources": circuit_resources(transpiled),
        "sweep": sweep,
        "max_working_p2": max((r["p2"] for r in working), default=None),
        "uniform_baseline": 1.0 / inst.params.key_space,
    }


# --------------------------------------------------------------------------
# Experiment E -- resource scaling
# --------------------------------------------------------------------------
def experiment_e_resources(
    key_widths: list[int] | None = None,
    config: RunConfig | None = None,
    secret_key: int = DEMO_SECRET_KEY,
) -> dict[str, Any]:
    """Transpiled cost and query complexity as the key space grows.

    This is the experiment that connects the toy study to the real question.
    Grover's quadratic saving is in *oracle queries*, but each query costs a
    circuit whose depth grows with the cipher and with the number of plaintext
    blocks needed for a unique key.  Counting both is what turns a speedup
    claim into a resource estimate.
    """
    cfg = config or RunConfig()
    widths = key_widths or [4, 5, 6, 7, 8]

    rows = []
    for key_bits in widths:
        rounds = max(2, SPNParams(key_bits, 2).min_rounds_for_full_coverage())
        params = SPNParams(key_bits=key_bits, rounds=rounds)
        inst = Instance.build(secret_key % params.key_space, params)

        transpiled = transpile_for(
            grover_circuit(inst.pairs, inst.optimal_iterations, params, measure=True), cfg
        )
        resources = circuit_resources(transpiled)
        single = circuit_resources(
            transpile_for(grover_circuit(inst.pairs, 1, params, measure=False), cfg)
        )

        rows.append(
            {
                "key_bits": key_bits,
                "rounds": rounds,
                "key_space": params.key_space,
                "num_pairs": len(inst.pairs),
                "theoretical_min_pairs": required_pairs(params),
                "num_solutions": inst.num_solutions,
                "classical_queries": classical_query_cost(params),
                "grover_iterations": inst.optimal_iterations,
                "sqrt_key_space": params.key_space**0.5,
                "query_speedup": classical_query_cost(params)
                / max(1, inst.optimal_iterations),
                "analytic_p_success": analytic_success(
                    inst.optimal_iterations, params.key_space, max(1, inst.num_solutions)
                ),
                "full_circuit": resources,
                "single_iteration": single,
                "statevector_amplitudes": 2 ** resources["num_qubits"],
                "statevector_bytes": 2 ** resources["num_qubits"] * 16,
                "density_matrix_bytes": (2 ** resources["num_qubits"]) ** 2 * 16,
                "calibration_circuits": 1 << key_bits,
            }
        )

    return {
        "experiment": "E_resources",
        "seed": cfg.seed,
        "block_bits": BLOCK_BITS,
        "rows": rows,
        "note": (
            "classical_queries is worst-case exhaustive search; grover_iterations is "
            "the oracle-query count, each query costing the listed CX count and depth."
        ),
    }
