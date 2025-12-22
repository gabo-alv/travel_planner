FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project metadata first (better cache)
COPY pyproject.toml ./
# If you already generated it locally, also copy the lock
# COPY uv.lock ./

# Install deps into the image (no venv, or you can choose to use one)
RUN uv sync --no-dev --no-install-project

# Now copy the rest of the source code
COPY . .

# Default command
CMD ["sh", "start_"]
