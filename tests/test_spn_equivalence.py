"""The project's foundational test: the quantum circuit *is* the classical cipher.

Everything downstream (Grover, noise, mitigation) is meaningless if the
reversible encryption circuit does not reproduce the classical reference
implementation.  These tests check the full unitary against the classical
truth table for every key and every plaintext -- an exhaustive check, which the
toy size makes affordable.
"""

from __future__ import annotations

import numpy as np
import pytest
from qiskit.quantum_info import Operator

from qspn.oracle import encryption_circuit
from qspn.spn import (
    BLOCK_BITS,
    SBOX,
    SBOX_INV,
    SPNParams,
    decrypt,
    encrypt,
    p_layer,
    p_layer_inv,
)


def test_sbox_is_a_bijection():
    assert sorted(SBOX) == list(range(16))
    assert all(SBOX_INV[SBOX[x]] == x for x in range(16))


def test_p_layer_is_a_bijection():
    assert sorted(p_layer(x) for x in range(16)) == list(range(16))
    assert all(p_layer_inv(p_layer(x)) == x for x in range(16))


@pytest.mark.parametrize("key_bits,rounds", [(4, 1), (4, 2), (4, 3), (5, 2), (6, 2)])
def test_encrypt_decrypt_roundtrip(key_bits, rounds):
    params = SPNParams(key_bits=key_bits, rounds=rounds)
    for key in range(params.key_space):
        for plaintext in range(1 << BLOCK_BITS):
            assert decrypt(encrypt(plaintext, key, params), key, params) == plaintext


@pytest.mark.parametrize("key_bits,rounds", [(4, 1), (4, 2), (4, 3), (5, 2), (6, 2)])
def test_quantum_circuit_matches_classical_cipher(key_bits, rounds):
    """``U_E |K>|X> == |K>|E_K(X)>`` for every ``K`` and ``X``.

    Checked on the exact unitary rather than by sampling, so the assertion is
    about the circuit itself and not about a particular measurement outcome.
    """
    params = SPNParams(key_bits=key_bits, rounds=rounds)
    unitary = Operator(encryption_circuit(params)).data

    # Little-endian layout: key occupies qubits 0..key_bits-1 (low bits of the
    # index), data occupies the next BLOCK_BITS qubits.
    for key in range(params.key_space):
        for plaintext in range(1 << BLOCK_BITS):
            column = key + (plaintext << key_bits)
            expected_row = key + (encrypt(plaintext, key, params) << key_bits)
            amplitudes = unitary[:, column]
            row = int(np.argmax(np.abs(amplitudes)))
            assert row == expected_row, (
                f"K={key:0{key_bits}b} P={plaintext:04b}: circuit gave "
                f"{(row >> key_bits):04b}, classical gave "
                f"{encrypt(plaintext, key, params):04b}"
            )
            assert np.isclose(abs(amplitudes[row]), 1.0, atol=1e-9)


def test_encryption_circuit_uses_no_ancillas():
    """Every cipher layer is a bijection on 4 bits, so no ancillas are needed."""
    params = SPNParams(key_bits=4, rounds=2)
    assert encryption_circuit(params).num_qubits == params.key_bits + BLOCK_BITS


def test_round_key_schedule_is_a_rotation():
    params = SPNParams(key_bits=6, rounds=3)
    key = 0b101100
    assert params.round_key(key, 0) == key & 0xF
    # rotl by 1 within 6 bits, then take the low nibble
    assert params.round_key(key, 1) == 0b011001 & 0xF
