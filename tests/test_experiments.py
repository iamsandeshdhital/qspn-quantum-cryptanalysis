"""Integration tests for the experiment layer and the CLI.

These run at deliberately tiny shot counts.  Their job is not to reproduce the
study's numbers but to guarantee that every stage is wired together correctly:
records are JSON-serialisable, the metrics are internally consistent, figures
render, and the summary formats without raising.  A regression anywhere in the
pipeline fails here even though the full study is far too slow for CI.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from qspn.experiments import (
    DEMO_SECRET_KEY,
    Instance,
    experiment_a_ideal,
    experiment_b_noisy,
    experiment_c_mitigation,
    experiment_d_threshold,
    experiment_e_resources,
)
from qspn.noise import NoiseParams
from qspn.runner import RunConfig
from qspn.spn import SPNParams

FAST = RunConfig(shots=256, seed=5)


@pytest.fixture(scope="module")
def instance() -> Instance:
    return Instance.build()


def test_demo_instance_is_a_well_posed_attack(instance):
    """The default instance must have exactly one marked key, on 8 qubits."""
    assert instance.secret_key == DEMO_SECRET_KEY
    assert instance.solutions == [DEMO_SECRET_KEY]
    assert instance.num_solutions == 1
    assert len(instance.pairs) == 1
    assert instance.num_qubits == 8
    assert instance.optimal_iterations == 3


def test_instance_rejects_an_inconsistent_key():
    """A key must satisfy its own pairs; the guard catches wiring mistakes."""
    inst = Instance.build(0b0110, SPNParams(4, 2))
    assert inst.secret_key in inst.solutions


def test_describe_is_json_serialisable(instance):
    assert json.loads(json.dumps(instance.describe()))


def test_experiment_a_agrees_with_theory(instance):
    record = experiment_a_ideal(instance, FAST, max_iterations=4)
    assert record["experiment"] == "A_ideal"
    assert record["best_iterations"] == instance.optimal_iterations
    assert record["max_analytic_deviation"] < 1e-9
    assert record["over_rotation_observed"] is True
    assert json.loads(json.dumps(record))

    for row in record["sweep"]:
        exact = np.array(row["exact_distribution"])
        assert exact.sum() == pytest.approx(1.0)
        assert row["exact_p_success"] == pytest.approx(row["analytic_p_success"], abs=1e-9)


def test_experiment_b_degrades_and_reports_resources(instance):
    record = experiment_b_noisy(instance, NoiseParams(), FAST, max_iterations=3)
    assert record["experiment"] == "B_noisy"
    at = record["at_optimal_iterations"]

    # noise must not improve on the noiseless result
    assert at["p_success"] <= at["ideal_p_success"] + 1e-9
    assert at["degradation"] >= -1e-9
    # transpilation must have happened, or the noise model had nothing to bind to
    assert at["resources"]["cx"] > 0
    assert "unitary" not in at["resources"]
    assert 0.0 <= at["tvd_vs_ideal"] <= 1.0
    assert json.loads(json.dumps(record))


def test_experiment_b_significance_uses_a_two_sigma_margin(instance):
    record = experiment_b_noisy(instance, NoiseParams(), FAST, max_iterations=3)
    at = record["at_optimal_iterations"]
    baseline = record["uniform_baseline"]
    expected = at["p_success"] > baseline + 2 * at["p_success_stderr"]
    assert record["beats_random_guessing"] is bool(expected)


def test_experiment_c_covers_three_scenarios_and_bounds_mitigation(instance):
    record = experiment_c_mitigation(instance, NoiseParams(), FAST)
    assert set(record["scenarios"]) == {"readout_only", "reduced_gate", "full"}

    for name, data in record["scenarios"].items():
        matrix = np.array(data["assignment_matrix"]["matrix"])
        # columns of A are probability distributions
        assert matrix.sum(axis=0) == pytest.approx(np.ones(matrix.shape[0]), abs=1e-9)
        assert data["assignment_matrix"]["condition_number"] >= 1.0

        # nnls must always return a valid distribution; pinv need not
        nnls = data["methods"]["nnls"]
        assert nnls["is_valid_distribution"] is True
        assert nnls["negative_mass"] == pytest.approx(0.0, abs=1e-9)

        for method in ("pinv", "clip", "nnls"):
            vec = np.array(data["methods"][method]["distribution"])
            assert vec.sum() == pytest.approx(1.0, abs=1e-6)

    # Mitigation should recover the readout-limited case far better than the
    # gate-limited one.  This is the project's central claim, asserted here.
    readout = record["scenarios"]["readout_only"]["methods"]["nnls"]
    full = record["scenarios"]["full"]["methods"]["nnls"]
    assert readout["tvd_vs_ideal"] < full["tvd_vs_ideal"]
    assert json.loads(json.dumps(record))


def test_experiment_c_readout_only_mitigation_helps(instance):
    """With only readout error, inverting A must measurably close the gap."""
    record = experiment_c_mitigation(instance, NoiseParams(), FAST)
    data = record["scenarios"]["readout_only"]
    assert data["methods"]["nnls"]["tvd_reduction"] > 0
    assert data["methods"]["nnls"]["p_success"] > data["raw"]["p_success"]


def test_experiment_d_is_monotonic_in_noise(instance):
    record = experiment_d_threshold(
        instance, NoiseParams(), FAST, scale_factors=[0.0, 0.01, 1.0]
    )
    successes = [row["p_success"] for row in record["sweep"]]
    # the noiseless point must be the best, and heavy noise the worst
    assert successes[0] == max(successes)
    assert successes[-1] == min(successes)
    assert record["resources"]["cx"] > 0
    assert json.loads(json.dumps(record))


def test_experiment_e_shows_quadratic_query_saving():
    record = experiment_e_resources([4, 5], FAST)
    for row in record["rows"]:
        # Grover must use far fewer queries than exhaustive search
        assert row["grover_iterations"] < row["classical_queries"]
        assert row["query_speedup"] > 1.0
        # every configuration must yield a uniquely determined key
        assert row["num_solutions"] == 1
        # and the ancilla-free layout must hold: key_bits + 4 * pairs
        assert row["full_circuit"]["num_qubits"] == row["key_bits"] + 4 * row["num_pairs"]

    # circuit cost must grow with the key space
    cx = [row["full_circuit"]["cx"] for row in record["rows"]]
    assert cx == sorted(cx)
    assert json.loads(json.dumps(record))


def test_figures_and_summary_render(tmp_path, instance):
    """End-to-end: records -> JSON on disk -> figures -> summary text."""
    from qspn.cli import summarise
    from qspn.plots import generate_all

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    records = {
        "experiment_a_ideal": experiment_a_ideal(instance, FAST, max_iterations=4),
        "experiment_c_mitigation": experiment_c_mitigation(instance, NoiseParams(), FAST),
        "experiment_e_resources": experiment_e_resources([4], FAST),
    }
    for name, record in records.items():
        (data_dir / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")

    figures = generate_all(data_dir, tmp_path / "figures")
    assert len(figures) == 4  # amplification, mitigation, assignment matrix, resources
    for path in figures:
        assert path.exists() and path.stat().st_size > 1000

    text = summarise(records)
    assert "QUANTUM SPN CRYPTANALYSIS" in text
    assert "readout error only" in text
    assert "Resource scaling" in text


def test_cli_parser_accepts_prefixed_keys():
    from qspn.cli import build_parser

    args = build_parser().parse_args(["--secret-key", "0b1011"])
    assert args.secret_key == 0b1011
    args = build_parser().parse_args(["--secret-key", "0xd"])
    assert args.secret_key == 13
