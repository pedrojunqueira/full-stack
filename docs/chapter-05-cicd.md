# Chapter 5: CI/CD with GitHub Actions

[← Chapter 4](./chapter-04-azure-deployment.md) | [Back to Index](./README.md) | [Chapter 6 →](./chapter-06-azure-auth.md)

---

**Goal:** Automate testing and deployment with GitHub Actions

**Time:** 40-50 minutes

**What you'll learn:**

- GitHub Actions workflow syntax
- Running tests in CI
- Automatic deployments on merge
- Service Principal authentication
- PR validation workflows

---

## CI/CD Pipeline Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        GitHub Actions Pipeline                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   Push to default branch (e.g. master)    Pull Request                 │
│        │                               │                               │
│        ▼                               ▼                               │
│   ┌─────────┐                    ┌─────────┐                          │
│   │  Test   │                    │  Test   │                          │
│   │  Job    │                    │  Job    │                          │
│   └────┬────┘                    └────┬────┘                          │
│        │                               │                               │
│        ▼                               ▼                               │
│   ┌─────────┐                    ┌─────────┐                          │
│   │  Lint   │                    │  Lint   │                          │
│   │  Job    │                    │  Job    │                          │
│   └────┬────┘                    └─────────┘                          │
│        │                                                               │
│        ▼                         (No deploy for PRs)                  │
│   ┌─────────┐                                                         │
│   │ Deploy  │ ◄── Only on push to default branch                      │
│   │  Job    │                                                         │
│   └─────────┘                                                         │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Step 5.1: Create GitHub Repository

If you haven't already, create a GitHub repository:

```bash
# Create repo on GitHub first, then:
git remote add origin git@github.com:YOUR_USERNAME/full-stack.git
git branch -M master
git push -u origin master
```

---

## Step 5.2: Create Azure Service Principal

A Service Principal is like a service account that GitHub Actions uses to deploy to Azure.

**1. Create the Service Principal with Contributor**

```bash
# Get your subscription ID
SUB_ID=$(az account show --query id -o tsv)
echo "Subscription ID: $SUB_ID"

# Create the service principal (Contributor on the subscription)
az ad sp create-for-rbac \
  --name "github-actions-full-stack" \
  --role contributor \
  --scopes /subscriptions/$SUB_ID \
  --sdk-auth
```

This outputs JSON with `clientId`, `clientSecret`, `subscriptionId`, `tenantId`. **Save the `clientId` and `clientSecret`** — you'll add them to GitHub secrets.

**2. Grant permission to create role assignments**

The infrastructure assigns the **AcrPull** role to the Container App's managed identity so it can pull images from the registry. Only an identity with **User Access Administrator** (or Owner) can create role assignments; Contributor is not enough. Grant that to the Service Principal:

```bash
# Use the clientId (Application ID) from the JSON output above
APP_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

az role assignment create \
  --assignee "$APP_ID" \
  --role "User Access Administrator" \
  --scope "/subscriptions/$SUB_ID"
```

Replace `APP_ID` with your Service Principal's **clientId**. After this, the SP can both deploy resources and create the AcrPull role assignment during `azd up`.

---

## Step 5.3: Configure GitHub Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**

Add these secrets (all come from the Service Principal JSON or your subscription):

| Secret Name             | Value                              |
| ----------------------- | ---------------------------------- |
| `AZURE_CLIENT_ID`       | The `clientId` from the JSON       |
| `AZURE_CLIENT_SECRET`   | The `clientSecret` from the JSON   |
| `AZURE_TENANT_ID`       | The `tenantId` from the JSON       |
| `AZURE_SUBSCRIPTION_ID` | The `subscriptionId` from the JSON |

The workflow uses these for both `azure/login` and `azd auth login` (service principal with client secret).

---

## Step 5.4: Create Main CI/CD Workflow

