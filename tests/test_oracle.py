"""Tests for the Grover phase oracle.

Two properties matter, and both are easy to get silently wrong:

1. The oracle applies ``-1`` to exactly the marked keys and ``+1`` elsewhere.
2. The data registers are **restored** to ``|P_i>``, leaving no entanglement
   with the key register.  A missing uncomputation still produces a circuit
   that marks the right states, but the residual entanglement destroys the
   interference Grover depends on -- so this test is what makes the whole
   construction trustworthy.
"""

from __future__ import annotations

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from qspn.oracle import key_search_oracle, oracle_truth_table
from qspn.spn import BLOCK_BITS, SPNParams, brute_force_keys, encrypt, make_attack_instance

CONFIGS = [(4, 1), (4, 2), (4, 3), (5, 2)]

#: Configs cheap enough for the default statevector run (see the ``slow`` marker).
FAST_CONFIGS = [(4, 1), (4, 2), (4, 3)]

#: Secret keys exercised by the expensive statevector tests.  The cheap
#: truth-table test still covers every key; here we sample, because each case
#: builds a statevector over ``key_bits + 4r`` qubits.
SAMPLE_SECRETS = (0, 1, 0b1011, 0b0110)


def _superposition_with_plaintexts(pairs, params) -> QuantumCircuit:
    """``H^n`` on the key register, data register ``i`` loaded with ``P_i``."""
    num_qubits = params.key_bits + BLOCK_BITS * len(pairs)
    qc = QuantumCircuit(num_qubits)
    qc.h(range(params.key_bits))
    for reg_index, (plaintext, _) in enumerate(pairs):
        base = params.key_bits + reg_index * BLOCK_BITS
        for bit in range(BLOCK_BITS):
            if (plaintext >> bit) & 1:
                qc.x(base + bit)
    return qc


@pytest.mark.parametrize("key_bits,rounds", CONFIGS)
def test_oracle_truth_table_matches_brute_force(key_bits, rounds):
    """Cheap, exhaustive: check every secret key in the space."""
    params = SPNParams(key_bits=key_bits, rounds=rounds)
    for secret in range(params.key_space):
        pairs = make_attack_instance(secret, params)
        table = oracle_truth_table(pairs, params)
        assert [k for k, m in enumerate(table) if m] == brute_force_keys(pairs, params)
        assert sum(table) == 1, "make_attack_instance should yield a unique key"


@pytest.mark.parametrize("key_bits,rounds", FAST_CONFIGS)
def test_oracle_applies_correct_phases_and_restores_data(key_bits, rounds):
    """The decisive test: correct phase *and* clean uncomputation."""
    params = SPNParams(key_bits=key_bits, rounds=rounds)
    for secret in (s % params.key_space for s in SAMPLE_SECRETS):
        pairs = make_attack_instance(secret, params)
        marked = set(brute_force_keys(pairs, params))

        prep = _superposition_with_plaintexts(pairs, params)
        state = Statevector.from_instruction(prep)
        after = state.evolve(key_search_oracle(pairs, params))

        amplitudes = np.asarray(after.data)
        norm = 1.0 / np.sqrt(params.key_space)

        # Offset of the basis state |key> |P_1 .. P_r> in the little-endian index.
        data_offset = 0
        for reg_index, (plaintext, _) in enumerate(pairs):
            data_offset |= plaintext << (params.key_bits + reg_index * BLOCK_BITS)

        for key in range(params.key_space):
            expected = -norm if key in marked else norm
            actual = amplitudes[key + data_offset]
            assert np.isclose(actual, expected, atol=1e-9), (
                f"secret={secret} key={key}: expected {expected:.6f}, got {actual}"
            )

        # All amplitude must live on the restored-plaintext subspace: any mass
        # elsewhere means the data registers were not uncomputed.
        restored_mass = sum(
            abs(amplitudes[key + data_offset]) ** 2 for key in range(params.key_space)
        )
        assert np.isclose(restored_mass, 1.0, atol=1e-9), (
            f"secret={secret}: only {restored_mass:.6f} of the probability mass "
            "returned to the plaintext subspace -- uncomputation is incomplete"
        )


def test_oracle_is_its_own_inverse():
    """A phase oracle is an involution: ``O_f^2 == I``."""
    from qiskit.quantum_info import Operator

    # One pair keeps this to key_bits + 4 = 8 qubits; the involution property is
    # structural and does not depend on the number of pairs.
    params = SPNParams(key_bits=4, rounds=2)
    pairs = make_attack_instance(0b1011, params, num_pairs=1)
    oracle = key_search_oracle(pairs, params)
    doubled = oracle.compose(oracle)
    assert Operator(doubled).equiv(Operator(np.eye(2**doubled.num_qubits)))


def test_oracle_requires_at_least_one_pair():
    with pytest.raises(ValueError, match="at least one"):
        key_search_oracle([], SPNParams())


def test_oracle_qubit_count_is_ancilla_free():
    """``key_bits + 4r`` qubits, no flags and no MCX workspace."""
    params = SPNParams(key_bits=4, rounds=2)
    pairs = make_attack_instance(0b1011, params)
    oracle = key_search_oracle(pairs, params)
    assert oracle.num_qubits == params.key_bits + BLOCK_BITS * len(pairs)


@pytest.mark.slow
@pytest.mark.parametrize("key_bits,rounds", [(5, 2), (6, 2)])
def test_oracle_phases_larger_key_spaces(key_bits, rounds):
    """Same check at larger key widths; slow because the statevector grows as ``2**(k+4r)``."""
    test_oracle_applies_correct_phases_and_restores_data(key_bits, rounds)
