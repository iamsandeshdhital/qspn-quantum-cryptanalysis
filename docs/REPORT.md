# Project Report — What This Is, How It Works, and Why It's Built This Way

This is the orientation document. It explains every moving part, the reasoning
behind each design decision, the traps that were avoided, and how the pieces
connect into one argument. Read `README.md` for how to *run* things; read this
for *why*.

---

## 1. The one-paragraph version

We take a small but genuine symmetric cipher, turn its encryption function into
a reversible quantum circuit, wrap that circuit in a Grover oracle that
recognises the correct key from known plaintext/ciphertext pairs, and run the
resulting search. We then re-run it under simulated hardware noise to see how
badly it breaks, and apply classical readout-error mitigation to see how much
can be clawed back. The headline finding is a **boundary**: mitigation of this
kind fixes measurement error almost perfectly and gate error not at all — and
gate error is what actually kills the attack.

---

## 2. The pipeline, stage by stage

```
      spn.py              oracle.py            grover.py
  ┌────────────┐      ┌───────────────┐    ┌──────────────┐
  │ classical  │─────►│  reversible   │───►│   Grover     │
  │ SPN cipher │      │    oracle     │    │ amplification│
  └────────────┘      └───────────────┘    └──────────────┘
        │                     │                    │
        │ ground truth        │ compute/phase/     │ ⌊(π/4)√(N/M)⌋
        │ for tests           │ uncompute          │ iterations
        ▼                     ▼                    ▼
  ┌──────────────────────────────────────────────────────┐
  │              runner.py  (transpile → Aer)            │
  └──────────────────────────────────────────────────────┘
        │                                          │
        ▼ noise.py                                 ▼ mitigation.py
  depolarizing + readout                    assignment matrix A
  error injection                           and its inversion
        │                                          │
        └──────────────► experiments.py ◄──────────┘
                    A · B · C · D · E → JSON → plots
```

Each stage is a separate module with one job, and — importantly — each stage is
independently checkable. That property is what makes the results trustworthy:
if the final numbers looked wrong, we could localise the fault.

---

## 3. Stage 1 — The classical cipher (`spn.py`)

### What it is

A 4-bit block substitution–permutation network:

```
ARK(rk₀) ──► [ S-box ──► P-layer ──► ARK(rk_r) ] × rounds
```

with `rounds = 2` by default, giving 2 S-box layers and 3 key additions.

### The three components

**S-box** — the actual PRESENT S-box (Bogdanov et al., CHES 2007):

```
x     : 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
S[x]  : C  5  6  B  9  0  A  D  3  E  F  8  4  7  1  2
```

Using a published cipher's S-box rather than inventing one matters for two
reasons. It is a real cryptographic primitive with known differential and linear
properties, and it means the toy cipher inherits genuine nonlinearity rather
than accidental structure.

**P-layer** — the fixed bit permutation `(0→1, 1→3, 2→0, 3→2)`. Deliberately
*not* a rotation, so the diffusion layer isn't trivially self-similar with the
rotation-based key schedule.

**Key schedule** — round key `r` is `rotl(K, r) & 0xF`.

That last choice is quietly important. A rotation is **free** on a quantum
register: to XOR `rotl(K, r)` into the data register you simply change *which
key qubit is the CNOT control*. Zero gates. A key schedule involving S-boxes or
additions would have to be computed inside the oracle, on every call, and
uncomputed afterwards — a large cost for no benefit to what we're studying.

### Why this module is dependency-free

`spn.py` imports nothing but the standard library. It is the **ground truth**.
If it shared code with the quantum implementation, a bug in shared code would
pass the equivalence test silently. Keeping them fully independent means the
test in §4 is a real cross-check, not a tautology.

---

## 4. Stage 2 — The reversible oracle (`oracle.py`)

This is where the project's substance lives, and where the original project
specification had its one real flaw.

### The flaw that was fixed

A tempting way to write the oracle is:

```
f(K) = 1  if  K == K*,  else 0
```

This is **circular**. It assumes you already know the key. It produces a
perfectly good Grover demonstration of "find the number I told you about", but
it isn't cryptanalysis, and any reviewer will notice immediately.

The real oracle must **evaluate the cipher on the key register in
superposition** and compare the result to the known ciphertext:

```
f(K) = 1  iff  E_K(Pᵢ) == Cᵢ  for every known pair i
```

Nowhere does `K*` appear. The oracle only knows `(Pᵢ, Cᵢ)` — exactly what a
known-plaintext attacker has.

### Compute → phase → uncompute

```
        key ───●────────────────────────●───────  (never modified)
               │                        │
       d₀ ─────U_E──── [X-mask] ────────U_E† ───  restored to |P₀⟩
                          │
       d₁ ─────U_E──────  MCZ  ─────────U_E† ───  restored to |P₁⟩
                          │
       ...                └── −1 phase iff all match
```