Create `.github/workflows/ci-cd.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [master]

env:
  AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
  AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
  AZURE_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
  AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}

jobs:
  # ============================================
  # Job 1: Run Tests with Coverage
  # ============================================
  test:
    name: "🧪 Tests & Coverage"
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: backend_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install UV
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
          cache-dependency-glob: "backend/uv.lock"

      - name: Install dependencies
        working-directory: ./backend
        run: uv sync --extra test --extra dev

      - name: Wait for PostgreSQL
        run: |
          timeout 30s bash -c 'until pg_isready -h localhost -p 5432 -U postgres; do sleep 1; done'

      - name: Run tests with coverage
        working-directory: ./backend
        run: |
          uv run pytest \
            --cov=app \
            --cov-report=term-missing \
            --cov-report=xml \
            --cov-fail-under=80 \
            -v
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/backend_dev
          DATABASE_TEST_URL: postgres://postgres:postgres@localhost:5432/backend_test
          ENVIRONMENT: dev
          TESTING: 1

  # ============================================
  # Job 2: Code Quality Checks
  # ============================================
  lint:
    name: "📝 Code Quality"
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install UV
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Install dependencies
        working-directory: ./backend
        run: uv sync --extra dev

      - name: Run Ruff linter
        working-directory: ./backend
        run: uv run ruff check .

      - name: Run Ruff formatter check
        working-directory: ./backend
        run: uv run ruff format --check .

  # ============================================
  # Job 3: Deploy to Azure
  # ============================================
  deploy:
    name: "🚀 Deploy to Azure"
    runs-on: ubuntu-latest
    needs: [test, lint]
    if: github.ref == 'refs/heads/master' && github.event_name == 'push'

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install Azure Developer CLI (azd)
        run: |
          curl -fsSL https://aka.ms/install-azd.sh | bash
          echo "$HOME/.azd/bin" >> $GITHUB_PATH

      - name: Log in to Azure
        uses: azure/login@v2
        with:
          creds: '{"clientId":"${{ secrets.AZURE_CLIENT_ID }}","clientSecret":"${{ secrets.AZURE_CLIENT_SECRET }}","subscriptionId":"${{ secrets.AZURE_SUBSCRIPTION_ID }}","tenantId":"${{ secrets.AZURE_TENANT_ID }}"}'

      # The Service Principal must have User Access Administrator (or Owner) so it can create
      # the AcrPull role assignment in backend.bicep. Contributor alone is not enough.
      - name: Deploy to Azure with azd
        run: |
          azd auth login --client-id "$SP_CLIENT_ID" --client-secret "$SP_CLIENT_SECRET" --tenant-id "$SP_TENANT_ID"
          azd env select production || azd env new production
          azd up --no-prompt

        env:
          SP_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
          SP_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
          SP_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
          AZURE_ENV_NAME: production
          AZURE_LOCATION: australiaeast
          AZURE_APP_NAME: full-stack

      - name: Get deployment URL
        id: get-url
        run: |
          URL=$(azd show --output json | jq -r '.services.backend.endpoint // "Not available"')
          echo "deployment-url=$URL" >> $GITHUB_OUTPUT

      - name: Test deployed application
        if: steps.get-url.outputs.deployment-url != 'Not available'
        run: |
          echo "Testing deployment at: ${{ steps.get-url.outputs.deployment-url }}"
          for i in {1..10}; do
            if curl -f "${{ steps.get-url.outputs.deployment-url }}/ping" > /dev/null 2>&1; then
              echo "✅ Deployment is ready!"
              break
            fi
            echo "⏳ Waiting for deployment... (attempt $i/10)"
            sleep 30
          done
          RESPONSE=$(curl -s "${{ steps.get-url.outputs.deployment-url }}/ping")
          echo "Ping response: $RESPONSE"

      - name: Create deployment summary
        run: |
          echo "## 🚀 Deployment Successful!" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Application URL:** ${{ steps.get-url.outputs.deployment-url }}" >> $GITHUB_STEP_SUMMARY
```

> **Note:** Use `branches: [main]` and `refs/heads/main` if your default branch is `main` instead of `master`. Adjust `AZURE_LOCATION` (e.g. `eastus`) if you use a different region.

