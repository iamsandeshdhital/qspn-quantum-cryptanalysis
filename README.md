# Complexity and Noise-Resilience of Quantum Oracles for Symmetric Cryptanalysis

A reproducible study of **Grover-based known-plaintext key search** against a toy
4-bit substitution–permutation network (SPN), executed under **simulated NISQ
noise**, with **classical readout-error mitigation**.

Everything runs on a laptop. No quantum hardware and no cloud account required.

```
Classical SPN  ──►  Reversible oracle  ──►  Grover search  ──►  NISQ noise  ──►  Error mitigation
   spn.py            oracle.py              grover.py           noise.py         mitigation.py
```

---

## What this project actually establishes

| # | Result | Where |
|---|--------|-------|
| 1 | The quantum circuit provably computes the classical cipher — verified on the **exact unitary** for every key × plaintext, across 5 configurations | `tests/test_spn_equivalence.py` |
| 2 | The oracle marks the right keys **and** fully uncomputes its data registers (no residual entanglement) | `tests/test_oracle.py` |
| 3 | Ideal amplification matches `sin²((2k+1)θ)` to **~4×10⁻¹⁵**, including the over-rotation decline past `k*` | Experiment A |
| 4 | At today's error rates (`p₂ = 10⁻²`) the attack is **completely destroyed** — output entropy 3.995 of 4.000 bits, −1.4σ vs random | Experiment B |
| 5 | Readout mitigation recovers **0.841 → 0.965** when readout error is the only channel, and does **nothing** (0.057 → 0.060) against gate error | Experiment C |
| 6 | Naive pseudo-inverse mitigation returns **negative probabilities** and overshoots past the ideal; NNLS stays physical | Experiment C |
| 7 | The attack needs two-qubit error rates **~1–2 orders of magnitude** better than current hardware (`p₂ ≤ 3×10⁻³`) | Experiment D |
| 8 | Grover's quadratic *query* saving is bought with circuits whose CX count grows steeply — the honest cost picture | Experiment E |
| 9 | The quadratic saving **does not parallelise** (Zalka 1999), so `k*` is a sequential depth, not a cost more hardware can spend down | Experiment E |

Result 5 is the one worth internalising: readout-error mitigation is a
**measurement-channel** correction. It is not a general-purpose noise fix, and
this repository measures that boundary rather than assuming it.

---

## Quick start

### 1. Install

Requires **Python 3.10+**.

```bash
git clone <your-repo-url> quantum-spn-cryptanalysis
cd quantum-spn-cryptanalysis

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e .
```

<details>
<summary>Windows PowerShell / Git Bash notes</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

In Git Bash, call the interpreter directly if activation misbehaves:

```bash
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m qspn.cli --quick
```
</details>

### 2. Verify correctness first

Never trust the physics before the tests pass — the whole study rests on the
oracle being right.

```bash
pip install -e ".[dev]"
pytest -q
```

Expect **60 passed, 2 deselected** in roughly 5 minutes. Add the larger
key-space checks (statevector tests at 5- and 6-bit keys) with:

```bash
pytest -q -m slow
```

### 3. Run it

```bash
# fast end-to-end check: ~6 minutes
qspn-run --quick

# full study, all five experiments: ~40 minutes
qspn-run

# a single experiment
qspn-run --experiments c
```

Outputs land in `results/`:

```
results/
├── data/        one JSON record per experiment (full distributions + provenance)
├── figures/     six PNG figures
└── summary.txt  the printed summary table
```

Figures are generated **from the saved JSON**, so you can restyle them without
re-simulating:

```bash
qspn-run --plots-only
```

---

## Reading the output

`qspn-run` prints a summary like this (abridged, from a real run):

