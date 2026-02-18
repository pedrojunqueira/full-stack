# Chapter 2: CRUD API with TDD

[← Chapter 1](./chapter-01-fastapi-docker.md) | [Back to Index](./README.md) | [Chapter 3 →](./chapter-03-code-quality.md)

---

**Goal:** Build a complete CRUD API using Test-Driven Development

**Time:** 45-60 minutes

**What you'll learn:**

- The TDD (Red-Green-Refactor) workflow
- Writing async tests with pytest
- Building RESTful CRUD endpoints
- Using Pydantic for validation

---

## The TDD Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    TDD Cycle                                 │
│                                                              │
│    ┌─────────┐      ┌─────────┐      ┌──────────┐          │
│    │  RED    │ ──→  │  GREEN  │ ──→  │ REFACTOR │ ──→ 🔄   │
│    │ (Write  │      │ (Make   │      │ (Clean   │          │
│    │  Test)  │      │ it Pass)│      │   Up)    │          │
│    └─────────┘      └─────────┘      └──────────┘          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

1. **RED:** Write a failing test
2. **GREEN:** Write minimal code to make it pass
3. **REFACTOR:** Clean up the code while keeping tests green

---

## Step 2.1: Create Test Configuration

Create `backend/tests/__init__.py`:

```python
# Tests Package
```

Create `backend/tests/conftest.py`:

```python
import os

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.config import Settings, get_settings
from app.main import create_application


def get_settings_override():
    return Settings(testing=True)


@pytest.fixture(scope="module")
def test_app():
    app = create_application()
    app.dependency_overrides[get_settings] = get_settings_override
    return app


@pytest.fixture(scope="function")
async def test_app_with_db(test_app):
    """Create a fresh database for each test."""
    test_db_url = os.getenv(
        "DATABASE_TEST_URL", "postgres://postgres:postgres@backend-db:5432/backend_test"
    )

    await Tortoise.init(
        db_url=test_db_url,
        modules={"models": ["app.models.tortoise"]},
    )
    await Tortoise.generate_schemas()

    yield test_app

    # Clean up: drop tables but keep the database
    conn = Tortoise.get_connection("default")
    await conn.execute_query("DROP SCHEMA public CASCADE")
    await conn.execute_query("CREATE SCHEMA public")
    await Tortoise.close_connections()


@pytest.fixture
async def client(test_app_with_db):
    async with AsyncClient(
        transport=ASGITransport(app=test_app_with_db),
        base_url="http://test",
    ) as ac:
        yield ac
```

> 💡 **Key Concepts:**
>
> - `@pytest.fixture` creates reusable test setup
> - `scope="function"` means fresh database for each test
> - `AsyncClient` from httpx tests async endpoints

---

## Step 2.2: Write Tests First (TDD Style)

Create `backend/tests/test_ping.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_ping(client):
    response = await client.get("/ping")
    assert response.status_code == 200
    assert response.json()["ping"] == "pong!"
```

Create `backend/tests/test_summaries.py`:

```python
import pytest


# ============== CREATE ==============

@pytest.mark.asyncio
async def test_create_summary(client):
    """Test creating a new summary."""
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    assert response.status_code == 201
    assert response.json()["url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_create_summary_invalid_json(client):
    """Test that missing URL returns 422."""
    response = await client.post(
        "/summaries/",
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_summary_invalid_url(client):
    """Test that invalid URL returns 422."""
    response = await client.post(
        "/summaries/",
        json={"url": "not-a-valid-url"},
    )
    assert response.status_code == 422


# ============== READ ==============

@pytest.mark.asyncio
async def test_read_summary(client):
    """Test reading a single summary."""
    # Create a summary first
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    summary_id = response.json()["id"]

    # Read it back
    response = await client.get(f"/summaries/{summary_id}/")
    assert response.status_code == 200
    assert response.json()["id"] == summary_id
    assert response.json()["url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_read_summary_not_found(client):
    """Test that non-existent ID returns 404."""
    response = await client.get("/summaries/99999/")
    assert response.status_code == 404
    assert response.json()["detail"] == "Summary not found"


@pytest.mark.asyncio
async def test_read_all_summaries(client):
    """Test reading all summaries."""
    # Create some summaries
    await client.post("/summaries/", json={"url": "https://example1.com"})
    await client.post("/summaries/", json={"url": "https://example2.com"})

    response = await client.get("/summaries/")
    assert response.status_code == 200
    assert len(response.json()) >= 2


# ============== UPDATE ==============

@pytest.mark.asyncio
async def test_update_summary(client):
    """Test updating a summary."""
    # Create
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    summary_id = response.json()["id"]

    # Update
    response = await client.put(
        f"/summaries/{summary_id}/",
        json={"url": "https://updated.com", "summary": "Updated summary text"},
    )
    assert response.status_code == 200
    assert response.json()["url"] == "https://updated.com/"
    assert response.json()["summary"] == "Updated summary text"


@pytest.mark.asyncio
async def test_update_summary_not_found(client):
    """Test updating non-existent summary returns 404."""
    response = await client.put(
        "/summaries/99999/",
        json={"url": "https://example.com", "summary": "test"},
    )
    assert response.status_code == 404


# ============== DELETE ==============

@pytest.mark.asyncio
async def test_delete_summary(client):
    """Test deleting a summary."""
    # Create
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    summary_id = response.json()["id"]

    # Delete
    response = await client.delete(f"/summaries/{summary_id}/")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    # Verify deleted
    response = await client.get(f"/summaries/{summary_id}/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_summary_not_found(client):
    """Test deleting non-existent summary returns 404."""
    response = await client.delete("/summaries/99999/")
    assert response.status_code == 404
```

