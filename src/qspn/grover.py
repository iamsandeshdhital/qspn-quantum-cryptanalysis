"""Grover amplitude amplification over the key register.

Contains the diffusion operator, the full search circuit, and the *analytic*
success probability used to sanity-check the simulations.

The optimal iteration count is ``floor((pi/4) * sqrt(N/M))`` (Boyer, Brassard,
Hoyer & Tapp 1998), where ``N = 2**key_bits`` and ``M`` is the number of marked
keys.  Note this is not ``sqrt(N)``: the ``pi/4`` factor matters, and applying
*more* than the optimal number of iterations makes the success probability go
back *down* -- the over-rotation effect that Experiment A measures directly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from qiskit import QuantumCircuit
from qiskit.circuit import ClassicalRegister, QuantumRegister
from qiskit.circuit.library import ZGate

from .oracle import key_search_oracle
from .spn import BLOCK_BITS, SPNParams, brute_force_keys


def optimal_iterations(key_space: int, num_solutions: int = 1) -> int:
    """Optimal number of Grover iterations for ``num_solutions`` marked states."""
    if num_solutions <= 0:
        raise ValueError("num_solutions must be >= 1")
    if num_solutions >= key_space:
        return 0
    return int(math.floor((math.pi / 4.0) * math.sqrt(key_space / num_solutions)))


def success_probability(iterations: int, key_space: int, num_solutions: int = 1) -> float:
    """Analytic probability of measuring *some* marked key after ``iterations``.

    With ``theta = arcsin(sqrt(M/N))``, the amplitude after ``k`` iterations
    puts probability ``sin^2((2k + 1) * theta)`` on the marked subspace.
    """
    theta = math.asin(math.sqrt(num_solutions / key_space))
    return math.sin((2 * iterations + 1) * theta) ** 2


def diffuser(num_qubits: int) -> QuantumCircuit:
    """Grover diffusion operator: reflection about the uniform superposition.

    ``D = 2|s><s| - I``, built as ``H^n (2|0><0| - I) H^n`` up to an irrelevant
    global sign.  The inner reflection is an X-conjugated multi-controlled Z, so
    no ancilla is required.
    """
    qc = QuantumCircuit(num_qubits, name="D")
    qc.h(range(num_qubits))
    qc.x(range(num_qubits))
    if num_qubits == 1:
        qc.z(0)
    else:
        qc.append(ZGate().control(num_qubits - 1), list(range(num_qubits)))
    qc.x(range(num_qubits))
    qc.h(range(num_qubits))
    return qc


def grover_circuit(
    pairs: Sequence[tuple[int, int]],
    iterations: int | None = None,
    params: SPNParams | None = None,
    measure: bool = True,
) -> QuantumCircuit:
    """Assemble the full key-search circuit.

    Each data register is initialised to its plaintext ``|P_i>`` exactly once,
    before the first iteration.  This is sound because the oracle restores every
    data register after each call -- precisely the property
    ``tests/test_oracle.py`` pins down.

    Only the key register is measured; the data registers are left unmeasured,
    which keeps the readout-error calibration at ``2**key_bits`` circuits
    instead of ``2**(key_bits + 4r)``.

    If ``iterations`` is ``None`` the optimal count is derived from the *true*
    number of marked keys, found by classical brute force.  That is legitimate
    here because we are studying the algorithm's behaviour, not mounting a real
    attack; an actual attacker without knowledge of ``M`` would use the
    exponential-search schedule of Boyer et al. (1998).
    """
    p = params or SPNParams()
    if iterations is None:
        solutions = brute_force_keys(pairs, p)
        iterations = optimal_iterations(p.key_space, max(1, len(solutions)))

    key = QuantumRegister(p.key_bits, "key")
    data_regs = [QuantumRegister(BLOCK_BITS, f"d{i}") for i in range(len(pairs))]
    qc = QuantumCircuit(key, *data_regs, name=f"grover_r{iterations}")

    # Load the known plaintexts into the data registers.
    for reg, (plaintext, _) in zip(data_regs, pairs):
        for i in range(BLOCK_BITS):
            if (plaintext >> i) & 1:
                qc.x(reg[i])

    # Uniform superposition over all candidate keys.
    qc.h(key)
    qc.barrier()

    all_qubits = list(key) + [q for reg in data_regs for q in reg]
    oracle = key_search_oracle(pairs, p)
    diff = diffuser(p.key_bits)
    for _ in range(iterations):
        qc.compose(oracle, qubits=all_qubits, inplace=True)
        qc.compose(diff, qubits=list(key), inplace=True)
        qc.barrier()

    if measure:
        _add_key_measurement(qc, p)
    return qc


def _add_key_measurement(qc: QuantumCircuit, p: SPNParams) -> None:
    """Measure only the key register into a dedicated ``key_bits``-wide clbit register.

    Measuring the data register too would be harmless but would blow the
    readout-calibration cost up from ``2**key_bits`` to ``2**(key_bits + 4)``
    circuits, so we deliberately leave it out.
    """
    creg = ClassicalRegister(p.key_bits, "c")
    qc.add_register(creg)
    qc.measure([qc.qubits[i] for i in range(p.key_bits)], creg)