```
Instance   : 4-bit key, 2 rounds, secret = 1101
             1 known pair(s), M = 1 marked key(s), 8 qubits

[A] Ideal simulation
    optimal iterations k*        : 3
    best measured P(key)         : 0.9613 at k = 3
    max deviation from sin^2     : 4.33e-15
    over-rotation observed       : yes

[B] Noisy simulation (at k*)
    ideal  P(key)                : 0.9613
    noisy  P(key)                : 0.0574 +/- 0.0036
    output entropy (bits)        : 3.9951 (uniform = 4.0000)
    advantage over random        : -1.4 sigma  (significant: no)

[C] Readout-error mitigation
    ideal P(key)                 : 0.9613
    -- readout error only
       raw P(key)                : 0.8408   TVD = 0.1225
       pinv  P(key)              : 0.9692   TVD = 0.0143   neg.mass = 0.0049   valid = no
       nnls  P(key)              : 0.9652   TVD = 0.0127   neg.mass = 0.0000   valid = yes
    -- readout + full gate error
       raw P(key)                : 0.0574   TVD = 0.9039
       nnls  P(key)              : 0.0596   TVD = 0.9017   valid = yes

[D] Noise threshold
    largest p2 still recovering  : 3.0e-03
```

Four things to notice:

- `max deviation from sin^2` at `4e-15` is floating-point noise. The
  implementation is not "approximately" Grover; it is Grover.
- `advantage over random` is **-1.4 sigma** — the noisy result sits marginally
  *below* the `1/16 = 0.0625` baseline, well inside sampling error. A bare `>`
  comparison would have called this a success; it is not.
- `pinv` reports `valid = no` because it produced negative probabilities, and its
  `P(key) = 0.9692` **exceeds the ideal 0.9613** — an unphysical
  overshoot, not a better answer.
- In the `readout + full gate error` block, mitigation moves `P(key)` from
  0.0574 to 0.0596. Both are random guessing. Nothing was recovered,
  and that is the correct outcome.

---

## Command-line reference

```
qspn-run [options]

  --experiments abcde     subset of experiments to run                (default: abcde)
  --shots N               shots per circuit                           (default: 4096)
  --seed N                master RNG seed                             (default: 20260902)

  --key-bits N            master key width in bits                    (default: 4)
  --rounds N              SPN rounds                                  (default: 2)
  --secret-key V          key to recover; accepts 0b1101 / 0xd / 13   (default: 0b1101)
  --num-pairs N           known plaintext/ciphertext pairs            (default: auto)

  --p1 F                  1-qubit depolarizing rate                   (default: 1e-3)
  --p2 F                  2-qubit depolarizing rate                   (default: 1e-2)
  --readout-01 F          P(measure 1 | prepared 0)                   (default: 0.02)
  --readout-10 F          P(measure 0 | prepared 1)                   (default: 0.04)

  --key-widths 4,5,6,7,8  key widths for the Experiment E resource scan
  --quick                 fewer shots and sweep points
  --plots-only            rebuild figures + summary from saved JSON
  --out DIR               results directory                           (default: ./results)
```

Useful variations:

```bash
# Find the noise threshold on a deeper cipher
qspn-run --experiments d --rounds 3

# A key that needs 3 plaintext pairs (16 qubits — slow, see Hardware below)
qspn-run --experiments ae --secret-key 0b1011

# Near-term-optimistic hardware
qspn-run --experiments bc --p2 1e-4 --readout-01 0.005 --readout-10 0.008
```

---

## Hardware constraints — read this before scaling up

The binding constraint is **not** memory. It is **time**.

### Memory: safe, because of one deliberate choice

Noisy simulation has two possible representations:

| Method | Memory | 8 qubits | 16 qubits | 20 qubits |
|--------|--------|----------|-----------|-----------|
| Density matrix | `O(4ⁿ)` | 1 MB | **68 GB** | **17.6 TB** |
| Statevector trajectories | `O(2ⁿ)` | 4 KB | 1 MB | 16 MB |

