# Chapter 6: Azure Entra ID Authentication

[← Chapter 5](./chapter-05-cicd.md) | [Back to Index](./README.md) | [Chapter 7 →](./chapter-07-rbac.md)

---

**Goal:** Secure your API with Azure AD OAuth2 authentication

**Time:** 60-75 minutes

**What you'll learn:**

- Azure App Registration setup
- OAuth2 Authorization Code Flow with PKCE
- JWT token validation
- Protecting FastAPI endpoints
- Swagger UI OAuth2 integration

---

## Authentication Flow Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    OAuth2 Authorization Code Flow                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. User clicks "Authorize" in Swagger UI                            │
│        │                                                              │
│        ▼                                                              │
│  ┌─────────────┐                                                     │
│  │   Swagger   │──── 2. Redirect to Azure AD ────▶┌──────────────┐  │
│  │     UI      │                                   │   Azure AD   │  │
│  └─────────────┘                                   │  Login Page  │  │
│        ▲                                           └──────┬───────┘  │
│        │                                                  │          │
│  ┌─────┴─────────────────────────────────────────────────┘          │
│  │  3. User logs in, Azure redirects with authorization code         │
│  │                                                                    │
│  │  4. Swagger exchanges code for tokens (PKCE)                      │
│  │        │                                                          │
│  │        ▼                                                          │
│  │  ┌─────────────┐      5. API Request       ┌─────────────┐       │
│  │  │   Swagger   │───── with JWT Token ─────▶│   FastAPI   │       │
│  │  │     UI      │◀──── Response ────────────│    API      │       │
│  │  └─────────────┘                           └──────┬──────┘       │
│  │                                                    │              │
│  │                                    6. Validate JWT │              │
│  │                                                    ▼              │
│  │                                            ┌──────────────┐       │
│  │                                            │   Azure AD   │       │
│  │                                            │  (JWKS keys) │       │
│  │                                            └──────────────┘       │
│  │                                                                    │
└──┴────────────────────────────────────────────────────────────────────┘
```

---

## Step 6.1: Create Azure App Registrations

We need **two** app registrations:

1. **API App** - Represents your backend (validates tokens)
2. **Swagger App** - Represents the Swagger UI client (requests tokens)

### Create the API App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Entra ID** (formerly Azure AD)
3. Click **App registrations** → **New registration**

Configure:

- **Name:** `fastapi-tdd-api`
- **Supported account types:** "Accounts in this organizational directory only"
- **Redirect URI:** Leave blank
- Click **Register**

After creation, note these values:

- **Application (client) ID** → This is your `APP_CLIENT_ID`
- **Directory (tenant) ID** → This is your `TENANT_ID`

### Expose an API

1. Go to **Expose an API** in your API app
2. Click **Add a scope**
3. Set Application ID URI (accept default or customize, e.g., `api://fastapi-tdd-api`)
4. Add scope:
   - **Scope name:** `user_impersonation`
   - **Who can consent:** Admins and users
   - **Admin consent display name:** "Access FastAPI App"
   - **Admin consent description:** "Allows the app to access the API on behalf of the user"
   - **State:** Enabled
5. Click **Add scope**

### Set Token Version to v2

By default Azure issues v1.0 tokens. `fastapi-azure-auth` requires v2.0 tokens. You must update the API app manifest:

1. In your API app registration (`fastapi-tdd-api`), click **Manifest** in the left menu
2. Find this line:
   ```json
   "accessTokenAcceptedVersion": null,
   ```
3. Change it to:
   ```json
   "accessTokenAcceptedVersion": 2,
   ```
4. Click **Save**

> ⚠️ Without this step the API will return `"Token contains invalid claims"` even when authentication succeeds.

### Create the Swagger Client App Registration

1. Create another App Registration: `fastapi-tdd-swagger`
2. **Redirect URI:**
   - Type: **Single-page application (SPA)**
   - URI: `http://localhost:8004/oauth2-redirect`
3. Click **Register**

Note the **Application (client) ID** → This is your `OPENAPI_CLIENT_ID`

### Grant API Permissions

1. In the Swagger app, go to **API permissions**
2. Click **Add a permission** → **My APIs**
3. Select your API app (`fastapi-tdd-api`)
4. Check `user_impersonation`
5. Click **Add permissions**
6. Click **Grant admin consent** (if you're an admin)

### Which user account to log in with

When you click **Authorize** in Swagger UI, use an account that is a **Member** of your Azure tenant — not a **Guest**.

- **Member** = a native account in your tenant (e.g. `user@yourcompany.onmicrosoft.com`)
- **Guest** = an external account invited via B2B (shows as `user_externalcompany.com#EXT#@yourcompany.onmicrosoft.com`)

Guest accounts will be rejected with `"Guest users not allowed"`. You can check account type in **Azure Entra ID → Users** — the `User type` column shows `Member` or `Guest`.

---

## Step 6.2: Install Auth Dependencies

Update `backend/pyproject.toml` dependencies:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "tortoise-orm[asyncpg]>=0.23.0",
    "pydantic-settings>=2.6.0",
    "aerich>=0.8.0",
    "fastapi-azure-auth>=5.0.0",    # Add this line
]
```

Rebuild:

```bash
docker-compose build backend
docker-compose up -d
```

---

## Step 6.3: Update Configuration

Update `backend/app/config.py`:

```python
import logging
import os
from functools import lru_cache

