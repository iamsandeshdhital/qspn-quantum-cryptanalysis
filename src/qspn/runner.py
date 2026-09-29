"""Simulation backend: transpilation, execution, and readout calibration.

Everything that touches the simulator lives here so the algorithmic modules
stay pure and unit-testable.

The single most important detail in this file is :func:`transpile_for`.  A
noise model attaches errors to *named basis gates*; a circuit still containing
composite instructions (``UnitaryGate``, multi-controlled Z, ``swap``) has no
``cx`` or ``sx`` for the model to bind to, so it would run essentially
noise-free and the whole noise study would be silently meaningless.  Every
execution path therefore transpiles to :data:`qspn.noise.BASIS_GATES` first.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from .mitigation import Counts, calibration_circuits, counts_to_vector
from .noise import BASIS_GATES, NoiseModel, NoiseParams, build_noise_model

DEFAULT_SHOTS = 4096
DEFAULT_SEED = 20260902


@dataclass(frozen=True)
class RunConfig:
    """Execution settings shared by every experiment."""

    shots: int = DEFAULT_SHOTS
    seed: int = DEFAULT_SEED
    optimization_level: int = 1

    #: Aer simulation method.  **This must stay ``"statevector"``.**
    #:
    #: With a noise model attached, Aer's ``"automatic"`` method may select
    #: density-matrix simulation, which stores ``4**n`` complex amplitudes --
    #: 68 GB at 16 qubits, enough to exhaust any commodity machine.  Forcing
    #: ``"statevector"`` makes Aer use stochastic *quantum trajectories*
    #: instead: one pure state per shot, sampling a Kraus operator at each
    #: noisy gate, so memory stays at ``O(2**n)`` (1 MB at 16 qubits) and the
    #: shot average converges to the same density-matrix result.
    #:
    #: The cost is moved from memory to time: runtime is
    #: ``O(shots * gates * 2**n)``.  This trade is the concrete content of the
    #: project's resource-efficiency objective.
    method: str = "statevector"

    #: Hard cap handed to Aer, so an over-large configuration fails fast with a
    #: clear error instead of silently swapping to disk.
    max_memory_mb: int = 4096


def transpile_for(
    circuit: QuantumCircuit, config: RunConfig | None = None
) -> QuantumCircuit:
    """Decompose ``circuit`` into the native basis so noise has something to bind to."""
    cfg = config or RunConfig()
    return transpile(
        circuit,
        basis_gates=BASIS_GATES,
        optimization_level=cfg.optimization_level,
        seed_transpiler=cfg.seed,
    )


def make_simulator(
    noise_params: NoiseParams | None = None,
    config: RunConfig | None = None,
    noise_model: NoiseModel | None = None,
) -> AerSimulator:
    """Build an :class:`AerSimulator`, optionally with a noise model attached."""
    cfg = config or RunConfig()
    if noise_model is None and noise_params is not None:
        noise_model = build_noise_model(noise_params)
    kwargs: dict = {
        "method": cfg.method,
        "seed_simulator": cfg.seed,
        "max_memory_mb": cfg.max_memory_mb,
    }
    if noise_model is not None:
        kwargs["noise_model"] = noise_model
    return AerSimulator(**kwargs)


def run_counts(
    circuit: QuantumCircuit,
    noise_params: NoiseParams | None = None,
    config: RunConfig | None = None,
    noise_model: NoiseModel | None = None,
    already_transpiled: bool = False,
) -> Counts:
    """Execute one circuit and return raw measurement counts."""
    cfg = config or RunConfig()
    prepared = circuit if already_transpiled else transpile_for(circuit, cfg)
    simulator = make_simulator(noise_params, cfg, noise_model)
    result = simulator.run(prepared, shots=cfg.shots).result()
    return result.get_counts()


def run_distribution(
    circuit: QuantumCircuit,
    num_qubits: int,
    noise_params: NoiseParams | None = None,
    config: RunConfig | None = None,
    noise_model: NoiseModel | None = None,
    already_transpiled: bool = False,
) -> tuple[np.ndarray, Counts]:
    """Execute one circuit and return ``(probability_vector, raw_counts)``."""
    counts = run_counts(
        circuit, noise_params, config, noise_model, already_transpiled
    )
    return counts_to_vector(counts, num_qubits), counts


def ideal_distribution(
    circuit: QuantumCircuit, num_qubits: int, config: RunConfig | None = None
) -> np.ndarray:
    """Exact output distribution of the key register, computed without sampling.

    Uses Aer's statevector method with ``save_probabilities`` on the key qubits,
    so this reference curve carries *no shot noise at all* -- important, since it
    is the baseline every distance metric is measured against.  (Aer's C++
    statevector is used rather than :class:`qiskit.quantum_info.Statevector`
    purely for speed; the result is identical.)

    Final measurements are stripped first, because a measured circuit would
    collapse the state before the probabilities are saved.
    """
    cfg = config or RunConfig()
    stripped = circuit.remove_final_measurements(inplace=False)
    simulator = AerSimulator(method="statevector", seed_simulator=cfg.seed)
    prepared = transpile(stripped, simulator, optimization_level=0)
    prepared.save_probabilities(list(range(num_qubits)))
    data = simulator.run(prepared, shots=1).result().data()
    return np.asarray(data["probabilities"], dtype=float)


def run_calibration(
    num_qubits: int,
    noise_params: NoiseParams | None = None,
    config: RunConfig | None = None,
    noise_model: NoiseModel | None = None,
) -> list[Counts]:
    """Run the ``2**num_qubits`` readout-calibration circuits.

    Calibration circuits are transpiled with the *same* settings as the payload
    circuit, so the readout channel is characterised under matching conditions.
    Note they are shallow (X gates then measure), so gate depolarizing error
    contributes negligibly and ``A`` really does capture the measurement
    channel rather than a mixture of gate and readout effects.
    """
    cfg = config or RunConfig()
    circuits = [transpile_for(c, cfg) for c in calibration_circuits(num_qubits)]
    simulator = make_simulator(noise_params, cfg, noise_model)
    result = simulator.run(circuits, shots=cfg.shots).result()
    return [result.get_counts(i) for i in range(len(circuits))]
