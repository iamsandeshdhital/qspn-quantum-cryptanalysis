# Original Project Brief (verbatim)

> Converted from `Quantum_Cryptanalysis_Documentation.docx` so the specification
> is diffable and has version history. This is the **brief as written**, not the
> project as built.
>
> Three points in this document were revised during implementation. They are
> flagged inline as **[REVISED]** and discussed in `docs/REPORT.md`:
>
> 1. **Section 5.2, the oracle**, as specified is circular: `f(K) = 1 if K = K*`
>    presupposes the secret key. The implemented oracle instead evaluates
>    `E_K(P)` on the key register in superposition and compares against known
>    ciphertexts. See `docs/REPORT.md` section 4.
> 2. **Section 7, the Grover iteration count**, is given as `sqrt(N)`. The
>    correct value is `floor((pi/4) * sqrt(N/M))` -- 3 rather than 4 at
>    `N = 16` -- and the success probability *decreases* past that point. See
>    `docs/REPORT.md` section 5.
> 3. **Section 11, the memory claim**, states that shot-based sampling avoids
>    storing the statevector. Aer maintains a statevector either way; what
>    trajectory sampling avoids is the **density matrix**, an `O(4^n)` to
>    `O(2^n)` saving. See `docs/REPORT.md` section 10.

---

## Document header

```
PROJECT DOCUMENTATION
Quantum Cryptanalysis & Error Mitigation
Project Title:
Complexity and Noise-Resilience of Quantum Oracles for Symmetric Cryptanalysis
```


## 1. Abstract & Research Alignment

This project investigates the computational complexity, implementation cost, and noise resilience of quantum oracles used for symmetric-key cryptanalysis. The study uses a simplified 4-bit Substitution-Permutation Network (SPN) as a controlled cryptographic model for examining how quantum search can be applied to a classical encryption problem.
A reversible quantum oracle is constructed to represent the encryption function and identify the correct cryptographic key. Grover's search algorithm is then employed to amplify the probability of measuring the correct key, demonstrating the theoretical quadratic speedup of quantum search over classical exhaustive search.
Because current Noisy Intermediate-Scale Quantum (NISQ) devices are affected by gate, measurement, and environmental errors, the project additionally evaluates Grover's algorithm under simulated hardware noise. In particular, depolarizing noise and readout errors are introduced using Qiskit Aer to investigate their effects on the probability distribution of the candidate keys.
To improve the reliability of the measured results, the project implements classical Readout Error Mitigation (REM). Calibration circuits are used to characterize measurement errors and construct an assignment matrix. The inverse of this matrix is subsequently applied to the observed measurement distribution to estimate a distribution closer to the ideal result.
The project therefore combines three interconnected areas:
Quantum algorithms — Grover's search
Quantum cryptography/cryptanalysis — reversible cryptographic oracles
NISQ computing — noise modeling and error mitigation
The work is also aligned with energy-efficient software development, as the simulation is designed to operate within the constraints of an 8 GB RAM computing environment without relying on full statevector simulation for the noisy experiments.

## 2. Research Objectives

The project has the following objectives:
- **Objective 1** — Quantum Cryptanalytic Oracle: Design and implement a reversible quantum oracle representing a simplified symmetric cipher and capable of identifying a target cryptographic key.
- **Objective 2** — Grover Search: Implement Grover's algorithm to demonstrate quantum amplitude amplification for searching the 4-bit key space.
- **Objective 3** — Complexity Analysis: Compare the computational search complexity of classical exhaustive search with quantum Grover search.
- **Objective 4** — NISQ Noise Analysis: Investigate how realistic noise affects Grover's amplitude amplification and the probability of recovering the correct key.
- **Objective 5** — Error Mitigation: Apply classical readout-error mitigation to determine whether measurement-error correction can improve the probability of identifying the correct key.
- **Objective 6** — Resource Efficiency: Develop an implementation capable of performing noisy quantum simulations within an 8 GB RAM environment, reducing unnecessary memory consumption and computational overhead.

## 3. Theoretical Framework


### 3.1 Symmetric Cryptanalysis

