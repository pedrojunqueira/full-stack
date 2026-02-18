# Chapter 1: FastAPI + PostgreSQL with Docker

[← Back to Tutorial Index](./README.md) | [Next: Chapter 2 →](./chapter-02-crud-tdd.md)

---

**Goal:** Get a basic API running locally with Docker

**Time:** 30-45 minutes

**What you'll learn:**

- Setting up a FastAPI project structure
- Configuring PostgreSQL with Docker
- Using Tortoise ORM for async database operations
- Docker Compose for multi-container development

---

## Step 1.1: Create Project Structure

Start by creating the directory structure for your project:

```bash
mkdir full-stack
cd full-stack

# Create directory structure
mkdir -p backend/app/api
mkdir -p backend/app/models
mkdir -p backend/db
mkdir -p backend/tests
```

Your structure should look like:

```
full-stack/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   └── models/
│   ├── db/
│   └── tests/
```

---

## Step 1.2: Create the Database Dockerfile

We'll use PostgreSQL 17 in a Docker container.

Create `backend/db/Dockerfile`:

```dockerfile
FROM postgres:17

# Add any initialization scripts here
COPY create.sql /docker-entrypoint-initdb.d/
```

Create `backend/db/create.sql`:

```sql
-- Create databases for development and testing
CREATE DATABASE backend_dev;
CREATE DATABASE backend_test;
```

> 💡 **Tip:** Files in `/docker-entrypoint-initdb.d/` run automatically when PostgreSQL starts for the first time.

---

## Step 1.3: Create the FastAPI Application

### Configuration Module

Create `backend/app/__init__.py`:

```python
# FastAPI Application Package
```

Create `backend/app/config.py`:

```python
import logging
import os
from functools import lru_cache

from pydantic_settings import BaseSettings

log = logging.getLogger("uvicorn")


class Settings(BaseSettings):
    environment: str = os.getenv("ENVIRONMENT", "dev")
    testing: bool = os.getenv("TESTING", "0") == "1"
    database_url: str = os.getenv(
        "DATABASE_URL", "postgres://postgres:postgres@backend-db:5432/backend_dev"
    )
    database_test_url: str = os.getenv(
        "DATABASE_TEST_URL", "postgres://postgres:postgres@backend-db:5432/backend_test"
    )


@lru_cache
def get_settings() -> Settings:
    log.info("Loading config settings from the environment...")
    return Settings()
```

> 💡 **Why `@lru_cache`?** It ensures settings are loaded only once, not on every request.

### Database Module

Create `backend/app/db.py`:

```python
import logging
import os

from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise

from app.config import get_settings

log = logging.getLogger("uvicorn")

TORTOISE_ORM = {
    "connections": {
        "default": os.getenv(
            "DATABASE_URL", "postgres://postgres:postgres@backend-db:5432/backend_dev"
        )
    },
    "apps": {
        "models": {
            "models": ["app.models.tortoise", "aerich.models"],
            "default_connection": "default",
        },
    },
}


def init_db(app, generate_schemas: bool = False):
    settings = get_settings()
    db_url = settings.database_test_url if settings.testing else settings.database_url

    register_tortoise(
        app,
        db_url=db_url,
        modules={"models": ["app.models.tortoise"]},
        generate_schemas=generate_schemas,
        add_exception_handlers=True,
    )


async def close_db():
    await Tortoise.close_connections()
```

### API Routes Package

Create `backend/app/api/__init__.py`:

```python
# API Routes Package
```

Create `backend/app/api/ping.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def pong():
    return {"ping": "pong!", "environment": "dev"}
```

### Main Application

Create `backend/app/main.py`:

```python
import logging

from fastapi import FastAPI

from app.api import ping
from app.db import init_db

log = logging.getLogger("uvicorn")


def create_application() -> FastAPI:
    application = FastAPI(title="FastAPI TDD Docker")

    # Include routers
    application.include_router(ping.router, tags=["Health"])

    # Initialize database (registers startup/shutdown hooks)
    init_db(application)

    return application


app = create_application()


@app.on_event("startup")
async def startup_event():
    log.info("Starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    log.info("Shutting down...")
```

---

## Step 1.4: Create the Models

### Tortoise ORM Models

Create `backend/app/models/__init__.py`:

```python
# Models Package
```

Create `backend/app/models/tortoise.py`:

```python
from tortoise import fields
from tortoise.models import Model


class TextSummary(Model):
    id = fields.IntField(pk=True)
    url = fields.TextField()
    summary = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    def __str__(self):
        return self.url
```

### Pydantic Schemas

Create `backend/app/models/pydantic.py`:

```python
from pydantic import BaseModel


class SummaryPayloadSchema(BaseModel):
    url: str


class SummaryResponseSchema(SummaryPayloadSchema):
    id: int
```

---

## Step 1.5: Create the Backend Dockerfile