from pydantic_settings import BaseSettings

log = logging.getLogger("uvicorn")


class Settings(BaseSettings):
    # Existing settings
    environment: str = os.getenv("ENVIRONMENT", "dev")
    testing: bool = os.getenv("TESTING", "0") == "1"
    database_url: str = os.getenv(
        "DATABASE_URL", "postgres://postgres:postgres@backend-db:5432/backend_dev"
    )
    database_test_url: str = os.getenv(
        "DATABASE_TEST_URL", "postgres://postgres:postgres@backend-db:5432/backend_test"
    )

    # Azure AD Configuration
    tenant_id: str = os.getenv("TENANT_ID", "")
    app_client_id: str = os.getenv("APP_CLIENT_ID", "")
    openapi_client_id: str = os.getenv("OPENAPI_CLIENT_ID", "")
    scope_description: str = os.getenv("SCOPE_DESCRIPTION", "user_impersonation")

    # CORS - Add your frontend URLs here
    backend_cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8004"]

    @property
    def is_auth_enabled(self) -> bool:
        """Check if authentication is properly configured."""
        return bool(self.tenant_id and self.app_client_id)


@lru_cache
def get_settings() -> Settings:
    log.info("Loading config settings from the environment...")
    return Settings()
```

---

## Step 6.4: Create Azure Auth Scheme

Create `backend/app/azure.py`:

```python
"""
Azure AD authentication scheme configuration.
"""

from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

from app.config import get_settings

settings = get_settings()

# Only configure if Azure AD is enabled
if settings.is_auth_enabled:
    azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
        app_client_id=settings.app_client_id,
        tenant_id=settings.tenant_id,
        scopes={
            f"api://{settings.app_client_id}/{settings.scope_description}": settings.scope_description,
        },
        allow_guest_users=True,
    )
else:
    # For local development without Azure AD
    azure_scheme = None
```

> 💡 **What this does:**
>
> - `SingleTenantAzureAuthorizationCodeBearer` validates JWT tokens from your tenant
> - It automatically fetches Azure AD's public keys for signature validation
> - Configures the scopes required by your API

---

## Step 6.5: Create Auth Module

Create `backend/app/auth.py`:

```python
"""
Authentication and authorization using fastapi-azure-auth.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security

from app.azure import azure_scheme
from app.models.pydantic import CurrentUserSchema

logger = logging.getLogger(__name__)


class AzureUserClaims:
    """
    Parsed Azure user claims from JWT token.

    Common claims:
    - preferred_username: User's email/UPN
    - oid: Object ID (unique user identifier in Azure AD)
    - name: Display name
    - roles: App roles assigned to user
    """

    def __init__(self, claims: dict):
        self.email = (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("upn")
        )
        self.azure_oid = claims.get("oid")
        self.name = claims.get("name")
        self.roles = claims.get("roles", [])

    def is_valid(self) -> bool:
        """Check if required claims are present."""
        return bool(self.email and self.azure_oid)


async def get_azure_user(
    azure_user: Annotated[object, Security(azure_scheme)],
) -> object:
    """
    Get the raw Azure user from the validated token.

    This is a separate dependency to allow easy mocking in tests.
    The azure_scheme automatically:
    - Validates the JWT signature
    - Checks token expiration
    - Verifies the audience and issuer
    """
    return azure_user


def parse_azure_claims(azure_user: object) -> AzureUserClaims:
    """Parse Azure user claims from the token."""
    if azure_user is None:
        raise HTTPException(
            status_code=500,
            detail="Authentication scheme not configured"
        )
    return AzureUserClaims(azure_user.claims)


async def get_current_user(
    azure_user: Annotated[object, Depends(get_azure_user)],
) -> CurrentUserSchema:
    """
    Get current authenticated user from Azure token.

    Returns a simplified user object with:
    - email: User's email address
    - azure_oid: Unique Azure AD identifier
    - name: Display name
    """
    claims = parse_azure_claims(azure_user)

    if not claims.is_valid():
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing required claims (email or oid)"
        )

    logger.info(f"User authenticated: {claims.email}")

    return CurrentUserSchema(
        email=claims.email,
        azure_oid=claims.azure_oid,
        name=claims.name,
    )
```

---

## Step 6.6: Update Pydantic Models

Add auth schemas to `backend/app/models/pydantic.py`:

```python
from pydantic import AnyHttpUrl, BaseModel


# Summary schemas (existing)
class SummaryPayloadSchema(BaseModel):
    url: AnyHttpUrl


class SummaryResponseSchema(BaseModel):
    id: int
    url: str
    summary: str | None = None


class SummaryUpdatePayloadSchema(BaseModel):
    url: AnyHttpUrl
    summary: str | None = None


# Auth schemas (new)
class CurrentUserSchema(BaseModel):
    """Current authenticated user from Azure AD token."""
    email: str
    azure_oid: str
    name: str | None = None
```

---

## Step 6.7: Update Main App with OAuth2

Update `backend/app/main.py`:

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ping, summaries
from app.azure import azure_scheme
from app.config import get_settings
from app.db import init_db

log = logging.getLogger("uvicorn")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup: Load Azure AD config
    Shutdown: Clean up resources
    """
    log.info("Starting up...")

    # Load Azure AD OpenID configuration (public keys for JWT validation)
    if azure_scheme:
        log.info("Loading Azure AD OpenID configuration...")
        await azure_scheme.openid_config.load_config()

    yield

    log.info("Shutting down...")


