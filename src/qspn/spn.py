"""Classical reference implementation of the toy Substitution-Permutation Network.

This module is deliberately dependency-free and written in plain Python.  It is
the *ground truth* for the whole project: the quantum encryption circuit in
:mod:`qspn.oracle` is validated by asserting that it reproduces
:func:`encrypt` for every key in the key space (see ``tests/test_spn_equivalence.py``).

Cipher structure (mirrors the classical SPN teaching model of Heys 2002 and the
round structure of PRESENT, Bogdanov et al. 2007):

    ARK(rk_0) -> [ SBox -> PLayer -> ARK(rk_r) ] x rounds

The block is always 4 bits.  The master key is ``key_bits`` wide (>= 4) and the
4-bit round keys are extracted by rotating the master key, so round key ``r`` is
``rotl(K, r) & 0xF``.  Rotation is chosen because it is *free* on a quantum
register -- it is pure qubit relabelling and costs zero gates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

BLOCK_BITS = 4
BLOCK_MASK = (1 << BLOCK_BITS) - 1

# PRESENT 4-bit S-box (Bogdanov et al., CHES 2007, Table 1).  A real, published
# cryptographic S-box rather than an ad-hoc permutation.
SBOX: tuple[int, ...] = (
    0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,
    0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2,
)

#: Inverse of :data:`SBOX`, used by the decryption direction and by the
#: uncomputation step of the quantum oracle.
SBOX_INV: tuple[int, ...] = tuple(SBOX.index(y) for y in range(1 << BLOCK_BITS))

#: Bit permutation of the 4-bit block.  ``PERM[i] = j`` means "the bit at
#: position ``i`` of the input moves to position ``j`` of the output".  Chosen to
#: be a genuine permutation rather than a rotation so the diffusion layer is not
#: trivially self-similar with the key schedule.
PERM: tuple[int, ...] = (1, 3, 0, 2)

PERM_INV: tuple[int, ...] = tuple(PERM.index(j) for j in range(BLOCK_BITS))


def rotl(value: int, amount: int, width: int) -> int:
    """Rotate ``value`` left by ``amount`` positions within ``width`` bits."""
    amount %= width
    mask = (1 << width) - 1
    value &= mask
    return ((value << amount) | (value >> (width - amount))) & mask


def sbox_layer(state: int) -> int:
    """Apply the S-box to a 4-bit block."""
    return SBOX[state & BLOCK_MASK]


def sbox_layer_inv(state: int) -> int:
    """Apply the inverse S-box to a 4-bit block."""
    return SBOX_INV[state & BLOCK_MASK]


def p_layer(state: int) -> int:
    """Apply the bit permutation to a 4-bit block."""
    out = 0
    for i, j in enumerate(PERM):
        if (state >> i) & 1:
            out |= 1 << j
    return out


def p_layer_inv(state: int) -> int:
    """Apply the inverse bit permutation to a 4-bit block."""
    out = 0
    for j, i in enumerate(PERM_INV):
        if (state >> j) & 1:
            out |= 1 << i
    return out


@dataclass(frozen=True)
class SPNParams:
    """Configuration of the toy cipher.

    Parameters
    ----------
    key_bits:
        Width of the master key, i.e. the size of the search space is
        ``2 ** key_bits``.  Must be at least :data:`BLOCK_BITS`.
    rounds:
        Number of ``SBox -> PLayer -> ARK`` rounds applied after the initial
        key addition.  There are therefore ``rounds + 1`` round keys.
    """

    key_bits: int = 4
    rounds: int = 2

    def __post_init__(self) -> None:
        if self.key_bits < BLOCK_BITS:
            raise ValueError(f"key_bits must be >= {BLOCK_BITS}, got {self.key_bits}")
        if self.rounds < 1:
            raise ValueError(f"rounds must be >= 1, got {self.rounds}")

    @property
    def key_space(self) -> int:
        """Number of candidate keys, ``2 ** key_bits``."""
        return 1 << self.key_bits

    @property
    def num_round_keys(self) -> int:
        return self.rounds + 1

    def round_key(self, master_key: int, index: int) -> int:
        """Return 4-bit round key ``index`` derived from ``master_key``."""
        return rotl(master_key, index, self.key_bits) & BLOCK_MASK

    def covers_all_key_bits(self) -> bool:
        """True if every master-key bit influences at least one round key.

        Each round key exposes ``BLOCK_BITS`` consecutive (rotated) master-key
        bits, so ``num_round_keys`` rotations cover
        ``num_round_keys + BLOCK_BITS - 1`` distinct positions.  If that is less
        than ``key_bits`` some key bits are never used, which guarantees the
        key is not uniquely determined by a single plaintext/ciphertext pair.
        """
        return self.num_round_keys + BLOCK_BITS - 1 >= self.key_bits

    def min_rounds_for_full_coverage(self) -> int:
        """Smallest ``rounds`` value for which every key bit is used.

        From :meth:`covers_all_key_bits`, we need
        ``rounds + 1 + BLOCK_BITS - 1 >= key_bits``, i.e.
        ``rounds >= key_bits - BLOCK_BITS``.
        """
        return max(1, self.key_bits - BLOCK_BITS)


def encrypt(plaintext: int, master_key: int, params: SPNParams | None = None) -> int:
    """Encrypt a 4-bit ``plaintext`` under ``master_key``."""
    p = params or SPNParams()
    state = (plaintext & BLOCK_MASK) ^ p.round_key(master_key, 0)
    for r in range(1, p.rounds + 1):
        state = sbox_layer(state)
        state = p_layer(state)
        state ^= p.round_key(master_key, r)
    return state & BLOCK_MASK


def decrypt(ciphertext: int, master_key: int, params: SPNParams | None = None) -> int:
    """Inverse of :func:`encrypt`."""
    p = params or SPNParams()
    state = ciphertext & BLOCK_MASK
    for r in range(p.rounds, 0, -1):
        state ^= p.round_key(master_key, r)
        state = p_layer_inv(state)
        state = sbox_layer_inv(state)
    return (state ^ p.round_key(master_key, 0)) & BLOCK_MASK


def brute_force_keys(
    pairs: Sequence[tuple[int, int]], params: SPNParams | None = None
) -> list[int]:
    """Classical exhaustive search: every key consistent with all ``pairs``.

    This is both the classical attack the quantum search is compared against and
    the source of ``M``, the number of marked oracle states -- which is what
    sets the optimal Grover iteration count.
    """
    p = params or SPNParams()
    return [
        k
        for k in range(p.key_space)
        if all(encrypt(pt, k, p) == ct for pt, ct in pairs)
    ]


def make_attack_instance(
    master_key: int,
    params: SPNParams | None = None,
    num_pairs: int | None = None,
    ensure_unique: bool = True,
) -> list[tuple[int, int]]:
    """Generate known plaintext/ciphertext pairs for ``master_key``.

    Plaintexts are taken as ``0, 1, 2, ...`` for reproducibility.

    With ``ensure_unique=True`` (the default) the pair count starts at 1 and
    grows until classical brute force finds exactly one consistent key, so the
    Grover instance has ``M = 1``.  Using the *minimum* sufficient number of
    pairs matters: each extra pair adds a whole 4-qubit register and two more
    encryption circuits per oracle call, so it is the dominant cost driver.

    The number actually required is key-dependent and is not the same as the
    information-theoretic estimate :func:`required_pairs`; the gap between them
    is one of the project's reported findings (see Experiment E).

    Raises
    ------
    ValueError
        If the key cannot be made unique with the ``2**BLOCK_BITS`` distinct
        plaintexts available -- which happens when :meth:`SPNParams.covers_all_key_bits`
        is false, because unused key bits are unrecoverable *in principle*.
    """
    p = params or SPNParams()
    max_pairs = 1 << BLOCK_BITS

    if num_pairs is not None:
        if num_pairs > max_pairs:
            raise ValueError(f"only {max_pairs} distinct plaintexts exist")
        return [(pt, encrypt(pt, master_key, p)) for pt in range(num_pairs)]

    count = 1
    while count <= max_pairs:
        pairs = [(pt, encrypt(pt, master_key, p)) for pt in range(count)]
        if not ensure_unique or len(brute_force_keys(pairs, p)) == 1:
            return pairs
        count += 1

    raise ValueError(
        f"key {master_key} is not uniquely determined by any number of plaintexts "
        f"for {p!r}; covers_all_key_bits={p.covers_all_key_bits()} "
        f"(need rounds >= {p.min_rounds_for_full_coverage()})"
    )


def required_pairs(params: SPNParams | None = None) -> int:
    """Number of plaintext blocks needed to pin the key down, with one block of margin.

    ``ceil(key_bits / BLOCK_BITS)`` blocks match the key's information content
    exactly, which leaves an expected ``~1/e`` fraction of spurious keys; one
    extra block removes them in practice.
    """
    p = params or SPNParams()
    return -(-p.key_bits // BLOCK_BITS) + 1


def classical_query_cost(params: SPNParams | None = None) -> int:
    """Worst-case number of encryption calls for classical exhaustive search."""
    p = params or SPNParams()
    return p.key_space
