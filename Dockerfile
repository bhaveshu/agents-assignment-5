FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

# Copy application source code
COPY backend ./backend
COPY .env.example .env* ./

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "backend.server"]