def create_application() -> FastAPI:
    # Configure OAuth2 for Swagger UI
    swagger_ui_init_oauth = None
    if settings.openapi_client_id:
        swagger_ui_init_oauth = {
            "usePkceWithAuthorizationCodeGrant": True,
            "clientId": settings.openapi_client_id,
            "scopes": f"api://{settings.app_client_id}/{settings.scope_description}",
        }

    application = FastAPI(
        title="FastAPI TDD Docker",
        description="A FastAPI application with Azure AD authentication",
        version="1.0.0",
        lifespan=lifespan,
        # OAuth2 redirect endpoint for Swagger
        swagger_ui_oauth2_redirect_url="/oauth2-redirect",
        swagger_ui_init_oauth=swagger_ui_init_oauth,
    )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    application.include_router(ping.router, tags=["Health"])
    application.include_router(
        summaries.router,
        prefix="/summaries",
        tags=["Summaries"],
    )

    # Register Tortoise ORM — must be called here, not inside lifespan,
    # so its startup hooks are registered before the app starts
    init_db(application)

    return application


app = create_application()
```

---

## Step 6.8: Protect Endpoints

Update `backend/app/api/summaries.py` to require authentication:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api import crud
from app.auth import get_current_user
from app.models.pydantic import (
    CurrentUserSchema,
    SummaryPayloadSchema,
    SummaryResponseSchema,
    SummaryUpdatePayloadSchema,
)

router = APIRouter()


@router.post("/", response_model=SummaryResponseSchema, status_code=201)
async def create_summary(
    payload: SummaryPayloadSchema,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Create a new text summary.

    **Requires authentication.**
    """
    summary_id = await crud.create_summary(payload)
    summary = await crud.get_summary(summary_id)
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )


@router.get("/{id}/", response_model=SummaryResponseSchema)
async def read_summary(
    id: int,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Get a summary by ID.

    **Requires authentication.**
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
async def read_all_summaries(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Get all summaries.

    **Requires authentication.**
    """
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
async def update_summary(
    id: int,
    payload: SummaryUpdatePayloadSchema,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Update a summary.

    **Requires authentication.**
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
async def delete_summary(
    id: int,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Delete a summary.

    **Requires authentication.**
    """
    deleted = await crud.delete_summary(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"id": id, "deleted": True}
```

---

## Step 6.9: Update Docker Compose

Update `docker-compose.yml` with Azure AD environment variables:

```yaml
services:
  web:
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
      # Azure Authentication - Replace with your values!
      - TENANT_ID=your-tenant-id-here
      - APP_CLIENT_ID=your-api-client-id-here
      - OPENAPI_CLIENT_ID=your-swagger-client-id-here
      - BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8004"]
      - SCOPE_DESCRIPTION=user_impersonation
    depends_on:
      - backend-db

  backend-db:
    # ... unchanged
```

---

## Step 6.10: Update Tests to Mock Authentication

Update `backend/tests/conftest.py`:

```python
import os
from unittest.mock import MagicMock

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.auth import get_azure_user
from app.config import Settings, get_settings
from app.main import create_application


def get_settings_override():
    return Settings(testing=True)


def get_mock_azure_user():
    """
    Create a mock Azure user for testing.

    This simulates a validated Azure AD token with user claims.
    """
    mock_user = MagicMock()
    mock_user.claims = {
        "preferred_username": "test@example.com",
        "oid": "test-oid-12345-67890",
        "name": "Test User",
        "roles": [],
    }
    return mock_user


@pytest.fixture(scope="module")
def test_app():
    """Create test application with mocked dependencies."""
    app = create_application()

    # Override settings for testing
    app.dependency_overrides[get_settings] = get_settings_override

    # Mock Azure authentication - return a fake validated user
    app.dependency_overrides[get_azure_user] = lambda: get_mock_azure_user()

    return app


@pytest.fixture(scope="function")
async def test_app_with_db(test_app):
    """Create a fresh database for each test."""
    test_db_url = os.getenv(
        "DATABASE_TEST_URL",
        "postgres://postgres:postgres@backend-db:5432/backend_test"
    )

    # Ensure the test database exists (creates it if missing)
    sys_conn = await asyncpg.connect(
        "postgres://postgres:postgres@backend-db:5432/postgres"
    )
    db_exists = await sys_conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = 'backend_test'"
    )
    if not db_exists:
        await sys_conn.execute("CREATE DATABASE backend_test")
    await sys_conn.close()

    await Tortoise.init(
        db_url=test_db_url,
        modules={"models": ["app.models.tortoise"]},
    )
    await Tortoise.generate_schemas()

    yield test_app

    # Drop all tables but keep the database — _drop_databases() would delete
    # the entire DB, causing subsequent tests to fail on connection
    conn = Tortoise.get_connection("default")
    await conn.execute_script("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    await Tortoise.close_connections()


@pytest.fixture
async def client(test_app_with_db):
    """Create async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app_with_db),
        base_url="http://test",
    ) as ac:
        yield ac
```

---

## Step 6.11: Create Auth Tests

Create `backend/tests/test_auth.py`:

```python
"""
Tests for authentication functionality.
"""

import pytest


@pytest.mark.asyncio
async def test_protected_endpoint_with_auth(client):
    """Test that authenticated requests succeed."""
    response = await client.get("/summaries/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_summary_with_auth(client):
    """Test creating a summary as authenticated user."""
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    assert response.status_code == 201
    assert response.json()["url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_ping_no_auth_required(client):
    """Test that health check doesn't require auth."""
    response = await client.get("/ping")
    assert response.status_code == 200
    assert response.json()["ping"] == "pong!"
```

---

## Step 6.12: Run and Test

```bash
# Rebuild and restart
docker-compose up -d --build

# Run tests
docker-compose exec backend uv run pytest -v
```

Visit http://localhost:8004/docs

You should see:

1. An **Authorize** button at the top
2. Lock icons 🔒 on protected endpoints
3. Clicking Authorize opens Azure AD login

---

## ✅ Chapter 6 Checkpoint

You should now have:

- [x] Azure AD App Registrations created
- [x] OAuth2 + PKCE authentication working
- [x] Protected API endpoints
- [x] Swagger UI with login button
- [x] Tests passing with mocked auth

**Commit your progress:**

```bash
git add .
git commit -m "Chapter 6: Azure Entra ID authentication"
```

---

## 🔐 Understanding JWT Claims

When a user authenticates, Azure AD issues a JWT with claims like:

```json
{
  "aud": "api://your-app-id", // Audience (your API)
  "iss": "https://login.microsoftonline.com/.../v2.0",
  "iat": 1699000000, // Issued at
  "exp": 1699003600, // Expires at
  "name": "John Doe", // Display name
  "oid": "12345678-...", // Object ID (unique)
  "preferred_username": "john@company.com",
  "roles": ["Admin", "Writer"], // App roles (Chapter 7)
  "scp": "user_impersonation" // Scopes
}
```

---

## 🔍 Troubleshooting

### "AADSTS50011: The reply URL does not match"

- Check redirect URI in Azure matches exactly: `http://localhost:8004/oauth2-redirect`
- Make sure it's registered as SPA type

### "AADSTS65001: User needs to consent"

- Grant admin consent in Azure Portal
- Or let users consent on first login

### "Invalid token" errors

- Check `TENANT_ID` and `APP_CLIENT_ID` are correct
- Ensure the token hasn't expired
- Verify the audience matches your API

### Tests fail with auth errors

- Make sure `get_azure_user` is being overridden in tests
- Check the mock user has all required claims

---

## 📁 Files Created/Modified in This Chapter

```
backend/
├── app/
│   ├── config.py          # Updated: Azure AD settings
│   ├── azure.py           # NEW: Azure auth scheme
│   ├── auth.py            # NEW: Auth dependencies
│   ├── main.py            # Updated: OAuth2 config
│   ├── api/
│   │   └── summaries.py   # Updated: protected endpoints
│   └── models/
│       └── pydantic.py    # Updated: CurrentUserSchema
└── tests/
    ├── conftest.py        # Updated: mock auth
    └── test_auth.py       # NEW: auth tests
```

---

[← Chapter 5](./chapter-05-cicd.md) | [Back to Index](./README.md) | [Chapter 7: RBAC →](./chapter-07-rbac.md)
