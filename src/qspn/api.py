"""REST API for remote access to QSPN experiments.

Provides a FastAPI-based web service for running quantum experiments
remotely, enabling:
* Cloud-based quantum experiment execution
* Integration with existing lab infrastructure
* Multi-user access to quantum resources
* Automated benchmarking and reporting

Usage:
    uvicorn qspn.api:app --host 0.0.0.0 --port 8000

Then access:
    http://localhost:8000/docs for interactive API documentation
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .experiments import (
    Instance,
    experiment_a_ideal,
    experiment_b_noisy,
    experiment_c_mitigation,
    experiment_d_threshold,
    experiment_e_resources,
)
from .noise import NoiseParams
from .runner import RunConfig
from .spn import SPNParams

app = FastAPI(
    title="QSPN API",
    description="Quantum SPN Cryptanalysis API for remote experiment execution",
    version="1.0.0",
)


# ===========================================================================
# Request/Response models
# ===========================================================================

class ExperimentRequest(BaseModel):
    """Request model for running experiments."""

    experiment: str = Field(..., description="Experiment to run: a, b, c, d, e")
    shots: int = Field(default=4096, ge=1, le=100000)
    seed: int = Field(default=20260902)
    key_bits: int = Field(default=4, ge=4, le=8)
    rounds: int = Field(default=2, ge=1, le=10)
    secret_key: int = Field(default=0b1101, ge=0, le=255)
    p1: float = Field(default=1e-3, ge=0, le=1)
    p2: float = Field(default=1e-2, ge=0, le=1)
    readout_01: float = Field(default=0.02, ge=0, le=1)
    readout_10: float = Field(default=0.04, ge=0, le=1)


class ExperimentResponse(BaseModel):
    """Response model for experiment results."""

    experiment: str
    status: str
    result: dict[str, Any]
    runtime_seconds: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    available_experiments: list[str]


# ===========================================================================
# API endpoints
# ===========================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    from . import __version__

    return HealthResponse(
        status="healthy",
        version=__version__,
        available_experiments=["a", "b", "c", "d", "e"],
    )


@app.post("/run/{experiment}", response_model=ExperimentResponse)
async def run_experiment(
    experiment: str,
    request: ExperimentRequest,
    background_tasks: BackgroundTasks,
) -> ExperimentResponse:
    """Run a single experiment.

    Parameters
    ----------
    experiment:
        Experiment to run: a, b, c, d, or e
    request:
        Experiment parameters

    Returns
    -------
    ExperimentResponse with results
    """
    import time

    if experiment not in "abcde":
        raise HTTPException(
            status_code=400,
            detail=f"Unknown experiment '{experiment}'. Choose from: a, b, c, d, e",
        )

    start_time = time.time()

    # Build configuration
    config = RunConfig(shots=request.shots, seed=request.seed)
    params = SPNParams(key_bits=request.key_bits, rounds=request.rounds)
    noise = NoiseParams(
        p1=request.p1,
        p2=request.p2,
        p_read_1_given_0=request.readout_01,
        p_read_0_given_1=request.readout_10,
    )

    instance = Instance.build(request.secret_key, params)

    # Run the appropriate experiment
    if experiment == "a":
        result = experiment_a_ideal(instance, config)
    elif experiment == "b":
        result = experiment_b_noisy(instance, noise, config)
    elif experiment == "c":
        result = experiment_c_mitigation(instance, noise, config)
    elif experiment == "d":
        result = experiment_d_threshold(instance, noise, config)
    elif experiment == "e":
        result = experiment_e_resources(config=config)
    else:
        raise HTTPException(status_code=400, detail="Invalid experiment")

    runtime = time.time() - start_time

    return ExperimentResponse(
        experiment=experiment,
        status="completed",
        result=result,
        runtime_seconds=runtime,
    )


@app.post("/run/all", response_model=list[ExperimentResponse])
async def run_all_experiments(
    request: ExperimentRequest,
) -> list[ExperimentResponse]:
    """Run all experiments (A through E)."""
    responses = []
    for exp in "abcde":
        response = await run_experiment(exp, request, BackgroundTasks())
        responses.append(response)
    return responses


@app.get("/noise/validate")
async def validate_noise_model() -> dict[str, Any]:
    """Validate the current noise model."""
    from .validation import validate_noise_model

    noise = NoiseParams()
    result = validate_noise_model(noise)
    return result


@app.get("/mitigation/methods")
async def list_mitigation_methods() -> dict[str, Any]:
    """List available error mitigation methods."""
    return {
        "readout_mitigation": ["pinv", "clip", "nnls"],
        "zero_noise_extrapolation": ["linear", "richardson", "exponential"],
        "probabilistic_error_cancellation": ["pec"],
        "clifford_data_regression": ["cdr"],
        "virtual_distillation": ["vd"],
        "dynamical_decoupling": ["xy4", "xy8", "cpmg", "udd"],
    }


# ===========================================================================
# Main entry point
# ===========================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
