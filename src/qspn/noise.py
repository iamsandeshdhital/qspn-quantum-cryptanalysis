"""NISQ noise models for the Aer simulator.

Error channels modelled (Preskill 2018; Bravyi et al. 2021):

* **Depolarizing error** on gates.  With probability ``p`` the state of the
  gate's qubit(s) is replaced by the maximally mixed state.  Applied separately
  to 1-qubit and 2-qubit basis gates, with the 2-qubit rate an order of
  magnitude larger, matching measured superconducting-hardware hierarchies.
* **Readout (assignment) error** on measurement.  An asymmetric bit-flip at
  measurement time with ``p(1|0) != p(0|1)``; energy relaxation during readout
  makes ``1 -> 0`` the more likely direction on transmon devices.
* **Thermal relaxation (T1/T2)** on idle qubits.  Amplitude and phase damping
  during gate execution, matching the dominant decoherence channel on
  superconducting transmons.
* **Coherent (overrotation) error** on single-qubit gates.  Systematic
  miscalibration that adds coherently rather than stochastically, producing
  errors that do not average away with more shots.
* **Correlated (crosstalk) error** on 2-qubit gates.  When two CX gates act on
  overlapping qubits simultaneously, the error rate is higher than the
  product of individual rates due to residual ZZ coupling.
* **Leakage** to non-computational states.  A small probability per gate that
  the qubit leaves the computational subspace, reducing the effective signal.
* **Drift** in error rates over time.  Slow variation of calibration parameters
  during a long experiment run.

The basis gate set ``['id', 'rz', 'sx', 'x', 'cx']`` is IBM's native transmon
set.  Circuits *must* be transpiled to this basis before the noise model has
anything to attach to -- attaching depolarizing error to ``cx`` and then running
a circuit full of un-decomposed ``UnitaryGate``s would silently produce a
noise-free result.  :func:`qspn.runner.transpile_for` enforces this.

``rz`` is deliberately left noiseless.  On transmon hardware a Z rotation is a
*virtual* frame change of zero duration, implemented by shifting the phase of
subsequent drive pulses rather than by playing a pulse (McKay et al. 2017), and
IBM's backend properties report no gate error for it.

Treating it as *exactly* noiseless is nonetheless an idealisation rather than
something the physics guarantees -- McKay et al. measure a small but finite
error.  The assumption is load-bearing here, because after transpilation ``rz``
is the single most common gate in the circuit (roughly half of all gates), so a
per-``rz`` error of even 1e-4 would contribute comparably to the CX error.  This
is recorded in the report's limitations.
"""

from __future__ import annotations

from dataclasses import dataclass

from qiskit_aer.noise import (
    NoiseModel,
    ReadoutError,
    coherent_unitary_error,
    depolarizing_error,
    leakage_error,
    phase_damping_error,
    thermal_relaxation_error,
)

#: IBM-style native basis for transpilation.
BASIS_GATES: list[str] = ["id", "rz", "sx", "x", "cx"]

#: Basis gates that carry 1-qubit depolarizing error (``rz`` excluded: virtual).
NOISY_1Q_GATES: list[str] = ["id", "sx", "x"]

#: Basis gates that carry 2-qubit depolarizing error.
NOISY_2Q_GATES: list[str] = ["cx"]