---

## Step 2.3: Update Docker Compose for Testing

Before running tests, we need to update `docker-compose.yml` to prevent the host's `.venv` from overwriting the container's virtual environment.

When you run `uv sync` locally, it creates a `.venv` with Python symlinks pointing to your host's Python. Since we mount `./backend:/usr/src/app`, this local `.venv` would shadow the container's properly-built one, causing pytest to fail with "No such file or directory".

The fix is to add an anonymous volume that preserves the container's `.venv`:

```yaml
- /usr/src/app/.venv # Use container's venv, not host's
```

Update `docker-compose.yml` with the complete configuration:

```yaml
services:
  # FastAPI Backend
  backend:
    build: ./backend
    command: uv run uvicorn app.main:app --reload --workers 1 --host 0.0.0.0 --port 8000
    volumes:
      - ./backend:/usr/src/app
      - /usr/src/app/.venv # Use container's venv, not host's
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

Rebuild and restart the containers:

```bash
docker-compose down && docker-compose up -d --build
```

---

## Step 2.4: Run Tests (They Should Fail - RED)

```bash
docker-compose exec backend uv run pytest -v
```

You should see failures like:

```
FAILED test_summaries.py::test_create_summary - 404 Not Found
```

This is expected! We haven't implemented the endpoints yet. This is the **RED** phase.

---

## Step 2.5: Implement CRUD Operations (GREEN)

### Update Pydantic Models

Update `backend/app/models/pydantic.py`:

```python
from pydantic import AnyHttpUrl, BaseModel


class SummaryPayloadSchema(BaseModel):
    url: AnyHttpUrl


class SummaryResponseSchema(BaseModel):
    id: int
    url: str
    summary: str | None = None


class SummaryUpdatePayloadSchema(BaseModel):
    url: AnyHttpUrl
    summary: str | None = None
```

> 💡 **Pydantic Features:**
>
> - `AnyHttpUrl` validates that the string is a valid URL
> - `str | None = None` means optional field with None default

### Create CRUD Operations

Create `backend/app/api/crud.py`:

```python
from app.models.pydantic import SummaryPayloadSchema
from app.models.tortoise import TextSummary


async def create_summary(payload: SummaryPayloadSchema) -> int:
    """Create a new summary and return its ID."""
    summary = await TextSummary.create(url=str(payload.url))
    return summary.id


async def get_summary(id: int) -> TextSummary | None:
    """Get a summary by ID."""
    return await TextSummary.filter(id=id).first()


async def get_all_summaries() -> list[TextSummary]:
    """Get all summaries."""
    return await TextSummary.all()


async def update_summary(
    id: int, url: str, summary: str | None = None
) -> TextSummary | None:
    """Update a summary and return the updated object."""
    summary_obj = await TextSummary.filter(id=id).first()
    if summary_obj:
        summary_obj.url = url
        if summary is not None:
            summary_obj.summary = summary
        await summary_obj.save()
    return summary_obj


async def delete_summary(id: int) -> bool:
    """Delete a summary. Returns True if deleted."""
    deleted_count = await TextSummary.filter(id=id).delete()
    return deleted_count > 0
```

### Create Summaries Router

Create `backend/app/api/summaries.py`:

```python
from fastapi import APIRouter, HTTPException

from app.api import crud
from app.models.pydantic import (
    SummaryPayloadSchema,
    SummaryResponseSchema,
    SummaryUpdatePayloadSchema,
)

router = APIRouter()


@router.post("/", response_model=SummaryResponseSchema, status_code=201)
async def create_summary(payload: SummaryPayloadSchema):
    """
    Create a new text summary.

    - **url**: The URL to summarize (must be valid HTTP/HTTPS URL)
    """
    summary_id = await crud.create_summary(payload)
    summary = await crud.get_summary(summary_id)
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )


@router.get("/{id}/", response_model=SummaryResponseSchema)
async def read_summary(id: int):
    """
    Get a summary by ID.

    - **id**: The unique identifier of the summary
    """
    summary = await crud.get_summary(id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )


@router.get("/", response_model=list[SummaryResponseSchema])
async def read_all_summaries():
    """Get all summaries."""
    summaries = await crud.get_all_summaries()
    return [
        SummaryResponseSchema(
            id=s.id,
            url=str(s.url),
            summary=s.summary,
        )
        for s in summaries
    ]


@router.put("/{id}/", response_model=SummaryResponseSchema)
async def update_summary(id: int, payload: SummaryUpdatePayloadSchema):
    """
    Update a summary.

    - **id**: The unique identifier of the summary
    - **url**: New URL value
    - **summary**: New summary text (optional)
    """
    summary = await crud.update_summary(id, str(payload.url), payload.summary)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )


@router.delete("/{id}/")
async def delete_summary(id: int):
    """
    Delete a summary.

    - **id**: The unique identifier of the summary to delete
    """
    deleted = await crud.delete_summary(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"id": id, "deleted": True}
```

---

## Step 2.6: Register the Router

Update `backend/app/main.py`:

```python
import logging

from fastapi import FastAPI

from app.api import ping, summaries
from app.db import init_db

log = logging.getLogger("uvicorn")


def create_application() -> FastAPI:
    application = FastAPI(title="FastAPI TDD Docker")

    # Include routers
    application.include_router(ping.router, tags=["Health"])
    application.include_router(
        summaries.router,
        prefix="/summaries",
        tags=["Summaries"],
    )

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

## Step 2.7: Run Tests Again (They Should Pass - GREEN)

```bash
docker-compose exec backend uv run pytest -v
```

All tests should now pass! ✅

```
tests/test_ping.py::test_ping PASSED
tests/test_summaries.py::test_create_summary PASSED
tests/test_summaries.py::test_create_summary_invalid_json PASSED
tests/test_summaries.py::test_read_summary PASSED
tests/test_summaries.py::test_read_summary_not_found PASSED
tests/test_summaries.py::test_read_all_summaries PASSED
tests/test_summaries.py::test_update_summary PASSED
tests/test_summaries.py::test_delete_summary PASSED
...
```

---

## Step 2.8: Test the API Manually

Visit http://localhost:8004/docs to see the interactive Swagger UI.

Try these operations:

1. **POST /summaries/** - Create a summary
2. **GET /summaries/** - List all summaries
3. **GET /summaries/{id}/** - Get one summary
4. **PUT /summaries/{id}/** - Update a summary
5. **DELETE /summaries/{id}/** - Delete a summary

---

## ✅ Chapter 2 Checkpoint

You should now have:

- [x] Full CRUD API for summaries
- [x] All tests passing
- [x] TDD workflow established
- [x] Swagger docs showing all endpoints
- [x] Pydantic validation working

**Commit your progress:**

```bash
git add .
git commit -m "Chapter 2: CRUD API with TDD"
```

---

## 🔍 Understanding the Test Fixtures

```python
@pytest.fixture(scope="function")
async def test_app_with_db(test_app):
    # 1. Connect to test database
    await Tortoise.init(...)

    # 2. Create tables
    await Tortoise.generate_schemas()

    # 3. Provide the app to tests
    yield test_app

    # 4. Clean up: drop tables but keep the database
    conn = Tortoise.get_connection("default")
    await conn.execute_query("DROP SCHEMA public CASCADE")
    await conn.execute_query("CREATE SCHEMA public")
    await Tortoise.close_connections()
```

Each test gets:

- A fresh schema (tables created, then dropped)
- Isolated from other tests
- Proper async handling

---

## 📁 Files Created/Modified in This Chapter

```
backend/
├── app/
│   ├── main.py              # Updated: added summaries router
│   ├── api/
│   │   ├── crud.py          # NEW: database operations
│   │   └── summaries.py     # NEW: REST endpoints
│   └── models/
│       └── pydantic.py      # Updated: new schemas
└── tests/
    ├── __init__.py          # NEW
    ├── conftest.py          # NEW: test fixtures
    ├── test_ping.py         # NEW
    └── test_summaries.py    # NEW: CRUD tests
```

---

## 💡 TDD Best Practices

1. **Write tests before code** - Forces you to think about the API design
2. **One assertion per test** - Makes failures easier to debug
3. **Test edge cases** - Empty data, invalid input, not found
4. **Use descriptive names** - `test_create_summary_invalid_json` tells you what it tests
5. **Keep tests fast** - Each test should run in milliseconds

---

[← Chapter 1](./chapter-01-fastapi-docker.md) | [Back to Index](./README.md) | [Chapter 3: Code Quality →](./chapter-03-code-quality.md)