1. **Compute.** `U_E` computes `E_K(Pᵢ)` in place on data register `i`, using
   the key register purely as CNOT controls. From `Σ_K |K⟩|P₀…P_r⟩` this gives
   `Σ_K |K⟩|E_K(P₀)…E_K(P_r)⟩`.

2. **Phase.** An X-mask maps the winning concatenated ciphertext to all-ones,
   then a single multi-controlled Z over all `4r` data qubits fires only on
   all-ones, applying `−1`.

3. **Uncompute.** `U_E†` runs the encryption backwards, restoring every data
   register to `|Pᵢ⟩`.

Because the phase is diagonal it survives step 3, so the net effect is exactly

```
Σ_K |K⟩|P₀…P_r⟩  ──►  Σ_K (−1)^f(K) |K⟩|P₀…P_r⟩
```

and the data registers **factor out** — restored to their input state with no
residual entanglement with the key register.

### Why uncomputation is the whole ballgame

This is the single most important subtlety in the project.

Skip step 3 and the oracle *still marks the right states*. Inspect the phases
and they look correct. But the key register is now entangled with the data
registers, and Grover's diffusion operator depends on **interference** between
key amplitudes. Entangled "which-path" information destroys that interference,
and amplification silently fails to build up.

It is a bug that looks like correct code and produces plausible-but-wrong
physics. So the test for it is explicit and load-bearing
(`tests/test_oracle.py::test_oracle_applies_correct_phases_and_restores_data`):
it checks the phase on every key **and** asserts that all probability mass has
returned to the plaintext subspace.

```python
restored_mass = sum(|amplitude[key + data_offset]|² for key in range(key_space))
assert restored_mass ≈ 1.0     # ← anything less means incomplete uncomputation
```

### Ancilla-free, by design

The oracle uses `key_bits + 4r` qubits and **no ancillas at all**. Two reasons:

- Every cipher layer (XOR, S-box, bit permutation) is individually a bijection
  on 4 bits, so each can act in place. Nothing needs scratch space.
- The `r` separate 4-bit equality tests are fused into **one** `4r`-qubit AND
  condition, rather than computing `r` flag qubits and combining them. Flags
  would themselves need uncomputing — more gates, more depth, more to get wrong.

### Why more than one plaintext pair is needed

Here is a finding that emerged from building this, and it is not a toy artefact.

For a 4-bit block, the map `K ↦ E_K(P)` is **not injective**. Measured over the
whole key space with `rounds = 2`:

| Known pairs | Worst-case consistent keys | Mean | Keys uniquely determined |
|---|---|---|---|
| 1 | 3 | 1.88 | 8 / 16 |
| 2 | 2 | 1.25 | 12 / 16 |
| 3 | **1** | 1.00 | **16 / 16** |

A single known-plaintext pair usually leaves several candidate keys. This is the
same counting argument that forces quantum key-search oracles against AES-128 to
encrypt **several plaintext blocks** (Grassl et al. 2016; Jaques et al. 2020).
Our measurements reproduce it at 8-bit keys too:

| Key width | Info-theoretic minimum `⌈k/4⌉+1` | Actually required (measured) |
|---|---|---|
| 4 bits | 2 | 1–3 (key-dependent) |
| 6 bits | 3 | 3 |
| 8 bits | 3 | 3–4 |

So `make_attack_instance` **grows the pair count until brute force confirms
`M = 1`**. The information-theoretic estimate is a lower bound, and the gap
between it and reality is a reported result rather than an assumption.

This matters practically: each extra pair adds a whole 4-qubit register *and*
two more encryption circuits per oracle call. It is the dominant cost driver.

---

## 5. Stage 3 — Grover amplification (`grover.py`)

### The iteration count, done correctly

The optimal number of iterations is

```
k* = ⌊ (π/4) · √(N/M) ⌋
```

**not** `√N`. The `π/4` factor matters, and so does `M`:

| N | M | `√N` | correct `k*` |
|---|---|---|---|
| 16 | 1 | 4 | **3** |
| 64 | 1 | 8 | **6** |
| 256 | 1 | 16 | **12** |
| 65,536 | 1 | 256 | **201** |
| 256 | 4 | 16 | **6** |

### Grover does not saturate — it over-rotates

Amplitude amplification is a **rotation** in a two-dimensional subspace, so the
success probability is

```
P(k) = sin²((2k+1)·θ),     θ = arcsin(√(M/N))
```

which is periodic. Applying *more* iterations than optimal makes things **worse**.
At `N = 16, M = 1` the peak is `P(3) = 0.9613`, and `P(4) = 0.5817` — a third of
the success probability thrown away by one extra iteration.