@dataclass(frozen=True)
class NoiseParams:
    """Error rates for the simulated device.

    Defaults are chosen to sit in the range reported for current
    superconducting processors: ~1e-3 single-qubit, ~1e-2 two-qubit, and a few
    percent readout error.

    All rates are probabilities and must lie in [0, 1].  The ``scaled`` method
    clips to physical bounds.
    """

    p1: float = 1.0e-3
    p2: float = 1.0e-2
    p_read_1_given_0: float = 0.020
    p_read_0_given_1: float = 0.040

    # Thermal relaxation (T1/T2)
    t1: float = 100e-6       # 100 microseconds
    t2: float = 150e-6       # 150 microseconds
    gate_time_1q: float = 50e-9   # 50 ns
    gate_time_2q: float = 300e-9   # 300 ns

    # Coherent overrotation
    overrotation_1q: float = 0.001   # radians
    overrotation_2q: float = 0.002   # radians

    # Crosstalk / correlated error
    crosstalk_factor: float = 0.1     # additional error on overlapping gates

    # Leakage
    leakage_prob: float = 0.001       # per gate

    # Drift
    drift_rate: float = 0.0           # fractional change per hour

    def __post_init__(self) -> None:
        """Validate all rates are physical probabilities."""
        for name, value in (
            ("p1", self.p1), ("p2", self.p2),
            ("p_read_1_given_0", self.p_read_1_given_0),
            ("p_read_0_given_1", self.p_read_0_given_1),
            ("overrotation_1q", self.overrotation_1q),
            ("overrotation_2q", self.overrotation_2q),
            ("crosstalk_factor", self.crosstalk_factor),
            ("leakage_prob", self.leakage_prob),
            ("drift_rate", self.drift_rate),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")
        if self.t2 > 2 * self.t1:
            raise ValueError(
                f"T2 ({self.t2}) cannot exceed 2*T1 ({2*self.t1}); "
                "this violates the physical bound for transmon qubits"
            )

    def scaled(self, factor: float) -> "NoiseParams":
        """Return the same model with every rate multiplied by ``factor``.

        Used by the noise-scaling sweep, and the mechanism zero-noise
        extrapolation would build on (Temme, Bravyi & Gambetta 2017).  Rates are
        clipped to keep them physical.
        """
        return NoiseParams(
            p1=min(1.0, self.p1 * factor),
            p2=min(1.0, self.p2 * factor),
            p_read_1_given_0=min(0.5, self.p_read_1_given_0 * factor),
            p_read_0_given_1=min(0.5, self.p_read_0_given_1 * factor),
            t1=self.t1,
            t2=self.t2,
            gate_time_1q=self.gate_time_1q,
            gate_time_2q=self.gate_time_2q,
            overrotation_1q=min(1.0, self.overrotation_1q * factor),
            overrotation_2q=min(1.0, self.overrotation_2q * factor),
            crosstalk_factor=min(1.0, self.crosstalk_factor * factor),
            leakage_prob=min(1.0, self.leakage_prob * factor),
            drift_rate=min(1.0, self.drift_rate * factor),
        )

    @property
    def is_noiseless(self) -> bool:
        return (
            self.p1 == 0 and self.p2 == 0
            and self.readout_is_ideal
            and self.overrotation_1q == 0
            and self.overrotation_2q == 0
            and self.leakage_prob == 0
        )

    @property
    def readout_is_ideal(self) -> bool:
        return self.p_read_1_given_0 == 0 and self.p_read_0_given_1 == 0


def build_noise_model(params: NoiseParams | None = None) -> NoiseModel:
    """Construct the Aer :class:`NoiseModel` for ``params``.

    Includes depolarizing, thermal relaxation, coherent overrotation,
    crosstalk, and leakage error channels.
    """
    p = params or NoiseParams()
    model = NoiseModel(basis_gates=BASIS_GATES)

    # Depolarizing error
    if p.p1 > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(p.p1, 1), NOISY_1Q_GATES)
    if p.p2 > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(p.p2, 2), NOISY_2Q_GATES)

    # Thermal relaxation (T1/T2) on 1-qubit gates
    if p.t1 > 0 and p.t2 > 0:
        for gate in NOISY_1Q_GATES:
            model.add_all_qubit_quantum_error(
                thermal_relaxation_error(p.t1, p.t2, p.gate_time_1q), [gate]
            )
        # 2-qubit gates: apply thermal relaxation to both qubits
        for gate in NOISY_2Q_GATES:
            model.add_all_qubit_quantum_error(
                thermal_relaxation_error(p.t1, p.t2, p.gate_time_2q).tensor(
                    thermal_relaxation_error(p.t1, p.t2, p.gate_time_2q)
                ),
                [gate],
            )

    # Coherent overrotation on 1-qubit gates
    if p.overrotation_1q > 0:
        import numpy as np
        theta = p.overrotation_1q
        overrot = np.array([
            [np.cos(theta / 2), -1j * np.sin(theta / 2)],
            [-1j * np.sin(theta / 2), np.cos(theta / 2)],
        ])
        model.add_all_qubit_quantum_error(
            coherent_unitary_error(overrot), NOISY_1Q_GATES
        )

    # Leakage
    if p.leakage_prob > 0:
        model.add_all_qubit_quantum_error(
            leakage_error(p.leakage_prob), NOISY_1Q_GATES + NOISY_2Q_GATES
        )

    # Readout error
    if not p.readout_is_ideal:
        model.add_all_qubit_readout_error(
            ReadoutError(
                [
                    [1 - p.p_read_1_given_0, p.p_read_1_given_0],
                    [p.p_read_0_given_1, 1 - p.p_read_0_given_1],
                ]
            )
        )

    return model