Aer's `method="automatic"` may pick **density matrix** once a noise model is
attached, which is what makes naive noisy simulation blow up. This project
therefore **pins `method="statevector"`** in `RunConfig`, so Aer uses stochastic
quantum trajectories: one pure state per shot, sampling a Kraus operator at each
noisy gate, with the shot average converging to the same density-matrix result.

A `max_memory_mb = 4096` cap is also passed to Aer, so an over-large
configuration fails fast with a clear error instead of silently swapping to disk.

**Consequence: the default configuration needs about 4 GB of RAM, and the memory
figure barely moves as you add shots.**

### Time: this is what will actually stop you

Trajectory runtime scales as:

```
runtime  ∝  shots × gate_count × 2^qubits
```

All three factors grow together as you scale the key, which is why cost climbs
so fast. Measured on the reference machine (16 cores; Aer parallelises across
shots automatically):

| Configuration | Qubits | CX gates | 4096 shots |
|---------------|-------:|---------:|-----------:|
| 4-bit key, 1 pair (default) | 8 | 1,404 | ~2.3 min |
| 5-bit key, 2 pairs | 13 | 3,824 | ~3.3 hours |
| 6-bit key, 2 pairs | 14 | 5,784 | ~10 hours |
| 8-bit key, 3 pairs | 20 | 33,360 | ~150 days |

The 4-bit row is measured; the rest are extrapolated from it using
Eq. runtime ∝ shots × gates × 2^qubits, and are shown to convey the shape
of the wall, not as benchmarks.

So: **Experiments A–D deliberately run on the 8-qubit configuration**, and
**Experiment E measures the larger circuits by transpiling them without
simulating** — resource counts are exact and cost seconds, whereas simulating
them is infeasible.

The default secret key `0b1101` is chosen because it is uniquely determined by a
*single* plaintext/ciphertext pair, so the oracle needs only one 4-bit data
register (8 qubits total). Other keys need 2–3 pairs, pushing the circuit to
12–16 qubits and multiplying runtime by 16×–256×. The attack is not weakened by
this choice: `M = 1` either way, verified by brute force in `Instance.build`.

### Practical guidance

| You have | Do this |
|----------|---------|
| Any modern laptop, 4 GB free | `qspn-run` as-is |
| 8 GB RAM | Fine. Memory is not the limit; leave `method="statevector"` alone |
| Want a faster loop | `qspn-run --quick` (1024 shots), or `--experiments a` |
| Want bigger key spaces | Use `--key-widths` with Experiment E (transpile-only). Do **not** try to simulate a 20-qubit noisy circuit |
| Few CPU cores | Runtime scales roughly inversely with cores; halve `--shots` and expect larger error bars (`p_success_stderr` is reported) |

One more exponential to respect: full readout calibration needs `2ⁿ` circuits
over the **measured** qubits — 16 at 4 bits, 256 at 8 bits. Only the key
register is measured, which is what keeps this tractable; measuring the data
registers too would demand `2^(k+4r)` calibration circuits. Beyond ~10 measured
qubits, switch to a tensored or subspace-reduced method such as M3
(Nation et al. 2021).

---

## Repository layout

```
├── src/qspn/
│   ├── spn.py            classical reference cipher + exhaustive search  (ground truth)
│   ├── oracle.py         reversible encryption circuit + phase oracle
│   ├── grover.py         diffuser, search circuit, analytic success probability
│   ├── noise.py          depolarizing + readout NoiseModel factories
│   ├── mitigation.py     assignment matrix, three inversion strategies
│   ├── metrics.py        success probability, TVD, Hellinger, entropy, resources
│   ├── runner.py         transpilation, execution, calibration  (Aer lives here only)
│   ├── experiments.py    Experiments A–E, each returning a JSON record
│   ├── plots.py          figure generation from saved records
│   └── cli.py            qspn-run entry point
├── tests/                62 tests; the equivalence + oracle tests are the load-bearing ones
├── docs/
│   ├── REPORT.md         narrative walkthrough: what each piece does and why
│   ├── original-brief.md the original .docx spec, in diffable form
│   └── report/           LaTeX report + references.bib
└── results/              data/, figures/, summary.txt
```

