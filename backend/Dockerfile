FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency requirements first to leverage Docker layer caching
COPY backend/requirements.txt ./backend/requirements.txt
RUN uv pip install --system -r backend/requirements.txt

# Copy backend application source
COPY backend ./backend
COPY .env.example .env* ./

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "backend.server"]
