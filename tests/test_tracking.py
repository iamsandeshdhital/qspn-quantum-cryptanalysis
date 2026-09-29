"""Tests for experiment tracking and versioning."""

from __future__ import annotations

import json

from qspn.noise import NoiseParams
from qspn.runner import RunConfig
from qspn.spn import SPNParams
from qspn.tracking import ExperimentRecord, ExperimentTracker, track_experiment


class TestExperimentRecord:
    """Tests for ExperimentRecord."""

    def test_create_record(self):
        record = ExperimentRecord(
            name="test_experiment",
            results={"p_success": 0.96},
        )
        assert record.name == "test_experiment"
        assert record.results["p_success"] == 0.96
        assert record.timestamp != ""

    def test_record_id_is_unique(self):
        record1 = ExperimentRecord(name="test", results={})
        record2 = ExperimentRecord(name="test", results={})
        # Different timestamps should produce different IDs
        assert record1.record_id != record2.record_id()

    def test_save_and_load(self, tmp_path):
        record = ExperimentRecord(
            name="test",
            results={"p_success": 0.96},
            tags=["baseline"],
        )
        path = tmp_path / "record.json"
        record.save(path)

        loaded = ExperimentRecord.load(path)
        assert loaded.name == record.name
        assert loaded.results == record.results
        assert loaded.tags == record.tags


class TestExperimentTracker:
    """Tests for ExperimentTracker."""

    def test_record_experiment(self, tmp_path):
        tracker = ExperimentTracker(tmp_path)
        config = RunConfig(shots=1024)
        noise = NoiseParams()
        params = SPNParams()

        record = tracker.record(
            "test_experiment",
            results={"p_success": 0.96},
            config=config,
            noise_params=noise,
            spn_params=params,
            tags=["baseline"],
        )

        assert record.name == "test_experiment"
        assert len(tracker.records) == 1

    def test_get_history(self, tmp_path):
        tracker = ExperimentTracker(tmp_path)
        tracker.record("exp1", {"p_success": 0.96})
        tracker.record("exp2", {"p_success": 0.85})
        tracker.record("exp1", {"p_success": 0.97})

        all_records = tracker.get_history()
        assert len(all_records) == 3

        exp1_records = tracker.get_history("exp1")
        assert len(exp1_records) == 2

    def test_compare_records(self, tmp_path):
        tracker = ExperimentTracker(tmp_path)
        record1 = tracker.record("exp", {"p_success": 0.96}, config=RunConfig(shots=1024))
        record2 = tracker.record("exp", {"p_success": 0.85}, config=RunConfig(shots=2048))

        comparison = tracker.compare(record1, record2)
        assert "config_diff" in comparison
        assert "results_diff" in comparison

    def test_generate_report(self, tmp_path):
        tracker = ExperimentTracker(tmp_path)
        tracker.record("exp1", {"p_success": 0.96})
        tracker.record("exp2", {"p_success": 0.85})

        report_path = tmp_path / "report.html"
        tracker.generate_report(report_path)

        assert report_path.exists()
        content = report_path.read_text()
        assert "QSPN Experiment Report" in content

    def test_export_csv(self, tmp_path):
        tracker = ExperimentTracker(tmp_path)
        tracker.record("exp1", {"p_success": 0.96}, tags=["baseline"])

        csv_path = tmp_path / "experiments.csv"
        tracker.export_csv(csv_path)

        assert csv_path.exists()
        content = csv_path.read_text()
        assert "exp1" in content


class TestTrackExperiment:
    """Tests for the track_experiment convenience function."""

    def test_track_single_experiment(self, tmp_path):
        record = track_experiment(
            "test",
            {"p_success": 0.96},
            storage_dir=tmp_path,
        )
        assert record.name == "test"
        assert record.results["p_success"] == 0.96
