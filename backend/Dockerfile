# Pull official base image
FROM python:3.13-slim

# Set working directory
WORKDIR /usr/src/app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update \
    && apt-get -y install netcat-traditional gcc postgresql-client \
    && apt-get clean

# Install UV for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (including test and dev tools)
RUN uv sync --frozen --no-cache --extra test --extra dev

# Copy project
COPY . .