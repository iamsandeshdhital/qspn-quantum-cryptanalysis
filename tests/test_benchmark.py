"""Tests for the benchmarking suite."""

from __future__ import annotations

from qspn.benchmark import QuantumBenchmark, run_standard_benchmark_suite
from qspn.runner import RunConfig


class TestQuantumBenchmark:
    """Tests for the benchmark suite."""

    def test_benchmark_initialization(self):
        config = RunConfig(shots=1024)
        benchmark = QuantumBenchmark(config)
        assert benchmark.config.shots == 1024

    def test_run_all_benchmarks(self):
        config = RunConfig(shots=1024)
        benchmark = QuantumBenchmark(config)
        results = benchmark.run_all(backend=None)
        assert len(results) > 0

    def test_benchmark_result_structure(self):
        config = RunConfig(shots=1024)
        benchmark = QuantumBenchmark(config)
        result = benchmark.benchmark_single_qubit_gate_fidelity()
        assert result.name == "single_qubit_gate_fidelity"
        assert "metrics" in result.__dict__

    def test_save_results(self, tmp_path):
        import json
        from dataclasses import asdict

        config = RunConfig(shots=1024)
        benchmark = QuantumBenchmark(config)
        results = benchmark.run_all(backend=None)

        output_file = tmp_path / "results.json"
        benchmark.save_results(results, str(output_file))

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert len(data) > 0


class TestRunStandardBenchmarkSuite:
    """Tests for the standard benchmark suite entry point."""

    def test_run_suite(self):
        config = RunConfig(shots=1024)
        report = run_standard_benchmark_suite(backend=None, config=config)
        assert "backend" in report
        assert "num_benchmarks" in report
        assert "benchmarks" in report

    def test_report_structure(self):
        config = RunConfig(shots=1024)
        report = run_standard_benchmark_suite(backend=None, config=config)
        assert report["num_benchmarks"] == len(report["benchmarks"])
        for benchmark in report["benchmarks"]:
            assert "name" in benchmark
            assert "metrics" in benchmark
