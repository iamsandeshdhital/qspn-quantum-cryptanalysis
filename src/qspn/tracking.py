"""Experiment tracking and versioning for quantum computing research.

Provides tools for:
* Tracking experiment configurations and results
* Comparing results across runs
* Versioning noise models and parameters
* Generating reproducibility reports

Designed for:
* Quantum computing labs: track device performance over time
* Companies: compare results across teams and hardware
* Universities: ensure reproducibility of research results
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .noise import NoiseParams
from .runner import RunConfig
from .spn import SPNParams


@dataclass
class ExperimentRecord:
    """A single experiment record with full provenance.

    Attributes
    ----------
    name:
        Experiment name.
    timestamp:
        When the experiment was run.
    config:
        Run configuration.
    noise_params:
        Noise parameters used.
    spn_params:
        SPN cipher parameters.
    results:
        Experiment results.
    environment:
        Software and hardware environment.
    tags:
        User-defined tags for filtering.
    """

    name: str
    timestamp: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    noise_params: dict[str, Any] = field(default_factory=dict)
    spn_params: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def record_id(self) -> str:
        """Unique identifier for this record."""
        data = f"{self.name}:{self.timestamp}:{json.dumps(self.config, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        """Save record to JSON file."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str))

    @classmethod
    def load(cls, path: str | Path) -> "ExperimentRecord":
        """Load record from JSON file."""
        data = json.loads(Path(path).read_text())
        return cls(**data)


class ExperimentTracker:
    """Track and manage quantum computing experiments.

    Example
    -------
    >>> tracker = ExperimentTracker("experiments/")
    >>> tracker.record("experiment_a", results, tags=["baseline"])
    >>> history = tracker.get_history("experiment_a")
    >>> tracker.generate_report("report.html")
    """

    def __init__(self, storage_dir: str | Path = "experiments/"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[ExperimentRecord] = []

    def record(
        self,
        name: str,
        results: dict[str, Any],
        config: RunConfig | None = None,
        noise_params: NoiseParams | None = None,
        spn_params: SPNParams | None = None,
        tags: list[str] | None = None,
    ) -> ExperimentRecord:
        """Record a new experiment.

        Parameters
        ----------
        name:
            Experiment name.
        results:
            Experiment results.
        config:
            Run configuration.
        noise_params:
            Noise parameters.
        spn_params:
            SPN parameters.
        tags:
            User-defined tags.

        Returns
        -------
        ExperimentRecord
        """
        import platform
        import sys

        record = ExperimentRecord(
            name=name,
            config=asdict(config) if config else {},
            noise_params=asdict(noise_params) if noise_params else {},
            spn_params=asdict(spn_params) if spn_params else {},
            results=results,
            environment={
                "python": sys.version,
                "platform": platform.platform(),
                "timestamp": datetime.now().isoformat(),
            },
            tags=tags or [],
        )

        self.records.append(record)

        # Save to disk
        filename = f"{record.record_id}.json"
        record.save(self.storage_dir / filename)

        return record

    def get_history(self, name: str | None = None) -> list[ExperimentRecord]:
        """Get experiment history, optionally filtered by name."""
        if name is None:
            return self.records
        return [r for r in self.records if r.name == name]

    def compare(self, record_a: ExperimentRecord, record_b: ExperimentRecord) -> dict[str, Any]:
        """Compare two experiment records.

        Returns a comparison report showing differences in configuration
        and results.
        """
        return {
            "record_a": {
                "id": record_a.record_id,
                "name": record_a.name,
                "timestamp": record_a.timestamp,
            },
            "record_b": {
                "id": record_b.record_id,
                "name": record_b.name,
                "timestamp": record_b.timestamp,
            },
            "config_diff": self._dict_diff(record_a.config, record_b.config),
            "noise_diff": self._dict_diff(record_a.noise_params, record_b.noise_params),
            "results_diff": self._dict_diff(record_a.results, record_b.results),
        }

    def _dict_diff(self, a: dict, b: dict) -> dict[str, Any]:
        """Compute differences between two dictionaries."""
        diff = {}
        all_keys = set(a.keys()) | set(b.keys())
        for key in all_keys:
            if key not in a:
                diff[key] = {"status": "added", "value": b[key]}
            elif key not in b:
                diff[key] = {"status": "removed", "value": a[key]}
            elif a[key] != b[key]:
                diff[key] = {"status": "changed", "old": a[key], "new": b[key]}
        return diff

    def generate_report(self, output_path: str | Path) -> None:
        """Generate an HTML report of all tracked experiments.

        Parameters
        ----------
        output_path:
            Path to save the HTML report.
        """
        html = self._generate_html_report()
        Path(output_path).write_text(html)

    def _generate_html_report(self) -> str:
        """Generate HTML report content."""
        records_html = ""
        for record in self.records:
            records_html += f"""
            <div class="record">
                <h3>{record.name}</h3>
                <p><strong>ID:</strong> {record.record_id}</p>
                <p><strong>Timestamp:</strong> {record.timestamp}</p>
                <p><strong>Tags:</strong> {', '.join(record.tags)}</p>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>QSPN Experiment Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .record {{ border: 1px solid #ccc; padding: 20px; margin: 20px 0; border-radius: 5px; }}
        h1 {{ color: #333; }}
        h3 {{ color: #666; }}
    </style>
</head>
<body>
    <h1>QSPN Experiment Report</h1>
    <p>Generated: {datetime.now().isoformat()}</p>
    <p>Total experiments: {len(self.records)}</p>
    {records_html}
</body>
</html>
"""

    def export_csv(self, output_path: str | Path) -> None:
        """Export experiment history to CSV."""
        import csv

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "timestamp", "tags"])
            for record in self.records:
                writer.writerow([
                    record.record_id,
                    record.name,
                    record.timestamp,
                    ",".join(record.tags),
                ])


def track_experiment(
    name: str,
    results: dict[str, Any],
    storage_dir: str | Path = "experiments/",
    **kwargs,
) -> ExperimentRecord:
    """Convenience function to track a single experiment.

    Parameters
    ----------
    name:
        Experiment name.
    results:
        Experiment results.
    storage_dir:
        Directory to store records.
    **kwargs:
        Additional arguments passed to ExperimentTracker.record().

    Returns
    -------
    ExperimentRecord
    """
    tracker = ExperimentTracker(storage_dir)
    return tracker.record(name, results, **kwargs)