Symmetric cryptography uses the same secret key for encryption and decryption. In a simplified key-search problem, an attacker is given a known plaintext P, a corresponding ciphertext C, and an unknown key K. The objective is to determine K* = arg_find_K E_K(P) = C, where E_K represents encryption using candidate key K.
For a small n-bit key, a classical attacker can test every possible key. The search space therefore contains 2^n possible candidates. Although a 4-bit key is intentionally small and not cryptographically secure, it provides a manageable experimental environment for studying the behavior of a quantum cryptanalytic oracle.

## 4. Simplified 4-bit SPN Cipher

The project uses a simplified Substitution-Permutation Network (SPN) to represent a classical symmetric cipher. The SPN consists conceptually of key addition, substitution through an S-box, bit permutation, and additional key-dependent transformation.
The simplified structure allows the classical encryption function to be converted into a reversible quantum circuit. The small 4-bit configuration is deliberately chosen because it enables the complete experiment to be simulated efficiently while retaining the essential properties required to study reversible computation, oracle construction, amplitude amplification, noise, measurement, and error mitigation.

## 5. Reversible Quantum Oracle


### 5.1 Why Reversibility Is Required

Quantum operations must be unitary and therefore reversible. A conventional classical function f(x) cannot simply be inserted into a quantum circuit if it destroys information. Instead, the function is embedded into a reversible transformation U_f |x> |y> = |x> |y ⊕ f(x)>, where ⊕ represents bitwise XOR.

### 5.2 Cryptographic Oracle  **[REVISED]**

For the key-search problem, the oracle evaluates candidate keys and identifies the key satisfying the known plaintext-ciphertext relationship. The oracle can conceptually be represented as O_f |K> = (-1)^{f(K)} |K>, where f(K) = 1 if K = K*, and 0 otherwise. Thus, the correct key state receives a phase inversion while the other candidate states remain unchanged, allowing Grover's diffusion operator to amplify the amplitude of the correct key.

## 6. Grover's Search Algorithm

The quantum search begins by preparing the key register in an equal superposition |s> = (1/sqrt(N)) sum_{x=0}^{N-1} |x>. For a 4-bit key, N = 16. The algorithm repeatedly applies the oracle and diffusion operators (G = D O). After an appropriate number of iterations, the probability of measuring the target key becomes significantly larger than incorrect candidates.

## 7. Complexity Analysis  **[REVISED]**

The project evaluates the difference between classical exhaustive search (O(2^n)) and quantum search (O(2^{n/2})). This represents a quadratic reduction in query complexity.
Key Size
Classical Search
Grover Search
4 bits
2^4 = 16
≈ 4
8 bits
2^8 = 256
≈ 16
16 bits
2^{16} = 65,536
≈ 256


## 8. NISQ Noise Model

Real quantum processors do not execute quantum gates perfectly. Errors arise from imperfect control, environmental interactions, decoherence, gate imperfections, and measurement processes. This project introduces simulated noise using Qiskit Aer, specifically focusing on depolarizing noise and readout errors.

## 9. Readout Error & Mitigation

Quantum measurements can introduce errors (e.g., |0> flipping to 1 or |1> flipping to 0). To address this, the project implements classical Readout Error Mitigation (REM). Calibration circuits construct an assignment matrix A_ij = P(measured i | prepared j). The inverse of this matrix is applied to the observed measurement distribution to estimate the true mitigated distribution.

## 10. Experimental Design

The experiment is divided into three principal stages:
- **Experiment A** — Ideal Simulation: Executed without noise to verify oracle correctness and establish baseline probability.
- **Experiment B** — Noisy Simulation: Executed using depolarizing and readout noise models to measure degradation.
- **Experiment C** — Error-Mitigation Experiment: Processed using readout-error calibration to estimate underlying probabilities.

## 11. Resource Optimization & Green IT  **[REVISED]**

To operate within an 8 GB RAM commodity computing environment, the project uses qiskit_aer.AerSimulator with shot-based sampling (4096 shots). This avoids storing the complete 2^N-amplitude statevector as an output representation, connecting quantum computing research with sustainable software engineering principles.

## 12. Research Significance & Future Work

The project establishes an experimental pipeline connecting Classical Cryptography → Reversible Oracle → Grover Search → NISQ Noise → Error Mitigation. Future work includes scaling to larger key spaces, exploring advanced error mitigation like Zero-Noise Extrapolation (ZNE), and extending simulations to Quantum-HPC hybrid environments.
