"""NISQ noise models for the Aer simulator.

Two error channels are modelled, both standard in the NISQ literature
(Preskill 2018):

* **Depolarizing error** on gates.  With probability ``p`` the state of the
  gate's qubit(s) is replaced by the maximally mixed state.  Applied separately
  to 1-qubit and 2-qubit basis gates, with the 2-qubit rate an order of
  magnitude larger, matching measured superconducting-hardware hierarchies.
* **Readout (assignment) error** on measurement.  An asymmetric bit-flip at
  measurement time with ``p(1|0) != p(0|1)``; energy relaxation during readout
  makes ``1 -> 0`` the more likely direction on transmon devices.

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

from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error

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
    """

    p1: float = 1.0e-3
    p2: float = 1.0e-2
    p_read_1_given_0: float = 0.020
    p_read_0_given_1: float = 0.040

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
        )

    @property
    def is_noiseless(self) -> bool:
        return self.p1 == 0 and self.p2 == 0 and self.readout_is_ideal

    @property
    def readout_is_ideal(self) -> bool:
        return self.p_read_1_given_0 == 0 and self.p_read_0_given_1 == 0


def build_noise_model(params: NoiseParams | None = None) -> NoiseModel:
    """Construct the Aer :class:`NoiseModel` for ``params``."""
    p = params or NoiseParams()
    model = NoiseModel(basis_gates=BASIS_GATES)

    if p.p1 > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(p.p1, 1), NOISY_1Q_GATES)
    if p.p2 > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(p.p2, 2), NOISY_2Q_GATES)
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
