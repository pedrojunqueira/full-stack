# Chapter 3: Code Quality & Developer Experience

[← Chapter 2](./chapter-02-crud-tdd.md) | [Back to Index](./README.md) | [Chapter 4 →](./chapter-04-azure-deployment.md)

---

**Goal:** Add professional tooling for code quality and developer experience

**Time:** 20-30 minutes

**What you'll learn:**

- Configuring Ruff for linting and formatting
- Setting up test coverage thresholds
- Creating production-ready Dockerfiles
- Using UV for fast dependency management

---

## Why Code Quality Tools?

```
Without Tools                    With Tools
─────────────                   ──────────
❌ Inconsistent formatting       ✅ Auto-formatted code
❌ Hidden bugs                   ✅ Linting catches issues
❌ Unknown test coverage         ✅ 80%+ coverage required
❌ "Works on my machine"         ✅ Reproducible builds
```

---

## Step 3.1: Configure Ruff for Linting

[Ruff](https://github.com/astral-sh/ruff) is an extremely fast Python linter and formatter written in Rust.

Update the `[tool.ruff]` section in `backend/pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # Pyflakes
    "I",    # isort (import sorting)
    "UP",   # pyupgrade (modern Python syntax)
    "B",    # flake8-bugbear (common bugs)
    "SIM",  # flake8-simplify (code simplification)
]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.ruff.lint.isort]
known-first-party = ["app"]
```

> 💡 **What these rules catch:**
>
> - **E/F**: Syntax errors, undefined variables
> - **I**: Unsorted imports
> - **UP**: Old Python syntax (e.g., `dict()` vs `{}`)
> - **B**: Common bugs like mutable default arguments
> - **SIM**: Code that can be simplified

---

## Step 3.2: Add Test Coverage Configuration

Add coverage settings to `backend/pyproject.toml`:

```toml
[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

This configuration:

- Only measures coverage for the `app/` directory
- Fails the build if coverage drops below 80%
- Shows which lines are missing coverage

---

## Step 3.3: Create Lint Script

Create `scripts/lint.sh`:

```bash
#!/bin/bash

set -e  # Exit on any error

echo "🔍 Running Ruff linter..."
cd project
uv run ruff check .

echo "📐 Running Ruff formatter check..."
uv run ruff format --check .

echo "✅ All checks passed!"
```

Make it executable:

```bash
chmod +x scripts/lint.sh
```

---

## Step 3.4: Create Production Dockerfile

The development Dockerfile is optimized for hot-reloading. For production, we need:

- Multi-stage build (smaller image)
- Non-root user (security)
- No development dependencies

Create `backend/Dockerfile.prod`:

```dockerfile
# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.13-slim AS builder

WORKDIR /usr/src/app

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy application code
COPY . .

# ============================================
# Stage 2: Production
# ============================================
FROM python:3.13-slim

WORKDIR /usr/src/app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy UV and application from builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder /usr/src/app /usr/src/app

# Create non-root user for security with home directory
RUN addgroup --system app && adduser --system --group app --home /home/app
RUN chown -R app:app /usr/src/app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ping || exit 1

# Start the application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> 💡 **Multi-stage build benefits:**
>
> - Final image doesn't include gcc, build files
> - Smaller image size (faster deploys)
> - Better security (less attack surface)

---

## Step 3.5: Run Code Quality Checks

### Format Code

```bash
# Auto-format all code
docker-compose exec backend uv run ruff format .

# Check formatting without changing files
docker-compose exec backend uv run ruff format --check .
```

### Check Linting

```bash
# Check for issues
docker-compose exec backend uv run ruff check .

# Auto-fix what can be fixed
docker-compose exec backend uv run ruff check --fix .
```

### Run Tests with Coverage

```bash
# Run with coverage report
docker-compose exec backend uv run pytest \
    --cov=app \
    --cov-report=term-missing \
    --cov-fail-under=80

# Generate HTML coverage report
docker-compose exec backend uv run pytest \
    --cov=app \
    --cov-report=html
```

The HTML report is saved to `backend/htmlcov/index.html`.

---

## Step 3.6: View Coverage Report

```bash
# Open coverage report in browser
cd backend/htmlcov && python -m http.server 8080
```

You'll see:

- Overall coverage percentage
- File-by-file breakdown
- Line-by-line highlighting of covered/uncovered code

---

## Step 3.7: Test Production Build

```bash
# Build production image
docker build -f backend/Dockerfile.prod -t fastapi-tdd:prod ./backend

# Stop dev containers first (they use port 8004)
docker-compose down

# Run production container
docker run -p 8004:8000 \
    -e DATABASE_URL=postgres://postgres:postgres@host.docker.internal:5432/backend_dev \
    fastapi-tdd:prod

# Test it
curl http://localhost:8004/ping
```

> 💡 **Note:** After testing the production build, you can restart the dev containers with `docker-compose up -d`

---

## ✅ Chapter 3 Checkpoint

You should now have:

- [x] Ruff configured for linting and formatting
- [x] Test coverage at 80%+
- [x] Production-ready Dockerfile
- [x] Lint script for CI
- [x] HTML coverage reports

**Commit your progress:**

```bash
git add .
git commit -m "Chapter 3: Code quality and developer experience"
```

---

## 📊 Understanding Coverage

```
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
app/__init__.py             0      0   100%
app/api/__init__.py         0      0   100%
app/api/crud.py            18      0   100%
app/api/ping.py             5      0   100%
app/api/summaries.py       35      0   100%
app/config.py              12      0   100%
app/db.py                  15      3    80%   20-22
app/main.py                18      0   100%
app/models/pydantic.py     12      0   100%
app/models/tortoise.py      8      1    87%   15
-----------------------------------------------------
TOTAL                     123      4    97%
```

- **Stmts**: Number of executable statements
- **Miss**: Statements not covered by tests
- **Missing**: Line numbers not covered

---

## 🔧 Ruff Commands Cheat Sheet

| Command                     | Description                      |
| --------------------------- | -------------------------------- |
| `ruff check .`              | Check for linting issues         |
| `ruff check --fix .`        | Auto-fix issues                  |
| `ruff format .`             | Format all files                 |
| `ruff format --check .`     | Check formatting without changes |
| `ruff check --select E,F .` | Check only specific rules        |
| `ruff rule E501`            | Explain a specific rule          |

---

## 📁 Files Created/Modified in This Chapter

```
full-stack/
├── scripts/
│   └── lint.sh              # NEW: lint script
├── backend/
│   ├── Dockerfile.prod      # NEW: production Dockerfile
│   ├── pyproject.toml       # Updated: Ruff + coverage config
│   └── htmlcov/             # Generated: coverage reports
```

---

## 💡 Pro Tips

### 1. Add Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

Install:

```bash
pip install pre-commit
pre-commit install
```

Now code is automatically formatted before each commit!

### 2. IDE Integration

For VS Code, add to `.vscode/settings.json`:

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  },
  "ruff.lint.run": "onSave"
}
```

### 3. Make Coverage Part of CI

We'll do this in Chapter 5, but the key is:

```yaml
- name: Run tests with coverage
  run: |
    uv run pytest --cov=app --cov-fail-under=80
```

The `--cov-fail-under=80` flag makes the CI fail if coverage drops.

---

[← Chapter 2](./chapter-02-crud-tdd.md) | [Back to Index](./README.md) | [Chapter 4: Azure Deployment →](./chapter-04-azure-deployment.md)
