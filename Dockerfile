# QSPN Quantum Computing Project
# Docker container for reproducible quantum experiments

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"

# Copy project files
COPY src/ ./src/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY results/ ./results/
COPY notebooks/ ./notebooks/
COPY CITATION.cff LICENSE ./

# Create results directory
RUN mkdir -p results/data results/figures

# Set entry point
ENTRYPOINT ["python"]
CMD ["-m", "qspn.cli", "--help"]