---

## Step 5.5: Create PR Validation Workflow

This workflow runs on pull requests to catch issues before merging.

Create `.github/workflows/pr-validation.yml`:

````yaml
name: PR Validation

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]

jobs:
  validate:
    name: "✅ Validate PR"
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: backend_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install UV
        uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        working-directory: ./backend
        run: uv sync --extra test --extra dev

      - name: Run linting
        working-directory: ./backend
        run: |
          uv run ruff check .
          uv run ruff format --check .

      - name: Run tests
        working-directory: ./backend
        run: uv run pytest --cov=app --cov-fail-under=80 -v
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/backend_dev
          DATABASE_TEST_URL: postgres://postgres:postgres@localhost:5432/backend_test
          TESTING: 1

      - name: Comment on PR
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const status = '${{ job.status }}' === 'success' ? '✅' : '❌';
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `${status} PR Validation: ${{ job.status }}`
            })

### Create `ACTIONS_PAT` secret

If your PR validation workflow uses `actions/github-script` to post comments and you prefer to use a personal or machine token instead of the automatically provided `GITHUB_TOKEN`, add a repository secret named `ACTIONS_PAT` and reference it in the workflow as `github-token: ${{ secrets.ACTIONS_PAT }}`.

- **Generate a token:** In GitHub go to **Settings → Developer settings → Personal access tokens** (classic) or create a fine-grained token. Grant `repo` (for private repos) or `public_repo` (for public repos). Optionally include `workflow` if your setup needs it.
- **Add the secret:** Repository → **Settings → Secrets and variables → Actions → New repository secret**. Set the name to `ACTIONS_PAT` and paste the token value.
- **Security:** Use a machine/service account or a fine-grained token, set an expiration date, and rotate regularly.

After adding `ACTIONS_PAT` you can configure the `pr-validation.yml` step like this:

```yaml
      - name: Comment on PR
        if: always()
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.ACTIONS_PAT }}
          script: |
            const status = '${{ job.status }}' === 'success' ? '✅' : '❌';
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `${status} PR Validation: ${{ job.status }}`
            })
````

````

---

## Step 5.6: Create Infrastructure Destroy Workflow

Sometimes you need to tear down resources. This workflow does it safely with a manual trigger and uses the same Azure login and azd setup as the CI/CD pipeline.

Create `.github/workflows/destroy-infrastructure.yml`:

```yaml
name: 🗑️ Destroy Infrastructure

on:
  workflow_dispatch:
    inputs:
      environment:
        description: "Environment to destroy"
        required: true
        default: "production"
        type: choice
        options:
          - production
          - dev
          - staging
          - prod
      confirm:
        description: 'Type "DESTROY" to confirm'
        required: true

jobs:
  destroy:
    name: "🗑️ Destroy ${{ github.event.inputs.environment }}"
    runs-on: ubuntu-latest

    # Extra protection for production (requires GitHub environment "production" if configured)
    environment: ${{ github.event.inputs.environment == 'production' && 'production' || '' }}

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Validate confirmation
        if: github.event.inputs.confirm != 'DESTROY'
        run: |
          echo "❌ Confirmation failed. Please type 'DESTROY' to confirm."
          exit 1

      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install Azure Developer CLI (azd)
        run: |
          curl -fsSL https://aka.ms/install-azd.sh | bash
          echo "$HOME/.azd/bin" >> $GITHUB_PATH

      - name: Log in to Azure
        uses: azure/login@v2
        with:
          creds: '{"clientId":"${{ secrets.AZURE_CLIENT_ID }}","clientSecret":"${{ secrets.AZURE_CLIENT_SECRET }}","subscriptionId":"${{ secrets.AZURE_SUBSCRIPTION_ID }}","tenantId":"${{ secrets.AZURE_TENANT_ID }}"}'

      - name: Destroy Infrastructure
        run: |
          azd auth login --client-id "$SP_CLIENT_ID" --client-secret "$SP_CLIENT_SECRET" --tenant-id "$SP_TENANT_ID"
          azd env select "$AZURE_ENV_NAME" || azd env new "$AZURE_ENV_NAME"
          azd down --force --purge --no-prompt
        env:
          SP_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
          SP_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
          SP_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
          AZURE_ENV_NAME: ${{ github.event.inputs.environment }}
          AZURE_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          AZURE_LOCATION: australiaeast
          AZURE_APP_NAME: full-stack

      - name: Cleanup complete
        run: |
          echo "✅ Environment '${{ github.event.inputs.environment }}' has been destroyed."
