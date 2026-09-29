"""Command-line entry point: ``qspn-run`` (or ``python -m qspn.cli``).

Runs the experiments, writes one JSON record per experiment into
``results/data/``, regenerates the figures in ``results/figures/``, and prints a
human-readable summary table.  Because every record is saved, figures and the
summary can be rebuilt without re-simulating (``--plots-only``).
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .experiments import (
    DEMO_SECRET_KEY,
    Instance,
    experiment_a_ideal,
    experiment_b_noisy,
    experiment_c_mitigation,
    experiment_d_threshold,
    experiment_e_resources,
)
from .noise import NoiseParams
from .runner import RunConfig
from .spn import SPNParams

EXPERIMENTS: dict[str, str] = {
    "a": "experiment_a_ideal",
    "b": "experiment_b_noisy",
    "c": "experiment_c_mitigation",
    "d": "experiment_d_threshold",
    "e": "experiment_e_resources",
}

QUICK_SCALE_FACTORS = [0.0, 0.01, 0.1, 1.0]


def _repo_root() -> Path:
    """Project root, assuming the standard ``src/qspn`` layout."""
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qspn-run",
        description=(
            "Grover key search against a toy 4-bit SPN, under simulated NISQ "
            "noise, with classical readout-error mitigation."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--experiments",
        default="abcde",
        help="which experiments to run, as a subset of the letters abcde",
    )
    parser.add_argument("--shots", type=int, default=4096, help="shots per circuit")
    parser.add_argument("--seed", type=int, default=20260902, help="master RNG seed")
    parser.add_argument("--key-bits", type=int, default=4, help="master key width")
    parser.add_argument("--rounds", type=int, default=2, help="SPN rounds")
    parser.add_argument(
        "--secret-key",
        type=lambda v: int(v, 0),
        default=DEMO_SECRET_KEY,
        help="secret key to recover (accepts 0b/0x prefixes)",
    )
    parser.add_argument(
        "--num-pairs",
        type=int,
        default=None,
        help="known plaintext/ciphertext pairs; default grows until the key is unique",
    )
    parser.add_argument("--p1", type=float, default=1e-3, help="1-qubit depolarizing rate")
    parser.add_argument("--p2", type=float, default=1e-2, help="2-qubit depolarizing rate")
    parser.add_argument(
        "--readout-01", type=float, default=0.02, help="P(measure 1 | prepared 0)"
    )
    parser.add_argument(
        "--readout-10", type=float, default=0.04, help="P(measure 0 | prepared 1)"
    )
    parser.add_argument(
        "--key-widths",
        default="4,5,6,7,8",
        help="comma-separated key widths for the Experiment E resource scan",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="fewer shots and sweep points, for a fast end-to-end check (~2 min)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="results directory (default: <repo>/results)",
    )
    parser.add_argument(
        "--plots-only",
        action="store_true",
        help="regenerate figures and summary from saved JSON without simulating",
    )
    parser.add_argument("--version", action="version", version=f"qspn {__version__}")
    return parser


def _environment() -> dict[str, Any]:
    """Provenance block, so a saved record says what produced it."""
    import numpy
    import qiskit
    import qiskit_aer

    return {
        "qspn_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "qiskit": qiskit.__version__,
        "qiskit_aer": qiskit_aer.__version__,
        "numpy": numpy.__version__,
    }


def _save(record: dict[str, Any], data_dir: Path, name: str) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{name}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def summarise(records: dict[str, dict[str, Any]]) -> str:
    """Human-readable digest of whichever records are present."""
    lines: list[str] = []
    add = lines.append

    add("=" * 74)
    add("QUANTUM SPN CRYPTANALYSIS -- SUMMARY")
    add("=" * 74)

    if (a := records.get("experiment_a_ideal")):
        inst = a["instance"]
        add("")
        add(f"Instance   : {inst['key_bits']}-bit key, {inst['rounds']} rounds, "
            f"secret = {inst['secret_key_bits']}")
        add(f"             {inst['num_pairs']} known pair(s), M = {inst['num_solutions']} "
            f"marked key(s), {inst['num_qubits']} qubits")
        add("")
        add("[A] Ideal simulation")
        add(f"    optimal iterations k*        : {inst['optimal_iterations']}")
        add(f"    best measured P(key)         : {_fmt(a['best_p_success'])} "
            f"at k = {a['best_iterations']}")
        add(f"    max deviation from sin^2     : {a['max_analytic_deviation']:.2e}")
        add(f"    over-rotation observed       : {_fmt(a['over_rotation_observed'])}")

    if (b := records.get("experiment_b_noisy")):
        at = b["at_optimal_iterations"]
        add("")
        add("[B] Noisy simulation (at k*)")
        add(f"    noise p1/p2                  : {b['noise']['p1']:.1e} / "
            f"{b['noise']['p2']:.1e}")
        add(f"    transpiled CX / depth        : {at['resources']['cx']} / "
            f"{at['resources']['depth']}")
        add(f"    ideal  P(key)                : {_fmt(at['ideal_p_success'])}")
        add(f"    noisy  P(key)                : {_fmt(at['p_success'])} "
            f"+/- {at['p_success_stderr']:.4f}")
        add(f"    TVD vs ideal                 : {_fmt(at['tvd_vs_ideal'])}")
        add(f"    output entropy (bits)        : {_fmt(at['entropy_bits'])} "
            f"(uniform = {b['instance']['key_bits']}.0000)")
        add(f"    advantage over random        : {b['advantage_sigmas']:.1f} sigma"
            f"  (significant: {_fmt(b['beats_random_guessing'])})")

    if (c := records.get("experiment_c_mitigation")):
        add("")
        add("[C] Readout-error mitigation")
        add(f"    ideal P(key)                 : {_fmt(c['ideal_p_success'])}")
        titles = {
            "readout_only": "readout error only",
            "reduced_gate": "readout + reduced gate error",
            "full": "readout + full gate error",
        }
        for scenario, data in c["scenarios"].items():
            label = titles.get(scenario, scenario)
            add(f"    -- {label}")
            add(f"       mean readout fidelity     : "
                f"{_fmt(data['assignment_matrix']['mean_readout_fidelity'])}  "
                f"cond(A) = {data['assignment_matrix']['condition_number']:.1f}")
            add(f"       raw P(key)                : {_fmt(data['raw']['p_success'])}   "
                f"TVD = {_fmt(data['raw']['tvd_vs_ideal'])}")
            for method in ("pinv", "clip", "nnls"):
                m = data["methods"][method]
                add(f"       {method:<5s} P(key)              : {_fmt(m['p_success'])}   "
                    f"TVD = {_fmt(m['tvd_vs_ideal'])}   "
                    f"neg.mass = {m['negative_mass']:.4f}   "
                    f"valid = {_fmt(m['is_valid_distribution'])}")

    if (d := records.get("experiment_d_threshold")):
        add("")
        add("[D] Noise threshold")
        add(f"    circuit                      : {d['resources']['cx']} CX, "
            f"depth {d['resources']['depth']}")
        worst = d["max_working_p2"]
        add(f"    largest p2 still recovering  : "
            f"{('%.1e' % worst) if worst else 'none tested'}")
        add(f"    {'p2':>10s} {'P(key)':>9s} {'rank':>5s} {'checks':>7s} {'top-is-key':>11s}")
        for row in d["sweep"]:
            add(f"    {row['p2']:>10.1e} {row['p_success']:>9.4f} "
                f"{row['rank_of_secret']:>5d} {row['expected_classical_checks']:>7.1f} "
                f"{_fmt(row['top_key_is_solution']):>11s}")

    if (e := records.get("experiment_e_resources")):
        add("")
        add("[E] Resource scaling")
        add(f"    {'n':>3s} {'N=2^n':>8s} {'pairs':>6s} {'qubits':>7s} {'k*':>5s} "
            f"{'CX':>8s} {'depth':>8s} {'speedup':>9s}")
        for row in e["rows"]:
            add(f"    {row['key_bits']:>3d} {row['key_space']:>8d} {row['num_pairs']:>6d} "
                f"{row['full_circuit']['num_qubits']:>7d} {row['grover_iterations']:>5d} "
                f"{row['full_circuit']['cx']:>8d} {row['full_circuit']['depth']:>8d} "
                f"{row['query_speedup']:>8.1f}x")

    add("")
    add("=" * 74)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    out_dir = args.out or (_repo_root() / "results")
    data_dir = out_dir / "data"
    figure_dir = out_dir / "figures"

    shots = 1024 if args.quick else args.shots
    config = RunConfig(shots=shots, seed=args.seed)
    params = SPNParams(key_bits=args.key_bits, rounds=args.rounds)
    noise = NoiseParams(
        p1=args.p1,
        p2=args.p2,
        p_read_1_given_0=args.readout_01,
        p_read_0_given_1=args.readout_10,
    )

    records: dict[str, dict[str, Any]] = {}

    if args.plots_only:
        for name in EXPERIMENTS.values():
            path = data_dir / f"{name}.json"
            if path.exists():
                records[name] = json.loads(path.read_text(encoding="utf-8"))
        if not records:
            print(f"no saved records found in {data_dir}", file=sys.stderr)
            return 1
    else:
        instance = Instance.build(args.secret_key % params.key_space, params, args.num_pairs)
        key_widths = [int(v) for v in args.key_widths.split(",") if v.strip()]
        max_iters = instance.optimal_iterations + (1 if args.quick else 3)
        scale_factors = QUICK_SCALE_FACTORS if args.quick else None

        print(f"qspn {__version__}  |  {instance.num_qubits} qubits, "
              f"{shots} shots, seed {args.seed}")
        print(f"secret key {instance.describe()['secret_key_bits']}, "
              f"{len(instance.pairs)} pair(s), M = {instance.num_solutions}, "
              f"k* = {instance.optimal_iterations}")
        print()

        jobs: list[tuple[str, str, Callable[[], dict[str, Any]]]] = [
            ("a", "experiment_a_ideal",
             lambda: experiment_a_ideal(instance, config, max_iters)),
            ("b", "experiment_b_noisy",
             lambda: experiment_b_noisy(instance, noise, config, max_iters)),
            ("c", "experiment_c_mitigation",
             lambda: experiment_c_mitigation(instance, noise, config)),
            ("d", "experiment_d_threshold",
             lambda: experiment_d_threshold(instance, noise, config, scale_factors)),
            ("e", "experiment_e_resources",
             lambda: experiment_e_resources(key_widths, config)),
        ]

        selected = set(args.experiments.lower())
        env = _environment()
        for letter, name, run in jobs:
            if letter not in selected:
                continue
            print(f"  running experiment {letter.upper()} ...", end="", flush=True)
            started = time.time()
            record = run()
            elapsed = time.time() - started
            record["environment"] = env
            record["runtime_seconds"] = elapsed
            record["config"] = asdict(config)
            records[name] = record
            _save(record, data_dir, name)
            print(f" done in {elapsed:.1f}s -> results/data/{name}.json")
        print()

    from .plots import generate_all

    figures = generate_all(data_dir, figure_dir)
    for path in figures:
        print(f"  figure -> {path.relative_to(out_dir.parent)}")

    summary = summarise(records)
    print()
    print(summary)
    (out_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    print(f"\nsummary written to {(out_dir / 'summary.txt')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