### The cipher

A 4-bit block SPN in the structure of PRESENT (Bogdanov et al. 2007) and the
classic teaching cipher of Heys (2002):

```
ARK(rk₀) ──► [ S-box ──► P-layer ──► ARK(rk_r) ] × rounds
```

- **S-box** — the real PRESENT 4-bit S-box, not an ad-hoc permutation.
- **P-layer** — fixed bit permutation `(0→1, 1→3, 2→0, 3→2)`.
- **Key schedule** — round key `r` is `rotl(K, r) & 0xF`. Rotation is *free* on a
  quantum register: it only changes which key qubit acts as the control.

### The oracle

`f(K) = 1` iff `E_K(Pᵢ) == Cᵢ` for **every** known pair, built as
**compute → phase → uncompute**:

1. `U_E` computes `E_K(Pᵢ)` in place on data register `i`, key register as controls.
2. An X-mask plus one multi-controlled Z over all `4r` data qubits applies `−1`
   exactly on the winning concatenated ciphertext. The `r` equality tests fuse
   into a single AND, so **no flag ancillas are needed at all**.
3. `U_E†` restores every data register to `|Pᵢ⟩`.

Total: `key_bits + 4r` qubits, **zero ancillas** — every cipher layer is
individually a bijection on 4 bits.

> **Why multiple pairs?** For a 4-bit block, `K ↦ E_K(P)` is not injective, so one
> pair typically leaves several consistent keys. This is not a toy artefact: it
> is the same counting argument that forces quantum key-search oracles for
> AES-128 to encrypt several plaintext blocks (Grassl et al. 2016; Jaques et al.
> 2020). `make_attack_instance` grows the pair count until brute force confirms
> `M = 1`.

---

## Reproducibility

- Every run is seeded (`--seed`, default `20260902`): transpiler, simulator, and sampling.
- Every JSON record embeds a provenance block — `qspn` version, Python, platform,
  Qiskit/Aer/NumPy versions, runtime, and the full `RunConfig`.
- Full output distributions are saved, not just summary scalars, so any metric
  can be recomputed after the fact.
- `results/` is committed, so the figures in the report are traceable to data
  without anyone re-running the study.

Reported probabilities are estimates from finite sampling. Each carries a
binomial standard error (`p_success_stderr`); comparisons against the
random-guessing baseline require a two-sigma margin before the code claims an
advantage.

---

## Known limitations

These are stated plainly because they bound what the results mean.

1. **A 4-bit key is not cryptography.** It is a controlled testbed for oracle
   construction, amplification, noise and mitigation. Nothing here threatens any
   real cipher, and Grover against AES-128 remains far out of reach
   (Jaques et al. 2020).
2. **S-box synthesis is not optimised.** The S-box is exact but synthesised from
   its permutation matrix by quantum Shannon decomposition (Shende et al. 2006),
   costing ~95 CX. A hand-built Toffoli network would be substantially cheaper,
   so **all reported gate counts are upper bounds**, not optimal estimates.
3. **The noise model is a simplification.** The extended noise model now includes
   T1/T2 thermal relaxation, coherent overrotation, crosstalk, leakage, and drift,
   but real devices have additional correlated errors, non-Markovian noise, and
   time-varying calibration that are not fully captured.
4. **Mitigation ≠ correction.** Readout mitigation is post-processing on a
   classical histogram. It corrects no quantum state and cannot address gate
   error — Experiment C measures exactly that limit. Zero-noise extrapolation
   (Temme et al. 2017) would be the next step for gate error.
5. **Full calibration is exponential** in measured qubits, as described above.
6. **`M` is obtained by classical brute force** to set the iteration count. Valid
   for studying the algorithm; a real attacker would use the exponential-search
   schedule of Boyer et al. (1998).
