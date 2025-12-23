FROM python:3.10-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project definition
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project

# Copy source code
COPY src/ src/

# Run the application
# We use `uv run` to ensure we use the virtual environment, or we can add .venv/bin to PATH
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "src/main.py"]
