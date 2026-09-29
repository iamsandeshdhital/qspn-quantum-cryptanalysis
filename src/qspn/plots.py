"""Figure generation.  Every figure is written from a saved experiment record,
so plots can be regenerated from ``results/data/*.json`` without re-simulating.

The style is deliberately plain: no seaborn dependency, no styles that shift
between matplotlib versions, and colours chosen to stay distinguishable in
greyscale print.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: no display needed, and keeps CI reproducible
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

IDEAL_C = "#1f4e79"
NOISY_C = "#c0392b"
MITIG_C = "#1e8449"
ANALYTIC_C = "#7f8c8d"

#: Human-readable titles for the Experiment C scenarios.
_SCENARIO_TITLES = {
    "readout_only": "readout error only",
    "reduced_gate": "readout + reduced gate error (x{scale:g})",
    "full": "readout + full gate error",
}

FIGSIZE = (7.0, 4.2)
DPI = 160


def _finish(fig, axes, path: Path, legend: bool = True) -> Path:
    if legend:
        axes.legend(frameon=False, fontsize=9)
    axes.grid(True, alpha=0.25, linewidth=0.6)
    axes.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def plot_amplification(record: dict[str, Any], path: Path) -> Path:
    """Experiment A: measured amplification curve against the closed form."""
    sweep = record["sweep"]
    k = [r["iterations"] for r in sweep]
    fig, ax = plt.subplots(figsize=FIGSIZE)

    dense = np.linspace(0, max(k), 400)
    key_space = record["instance"]["key_space"]
    solutions = max(1, record["instance"]["num_solutions"])
    theta = np.arcsin(np.sqrt(solutions / key_space))
    ax.plot(
        dense,
        np.sin((2 * dense + 1) * theta) ** 2,
        color=ANALYTIC_C,
        lw=1.2,
        ls="--",
        label=r"analytic $\sin^2((2k{+}1)\theta)$",
    )
    ax.plot(k, [r["exact_p_success"] for r in sweep], "o-", color=IDEAL_C,
            lw=1.6, ms=5, label="statevector (exact)")
    ax.plot(k, [r["sampled_p_success"] for r in sweep], "s", color=NOISY_C,
            ms=5, label=f"sampled ({record['shots']} shots)")
    ax.axhline(1 / key_space, color="k", lw=0.8, ls=":", label="random guessing")
    ax.axvline(record["instance"]["optimal_iterations"], color=MITIG_C, lw=0.9, ls="-.",
               label=r"optimal $k^\ast$")

    ax.set_xlabel("Grover iterations $k$")
    ax.set_ylabel("P(correct key)")
    ax.set_title(
        f"Experiment A: ideal amplification, {record['instance']['key_bits']}-bit key "
        f"(N={key_space}, M={solutions})"
    )
    ax.set_ylim(-0.03, 1.05)
    return _finish(fig, ax, path)


def plot_noise_degradation(
    record_b: dict[str, Any], path: Path
) -> Path:
    """Experiment B: ideal versus noisy success across the iteration sweep."""
    sweep = record_b["sweep"]
    k = [r["iterations"] for r in sweep]
    fig, ax = plt.subplots(figsize=FIGSIZE)

    ax.plot(k, [r["ideal_p_success"] for r in sweep], "o-", color=IDEAL_C,
            lw=1.6, ms=5, label="ideal (noiseless)")
    ax.plot(k, [r["p_success"] for r in sweep], "s-", color=NOISY_C,
            lw=1.6, ms=5, label="noisy simulation")
    ax.axhline(record_b["uniform_baseline"], color="k", lw=0.8, ls=":",
               label="random guessing")

    noise = record_b["noise"]
    ax.set_xlabel("Grover iterations $k$")
    ax.set_ylabel("P(correct key)")
    ax.set_title(
        f"Experiment B: NISQ degradation ($p_1$={noise['p1']:.0e}, "
        f"$p_2$={noise['p2']:.0e}, readout {noise['p_read_1_given_0']:.1%}/"
        f"{noise['p_read_0_given_1']:.1%})"
    )
    ax.set_ylim(-0.03, 1.05)

    ax2 = ax.twinx()
    ax2.plot(k, [r["resources"]["cx"] for r in sweep], "^:", color=ANALYTIC_C,
             lw=1.0, ms=4)
    ax2.set_ylabel("CX gates (transpiled)", color=ANALYTIC_C)
    ax2.tick_params(axis="y", labelcolor=ANALYTIC_C)
    ax2.spines[["top"]].set_visible(False)
    return _finish(fig, ax, path)


def plot_mitigation(record_c: dict[str, Any], path: Path) -> Path:
    """Experiment C: per-key distributions (ideal / raw / mitigated), one panel per scenario."""
    key_bits = record_c["instance"]["key_bits"]
    keys = np.arange(1 << key_bits)
    labels = [format(i, f"0{key_bits}b") for i in keys]
    ideal = np.array(record_c["ideal_distribution"])
    secret = record_c["instance"]["secret_key"]

    scenarios = [
        name
        for name in ("readout_only", "reduced_gate", "full")
        if name in record_c["scenarios"]
    ]
    fig, axes = plt.subplots(
        len(scenarios), 1, figsize=(7.6, 3.1 * len(scenarios)), sharex=True
    )
    axes = np.atleast_1d(axes)
    width = 0.27
    for ax, scenario in zip(axes, scenarios):
        data = record_c["scenarios"][scenario]
        raw = np.array(data["raw"]["distribution"])
        mit = np.clip(np.array(data["methods"]["nnls"]["distribution"]), 0, None)

        ax.bar(keys - width, ideal, width, color=IDEAL_C, label="ideal")
        ax.bar(keys, raw, width, color=NOISY_C, label="noisy (raw)")
        ax.bar(keys + width, mit, width, color=MITIG_C, label="mitigated (NNLS)")
        ax.axvline(secret, color="k", lw=0.7, ls=":")

        title = _SCENARIO_TITLES[scenario].format(
            scale=record_c.get("reduced_gate_scale", 0)
        )
        ax.set_title(
            f"{title}: raw P={data['raw']['p_success']:.3f} "
            f"-> mitigated P={data['methods']['nnls']['p_success']:.3f} "
            f"(ideal {record_c['ideal_p_success']:.3f})",
            fontsize=10,
        )
        ax.set_ylabel("probability")
        ax.grid(True, alpha=0.25, axis="y", linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].legend(frameon=False, fontsize=9, ncol=3)
    axes[-1].set_xticks(keys)
    axes[-1].set_xticklabels(labels, rotation=90, fontsize=7)
    axes[-1].set_xlabel(f"candidate key (secret = {format(secret, f'0{key_bits}b')})")
    fig.suptitle("Experiment C: readout-error mitigation", fontsize=12)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def plot_threshold(record_d: dict[str, Any], path: Path) -> Path:
    """Experiment D: success probability against two-qubit error rate."""
    sweep = [r for r in record_d["sweep"] if r["p2"] > 0]
    p2 = [r["p2"] for r in sweep]
    fig, ax = plt.subplots(figsize=FIGSIZE)

    ax.semilogx(p2, [r["p_success"] for r in sweep], "o-", color=NOISY_C,
                lw=1.6, ms=5, label="P(correct key)")
    ax.axhline(record_d["uniform_baseline"], color="k", lw=0.8, ls=":",
               label="random guessing")
    ideal = next((r["p_success"] for r in record_d["sweep"] if r["p2"] == 0), None)
    if ideal is not None:
        ax.axhline(ideal, color=IDEAL_C, lw=0.9, ls="--", label="noiseless")
    if record_d["max_working_p2"]:
        ax.axvline(record_d["max_working_p2"], color=MITIG_C, lw=0.9, ls="-.",
                   label=f"last working $p_2$ = {record_d['max_working_p2']:.1e}")

    cx = record_d["resources"]["cx"]
    ax.set_xlabel("two-qubit depolarizing rate $p_2$")
    ax.set_ylabel("P(correct key)")
    ax.set_title(f"Experiment D: noise threshold ({cx} CX gates, "
                 f"depth {record_d['resources']['depth']})")
    ax.set_ylim(-0.03, 1.05)
    return _finish(fig, ax, path)


def plot_resources(record_e: dict[str, Any], path: Path) -> Path:
    """Experiment E: query complexity and circuit cost against key width."""
    rows = record_e["rows"]
    kb = [r["key_bits"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.2))

    ax1.semilogy(kb, [r["classical_queries"] for r in rows], "o-", color=NOISY_C,
                 lw=1.6, ms=5, label=r"classical $2^n$")
    ax1.semilogy(kb, [r["grover_iterations"] for r in rows], "s-", color=IDEAL_C,
                 lw=1.6, ms=5, label=r"Grover $\frac{\pi}{4}\sqrt{2^n}$")
    ax1.set_xlabel("key width $n$ (bits)")
    ax1.set_ylabel("oracle queries")
    ax1.set_title("Query complexity")
    ax1.legend(frameon=False, fontsize=9)
    ax1.grid(True, alpha=0.25, which="both", linewidth=0.6)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2.plot(kb, [r["full_circuit"]["cx"] for r in rows], "o-", color=MITIG_C,
             lw=1.6, ms=5, label="CX gates (full search)")
    ax2.plot(kb, [r["single_iteration"]["cx"] for r in rows], "s--", color=ANALYTIC_C,
             lw=1.4, ms=5, label="CX gates (one iteration)")
    ax2.set_xlabel("key width $n$ (bits)")
    ax2.set_ylabel("CX gates (transpiled)")
    ax2.set_title("Circuit cost: the price of each query")
    ax2.legend(frameon=False, fontsize=9)
    ax2.grid(True, alpha=0.25, linewidth=0.6)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Experiment E: quadratic query saving versus growing circuit cost",
                 fontsize=12)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def plot_assignment_matrix(record_c: dict[str, Any], path: Path) -> Path:
    """Heat map of the readout assignment matrix ``A``."""
    key_bits = record_c["instance"]["key_bits"]
    matrix = np.array(
        record_c["scenarios"]["readout_only"]["assignment_matrix"]["matrix"]
    )
    labels = [format(i, f"0{key_bits}b") for i in range(matrix.shape[0])]

    fig, ax = plt.subplots(figsize=(5.8, 5.0))
    image = ax.imshow(matrix, cmap="magma", norm=matplotlib.colors.LogNorm(
        vmin=max(matrix[matrix > 0].min(), 1e-5), vmax=1.0))
    fig.colorbar(image, ax=ax, label="P(observed | prepared)")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90, fontsize=6)
    ax.set_yticklabels(labels, fontsize=6)
    ax.set_xlabel("prepared state")
    ax.set_ylabel("observed state")
    cond = record_c["scenarios"]["readout_only"]["assignment_matrix"]["condition_number"]
    fid = record_c["scenarios"]["readout_only"]["assignment_matrix"]["mean_readout_fidelity"]
    ax.set_title(f"Assignment matrix $A$\nmean fidelity {fid:.3f}, cond(A) = {cond:.1f}",
                 fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def generate_all(data_dir: Path, figure_dir: Path) -> list[Path]:
    """Regenerate every figure from saved JSON records."""
    made: list[Path] = []

    def load(name: str) -> dict[str, Any] | None:
        path = data_dir / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    if (rec := load("experiment_a_ideal.json")):
        made.append(plot_amplification(rec, figure_dir / "fig1_amplification.png"))
    if (rec := load("experiment_b_noisy.json")):
        made.append(plot_noise_degradation(rec, figure_dir / "fig2_noise_degradation.png"))
    if (rec := load("experiment_c_mitigation.json")):
        made.append(plot_mitigation(rec, figure_dir / "fig3_mitigation.png"))
        made.append(plot_assignment_matrix(rec, figure_dir / "fig4_assignment_matrix.png"))
    if (rec := load("experiment_d_threshold.json")):
        made.append(plot_threshold(rec, figure_dir / "fig5_noise_threshold.png"))
    if (rec := load("experiment_e_resources.json")):
        made.append(plot_resources(rec, figure_dir / "fig6_resources.png"))
    return made
