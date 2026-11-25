# FleetSense — Lightweight runtime image
# Optional: not required for local Windows development.
# Usage: docker build -t fleetsense . && docker run fleetsense all

FROM python:3.11-slim AS base

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv pip install --system -e .

# Copy project source
COPY . .

# Default: run the full pipeline
ENTRYPOINT ["python", "-m", "fleetsense.cli"]
CMD ["all"]
