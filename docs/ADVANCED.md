# Advanced Usage Guide

This guide covers advanced features of the QSPN project for quantum computing
labs, companies, and universities.

## Table of Contents

1. [Advanced Error Mitigation](#advanced-error-mitigation)
2. [Benchmarking Suite](#benchmarking-suite)
3. [REST API](#rest-api)
4. [Docker Deployment](#docker-deployment)
5. [Hardware Integration](#hardware-integration)
6. [Custom Experiments](#custom-experiments)
7. [Continuous Integration](#continuous-integration)

---

## Advanced Error Mitigation

The project implements state-of-the-art error mitigation techniques:

### Zero-Noise Extrapolation (ZNE)

```python
from qspn.mitigation import zne_extrapolate

# Run circuit at multiple noise levels
scale_factors = [1.0, 2.0, 3.0]
noisy_values = [0.85, 0.72, 0.61]  # measured at each scale

result = zne_extrapolate(scale_factors, noisy_values, method="richardson")
print(f"Zero-noise estimate: {result['zero_noise_estimate']}")
```

### Probabilistic Error Cancellation (PEC)

```python
from qspn.mitigation import pec_mitigate

result = pec_mitigate(
    ideal_distribution=ideal_dist,
    noise_model=noise_model,
    num_samples=10000,
)
```

### Clifford Data Regression (CDR)

```python
from qspn.mitigation import cdr_mitigate

# Train on Clifford circuit data
clifford_data = [(noisy_1, ideal_1), (noisy_2, ideal_2), ...]
result = cdr_mitigate(noisy_distribution, clifford_data)
```

### Unified Mitigation Pipeline

```python
from qspn.mitigation import MitigationPipeline

pipeline = MitigationPipeline()
pipeline.add_readout_mitigation(assignment_matrix)
pipeline.add_zne(scale_factors, noisy_values)
results = pipeline.apply(counts, num_qubits=4)
```

---

## Benchmarking Suite

Run standardized benchmarks for device characterization:

```bash
# Run all benchmarks on simulator
python scripts/run_benchmark.py

# Run on real IBM Quantum hardware
python scripts/run_benchmark.py --backend ibmq_quito

# Save results
python scripts/run_benchmark.py --output benchmark_results.json
```

### Available Benchmarks

| Benchmark | Description |
|-----------|-------------|
| `single_qubit_gate_fidelity` | RB-based single-qubit gate fidelity |
| `two_qubit_gate_fidelity` | Interleaved RB for CX gates |
| `readout_fidelity` | Assignment matrix characterization |
| `coherence_times` | T1 and T2 measurement |
| `grover_search` | Grover algorithm performance |
| `quantum_volume` | Quantum volume measurement |

### Programmatic Usage

```python
from qspn.benchmark import QuantumBenchmark

benchmark = QuantumBenchmark()
results = benchmark.run_all(backend="ibmq_quito")
benchmark.save_results(results, "results.json")
```

---

## REST API

The project includes a FastAPI-based REST API for remote access:

### Start the API server

```bash
# Using uvicorn directly
uvicorn qspn.api:app --host 0.0.0.0 --port 8000

# Using Docker
docker-compose up qspn-api
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/run/{experiment}` | POST | Run single experiment |
| `/run/all` | POST | Run all experiments |
| `/noise/validate` | GET | Validate noise model |
| `/mitigation/methods` | GET | List mitigation methods |

### Example Request

```bash
curl -X POST "http://localhost:8000/run/a" \
  -H "Content-Type: application/json" \
  -d '{
    "experiment": "a",
    "shots": 4096,
    "seed": 20260902,
    "key_bits": 4
  }'
```

### Interactive Documentation

Once the server is running, visit:
- `http://localhost:8000/docs` for Swagger UI
- `http://localhost:8000/redoc` for ReDoc

---

## Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t qspn .

# Run experiments
docker run -v $(pwd)/results:/app/results qspn -m qspn.cli --quick

# Run API server
docker run -p 8000:8000 qspn -m uvicorn qspn.api:app --host 0.0.0.0

# Run Jupyter notebook
docker run -p 8888:8888 qspn jupyter notebook --ip=0.0.0.0 --no-browser
```

### Docker Compose

```bash
# Run all services
docker-compose up

# Run specific service
docker-compose up qspn-api
docker-compose up qspn-jupyter
```

---

## Hardware Integration

### IBM Quantum

```python
from qiskit_ibm_runtime import QiskitRuntimeService
from qspn.hardware import validate_against_hardware
from qspn.noise import NoiseParams

service = QiskitRuntimeService()
backend = service.backend("ibmq_quito")

# Validate simulation against hardware
report = validate_against_hardware(
    noise_params=NoiseParams(),
    backend=backend,
    num_qubits=4,
)
```

### AWS Braket

```python
from braket.aws import AwsDevice
from qspn.hardware import characterize_readout

device = AwsDevice("arn:aws:braket:us-east-1::device/qpu/ionq/Harmony")
# Use hardware characterization functions
```

### Google Quantum AI

```python
import cirq
from qspn.hardware import run_on_hardware

# Convert Qiskit circuit to Cirq and run
```

---

## Custom Experiments

### Creating a Custom Experiment

```python
from qspn.experiments import Instance, RunConfig
from qspn.runner import run_counts, transpile_for
from qspn.grover import grover_circuit

# Build a custom instance
instance = Instance.build(secret_key=0b1010, params=SPNParams(key_bits=5, rounds=3))

# Create a custom circuit
circuit = grover_circuit(instance.pairs, iterations=5, params=instance.params)

# Run with custom noise
config = RunConfig(shots=8192, seed=42)
transpiled = transpile_for(circuit, config)
counts = run_counts(transpiled, noise_params=config, already_transpiled=True)
```

### Adding a New Mitigation Method

```python
from qspn.mitigation import MitigationPipeline

class MyMitigation:
    def mitigate(self, distribution):
        # Your mitigation logic here
        return mitigated_distribution

# Add to pipeline
pipeline = MitigationPipeline()
# ... configure and run
```

---

## Continuous Integration

### GitHub Actions

The project includes a CI workflow (`.github/workflows/ci.yml`) that:
- Runs tests on Python 3.10 and 3.12
- Performs smoke tests of the CLI
- Validates report generation

### Adding Custom CI Steps

```yaml
- name: Run validation
  run: python scripts/run_validation.py

- name: Run benchmarks
  run: python scripts/run_benchmark.py --output benchmark_results.json

- name: Upload benchmark results
  uses: actions/upload-artifact@v4
  with:
    name: benchmark-results
    path: benchmark_results.json
```

---

## Best Practices

### For Quantum Computing Labs

1. **Characterize your device regularly** using the benchmark suite
2. **Validate simulation against hardware** before running large experiments
3. **Track drift** by running benchmarks at regular intervals
4. **Use version control** for all experiment configurations

### For Companies

1. **Deploy the API** for multi-user access to quantum resources
2. **Integrate with existing infrastructure** using the REST API
3. **Monitor device performance** with automated benchmarking
4. **Compare vendors** using standardized benchmarks

### For Universities

1. **Use Docker** for consistent environments across student machines
2. **Start with the Jupyter notebooks** for interactive learning
3. **Run the validation suite** to understand error mitigation
4. **Extend with custom experiments** for research projects

---

## Support

- **Documentation**: See `README.md` and `docs/VALIDATION.md`
- **Issues**: GitHub Issues for bug reports and feature requests
- **API Docs**: Run the API server and visit `/docs`
