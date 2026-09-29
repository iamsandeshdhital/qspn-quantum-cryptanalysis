"""Interactive dashboard for quantum computing experiment results.

Provides a web-based dashboard for visualizing and comparing experiment results,
making it easy for labs, companies, and universities to:
* Monitor experiment progress
* Compare results across runs
* Track device performance over time
* Generate publication-ready figures

Usage:
    python -m qspn.dashboard --results results/ --port 8050
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .noise import NoiseParams
from .runner import RunConfig
from .spn import SPNParams


def create_dashboard(results_dir: str | Path, port: int = 8050) -> None:
    """Create and launch an interactive dashboard.

    Parameters
    ----------
    results_dir:
        Directory containing experiment results.
    port:
        Port to run the dashboard on.
    """
    try:
        import dash
        from dash import dcc, html
        from dash.dependencies import Input, Output
        import plotly.express as px
        import plotly.graph_objects as go
    except ImportError:
        print("Dashboard requires dash and plotly. Install with:")
        print("  pip install dash plotly")
        return

    app = dash.Dash(__name__)

    # Load results
    results_path = Path(results_dir)
    results = {}
    for json_file in results_path.glob("data/*.json"):
        name = json_file.stem
        results[name] = json.loads(json_file.read_text())

    app.layout = html.Div([
        html.H1("QSPN Experiment Dashboard"),
        html.Hr(),

        html.H2("Experiment Selection"),
        dcc.Dropdown(
            id="experiment-selector",
            options=[{"label": name, "value": name} for name in results.keys()],
            value=list(results.keys())[0] if results else None,
        ),

        html.H2("Results"),
        dcc.Graph(id="results-graph"),

        html.H2("Summary"),
        html.Div(id="summary-table"),
    ])

    @app.callback(
        Output("results-graph", "figure"),
        Output("summary-table", "children"),
        Input("experiment-selector", "value"),
    )
    def update_graph(selected_experiment):
        if not selected_experiment:
            return go.Figure(), "No experiment selected"

        data = results[selected_experiment]

        # Create figure based on experiment type
        if "sweep" in data:
            fig = go.Figure()
            sweep = data["sweep"]
            iterations = [s["iterations"] for s in sweep]
            p_success = [s["p_success"] for s in sweep]
            fig.add_trace(go.Scatter(
                x=iterations, y=p_success,
                mode="lines+markers",
                name="P(success)",
            ))
            fig.update_layout(
                title=f"{selected_experiment}: Success Probability",
                xaxis_title="Iterations",
                yaxis_title="P(success)",
            )
        else:
            fig = go.Figure()

        # Create summary table
        summary_items = []
        for key, value in data.items():
            if isinstance(value, (int, float, str)):
                summary_items.append(html.Tr([
                    html.Td(key),
                    html.Td(str(value)),
                ]))

        table = html.Table([
            html.Thead(html.Tr([html.Th("Metric"), html.Th("Value")])),
            html.Tbody(summary_items),
        ])

        return fig, table

    print(f"Dashboard running at http://localhost:{port}")
    app.run(debug=True, port=port)


def generate_report(results_dir: str | Path, output_path: str | Path) -> None:
    """Generate a static HTML report from experiment results.

    Parameters
    ----------
    results_dir:
        Directory containing experiment results.
    output_path:
        Path to save the HTML report.
    """
    results_path = Path(results_dir)
    results = {}
    for json_file in results_path.glob("data/*.json"):
        name = json_file.stem
        results[name] = json.loads(json_file.read_text())

    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>QSPN Experiment Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .experiment { border: 1px solid #ccc; padding: 20px; margin: 20px 0; }
        h1 { color: #333; }
        h2 { color: #666; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>QSPN Experiment Report</h1>
"""

    for name, data in results.items():
        html_content += f"""
    <div class="experiment">
        <h2>{name}</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
"""
        for key, value in data.items():
            if isinstance(value, (int, float, str)):
                html_content += f"""
            <tr><td>{key}</td><td>{value}</td></tr>
"""
        html_content += """
        </table>
    </div>
"""

    html_content += """
</body>
</html>
"""

    Path(output_path).write_text(html_content)
    print(f"Report saved to {output_path}")


def compare_experiments(
    results_dir: str | Path,
    experiment_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compare multiple experiments and generate a comparison report.

    Parameters
    ----------
    results_dir:
        Directory containing experiment results.
    experiment_names:
        List of experiment names to compare. If None, compares all.

    Returns
    -------
    dict
        Comparison report with metrics for each experiment.
    """
    results_path = Path(results_dir)
    results = {}
    for json_file in results_path.glob("data/*.json"):
        name = json_file.stem
        if experiment_names is None or name in experiment_names:
            results[name] = json.loads(json_file.read_text())

    comparison = {}
    for name, data in results.items():
        comparison[name] = {
            "p_success": data.get("p_success", data.get("best_p_success", "N/A")),
            "p_success_stderr": data.get("p_success_stderr", "N/A"),
            "entropy_bits": data.get("entropy_bits", "N/A"),
        }

    return comparison


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="QSPN Dashboard")
    parser.add_argument("--results", default="results/", help="Results directory")
    parser.add_argument("--port", type=int, default=8050, help="Port")
    parser.add_argument("--report", type=Path, default=None, help="Generate static report")
    args = parser.parse_args()

    if args.report:
        generate_report(args.results, args.report)
    else:
        create_dashboard(args.results, args.port)
