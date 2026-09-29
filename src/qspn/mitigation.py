"""Classical readout-error mitigation by assignment-matrix inversion.

The measured distribution ``y`` relates to the true distribution ``x`` through
the *assignment matrix* ``A``, where ``A[i, j] = P(observe i | prepared j)``:

    y = A x

``A`` is characterised by running ``2**n`` calibration circuits, one per basis
state, and reading off the resulting histograms as columns.  Recovering ``x``
then means inverting that linear system.

Three inversion strategies are provided, in increasing order of robustness:

``pinv``
    Moore-Penrose pseudo-inverse.  Fast and unbiased, but ``A^-1`` is not a
    stochastic matrix, so the result routinely contains *negative
    probabilities* -- a well-known pathology of naive unfolding
    (Nachman et al. 2020).

``clip``
    ``pinv`` followed by clipping negatives to zero and renormalising.  Cheap,
    but the clip biases the estimate.

``nnls``
    Constrained least squares: minimise ``||A x - y||_2`` subject to ``x >= 0``,
    then renormalise so ``sum(x) = 1``.  Unlike ``pinv`` the estimate is always
    a valid probability distribution, which is why it is the project default.

    Two caveats, stated so the attribution is not overclaimed.  This is *not*
    the method used by M3 (Nation et al. 2021): M3 is matrix-free -- it never
    forms ``A`` or its inverse -- and solves within the subspace spanned by the
    observed bitstrings using a preconditioned iterative solver.  It shares the
    goal of avoiding exponential calibration, not the mechanism.  And Nachman
    et al. (2020), cited above against ``pinv``, in fact argue for iterative
    Bayesian unfolding over both matrix inversion *and* least squares.  NNLS is
    kept here because it is exactly solvable, dependency-light, and sufficient
    to establish the readout-versus-gate boundary this project measures; it is
    not claimed to be optimal.

**Scaling caveat, stated plainly:** ``A`` is ``2**n x 2**n``, so full
calibration is exponential in the number of *measured* qubits.  It is tractable
here only because we measure the ``key_bits`` key qubits alone (16 circuits at
4 bits, 256 at 8 bits).  Beyond ~10 measured qubits one must switch to a
subspace-reduced or tensored method -- this is the point for which
Nation et al. (2021) is the right citation.  See the report's limitations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import ClassicalRegister, QuantumRegister

Counts = dict[str, int]


def calibration_circuits(num_qubits: int) -> list[QuantumCircuit]:
    """One circuit per basis state: prepare ``|j>``, measure immediately.

    Returned in order ``j = 0 .. 2**n - 1`` so that circuit ``j`` yields column
    ``j`` of the assignment matrix.
    """
    circuits = []
    for j in range(1 << num_qubits):
        qr = QuantumRegister(num_qubits, "q")
        cr = ClassicalRegister(num_qubits, "c")
        qc = QuantumCircuit(qr, cr, name=f"cal_{j:0{num_qubits}b}")
        for i in range(num_qubits):
            if (j >> i) & 1:
                qc.x(qr[i])
        qc.measure(qr, cr)
        circuits.append(qc)
    return circuits


def counts_to_vector(counts: Counts, num_qubits: int) -> np.ndarray:
    """Convert a Qiskit counts dict to a normalised probability vector.

    Bitstring keys are big-endian (``c[n-1] ... c[0]``), so ``int(key, 2)``
    already gives the integer the register holds.
    """
    vec = np.zeros(1 << num_qubits, dtype=float)
    total = sum(counts.values())
    if total == 0:
        return vec
    for bitstring, n in counts.items():
        vec[int(bitstring.replace(" ", ""), 2)] = n / total
    return vec


def vector_to_counts(vec: np.ndarray, num_qubits: int, shots: int) -> Counts:
    """Convert a probability vector back to a counts-like dict (for plotting)."""
    return {
        format(i, f"0{num_qubits}b"): float(pr * shots)
        for i, pr in enumerate(vec)
        if pr > 0
    }


@dataclass
class AssignmentMatrix:
    """Characterised readout response of the measured register."""

    matrix: np.ndarray
    num_qubits: int
    shots: int = 0
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_calibration_counts(
        cls, counts_list: list[Counts], num_qubits: int, shots: int = 0
    ) -> "AssignmentMatrix":
        """Build ``A`` from calibration histograms, column ``j`` from circuit ``j``."""
        dim = 1 << num_qubits
        if len(counts_list) != dim:
            raise ValueError(f"expected {dim} calibration results, got {len(counts_list)}")
        matrix = np.zeros((dim, dim), dtype=float)
        for j, counts in enumerate(counts_list):
            matrix[:, j] = counts_to_vector(counts, num_qubits)
        return cls(matrix=matrix, num_qubits=num_qubits, shots=shots)

    @property
    def mean_readout_fidelity(self) -> float:
        """Average of the diagonal: probability a prepared state is read correctly."""
        return float(np.mean(np.diag(self.matrix)))

    @property
    def condition_number(self) -> float:
        """Condition number of ``A``.

        This is the amplification factor for statistical noise during
        inversion, and it is the reason mitigation is not free: a poorly
        conditioned ``A`` converts shot noise into large errors in ``x``.
        """
        return float(np.linalg.cond(self.matrix))

    def mitigate(self, counts: Counts, method: str = "nnls") -> np.ndarray:
        """Recover an estimate of the true distribution from observed ``counts``."""
        return mitigate_vector(self.matrix, counts_to_vector(counts, self.num_qubits), method)


def mitigate_vector(matrix: np.ndarray, observed: np.ndarray, method: str = "nnls") -> np.ndarray:
    """Solve ``A x = y`` for ``x`` using the requested strategy."""
    if method == "pinv":
        return np.linalg.pinv(matrix) @ observed

    if method == "clip":
        raw = np.linalg.pinv(matrix) @ observed
        return _renormalise(np.clip(raw, 0.0, None))

    if method == "nnls":
        try:
            from scipy.optimize import nnls
        except ImportError:  # pragma: no cover - scipy ships with qiskit
            raw = np.linalg.pinv(matrix) @ observed
            return _renormalise(np.clip(raw, 0.0, None))
        solution, _residual = nnls(matrix, observed)
        return _renormalise(solution)

    raise ValueError(f"unknown mitigation method {method!r}")


def _renormalise(vec: np.ndarray) -> np.ndarray:
    total = vec.sum()
    if total <= 0:
        return np.full_like(vec, 1.0 / vec.size)
    return vec / total


def negative_mass(vec: np.ndarray) -> float:
    """Total probability mass sitting below zero.

    Reported for the ``pinv`` method to make the unphysicality concrete rather
    than hand-waved -- a strictly-zero value means the raw inverse happened to
    land inside the simplex.

    Summing an empty selection yields ``-0.0``, which formats as ``-0.0000`` in
    the report tables, so the result is normalised to a positive zero.
    """
    total = float(-np.sum(vec[vec < 0]))
    return total if total > 0.0 else 0.0