Create `backend/Dockerfile`:

```dockerfile
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
```

> 💡 **Why UV?** It's 10-100x faster than pip for installing dependencies.

---

## Step 1.6: Create pyproject.toml

Create `backend/pyproject.toml`:

```toml
[project]
name = "fastapi-tdd-docker"
version = "0.1.0"
description = "FastAPI with TDD and Docker"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "tortoise-orm[asyncpg]>=0.23.0",
    "pydantic-settings>=2.6.0",
    "aerich>=0.8.0",
]

[project.optional-dependencies]
test = [
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "pytest-asyncio>=0.25.0",
]
dev = [
    "ruff>=0.8.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

Generate the lockfile:

```bash
cd backend
uv lock
cd ..
```

> 💡 **Why generate a lockfile?** The `uv.lock` file pins exact dependency versions for reproducible builds.

---

## Step 1.7: Create Docker Compose

Create `docker-compose.yml` in the project root:

```yaml
services:
  # FastAPI Backend
  backend:
    build: ./backend
    command: uv run uvicorn app.main:app --reload --workers 1 --host 0.0.0.0 --port 8000
    volumes:
      - ./backend:/usr/src/app
    ports:
      - 8004:8000
    environment:
      - ENVIRONMENT=dev
      - TESTING=0
      - DATABASE_URL=postgres://postgres:postgres@backend-db:5432/backend_dev
      - DATABASE_TEST_URL=postgres://postgres:postgres@backend-db:5432/backend_test
    depends_on:
      - backend-db

  # PostgreSQL Database
  backend-db:
    build:
      context: ./backend/db
      dockerfile: Dockerfile
    expose:
      - 5432
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Step 1.8: Build and Run

```bash
# Build and start containers
docker-compose up -d --build

# Check logs
docker-compose logs backend

# Test the endpoint
curl http://localhost:8004/ping
```

**Expected output:**

```json
{ "ping": "pong!", "environment": "dev" }
```

Visit http://localhost:8004/docs to see the Swagger UI!

---

## Step 1.9: Initialize Database Migrations

Aerich is a database migration tool for Tortoise ORM (similar to Alembic for SQLAlchemy).

```bash
# Initialize aerich configuration (only needed once)
docker-compose exec backend uv run aerich init -t app.db.TORTOISE_ORM

# Create initial database schema (only needed once)
docker-compose exec backend uv run aerich init-db
```

This creates a `migrations/` folder to track database schema changes.

If you ever wipe the database (e.g., `docker-compose down -v`) and need to recreate the tables:

```bash
# Apply existing migrations to recreate tables
docker-compose exec backend uv run aerich upgrade
```

---

## Step 1.10: Explore the Database

You can connect directly to PostgreSQL to inspect your tables:

```bash
# Connect to the dev database
docker-compose exec backend-db psql -U postgres -d backend_dev

# Inside psql, useful commands:
\l              # List all databases
\dt             # List all tables
\d textsummary  # Describe a specific table
SELECT * FROM textsummary;  # Run a query
\q              # Exit psql
```

Or run queries directly without entering psql:

```bash
# List all databases
docker-compose exec backend-db psql -U postgres -c "\l"

# List tables in backend_dev
docker-compose exec backend-db psql -U postgres -d backend_dev -c "\dt"

# Run a query
docker-compose exec backend-db psql -U postgres -d backend_dev -c "SELECT * FROM textsummary;"
```

> 💡 **Tip:** You can also use GUI tools like pgAdmin, TablePlus, or DBeaver by connecting to `localhost:5432` with username `postgres` and password `postgres`.

---

## ✅ Chapter 1 Checkpoint

You should now have:

- [x] FastAPI running at http://localhost:8004
- [x] PostgreSQL database running
- [x] `/ping` endpoint returning JSON
- [x] Swagger docs at http://localhost:8004/docs
- [x] Aerich migrations initialized

**Commit your progress:**

```bash
git init
git add .
git commit -m "Chapter 1: FastAPI + PostgreSQL with Docker"
```

---

## 🔍 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs backend
docker-compose logs backend-db

# Rebuild from scratch
docker-compose down -v
docker-compose up -d --build
```

### Database connection error

- Ensure `backend-db` is running: `docker-compose ps`
- Check the DATABASE_URL matches the container name

### Port already in use

```bash
# Find what's using port 8004
lsof -i :8004

# Use a different port in docker-compose.yml
ports:
  - 8005:8000  # Change 8004 to 8005
```

---

## 📁 Files Created in This Chapter

```
full-stack/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── ping.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── pydantic.py
│   │       └── tortoise.py
│   ├── db/
│   │   ├── Dockerfile
│   │   └── create.sql
│   └── tests/
└── migrations/
```

---

[← Back to Tutorial Index](./README.md) | [Next: Chapter 2 - CRUD API with TDD →](./chapter-02-crud-tdd.md)