7. **No real hardware validation by default.** The `qspn.hardware` module provides
   tools for hardware characterization, but validation against real IBM Quantum
   backends requires credentials and is not run in CI.

---

## Documentation

- **`docs/REPORT.md`** — narrative walkthrough of every component, the design
  decisions and why they were made, the pitfalls avoided, and the results in context.
- **`docs/report/report.tex`** — formal LaTeX report with `references.bib`. Every
  number in it is generated from `results/data/*.json` by
  `scripts/make_report_macros.py`, so the prose cannot drift from the data.
- **`docs/original-brief.md`** — the original `.docx` specification converted to
  Markdown, with the three points revised during implementation flagged inline.
- **`docs/ARXIV_VERIFICATION.md`** — an independent audit of every external
  citation against arXiv and the publishers of record, with a disposition table
  recording which findings were actioned. Three overclaims it identified (the M3
  attribution, the Nachman et al. reading, and the noiseless-`rz` justification)
  have been corrected in the code and both reports.
- **`docs/VALIDATION.md`** — comprehensive validation framework documentation,
  including noise model validation, oracle verification, and hardware
  characterization.

## Validation

The project includes a comprehensive validation framework:

```bash
# Run all validation checks
python scripts/run_validation.py

# Validate against real IBM Quantum hardware
python scripts/validate_hardware.py --backend ibmq_quito --qubits 4
```

See **`docs/VALIDATION.md`** for full documentation.

Build everything — experiments, figures, report macros, PDF — in one command:

```bash
python scripts/run_all.py           # full study, then build the PDF
python scripts/run_all.py --quick   # fast check
python scripts/run_all.py --pdf-only  # rebuild the report from existing results
```

Or build just the PDF by hand (three `pdflatex` passes are needed: the first
writes the `.aux`, `bibtex` turns it into `.bbl`, and the last two settle
citations and then cross-references):

```bash
cd docs/report
pdflatex report.tex && bibtex report && pdflatex report.tex && pdflatex report.tex
```

---

## Key references

Full bibliography in `docs/report/references.bib`.

- L. K. Grover, *A fast quantum mechanical algorithm for database search*, STOC 1996.
- M. Boyer, G. Brassard, P. Høyer, A. Tapp, *Tight bounds on quantum searching*,
  Fortschr. Phys. **46** (1998) 493. — the `⌊(π/4)√(N/M)⌋` iteration count.
- A. Bogdanov et al., *PRESENT: An ultra-lightweight block cipher*, CHES 2007. — the S-box.
- H. M. Heys, *A tutorial on linear and differential cryptanalysis*,
  Cryptologia **26** (2002) 189. — the SPN teaching model.
- M. Grassl, B. Langenberg, M. Roetteler, R. Steinwandt, *Applying Grover's
  algorithm to AES: quantum resource estimates*, PQCrypto 2016.
- S. Jaques, M. Naehrig, M. Roetteler, F. Virdia, *Implementing Grover oracles
  for quantum key search on AES and LowMC*, EUROCRYPT 2020.
- J. Preskill, *Quantum computing in the NISQ era and beyond*, Quantum **2** (2018) 79.
- S. Bravyi, S. Sheldon, A. Kandala, D. C. McKay, J. M. Gambetta, *Mitigating
  measurement errors in multiqubit experiments*, Phys. Rev. A **103** (2021) 042605.
- P. D. Nation, H. Kang, N. Sundaresan, J. M. Gambetta, *Scalable mitigation of
  measurement errors on quantum computers*, PRX Quantum **2** (2021) 040326.
- K. Temme, S. Bravyi, J. M. Gambetta, *Error mitigation for short-depth quantum
  circuits*, Phys. Rev. Lett. **119** (2017) 180509.

---

## License

MIT — see `LICENSE`.
