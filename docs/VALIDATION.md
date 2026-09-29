# Validation and Verification

This document describes the validation framework for the QSPN project,
including noise model validation, oracle verification, and hardware
characterization.

## Overview

The QSPN project includes a comprehensive validation framework to ensure
correctness and reproducibility:

1. **Oracle Equivalence**: Verifies the quantum oracle matches classical
   encryption for all keys in the key space.
2. **Noise Model Validation**: Ensures the simulated noise model produces
   physically meaningful results.
3. **Mitigation Bounds**: Validates that error mitigation produces valid
   probability distributions.
4. **Statistical Significance**: Checks that reported results are
   statistically significant.
5. **Reproducibility**: Verifies that experiments produce consistent
   results across multiple runs.

## Running Validation

### Quick validation

```bash
python scripts/run_validation.py
```

### Verbose validation with details

```bash
python scripts/run_validation.py --verbose
```

### Save validation report

```bash
python scripts/run_validation.py --output validation_report.json
```

## Noise Model Validation

The noise model is validated against several criteria:

### Error rates are physical

All error rates must be valid probabilities in [0, 1]. The `NoiseParams`
class enforces this in `__post_init__`.

### Noise produces different results

The noise model must produce different output distributions from the
ideal (noiseless) case. This is verified by comparing ideal and noisy
output distributions.

### Noise increases monotonically

Higher error rates should generally produce flatter (higher entropy)
output distributions. This is verified by comparing low-noise and
high-noise results.

## Oracle Equivalence

The quantum oracle is verified against the classical reference
implementation for every key in the key space:

```python
from qspn.validation import verify_oracle_equivalence

result = verify_oracle_equivalence()
print(f"Oracle verified: {result['passed']}")
print(f"Tested keys: {result['tested_keys']}")
```

## Mitigation Bounds

Error mitigation is validated to ensure:

1. **Valid distributions**: Mitigated distributions are valid probability
   distributions (non-negative, sum to 1).
2. **Bounded negative mass**: The `pinv` method may produce negative
   probabilities, but the total negative mass is bounded.
3. **Improvement**: Mitigation should not make results worse than the
   raw (unmitigated) distribution.

## Hardware Validation

The simulated noise model can be validated against real IBM Quantum
hardware:

```bash
python scripts/validate_hardware.py --backend ibmq_quito --qubits 4
```

This script:

1. Connects to IBM Quantum
2. Characterizes the readout error on the specified backend
3. Compares against the simulated noise model
4. Outputs a validation report

### Hardware characterization metrics

The hardware characterization measures:

- **T1/T2**: Thermal relaxation times
- **Gate errors**: Per-gate error rates
- **Readout errors**: Measurement error rates
- **Crosstalk**: Correlated errors on coupled qubits

## Statistical Significance

All reported probabilities include binomial standard errors. Results
are only claimed as significant if they exceed the baseline by more than
2 sigma:

```python
from qspn.validation import validate_statistical_significance

result = validate_statistical_significance(
    p_success=0.96,
    shots=4096,
    baseline=0.0625,  # 1/16 for 4-bit key
)
print(f"Significant: {result['significant']}")
print(f"Sigma: {result['sigma']:.1f}")
```

## Reproducibility

Experiments are designed to be reproducible:

- All runs are seeded (`--seed` parameter)
- Every JSON record includes a provenance block
- Full output distributions are saved, not just summary scalars
- The `results/` directory is committed to git

To verify reproducibility:

```python
from qspn.validation import validate_reproducibility

result = validate_reproducibility(
    experiment_func=lambda: experiment_a_ideal(),
    n_runs=3,
)
print(f"Reproducible: {result['reproducible']}")
```

## Continuous Integration

The CI workflow (`.github/workflows/ci.yml`) runs the test suite
on every push and pull request. The test suite includes:

- Unit tests for all modules
- Integration tests for the full pipeline
- Smoke tests for the CLI

## Known Limitations

1. **Simulated noise is simplified**: The noise model does not capture
   all error channels present on real hardware (e.g., leakage,
   crosstalk, drift).
2. **Toy scale**: The 4-bit key space is too small to validate
   scalability to real-world key sizes.
3. **No real hardware validation by default**: Hardware validation
   requires IBM Quantum credentials and is not run in CI.

## Future Work

- [ ] Add randomized benchmarking validation
- [ ] Add T1/T2 measurement scripts
- [ ] Add crosstalk detection circuits
- [ ] Validate against multiple hardware backends
- [ ] Add drift characterization over long runs
