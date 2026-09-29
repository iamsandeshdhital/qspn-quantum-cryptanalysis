#!/usr/bin/env python3
"""Script to track and manage quantum computing experiments.

Usage:
    python scripts/track_experiments.py --list
    python scripts/track_experiments.py --report
    python scripts/track_experiments.py --compare ID1 ID2

This script provides a command-line interface for the experiment tracking system.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qspn.tracking import ExperimentTracker


def main():
    parser = argparse.ArgumentParser(
        description="Track and manage quantum computing experiments"
    )
    parser.add_argument(
        "--storage",
        default="experiments/",
        help="Storage directory for experiment records",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all tracked experiments",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate HTML report",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("ID1", "ID2"),
        help="Compare two experiment records",
    )
    parser.add_argument(
        "--export-csv",
        type=Path,
        default=None,
        help="Export experiment history to CSV",
    )
    args = parser.parse_args()

    tracker = ExperimentTracker(args.storage)

    # Load existing records
    storage_dir = Path(args.storage)
    if storage_dir.exists():
        for file in storage_dir.glob("*.json"):
            record = ExperimentRecord.load(file)
            tracker.records.append(record)

    if args.list:
        print(f"Tracked experiments: {len(tracker.records)}")
        print()
        for record in tracker.records:
            print(f"  {record.record_id} | {record.name} | {record.timestamp}")
            if record.tags:
                print(f"    Tags: {', '.join(record.tags)}")

    elif args.report:
        output_path = Path(args.storage) / "report.html"
        tracker.generate_report(output_path)
        print(f"Report saved to {output_path}")

    elif args.compare:
        id1, id2 = args.compare
        record1 = next((r for r in tracker.records if r.record_id.startswith(id1)), None)
        record2 = next((r for r in tracker.records if r.record_id.startswith(id2)), None)

        if record1 is None or record2 is None:
            print("Error: Could not find one or both records")
            return 1

        comparison = tracker.compare(record1, record2)
        print("Comparison Report:")
        print("=" * 60)
        print(f"Record A: {comparison['record_a']['name']} ({comparison['record_a']['id']})")
        print(f"Record B: {comparison['record_b']['name']} ({comparison['record_b']['id']})")
        print()
        print("Configuration differences:")
        for key, diff in comparison["config_diff"].items():
            print(f"  {key}: {diff}")

    elif args.export_csv:
        tracker.export_csv(args.export_csv)
        print(f"CSV exported to {args.export_csv}")

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