Experiment A measures this curve directly, and it is the reason the sweep runs
past `k*` rather than stopping there. Note also that `P(3) = 0.9613`, not 1.0:
with 16 states and one solution, Grover simply cannot reach certainty, because
`(2k+1)θ` never lands exactly on `π/2` for integer `k`.

### Measuring only the key register

The data registers are left unmeasured. This is not laziness:

- They're restored to `|Pᵢ⟩`, so they carry no information.
- Full readout calibration costs `2ⁿ` circuits in the number of **measured**
  qubits. Measuring only the 4 key qubits costs 16 calibration circuits;
  measuring everything would cost `2^(4+4r)` = 256 at `r=1`, and 65,536 at `r=3`.

One design choice, an exponential saving.

---

## 6. Stage 4 — Noise (`noise.py`)

### What's modelled

- **Depolarizing error** on gates: with probability `p` the qubit(s) are replaced
  by the maximally mixed state. `p₁ = 10⁻³` on 1-qubit gates, `p₂ = 10⁻²` on
  2-qubit gates — the order-of-magnitude hierarchy measured on real
  superconducting hardware.
- **Readout error** at measurement: asymmetric bit flips with
  `P(1|0) = 0.02` and `P(0|1) = 0.04`. The asymmetry is physical — energy
  relaxation during readout makes `1 → 0` more likely on transmons.

`rz` is deliberately left **noiseless**. On transmon hardware a Z rotation is a
virtual frame change of zero duration — applied by shifting the phase of
subsequent drive pulses rather than by playing one (McKay et al. 2017) — and
IBM's backend properties report no gate error for it.

Treating it as *exactly* noiseless is an idealisation, though, and a
load-bearing one: after transpilation `rz` is the most common gate in the
circuit (13,439 of 25,471 gates in the default configuration, 53%). At even
`10⁻⁴` error per `rz` it would contribute comparably to the 4,344 CX gates at
`10⁻²`. Our noise model is therefore optimistic in this one respect — which
strengthens rather than weakens the negative result in Experiment C.

### The trap that would have invalidated everything

A noise model attaches errors to **named basis gates**. A circuit still
containing composite instructions — `UnitaryGate`, multi-controlled Z, `swap` —
contains no `cx` or `sx` for the model to bind to.

Run such a circuit against the noise model and it executes **essentially
noise-free**, while appearing to have noise configured. Every noise result would
be silently meaningless, with no error message anywhere.

So `runner.transpile_for` decomposes to the IBM-native basis
`['id', 'rz', 'sx', 'x', 'cx']` before *every* execution, and this is documented
at the top of `runner.py` as the single most important detail in the file.

---

## 7. Stage 5 — Readout-error mitigation (`mitigation.py`)

### The linear algebra

Measured and true distributions are related by the **assignment matrix**:

```
y = A x,      A[i,j] = P(observe i | prepared j)
```

`A` is characterised by running `2ⁿ` calibration circuits — prepare `|j⟩`,
measure immediately — and reading each resulting histogram as a column.
Recovering `x` means inverting that system.

Calibration circuits are shallow (X gates, then measure), so gate error
contributes negligibly and `A` genuinely captures the *measurement* channel
rather than a mixture of effects.

### Three inversion strategies, and why all three are implemented

| Method | What it does | Problem |
|---|---|---|
| `pinv` | Moore–Penrose pseudo-inverse | `A⁻¹` is not stochastic → **negative probabilities** |
| `clip` | `pinv`, clip negatives, renormalise | Cheap, but the clip biases the estimate |
| `nnls` | minimise `‖Ax − y‖₂` s.t. `x ≥ 0`, then renormalise | Always valid — the default |

Implementing all three isn't padding: it makes a known pathology **visible in
the results** rather than described in prose. From a real run (readout error
only, ideal `P = 0.9613`):

```
raw   P(key) = 0.8398    TVD = 0.1311
pinv  P(key) = 0.9818    TVD = 0.0266    neg.mass = 0.0135   valid = NO
clip  P(key) = 0.9687    TVD = 0.0199    neg.mass = 0.0000   valid = yes
nnls  P(key) = 0.9700    TVD = 0.0202    neg.mass = 0.0000   valid = yes
```

Look at `pinv`: it reports `P = 0.9818`, which is **higher than the ideal
0.9613**. That is not a better answer — it is an unphysical overshoot, and the
same run has `0.0135` of probability mass sitting below zero. This is precisely
the unfolding pathology documented by Nachman et al. (2020), reproduced here in
miniature. NNLS gives up a little accuracy to stay inside the probability
simplex, which is the right trade.

**Two attribution caveats**, worth stating because it is easy to overclaim here:

- NNLS is **not** the method M3 uses (Nation et al. 2021). M3 is *matrix-free* —
  it never forms `A` or its inverse — and solves within the subspace spanned by
  the observed bitstrings using a preconditioned iterative solver. It shares
  NNLS's *goal* of avoiding exponential calibration, not its mechanism. Nation
  et al. is the right citation for the `2ⁿ` calibration-scaling point, and the
  wrong one for NNLS.
- Nachman et al. (2020), cited above against `pinv`, actually advocate
  **iterative Bayesian unfolding** over both matrix inversion *and* least
  squares. So "NNLS is physically correct" would overstate what that paper
  supports. The safe, narrower claim — which is what the data here shows — is
  that NNLS always returns a valid distribution whereas `pinv` does not. NNLS is
  kept because it is exactly solvable and sufficient to establish the
  readout-versus-gate boundary; IBU would be the natural next comparison.

### The honest scaling caveat

`A` is `2ⁿ × 2ⁿ` in the number of measured qubits, so full calibration is
**exponential**. It is tractable here only because we measure the key register
alone: 16 circuits at 4 bits, 256 at 8 bits. Beyond ~10 measured qubits you must
switch to a tensored or subspace-reduced method such as M3
(Nation et al. 2021). This is stated in the module docstring, in the README, and
in the report's limitations — not buried.

`cond(A)` is also reported, because it is the amplification factor for
statistical noise during inversion. Mitigation is not free: a poorly conditioned
`A` converts shot noise into large errors in `x`.

---

## 8. Stage 6 — The experiments (`experiments.py`)

| Experiment | Question |
|---|---|
| **A** ideal | Does the oracle work, and does amplification match `sin²((2k+1)θ)`? |
| **B** noisy | How much does realistic NISQ noise degrade key recovery? |
| **C** mitigation | Can readout mitigation recover the signal, and where does it stop? |
| **D** threshold | At what two-qubit error rate does the attack stop working? |
| **E** resources | How do depth, CX count and pair count scale with key width? |

### Why Experiment C runs three noise models

This is the design decision that turns C from a demonstration into a
measurement. Readout error is held at full strength in all three; only gate
error changes, so any difference is *attributable to gate noise*:

1. **`readout_only`** — the technique's best case. `A` fully describes the
   corruption, so inversion should recover the ideal distribution up to shot noise.
2. **`reduced_gate`** — gate error scaled to 3%, so a partial signal survives.
   The informative middle regime: there's a real but degraded peak for
   mitigation to sharpen, so improvement is measurable rather than buried in an
   already-flat distribution.
3. **`full`** — gate error at the modelled hardware rate. Mitigation still
   corrects the measurement channel, but is structurally unable to touch gate
   error. The residual gap quantifies exactly that limitation.

Running only case 1 would overstate the technique. Running only case 3 would
understate it. Running all three **locates the boundary**, which is the actual
scientific content.

### Metrics, and why more than one

`metrics.py` reports several figures of merit because "P(correct key)" alone
hides things:

- **`p_success`** with a **binomial standard error**. Every probability is an
  estimate from finite shots; quoting it bare overstates precision.
- **TVD** and **Hellinger fidelity** against the exact distribution — distribution
  shape, not just the peak.
- **Shannon entropy** — a single number for "how far has noise pushed us back
  toward uniform". At 4 key bits, 4.00 bits *is* total failure.
- **`rank_of_secret`** and **`expected_classical_checks`** — the operationally
  honest attacker's view. If the correct key is ranked 2nd, that's still only two
  classical trial encryptions. This is the metric that answers "did mitigation
  actually help the attack?" rather than "did a number go up?"

### One statistical correction worth noting

An early version reported `beats_random_guessing: yes` when `p_success = 0.0654`
against a `1/16 = 0.0625` baseline. With 1024 shots the standard error is
`±0.0077`, so that "advantage" was **a third of one sigma** — pure noise.

The code now requires a **two-sigma margin** before claiming any advantage, and
reports `advantage_sigmas` explicitly. Without this, a fully decohered run would
have been recorded as a partial success.

---

## 9. The results, and what they mean

### Experiment A — the implementation is exact

- Optimal `k* = 3`, best `P(key) = 0.9613`.
- Maximum deviation from the closed form: **4.33e-15**.
- Over-rotation confirmed: `P` falls after `k*` —
  0.0625 → 0.4727 → 0.9084 → 0.9613 → 0.5817 → 0.1255 → 0.0204
  for `k = 0…6`.

That deviation is floating-point noise. The implementation is not
*approximately* Grover; within double precision, it *is* Grover. This is the
result that licenses everything downstream.

### Experiment B — current hardware error rates destroy the attack

At `p₁ = 1e-03`, `p₂ = 1e-02` with 1,404 CX gates and depth
4,861:

| k | CX | ideal P | noisy P | TVD | entropy (bits) |
|---|---|---|---|---|---|
| 0 | 0 | 0.0625 | 0.0593 | 0.03 | 3.997 |
| 1 | 468 | 0.4727 | 0.0647 | 0.41 | 3.996 |
| 2 | 936 | 0.9084 | 0.0583 | 0.85 | 3.996 |
| **3** | 1404 | 0.9613 | 0.0574 | 0.90 | 3.995 |
| 4 | 1872 | 0.5817 | 0.0618 | 0.52 | 3.997 |
| 5 | 2340 | 0.1255 | 0.0557 | 0.07 | 3.996 |
| 6 | 2808 | 0.0204 | 0.0623 | 0.06 | 3.996 |

The output is **indistinguishable from uniform** — 3.995 of a maximum
4.000 bits of entropy. Amplification isn't degraded; it is absent.
The noisy column is flat at `1/16 = 0.0625` regardless of iteration count, even as
the ideal column sweeps from 0.06 up to 0.96 and back down.

The advantage over random guessing measures **-1.41 standard errors** —
i.e. the noisy result sits marginally *below* the baseline, well within sampling
error. Significant: **no**.

This is worth dwelling on, because an earlier run at 1024 shots reported
`P(key) = 0.0654` against a `0.0625` baseline and a naive `>` comparison called
that a success. With the standard error at ±0.0077, that "advantage" was a third
of one sigma — pure noise. The two-sigma requirement is what turns this from a
misleading positive into the correct negative result.

The outcome agrees with the conclusion of Jaques et al. (2020) that Grover-based
key search is far out of reach of near-term hardware. Reporting it plainly is
more useful than tuning the noise down until the figure looks encouraging.

### Experiment C — the boundary of readout mitigation

| Scenario | raw `P(key)` | mitigated (NNLS) | ideal | recovered? |
|---|---|---|---|---|
| readout error only | 0.8408 | **0.9652** | 0.9613 | **essentially fully** |
| + gate error × 0.03 | 0.6343 | **0.7325** | 0.9613 | **partially** |
| + full gate error | 0.0574 | 0.0596 | 0.9613 | **not at all** |

Readout error is identical in all three rows; only gate error changes. So the
trend down that column is caused by gate noise and nothing else, and it is
monotonic: mitigation gains **+0.1243**, **+0.0982**, then **+0.0022** as gate
error rises.

- When measurement error is the only corruption, inverting `A` recovers the
  ideal distribution to within shot noise (0.8408 → 0.9652, ideal 0.9613),
  and cuts the TVD from 0.1225 to 0.0127.
- With gate error present but survivable, there is a real degraded peak and
  mitigation genuinely sharpens it (0.6343 → 0.7325).
- Once gate error has destroyed the quantum state, no amount of classical
  post-processing on the histogram can recover it. The information is gone
  *before* measurement happens. 0.0574 → 0.0596 is not a small
  improvement; both values *are* random guessing.

Mean readout fidelity was 0.8852 with
`cond(A) = 1.30` — a well-conditioned matrix, so
inversion amplifies shot noise only mildly.

#### The unphysicality of unconstrained inversion

In the readout-only scenario:

| Method | `P(key)` | TVD | negative mass | valid distribution? |
|---|---|---|---|---|
| raw | 0.8408 | 0.1225 | — | yes |
| `pinv` | 0.9692 | 0.0143 | 0.0049 | **NO** |
| `clip` | 0.9644 | 0.0119 | -0.0000 | yes |
| `nnls` | 0.9652 | 0.0127 | -0.0000 | yes |

`pinv` reports `P = 0.9692`, which **exceeds the ideal
0.9613**, while placing 0.0049 of probability mass below
zero. That is not a better answer — it is an unphysical overshoot, and exactly
the unfolding pathology documented by Nachman et al. (2020), reproduced here in
miniature. NNLS gives up a little accuracy to stay inside the probability
simplex, which is the right trade.

**Two attribution caveats**, worth stating because it is easy to overclaim here:

- NNLS is **not** the method M3 uses (Nation et al. 2021). M3 is *matrix-free* —
  it never forms `A` or its inverse — and solves within the subspace spanned by
  the observed bitstrings using a preconditioned iterative solver. It shares
  NNLS's *goal* of avoiding exponential calibration, not its mechanism. Nation
  et al. is the right citation for the `2ⁿ` calibration-scaling point, and the
  wrong one for NNLS.
- Nachman et al. (2020), cited above against `pinv`, actually advocate
  **iterative Bayesian unfolding** over both matrix inversion *and* least
  squares. So "NNLS is physically correct" would overstate what that paper
  supports. The safe, narrower claim — which is what the data here shows — is
  that NNLS always returns a valid distribution whereas `pinv` does not. NNLS is
  kept because it is exactly solvable and sufficient to establish the
  readout-versus-gate boundary; IBU would be the natural next comparison.