````

---

## Step 5.7: Push and Test the Pipeline

```bash
git add .
git commit -m "Chapter 5: CI/CD with GitHub Actions"
git push origin main
```

Go to your GitHub repository → **Actions** tab to watch the pipeline run!

---

## Step 5.8: Create a Test Pull Request

```bash
# Create a feature branch
git checkout -b feature/test-pr

# Make a small change
echo "# Test" >> README.md

# Push and create PR
git add .
git commit -m "Test PR validation"
git push origin feature/test-pr
```

Then create a Pull Request on GitHub. The PR validation workflow will run automatically.

---

## ✅ Chapter 5 Checkpoint

You should now have:

- [x] CI pipeline running tests on every push
- [x] Code quality checks in CI
- [x] Auto-deploy to Azure on merge to main
- [x] PR validation workflow
- [x] Manual infrastructure destroy workflow

**Commit your progress:**

```bash
git checkout main
git pull
git add .
git commit -m "Chapter 5: CI/CD with GitHub Actions"
git push
```

---

## 📊 Understanding Workflow Status

On your repository's main page, you'll see a status badge:

- ✅ Green checkmark: All jobs passed
- ❌ Red X: One or more jobs failed
- 🟡 Yellow dot: Workflow is running

You can also add a badge to your README:

```markdown
[![CI/CD Pipeline](https://github.com/YOUR_USERNAME/full-stack/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/YOUR_USERNAME/full-stack/actions)
```

---

## 🔒 Branch Protection (Recommended)

Go to **Settings** → **Branches** → **Add rule**

- Branch name pattern: `main`
- ✅ Require status checks before merging
- ✅ Require branches to be up to date
- Select required checks: `test`, `lint`
- ✅ Require pull request reviews before merging

This ensures:

- No direct pushes to main
- All PRs must pass tests
- Code review is required

---

## 🔍 Debugging Failed Workflows

### View Logs

Click on the failed workflow run → Click on the failed job → Expand the failed step.

### Common Issues

**1. Tests fail in CI but pass locally**

- Different Python version
- Missing environment variables
- Database connection issues

**2. Azure login fails**

- Ensure all four secrets are set: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- Verify the service principal has **Contributor** and **User Access Administrator** (see Step 5.2)
- Check subscription ID

**3. Deployment fails**

- Check Azure Portal for resource errors
- Run `azd up --debug` locally to see detailed output

---

## 📁 Files Created in This Chapter

```
.github/
└── workflows/
    ├── ci-cd.yml              # Main CI/CD pipeline
    ├── pr-validation.yml      # PR checks
    └── destroy-infrastructure.yml  # Cleanup workflow
```

---

## 💡 Advanced Tips

### 1. Parallel Jobs

Jobs without dependencies run in parallel:

```yaml
jobs:
  test: # Runs immediately
  lint: # Runs immediately (parallel with test)
  deploy:
    needs: [test, lint] # Waits for both
```

### 2. Job Matrix

Run tests on multiple Python versions:

```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.12", "3.13"]
```

### 3. Caching Dependencies

UV already handles caching, but for pip:

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### 4. Manual Deployment

Add a manual trigger to any workflow:

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: "Deploy to"
        required: true
        default: "staging"
```

---

[← Chapter 4](./chapter-04-azure-deployment.md) | [Back to Index](./README.md) | [Chapter 6: Azure Auth →](./chapter-06-azure-auth.md)
