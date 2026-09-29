# Literature Verification Against arXiv and Primary Sources

**Scope.** Every external claim and citation in `src/qspn/` and in
`Quantum_Cryptanalysis_Documentation.docx` was checked against arXiv listings or,
where a work is not on arXiv, against the publisher of record. Substantive
technical claims were re-derived numerically or measured directly from the code.

**Verified.** 2026-09-02, against `src/qspn/` as of 21:28 and the `.docx` of 21:09.
Environment: Qiskit 2.5.2, Aer 0.17.2, NumPy 2.5.2, SciPy 1.18.1, Python 3.13.

---

## 1. Citation audit

All ten citations appearing in the source resolve to real works, and in every case
the authors and year attributed in the code are correct. Years cited are venue
years, which differ from arXiv submission years in five cases — this is correct
practice, noted here only so the discrepancy is not mistaken for an error.

| Cited as | arXiv | Title / venue | Verdict |
|---|---|---|---|
| Boyer, Brassard, Hoyer & Tapp 1998 (`grover.py`) | [quant-ph/9605034](https://arxiv.org/abs/quant-ph/9605034) | *Tight bounds on quantum searching*, Fortschr. Phys. 46:493–506 (1998); submitted 1996 | **Correct** |
| Bogdanov et al., CHES 2007 (`spn.py`) | not on arXiv | *PRESENT: An Ultra-Lightweight Block Cipher*, CHES 2007, LNCS 4727 | **Correct** |
| Heys 2002 (`spn.py`) | not on arXiv | Howard M. Heys, *A Tutorial on Linear and Differential Cryptanalysis*, Cryptologia 26(3) (2002) | **Correct** |
| Shende, Bullock & Markov 2006 (`oracle.py`) | [quant-ph/0406176](https://arxiv.org/abs/quant-ph/0406176) | *Synthesis of Quantum Logic Circuits*, IEEE TCAD 25(6):1000–1010 (2006); submitted 2004 | **Correct** |
| Grassl et al. 2016 (`oracle.py`) | [1512.04965](https://arxiv.org/abs/1512.04965) | *Applying Grover's algorithm to AES: quantum resource estimates*, PQCrypto 2016; submitted 2015 | **Correct** |
| Jaques et al. 2020 (`oracle.py`) | [1910.01700](https://arxiv.org/abs/1910.01700) | *Implementing Grover oracles for quantum key search on AES and LowMC*, EUROCRYPT 2020; submitted 2019 | **Correct** |
| Preskill 2018 (`noise.py`) | [1801.00862](https://arxiv.org/abs/1801.00862) | *Quantum Computing in the NISQ era and beyond*, Quantum 2, 79 (2018) | **Correct** |
| Temme, Bravyi & Gambetta 2017 (`noise.py`) | [1612.02058](https://arxiv.org/abs/1612.02058) | *Error mitigation for short-depth quantum circuits*, PRL 119, 180509 (2017); submitted 2016 | **Correct** |
| Nachman et al. 2020 (`mitigation.py`) | [1910.01969](https://arxiv.org/abs/1910.01969) | *Unfolding Quantum Computer Readout Noise* (2020); submitted 2019 | **Correct, but see F2** |
| Nation et al. 2021 (`mitigation.py`) | [2108.12518](https://arxiv.org/abs/2108.12518) | *Scalable mitigation of measurement errors on quantum computers*, PRX Quantum 2, 040326 (2021) | **Correct, but see F1** |

### Claims confirmed against the primary sources

- **PRESENT S-box.** The table in `spn.py` — `C,5,6,B,9,0,A,D,3,E,F,8,4,7,1,2` — is an
  exact match to the S-box in the original CHES 2007 paper (verified against the
  [IACR archive PDF](https://www.iacr.org/archive/ches2007/47270450/47270450.pdf)).
  The `spn.py` claim that this is "a real, published cryptographic S-box" is accurate.
  Note for the write-up: PRESENT itself is a 64-bit block / 80- or 128-bit key cipher
  with 31 rounds, and applies this S-box 16x in parallel. The project borrows only the
  S-box, which is a legitimate and clearly-stated simplification.
- **Heys' SPN.** `spn.py` says the structure "mirrors the classical SPN teaching model
  of Heys 2002". Confirmed: Heys' tutorial cipher is a 16-bit block, 4-round SPN of
  substitution / transposition / key mixing — the same shape at a larger width.
- **Quantum Shannon decomposition.** `oracle.py`'s attribution is correct. Shende,
  Bullock & Markov introduce QSD via the "quantum multiplexor" block and prove an
  asymptotically-optimal ~(23/48)·4^n CNOT bound, within a factor 2 of the lower bound.
- **Zero-noise extrapolation.** `noise.py` cites Temme et al. as "the mechanism
  zero-noise extrapolation would build on". Correct: that paper introduces ZNE via
  Richardson extrapolation, plus probabilistic error cancellation. It is a *gate*-error
  method, which is consistent with how `noise.py` uses it (as motivation for
  `NoiseParams.scaled`, a rate-scaling hook) and correctly *not* conflated with the
  readout mitigation in `mitigation.py`.
- **Multi-pair oracle.** `oracle.py`'s rationale — that a single pair leaves several
  consistent keys, and that this is "the same counting argument that forces quantum
  key-search oracles for AES-128 to encrypt multiple plaintext blocks" — is accurate
  and correctly attributed. Grassl et al. use r = 3, 4, 5 pairs for AES-128/192/256;
  Jaques et al. later show these are conservative and that r = 2 suffices for AES-128
  with failure probability below 2^-128. The expected number of spurious keys scales as
  2^(k-rn) for key length k, block size n, r pairs. The project's rule
  r = ceil(key_bits/4) + 1 yields at most 2^-4 expected spurious keys at every width,
  so it sits on the correct side of the literature's criterion.
- **Grover iteration count.** `optimal_iterations` returns floor((pi/4)·sqrt(N/M)).
  This is the standard form and matches BBHT. I checked it against the exact maximiser
  of sin^2((2k+1)theta), theta = arcsin(sqrt(M/N)), i.e. round(pi/(4·theta) - 1/2), and
  the two agree exactly for key widths 4, 6, 8 and 16 at M = 1. The closed form is an
  approximation valid for small M/N, but in this project's regime it is exact.
- **BBHT unknown-M schedule.** `grover.py` says an attacker ignorant of M "would use
  the exponential-search schedule of Boyer et al. (1998)". Confirmed — BBHT give an
  algorithm for unknown M based on geometrically increasing the guessed range.
- **Memory footprint (Objective 6).** Verified empirically, not just argued. On the
  4-bit instance the transpiled circuit is 16 qubits and Aer's `automatic` method
  selects **`statevector`** (stochastic trajectories), i.e. 2^16 · 16 B ~ **1.05 MB**.
  Had it selected `density_matrix` the cost would have been 2^32 · 16 B ~ **68.7 GB**,
  which would have broken the 8 GB budget outright. `runner.py`'s claim of O(2^n)
  rather than O(4^n) scaling holds — but it holds *because of* Aer's method choice, so
  it is worth pinning down with an assertion rather than leaving to `automatic`.

---

## 2. Findings

Ranked by how much they affect the project's conclusions.

### F1 — `mitigation.py` misattributes NNLS to M3 *(factual error, one sentence)*

> "…and is the approach taken by production tooling such as M3 (Nation et al. 2021)."

M3 does **not** use non-negative least squares. Its defining feature is that it is
*matrix-free*: it never forms the assignment matrix **or its inverse**, and instead
solves in a subspace spanned by the observed noisy bitstrings using a preconditioned
iterative (Krylov/GMRES-type) solver that converges in O(1) steps, using "orders of
magnitude less memory than direct factorization" (PRX Quantum 2, 040326).

The project's NNLS default shares M3's *goal* — a physically valid distribution
obtained without exponential calibration — but not its mechanism. Nation et al. is the
right citation for the scalability critique already made in the module docstring
("full calibration is exponential in the number of measured qubits"), and the wrong
citation for NNLS. Suggested repair: cite Nation et al. only for the scaling point, and
drop or reword the "approach taken by" clause.

### F2 — `mitigation.py` cites Nachman et al. for half of its conclusion *(interpretive)*

Nachman et al. is cited, correctly, to support the criticism that naive `pinv`
unfolding produces negative probabilities. But the same paper's headline conclusion is
that **iterative Bayesian unfolding (IBU) avoids pathologies from commonly used matrix
inversion _and least squares_ methods** — i.e. it argues against the very family the
project adopts as its default, not merely against `pinv`.

Calling NNLS "the physically correct formulation" therefore overstates what the cited
literature supports. NNLS does guarantee a valid distribution, which is a real
advantage over `pinv`, and that narrower claim is safe. Two honest options: add IBU as
a fourth method and compare (it is ~15 lines, and would make the mitigation study
genuinely novel rather than standard), or keep NNLS and state explicitly that Nachman
et al. recommend IBU over least squares, with a sentence on why NNLS was kept anyway.

### F3 — the noise defaults destroy the Grover signal completely *(most consequential)*

This is the finding most likely to change what the project concludes, and it is
measured, not predicted.

On the default 4-bit instance (`key_bits=4`, `rounds=2`, which `make_attack_instance`
resolves to **r = 3 pairs**, M = 1, 3 iterations), the transpiled circuit is:

| metric | value |
|---|---|
| qubits | 16 |
| depth | 14,590 |
| **CX gates** | **4,344** |
| total gates | 25,471 (rz 13,439 · sx 7,624 · cx 4,344 · x 56) |

At the default `p2 = 1e-2`, the probability of no two-qubit depolarizing event anywhere
in the circuit is (1 - 0.01)^4344 ~ **1.1 x 10^-19**. I ran it: at default noise the
correct key `1011` received **1 of 64 shots** — the *smallest* bin in the histogram,
below the uniform expectation of 4. The output is indistinguishable from uniform.

Consequences:

1. **Objective 5 gets a null result for a structural reason.** Readout mitigation
   cannot recover a signal that gate error has already erased; `mitigation.py` can only
   undo the measurement channel. Experiment C will show mitigation doing essentially
   nothing, and the honest explanation is F3, not a shortcoming of NNLS.
   `readout_only_noise_model` is exactly the right instrument for separating the two,
   and this makes it the most important experiment in the set rather than a side-check.
2. **The dominant cost is the S-box synthesis, and it is avoidable.** Measured directly:
   one `sbox_gate()` costs **93–95 CX** after transpilation to
   `['id','rz','sx','x','cx']` (93 at optimization level 2–3), consistent with the
   generic QSD regime for a 4-qubit unitary — below, but the same order as, the
   (23/48)·4^4 ~ 123 generic bound. Across 2 rounds x 2 (compute + uncompute) x 3 pairs
   x 3 iterations that is ~3,348 CX, i.e. **~77% of all 4,344 CX**. The S-box is a
   *classical bijection*, so it does not need generic unitary synthesis at all: a
   reversible Toffoli network would cost of order tens of CX rather than 93.
   `oracle.py` already flags this ("a hand-optimised Toffoli network would use fewer
   non-Clifford gates"), which is the correct instinct — the measurement above
   quantifies what taking it would buy, which is better than an order of magnitude on
   the circuit's dominant cost.
3. **Recommended framing.** Report the noise sweep rather than a single operating point.
   From the same budget, `p2 = 1e-3` gives (1-p2)^4344 ~ 1.3 x 10^-2, and `p2 = 1e-4`
   ~ 0.65 — so the interesting transition lies between 1e-4 and 1e-3 for this circuit,
   which is where `NoiseParams.scaled` should be swept. Reporting "mitigation did not
   help at p2 = 1e-2" without this context would understate the result; the defensible
   claim is that the crossover is at least an order of magnitude below current
   two-qubit hardware error rates for a circuit of this depth.

### F4 — the missing theoretical result behind Objective 4 *(gap in the literature review)*

Objective 4 asks how noise affects amplitude amplification. The project currently cites
Preskill for "noise exists" and nothing for the sharp, directly-applicable theory, which
is that **constant-rate oracle noise destroys the quadratic speedup outright**. This is
the theoretical statement that explains F3, and it should anchor the noise discussion:

- **Regev & Schiff**, *Impossibility of a Quantum Speed-Up with a Faulty Oracle*,
  ICALP 2008 (LNCS 5125) —
  [publisher](https://link.springer.com/content/pdf/10.1007/978-3-540-70575-8_63.pdf).
  If each oracle call independently fails (applies identity) with constant probability
  p, then any quantum algorithm needs T > sqrt(p/(10(1-p)))·N queries, i.e. **Omega(N)**
  — no speedup at all. *Not on arXiv*, which matters given the arXiv-first verification
  brief; cite the ICALP version.
- **Rosmanis**, *Quantum Search with Noisy Oracle*,
  [arXiv:2309.14944](https://arxiv.org/abs/2309.14944) (2023) — the arXiv-available
  modern form. Complexity Theta~(max{np, sqrt(n)}) under depolarizing oracle noise with
  probability p <= 0.99, with a matching lower bound that holds even under dephasing and
  even if the algorithm is *told* when an error occurred. For constant p this recovers
  the linear bound; the expression interpolates cleanly between classical and quantum
  regimes and is the single best citation for this project's noise story. See also the
  [addendum](https://arxiv.org/abs/2405.11973).
- **Salas**, *Noise effect on Grover algorithm*,
  [arXiv:0801.1261](https://arxiv.org/abs/0801.1261), Eur. Phys. J. D (2008) — the
  closest match to what Experiment B actually does: numerical study under a depolarizing
  channel, finding **exponential damping of the successive probability maxima**, an
  allowed-error threshold scaling as E_th(N) ~ N^-1.1, and an absolute cutoff
  (free-evolution error > 0.043 implies failure regardless of register size). The
  exponential damping law is precisely the (1-p2)^CX behaviour measured in F3.
- **Zhang, Yu & Korepin**, *Quantum search on noisy intermediate-scale quantum devices*,
  [arXiv:2202.00122](https://arxiv.org/abs/2202.00122), EPL 140, 18002 (2022) — NISQ
  benchmarking of quantum search across platforms; useful for positioning "error-aware
  quantum search" as an active direction.
- **Vrana, Reeb, Reitzner & Wolf**, *Fault-ignorant quantum search*,
  [arXiv:1307.0771](https://arxiv.org/abs/1307.0771) — optional; the complementary
  question of searching without knowing the noise rate.

### F5 — Objective 3's speedup claim needs the non-parallelization caveat *(scope)*

The `.docx` presents the quadratic speedup (section 7) without the caveat that makes it
much less threatening in practice: **Grover cannot be parallelized better than by
partitioning the search space across independent machines**, so wall-clock attack cost
does not fall as sqrt(N) given many processors. This is proved in:

- **Zalka**, *Grover's quantum searching algorithm is optimal*,
  [arXiv:quant-ph/9711070](https://arxiv.org/abs/quant-ph/9711070),
  Phys. Rev. A 60, 2746–2751 (1999). Verified: establishes optimality for any success
  probability, and explicitly resolves that "quantum searching cannot be parallelized
  better than by assigning different parts of the search space to independent quantum
  computers."
- **Bennett, Bernstein, Brassard & Vazirani**, *Strengths and Weaknesses of Quantum
  Computing*, [arXiv:quant-ph/9701001](https://arxiv.org/abs/quant-ph/9701001),
  SIAM J. Comput. 26(5):1510–1523 (1997) — the Omega(sqrt(N)) lower bound, i.e. why
  Grover cannot be improved.

Jaques et al. (already cited) make the same practical point for AES and is the natural
bridge from the toy model to real-world assessments. Adding this strengthens the
project's credibility: it shows the quadratic speedup is understood as a query-count
statement, not a claim that AES is nearly broken.

### F6 — `.docx` section 7 complexity table disagrees with the code *(documentation)*

The table lists Grover search cost as 4 / 16 / 256 for 4 / 8 / 16-bit keys. Those are
sqrt(N). The code's `optimal_iterations`, and BBHT, give floor((pi/4)·sqrt(N)) =
**3 / 12 / 201**:

| key bits | N | sqrt(N) (table) | floor((pi/4)·sqrt(N)) (code) |
|---|---|---|---|
| 4 | 16 | 4 | **3** |
| 8 | 256 | 16 | **12** |
| 16 | 65,536 | 256 | **201** |

The table is defensible as an order-of-growth statement (Theta(2^(n/2))), and the code
is right, but as written the table will contradict Experiment A, which measures an
optimum of 3 for the 4-bit case. Either label the column "Theta(2^(n/2)), queries up to
a constant" or give both columns. `grover.py`'s own docstring already makes exactly this
point — "Note this is not sqrt(N): the pi/4 factor matters" — so the two documents are
internally inconsistent rather than the code being wrong.

Related figure worth stating explicitly in the report: the ideal 4-bit success
probability at the optimum is **sin^2(7·arcsin(1/4)) = 0.9613**, not 1.0. Experiment A
should be expected to land near 96.1%, and a result of ~96% is a *success*, not a
shortfall. Over-rotation past 3 iterations then drops it — the effect `grover.py` says
Experiment A measures.

### F7 — `noise.py`'s noiseless-`rz` justification is slightly overstated *(minor)*

> "`rz` is deliberately left noiseless: on transmon hardware it is a virtual frame
> change implemented in software, not a physical pulse."

The mechanism is verified — McKay, Wood, Sheldon, Chow & Gambetta, *Efficient Z-Gates
for Quantum Computing*, [arXiv:1612.00858](https://arxiv.org/abs/1612.00858),
Phys. Rev. A 96, 022330 (2017), establish zero-duration "virtual" Z gates implemented by
adjusting the phase of subsequent drives. But that paper does not claim zero *error*; it
reports low-but-finite error (~1.95 x 10^-4 for its DRAGZ scheme).

The modelling choice is nonetheless sound and matches IBM's own device convention, in
which `rz` carries zero duration and no reported gate error. Recommended wording: keep
the choice, cite McKay et al. for zero duration, and call the noiseless treatment an
idealisation consistent with IBM backend properties — rather than something the paper
asserts. This matters a little more than usual here because `rz` is the *most common*
gate in the transpiled circuit (13,439 of 25,471 gates, 53%), so "noiseless `rz`" is
load-bearing: were it assigned even 1e-4 error, it would contribute comparably to the
4,344 CX at 1e-2. Worth one sentence in the limitations section.

### F8 — closest prior art is uncited *(positioning)*

The project is not currently placed relative to work doing very nearly the same thing.
For a related-work section:

- **Kiran, Safdar, Khalid et al.**, *Quantum cryptanalysis of SPN ciphers with known
  plaintext*, npj Quantum Information (2026),
  [doi:10.1038/s41534-026-01218-x](https://doi.org/10.1038/s41534-026-01218-x).
  The nearest neighbour: quantum circuits for **Mini-AES** (a 16-bit AES variant) built
  from CNOT/Toffoli gates, scaled down to 8 qubits so Grover could be run with
  **end-to-end noise analysis**. Same three-part structure as this project — SPN oracle,
  Grover, noise — which makes it the key comparison, and a useful precedent for F3's
  recommendation to use Toffoli-based rather than generic-unitary synthesis.
  (Paywalled; abstract and reference list are public.)
- **Quantum circuit realization and Grover cryptanalysis of the hybrid ARX-SPN cipher
  GFSPX**, [arXiv:2605.27443](https://arxiv.org/abs/2605.27443) /
  [eprint 2026/949](https://eprint.iacr.org/2026/949) — current-practice resource
  estimation for Grover on a lightweight SPN-family cipher.
- **Demonstration of Grover's algorithm for retrieving secret keys in a basic SPN block
  cipher**, CTU Journal of Innovation and Sustainable Development — Grover key search on
  the toy "Yo-yo" SPN in Qiskit using 17 qubits, from at least one known pair. Directly
  comparable in scale (17 qubits vs this project's 16) and a good sanity check on the
  qubit budget.

---

## 3. Summary

Nothing in the project's cryptography or algorithmics is wrong. The PRESENT S-box is
exact against the CHES 2007 original, the Heys attribution is apt, the Grover iteration
formula matches BBHT exactly in this regime, the multi-pair oracle rationale is correct
and correctly credited to Grassl and Jaques, and the 8 GB memory claim holds empirically
with three orders of magnitude of headroom. All ten citations are real and correctly
attributed.

Two citation claims need repair (**F1**, M3 does not use NNLS; **F2**, Nachman et al.
argue against least squares, not just against `pinv`), and one documentation table
disagrees with the code (**F6**).

The substantive finding is **F3**: at 4,344 CX and the default `p2 = 1e-2`, the
circuit's survival probability is ~10^-19 and the measured output is uniform — so
Experiment C's null result is structural, ~77% of the gate cost comes from synthesising
a *classical* S-box as a generic unitary, and the informative experiment is a noise
sweep between 1e-4 and 1e-3 plus the gate-vs-readout split that
`readout_only_noise_model` already enables. **F4** supplies the theory that explains
this — Regev & Schiff (ICALP 2008) and Rosmanis
([arXiv:2309.14944](https://arxiv.org/abs/2309.14944)) on the loss of speedup under
constant oracle noise, and Salas ([arXiv:0801.1261](https://arxiv.org/abs/0801.1261)) on
exponential damping — and is the most valuable addition to the write-up.

---

## 4. Disposition

Recorded after the findings above were reviewed against the implementation.

| Finding | Action taken |
|---|---|
| **F1** — NNLS misattributed to M3 | **Fixed.** `mitigation.py`, `report.tex` and `REPORT.md` now state that M3 is matrix-free and shares NNLS's *goal*, not its mechanism. Nation et al. is cited only for the `2ⁿ` calibration-scaling point. |
| **F2** — Nachman et al. also argue against least squares | **Fixed.** The claim "physically correct formulation" is withdrawn in favour of the narrower, supportable claim that NNLS always returns a valid distribution whereas `pinv` does not. Nachman et al.'s preference for iterative Bayesian unfolding is now stated explicitly, and IBU is listed as the natural next comparison. |
| **F3** — noise defaults destroy the signal | **Already addressed, and now measured.** Experiment C runs three noise models (readout-only, gate error ×0.03, full) so the readout/gate boundary is measured rather than assumed; Experiment D sweeps the rate to locate the threshold. The complete-destruction result is reported as the finding it is, not tuned away. |
| **F4** — theoretical result behind Objective 4 | **Not incorporated.** Left for a future revision; the noise behaviour is reported empirically. |
| **F5** — non-parallelization caveat | **Fixed.** A dedicated paragraph in the Discussion (`report.tex`) and a matching section in `REPORT.md` now state that Grover cannot be parallelised better than by partitioning the search space (Zalka 1999), so `k*` is a sequential depth rather than a cost that more hardware can spend down. arXiv identifiers added to both `zalka1999` and `bennett1997`. |
| **F6** — `.docx` §7 table gives √N | **Fixed at the source of truth.** The code and report have always used `⌊(π/4)√(N/M)⌋`. `docs/original-brief.md` now flags §7 as **[REVISED]** with the correct formula, and the report states the 4-bit optimum of 3 iterations and the `0.9613` peak explicitly. |
| **F7** — noiseless `rz` overstated | **Fixed.** `noise.py`, `report.tex` and `REPORT.md` now cite McKay et al. (2017) for *zero duration*, call the noiseless treatment an idealisation consistent with IBM backend properties, and note that `rz` is roughly half of all transpiled gates so the assumption is load-bearing. Added to the limitations, with the observation that it makes the noise model optimistic and therefore strengthens the negative result. |
| **F8** — closest prior art uncited | **Deliberately not incorporated.** The three suggested works are dated 2026 and could not be verified against a primary source from within this environment. Citing unverified references would be a worse defect than omitting them. They are recorded here as leads for a related-work section, to be confirmed before use. |

**Net effect on conclusions:** none of the corrections change a measured result.
F1, F2 and F7 tighten attribution and remove three overclaims; F5 adds a caveat
that makes the complexity analysis more conservative, not less. The experimental
findings in `results/` stand as recorded.