### Experiment D — how much better does hardware need to be?

| `p₂` | `P(key)` | rank of key | key ranked 1st? |
|---|---|---|---|
| 0 (ideal) | 0.9636 | 1 | yes |
| `10⁻⁵` | 0.9495 | 1 | yes |
| `3×10⁻⁵` | 0.9358 | 1 | yes |
| `10⁻⁴` | 0.8687 | 1 | yes |
| `3×10⁻⁴` | 0.7300 | 1 | yes |
| `10⁻³` | 0.4048 | 1 | yes |
| `3×10⁻³` | 0.1282 | 1 | yes |
| `10⁻²` *(today)* | 0.0574 | 13 | **no** |
| `3×10⁻²` | 0.0530 | 14 | **no** |

The decay is smooth and monotonic across three decades, then falls off a cliff.
The correct key stays the single most likely outcome up to `p₂ = 3×10⁻³`
(at `P = 0.1282`) and is lost by `10⁻²`, where its rank drops to 13 of 16.

Note the `rank` column — it is the operationally honest metric. At
`3×10⁻³` the success probability has fallen to 0.13, which sounds like
failure, but the correct key is still *first*, so an attacker verifies one
candidate and is done. Judged on `P(key)` alone you would write that regime off;
judged on what an attacker actually has to do, it still works. Once rank
collapses at `10⁻²`, both metrics agree it is over.

Current superconducting two-qubit error rates sit around `10⁻²`–`10⁻³`, so this
circuit needs roughly **one order of magnitude** improvement to work reliably,
and about **two** to approach the noiseless result.

That qualifier matters more than the number: this is a 16-key search over
1,404 CX gates. Real key search needs error correction, not merely
better physical gates.

### Experiment E — the speedup is in queries, and queries aren't free

| n | N | pairs | qubits | k* | CX | depth | query speedup |
|---|---|---|---|---|---|---|---|
| 4 | 16 | 1 | 8 | 3 | 1,404 | 4,861 | 5.3× |
| 5 | 32 | 2 | 13 | 4 | 3,824 | 13,212 | 8.0× |
| 6 | 64 | 2 | 14 | 6 | 5,784 | 19,924 | 10.7× |
| 7 | 128 | 2 | 15 | 8 | 11,232 | 39,172 | 16.0× |
| 8 | 256 | 3 | 20 | 12 | 33,360 | 96,604 | 21.3× |

Grover's quadratic saving is real and visible in the `k*` column. But each query
costs a circuit, and the CX count grows steeply — driven by the cipher, the
iteration count, *and* the number of plaintext pairs needed for a unique key.

This is what separates a *speedup claim* from a *resource estimate*, and it is
the connection to the AES resource-estimation literature (Grassl et al. 2016;
Jaques et al. 2020): the query count is the easy part.

#### And the speedup does not parallelise

One caveat belongs with every statement of the quadratic saving, because it is
what makes the saving far less threatening than it first sounds. Grover **cannot
be parallelised better than by splitting the search space across independent
quantum computers** (Zalka 1999). Divide a search of size `N` across `p`
machines and each handles `N/p`, needing `√(N/p)` queries — a saving of only
`√p`, where classical brute force gets the full factor `p`. And the `Ω(√N)`
lower bound (Bennett et al. 1997; Zalka 1999) says no better schedule exists.

So the `k*` column above is effectively a **sequential depth**, not a bill you
can pay down with more hardware. Together with the CX counts next to it, that is
why Jaques et al. (2020) conclude Grover key search on AES stays out of reach
even generously: the attack is depth-bound, and depth is exactly what a noisy
device cannot deliver. Experiment D is that same conclusion at toy scale.

---

## 10. Hardware and computational constraints

Answering the question directly: **the binding constraint is time, not memory** —
but only because of one deliberate choice.

### Memory: the exponential that was avoided

| Method | Memory | 8 qubits | 16 qubits | 20 qubits |
|---|---|---|---|---|
| Density matrix | `O(4ⁿ)` | 1 MB | **68 GB** | **17.6 TB** |
| Statevector trajectories | `O(2ⁿ)` | 4 KB | 1 MB | 16 MB |

Aer's `method="automatic"` may select **density-matrix** simulation once a noise
model is attached. At 16 qubits that is 68 GB, which exhausts any commodity
machine — and this actually happened during development: the first noisy run
appeared to hang.

Pinning `method="statevector"` makes Aer use **stochastic quantum trajectories**
instead: one pure state per shot, sampling a Kraus operator at each noisy gate,
with the shot average converging to the same density-matrix answer. Memory drops
from `O(4ⁿ)` to `O(2ⁿ)`.

