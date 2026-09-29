"""Reversible quantum encryption circuit and the Grover phase oracle.

This is the heart of the project.  The oracle does *not* assume knowledge of the
secret key -- it evaluates the cipher on the key register in superposition.

Given ``r`` known plaintext/ciphertext pairs ``(P_i, C_i)`` the marking
predicate is

    f(K) = 1  iff  E_K(P_i) == C_i  for every i = 1..r

and the circuit is built as **compute -- phase -- uncompute**:

    1. For each pair, ``U_E`` computes ``E_K(P_i)`` in place on data register
       ``i``, using the key register only as CNOT controls.  Starting from
       ``sum_K |K> |P_1> ... |P_r>`` this yields
       ``sum_K |K> |E_K(P_1)> ... |E_K(P_r)>``.
    2. An X-mask encoding the concatenated target ciphertext maps the winning
       pattern to all-ones, and a single multi-controlled Z over all ``4r`` data
       qubits applies a ``-1`` phase exactly on that pattern.  Because the
       condition is one big AND, no per-pair flag ancillas are needed at all.
    3. ``U_E^dagger`` uncomputes every encryption, returning data register ``i``
       to ``|P_i>``.

Because the phase is diagonal it survives step 3, so the net effect is

    sum_K |K> |P_1..P_r>  ->  sum_K (-1)^{f(K)} |K> |P_1..P_r>

and the data registers factor out cleanly -- restored to their input state with
no residual entanglement with the key.  Verifying that they really are restored
is the job of ``tests/test_oracle.py``; a missing uncomputation is the classic
bug that silently destroys Grover interference while still "looking" correct.

**Why more than one pair is required.** For a 4-bit block, ``K -> E_K(P)`` is
not injective, so a single pair typically leaves several consistent keys.  This
is not an artefact of the toy size: it is the same counting argument that forces
quantum key-search oracles for AES-128 to encrypt multiple plaintext blocks
(Grassl et al. 2016; Jaques et al. 2020).  ``r = ceil(key_bits / 4) + 1``
suffices here, and :func:`qspn.spn.brute_force_keys` reports the true number of
marked states ``M`` so the Grover iteration count can be set correctly.

Register layout (Qiskit is little-endian; qubit 0 is the least significant bit):

    key[0..key_bits-1]     the search register, measured at the end
    d0[0..3], d1[0..3], .. one 4-bit cipher state per plaintext, restored to |P_i>
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Gate, QuantumRegister
from qiskit.circuit.library import UnitaryGate, ZGate

from .spn import BLOCK_BITS, PERM, SBOX, SPNParams


def _permutation_unitary(table: tuple[int, ...]) -> np.ndarray:
    """Build the unitary that maps ``|x>`` to ``|table[x]>``.

    A bijection on ``BLOCK_BITS`` bits is already reversible, so its matrix is a
    permutation matrix and no ancillas are needed to implement it in place.
    """
    dim = len(table)
    matrix = np.zeros((dim, dim), dtype=complex)
    for x, y in enumerate(table):
        matrix[y, x] = 1.0
    return matrix


@lru_cache(maxsize=None)
def sbox_gate() -> Gate:
    """The S-box as a 4-qubit in-place gate.

    Qiskit synthesises the permutation matrix into basis gates via quantum
    Shannon decomposition (Shende, Bullock & Markov 2006).  A hand-optimised
    Toffoli network would use fewer non-Clifford gates -- see the report's
    discussion of resource counting -- but this construction is exact and is
    what the noise model then acts on after transpilation.
    """
    return UnitaryGate(_permutation_unitary(SBOX), label="S")


def _perm_cycles(perm: tuple[int, ...]) -> list[list[int]]:
    """Decompose ``perm`` (read as "content of wire i moves to wire perm[i]") into cycles."""
    seen = [False] * len(perm)
    cycles = []
    for start in range(len(perm)):
        if seen[start]:
            continue
        cycle = []
        node = start
        while not seen[node]:
            seen[node] = True
            cycle.append(node)
            node = perm[node]
        if len(cycle) > 1:
            cycles.append(cycle)
    return cycles


def _apply_p_layer(qc: QuantumCircuit, data: QuantumRegister) -> None:
    """Apply the bit permutation as SWAP gates via cycle decomposition.

    For a cycle whose contents flow ``a_1 -> a_2 -> ... -> a_k -> a_1`` the
    swaps ``(a_k, a_{k-1}), (a_{k-1}, a_{k-2}), ..., (a_2, a_1)`` realise it,
    costing ``k - 1`` SWAPs.

    On real hardware a fixed bit permutation is in fact *free*: the compiler can
    absorb it into qubit relabelling, since it only renames wires.  We emit
    explicit SWAPs so the circuit object is a faithful self-contained
    description of the cipher, and account for the zero-cost alternative in the
    resource analysis.
    """
    for cycle in _perm_cycles(PERM):
        for idx in range(len(cycle) - 1, 0, -1):
            qc.swap(data[cycle[idx]], data[cycle[idx - 1]])


def _add_round_key(
    qc: QuantumCircuit,
    key: QuantumRegister,
    data: QuantumRegister,
    params: SPNParams,
    index: int,
) -> None:
    """XOR round key ``index`` into the data register with CNOTs.

    Round key ``index`` is ``rotl(K, index) & 0xF``, so data bit ``i`` is
    controlled by master-key qubit ``(i - index) mod key_bits``.  The rotation
    costs nothing: it only changes which key qubit is the control.
    """
    for i in range(BLOCK_BITS):
        control = (i - index) % params.key_bits
        qc.cx(key[control], data[i])


def encryption_circuit(params: SPNParams | None = None) -> QuantumCircuit:
    """Build ``U_E``: the reversible, key-controlled encryption of the data register.

    The returned circuit acts on ``key_bits + BLOCK_BITS`` qubits and computes
    ``|K>|X>  ->  |K>|E_K(X)>`` in place, for every ``K`` and ``X``
    simultaneously.  It uses no ancilla qubits at all, because every layer of
    the cipher (XOR, S-box, bit permutation) is individually a bijection on the
    4-bit block.
    """
    p = params or SPNParams()
    key = QuantumRegister(p.key_bits, "key")
    data = QuantumRegister(BLOCK_BITS, "data")
    qc = QuantumCircuit(key, data, name="U_E")

    _add_round_key(qc, key, data, p, 0)
    for r in range(1, p.rounds + 1):
        qc.append(sbox_gate(), list(data))
        _apply_p_layer(qc, data)
        _add_round_key(qc, key, data, p, r)
    return qc


def _phase_check(
    qc: QuantumCircuit, data_qubits: list, targets: list[int]
) -> None:
    """Apply a ``-1`` phase iff every data register holds its target ciphertext.

    The ``r`` separate 4-bit equality tests are fused into a *single*
    ``4r``-qubit condition: an X-mask maps the winning concatenated pattern to
    all-ones, one multi-controlled Z fires only on all-ones, and the mask is
    undone.  Using a multi-controlled Z rather than MCX gates onto per-pair flag
    qubits keeps the oracle completely ancilla-free -- the phase is kicked back
    directly, and there are no flags that would themselves need uncomputing.
    """
    mask = []
    for reg_index, target in enumerate(targets):
        for bit in range(BLOCK_BITS):
            if not (target >> bit) & 1:
                mask.append(data_qubits[reg_index * BLOCK_BITS + bit])
    for qubit in mask:
        qc.x(qubit)
    if len(data_qubits) == 1:
        qc.z(data_qubits[0])
    else:
        qc.append(ZGate().control(len(data_qubits) - 1), data_qubits)
    for qubit in mask:
        qc.x(qubit)


def key_search_oracle(
    pairs: Sequence[tuple[int, int]], params: SPNParams | None = None
) -> QuantumCircuit:
    """Build the Grover phase oracle ``O_f`` for a known-plaintext attack.

    Parameters
    ----------
    pairs:
        Known ``(plaintext, ciphertext)`` pairs.  ``f(K) = 1`` iff the candidate
        key reproduces *every* one of them.
    params:
        Cipher configuration.

    The circuit requires data register ``i`` to be in state ``|P_i>`` on entry,
    which :func:`qspn.grover.grover_circuit` arranges once, up front -- sound
    because the oracle restores every data register after each call.
    """
    p = params or SPNParams()
    if not pairs:
        raise ValueError("at least one plaintext/ciphertext pair is required")

    key = QuantumRegister(p.key_bits, "key")
    data_regs = [QuantumRegister(BLOCK_BITS, f"d{i}") for i in range(len(pairs))]
    qc = QuantumCircuit(key, *data_regs, name="O_f")

    enc = encryption_circuit(p)
    for reg in data_regs:
        qc.compose(enc, qubits=list(key) + list(reg), inplace=True)

    data_qubits = [q for reg in data_regs for q in reg]
    _phase_check(qc, data_qubits, [c for _, c in pairs])

    enc_inv = enc.inverse()
    for reg in data_regs:
        qc.compose(enc_inv, qubits=list(key) + list(reg), inplace=True)
    return qc


def oracle_truth_table(
    pairs: Sequence[tuple[int, int]], params: SPNParams | None = None
) -> list[int]:
    """Classical truth table of ``f``, for cross-checking the quantum oracle."""
    from .spn import encrypt

    p = params or SPNParams()
    return [
        int(all(encrypt(pt, k, p) == ct for pt, ct in pairs))
        for k in range(p.key_space)
    ]