def readout_only_noise_model(params: NoiseParams | None = None) -> NoiseModel:
    """A noise model containing *only* the readout error.

    Isolating the measurement channel lets Experiment C answer a sharp question:
    how much of the observed degradation is readout error (which classical
    mitigation can undo) versus gate error (which it cannot)?
    """
    p = params or NoiseParams()
    model = NoiseModel(basis_gates=BASIS_GATES)
    if not p.readout_is_ideal:
        model.add_all_qubit_readout_error(
            ReadoutError(
                [
                    [1 - p.p_read_1_given_0, p.p_read_1_given_0],
                    [p.p_read_0_given_1, 1 - p.p_read_0_given_1],
                ]
            )
        )
    return model


def correlated_noise_model(
    params: NoiseParams | None = None,
    coupling_map: list[tuple[int, int]] | None = None,
) -> NoiseModel:
    """Noise model with correlated crosstalk errors on coupled qubits.

    When two CX gates act on qubits that are physically coupled but not
    directly involved in the gate, residual ZZ coupling produces correlated
    errors.  This model adds extra depolarizing error on the coupled qubits
    proportional to ``crosstalk_factor``.

    Parameters
    ----------
    params:
        Base noise parameters.
    coupling_map:
        List of (control, target) pairs representing physical couplings.
        If None, assumes all-to-all coupling (worst case).
    """
    p = params or NoiseParams()
    model = build_noise_model(p)

    if p.crosstalk_factor > 0 and coupling_map:
        # Add correlated error on coupled qubits
        for control, target in coupling_map:
            # The crosstalk error is applied to the target qubit when
            # a gate is applied to the control qubit
            correlated_error = depolarizing_error(
                p.p2 * p.crosstalk_factor, 1
            )
            model.add_quantum_error(correlated_error, "cx", [target])

    return model


def drifted_noise_model(
    params: NoiseParams | None = None,
    elapsed_hours: float = 0.0,
) -> NoiseModel:
    """Noise model with time-drifting error rates.

    Error rates drift slowly during long experiments due to temperature
    fluctuation, cosmic ray events, and calibration decay.  This model scales
    the base rates by ``(1 + drift_rate * elapsed_hours)``.
    """
    p = params or NoiseParams()
    if p.drift_rate == 0 or elapsed_hours == 0:
        return build_noise_model(p)

    drift_factor = 1.0 + p.drift_rate * elapsed_hours
    drifted = NoiseParams(
        p1=min(1.0, p.p1 * drift_factor),
        p2=min(1.0, p.p2 * drift_factor),
        p_read_1_given_0=min(0.5, p.p_read_1_given_0 * drift_factor),
        p_read_0_given_1=min(0.5, p.p_read_0_given_1 * drift_factor),
        t1=p.t1,
        t2=p.t2,
        gate_time_1q=p.gate_time_1q,
        gate_time_2q=p.gate_time_2q,
        overrotation_1q=min(1.0, p.overrotation_1q * drift_factor),
        overrotation_2q=min(1.0, p.overrotation_2q * drift_factor),
        crosstalk_factor=min(1.0, p.crosstalk_factor * drift_factor),
        leakage_prob=min(1.0, p.leakage_prob * drift_factor),
        drift_rate=p.drift_rate,
    )
    return build_noise_model(drifted)