A note on framing: the original project brief claimed that *shot-based sampling*
avoids storing the statevector. That isn't right — Aer maintains a statevector
either way. What trajectory sampling avoids is the **density matrix**. The
distinction matters because it identifies the actual mechanism: `4ⁿ → 2ⁿ`, not
`2ⁿ → 1`.

A `max_memory_mb = 4096` cap is passed to Aer so an over-large configuration
fails fast with a clear error instead of silently swapping to disk.

### Time: the constraint that actually bites

```
runtime  ∝  shots × gate_count × 2^qubits
```

All three factors grow together as the key widens. Measured on the reference
machine (16 cores; Aer parallelises across shots automatically):

| Configuration | Qubits | CX | 4096 shots |
|---|---:|---:|---:|
| 4-bit key, 1 pair *(default)* | 8 | 1,404 | ~2.3 min |
| 5-bit key, 2 pairs | 13 | 3,824 | ~3.3 hours |
| 6-bit key, 2 pairs | 14 | 5,784 | ~10 hours |
| 8-bit key, 3 pairs | 20 | 33,360 | ~150 days |

The 4-bit row is measured; the rest are extrapolated from it using
Eq. runtime ∝ shots × gates × 2^qubits, and are shown to convey the shape
of the wall, not as benchmarks.

Two consequences shaped the project:

1. **Experiments A–D run on the 8-qubit configuration.** The default secret key
   `0b1101` is chosen because it is uniquely determined by a *single* plaintext
   pair, so the oracle needs one data register. The attack is not weakened —
   `M = 1` either way, verified by brute force — but runtime drops by 16×–256×
   versus keys needing 2–3 pairs.
2. **Experiment E measures larger circuits by transpiling without simulating.**
   Resource counts are exact and cost seconds; simulating them is infeasible.
   Getting real numbers for 20-qubit circuits without running them is the right
   engineering answer.

### Requirements summary

- **RAM:** ~4 GB for the default configuration. The original 8 GB target is met
  with room to spare, and memory is *not* the limiting factor.
- **CPU:** any modern multi-core machine. Runtime scales roughly inversely with
  core count.
- **Disk:** a few MB of JSON and PNG.
- **No GPU, no quantum hardware, no cloud account.**

### The green-IT connection, stated carefully

There is a legitimate energy argument, but it should be made precisely. The
trajectory method reduces the memory footprint of noisy simulation from `4ⁿ` to
`2ⁿ`, which is what keeps this study on one laptop instead of a cluster — and
compute time maps fairly directly onto energy consumed
(Lannelongue et al. 2021). There is also a deeper theoretical thread: reversible
computation has no thermodynamic lower bound on dissipation per operation
(Landauer 1961; Bennett 1973), which is exactly why quantum circuits must be
built from reversible primitives in the first place.

What should *not* be claimed is that this study measures energy savings. It
doesn't. It makes an algorithmic choice with a favourable memory-scaling
consequence, and that is worth stating plainly and no more strongly.

---

## 11. The test suite, and why it's the most important part

62 tests (60 by default, 2 behind a `slow` marker). Two of them carry the
whole project.

### `test_spn_equivalence.py` — the quantum circuit *is* the cipher

For every key × every plaintext, across 5 configurations, the **exact unitary**
of the encryption circuit is checked against the classical reference:

```python
unitary = Operator(encryption_circuit(params)).data
for key in range(key_space):
    for plaintext in range(16):
        column = key + (plaintext << key_bits)
        expected_row = key + (encrypt(plaintext, key, params) << key_bits)
        assert argmax(|unitary[:, column]|) == expected_row
```

This tests the *circuit*, not a sampled outcome. Exhaustive, and affordable
because the toy size makes it so. Without this, every downstream result would
rest on an unverified assumption.

### `test_oracle.py` — phases correct *and* uncomputation clean

Checks the `−1` phase on every marked key, `+1` elsewhere, and — the part that
matters — that all probability mass returns to the plaintext subspace. As
explained in §4, incomplete uncomputation is a bug that produces correct-looking
phases and silently broken amplification.

### The rest

- `test_grover.py` — iteration count against the closed form; over-rotation;
  diffuser fixes `|s⟩`; and simulation agreeing with `sin²((2k+1)θ)` to `10⁻⁶`
  rather than merely "being high".
- `test_mitigation.py` — the decisive test builds an **analytically known**
  assignment matrix from a tensor product of single-qubit flip matrices and
  checks exact recovery, rather than just checking things got closer. It also
  asserts that `pinv` *does* produce negative mass in a case where it should,
  pinning the documented pathology as tested behaviour.

### A note on test performance

One statevector test originally took 111 seconds because it used Qiskit's Python
`Statevector`. Switching `ideal_distribution` to Aer's C++ statevector with
`save_probabilities` cut it to 1.2 seconds — identical results, ~90× faster. The
full suite now runs in about five minutes, most of it in the noisy-simulation
integration tests, which is the difference between tests you run and tests you
skip.

Slower large-key-space checks are behind a `slow` marker (`pytest -m slow`).

---

## 12. What we deliberately did *not* claim

Being explicit about this is part of the work.

1. **A 4-bit key is not cryptography.** It is a controlled testbed. Nothing here
   threatens any real cipher.
2. **Gate counts are upper bounds, not optimal estimates.** The S-box is exact
   but synthesised from its permutation matrix by quantum Shannon decomposition
   (Shende et al. 2006), costing ~95 CX. A hand-built Toffoli network would be
   substantially cheaper. Reporting the automated-synthesis cost honestly, and
   labelling it an upper bound, is better than implying it's optimal.
3. **The noise model is a simplification.** Uniform depolarizing plus readout
   error, with no `T₁`/`T₂` decay, crosstalk, leakage, drift or correlated
   readout error. Real devices are worse *and* less uniform.
4. **Mitigation is not correction.** Post-processing a classical histogram
   corrects no quantum state. Experiment C measures where that boundary sits.
5. **`M` comes from classical brute force** to set the iteration count. Fine for
   studying the algorithm; a real attacker would use the exponential-search
   schedule of Boyer et al. (1998).
6. **Noiseless `rz` is an idealisation** — see §6. It is the most common gate
   after transpilation, so the assumption matters more than it looks.
7. **NNLS is sufficient, not optimal.** It is neither M3's mechanism nor the
   method Nachman et al. recommend (see §7). Iterative Bayesian unfolding is the
   natural next comparison.

---

## 13. Natural next steps

- **Zero-noise extrapolation** for gate error (Temme et al. 2017; Li & Benjamin
  2017). `NoiseParams.scaled()` already exists precisely to support this — it is
  the mechanism ZNE needs, and Experiment D already sweeps it.
- **A hand-optimised Toffoli S-box**, to turn the resource counts from upper
  bounds into tight estimates and to make deeper configurations simulable.
- **Tensored / M3 calibration** (Nation et al. 2021) to break the `2ⁿ`
  calibration wall and reach wider key registers.
- **Multiple-solution Grover** (`M > 1`) as a first-class experiment — the code
  already handles it correctly, but it isn't yet studied on purpose.
- **Simon's-algorithm-style attacks** (Kuwakado & Morii 2010; Kaplan et al.
  2016), which give *exponential* rather than quadratic advantage against certain
  symmetric constructions — a genuinely different threat model from Grover.

---

## 14. File-by-file map

| File | Responsibility | Depends on |
|---|---|---|
| `spn.py` | Classical cipher, brute force, instance generation | stdlib only |
| `oracle.py` | `U_E`, phase oracle, compute/phase/uncompute | `spn`, qiskit |
| `grover.py` | Diffuser, search circuit, `k*`, analytic `P` | `oracle`, `spn` |
| `noise.py` | Depolarizing + readout `NoiseModel` factories | qiskit-aer |
| `mitigation.py` | Calibration circuits, `A`, three inversions | numpy, scipy |
| `metrics.py` | `P_success`, TVD, Hellinger, entropy, rank, resources | numpy |
| `runner.py` | Transpile, execute, calibrate — *all* Aer contact | `noise`, `mitigation` |
| `experiments.py` | Experiments A–E → JSON records | everything above |
| `plots.py` | Figures from saved JSON | matplotlib |
| `cli.py` | `qspn-run`, summary table, provenance | all |

The dependency graph is a DAG with no cycles, and Aer is touched in exactly one
module. That's what keeps the algorithmic code unit-testable without a simulator.

---

## 15. Bottom line

The project does what its brief set out to do, with three substantive
corrections made along the way:

1. **The oracle was made non-circular** — it evaluates the cipher in
   superposition rather than being handed the answer, and needs multiple
   plaintext pairs to pin the key down, mirroring the AES literature.
2. **The iteration count and over-rotation were treated exactly** — `⌊(π/4)√(N/M)⌋`,
   with the periodic decline measured rather than ignored.
3. **The memory-scaling claim was corrected and then actually secured** — the
   saving is `4ⁿ → 2ⁿ` via trajectory sampling, not "avoiding the statevector",
   and pinning the simulation method is what makes the study run on a laptop.

The scientific content is the **boundary** in Experiment C: classical readout
mitigation recovers a readout-limited signal almost perfectly, and does nothing
whatever for a gate-error-limited one. Combined with Experiment D's threshold and
Experiment E's resource counts, the picture is consistent and unflattering —
which is the correct picture for Grover-based cryptanalysis on NISQ hardware.
