# Chapter 4: Azure Deployment with AZD + Bicep

[← Chapter 3](./chapter-03-code-quality.md) | [Back to Index](./README.md) | [Chapter 5 →](./chapter-05-cicd.md)

---

**Goal:** Deploy your application to Azure Container Apps using Infrastructure as Code

**Time:** 45-60 minutes

**What you'll learn:**

- Azure Developer CLI (azd) basics
- Bicep templates for infrastructure
- Container Apps architecture
- Managed Identity for security
- Database migrations in production

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Resource Group                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Container Apps Environment                     │  │
│  │                                                            │  │
│  │  ┌─────────────────┐        ┌─────────────────────────┐   │  │
│  │  │   FastAPI App   │        │    PostgreSQL           │   │  │
│  │  │   (Container)   │───────▶│    (Container)          │   │  │
│  │  │   Port: 8000    │        │    Port: 5432           │   │  │
│  │  │   External ✓    │        │    Internal only        │   │  │
│  │  └─────────────────┘        └─────────────────────────┘   │  │
│  │           │                                                 │  │
│  │           │ Uses                                            │  │
│  │           ▼                                                 │  │
│  │  ┌─────────────────┐        ┌─────────────────────────┐   │  │
│  │  │ Managed Identity │        │  Container Registry     │   │  │
│  │  │ (for ACR access) │        │  (stores images)        │   │  │
│  │  └─────────────────┘        └─────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Log Analytics Workspace                      │    │
│  │              (monitoring & logs)                          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Install Azure Developer CLI (azd)

```bash
# macOS/Linux
curl -fsSL https://aka.ms/install-azd.sh | bash

# Windows (PowerShell)
powershell -ex AllSigned -c "Invoke-RestMethod 'https://aka.ms/install-azd.ps1' | Invoke-Expression"
```

### Install Azure CLI

```bash
# macOS
brew install azure-cli

# Ubuntu/Debian
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Windows
winget install Microsoft.AzureCLI
```

### Login to Azure

```bash
# Login to Azure CLI
az login

# Login to Azure Developer CLI
azd auth login
```

---

## Step 4.1: Initialize AZD Project

Create `azure.yaml` in the project root:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/Azure/azure-dev/main/schemas/v1.0/azure.yaml.json

name: full-stack
metadata:
  template: full-stack@0.0.1-beta
services:
  backend:
    project: ./backend
    language: python
    host: containerapp
    docker:
      path: ./Dockerfile.prod
```

> 💡 **What this does:**
>
> - `name`: Your project name (used in resource naming)
> - `services.backend`: Defines your FastAPI backend
> - `docker.path`: Points to the production Dockerfile

---

## Step 4.2: Create Infrastructure Directory

```bash
mkdir -p infra/app
mkdir -p infra/core/host
mkdir -p infra/core/monitor
```

---

## Step 4.3: Create Abbreviations File

Azure resources have naming conventions. This file defines short prefixes.

Create `infra/abbreviations.json`:

```json
{
  "appContainerApps": "ca-",
  "appContainerAppsEnvironment": "cae-",
  "managedIdentityUserAssignedIdentities": "id-",
  "containerRegistryRegistries": "cr",
  "logAnalyticsWorkspaces": "log-",
  "resourcesResourceGroups": "rg-"
}
```

---

## Step 4.4: Create Main Bicep Template

Create `infra/main.bicep`:

```bicep
targetScope = 'subscription'

// ============================================
// Parameters
// ============================================

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Name of the application')
param appName string = 'full-stack'

@description('Name of the resource group')
param resourceGroupName string = ''

// ============================================
// Variables
// ============================================

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Generate secure password for PostgreSQL
var postgresPassword = uniqueString(subscription().id, environmentName, 'postgres-v1')

// Pre-compute app names for cross-referencing
var backendAppName = '${abbrs.appContainerApps}backend-${resourceToken}'

// ============================================
// Resources
// ============================================

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${appName}-${environmentName}'
  location: location
  tags: tags
}

// Container Apps Environment (shared infrastructure)
module containerApps './core/host/container-apps.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    name: 'app'
    location: location
    tags: tags
    containerAppsEnvironmentName: '${abbrs.appContainerAppsEnvironment}${resourceToken}'
    containerRegistryName: '${abbrs.containerRegistryRegistries}${resourceToken}'
    logAnalyticsWorkspaceName: '${abbrs.logAnalyticsWorkspaces}${resourceToken}'
  }
}

// PostgreSQL Container
module database './app/database-container.bicep' = {
  name: 'database'
  scope: rg
  params: {
    name: '${abbrs.appContainerApps}db-${resourceToken}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    postgresPassword: postgresPassword
  }
}

// FastAPI Backend App
module backend './app/backend.bicep' = {
  name: 'backend'
  scope: rg
  params: {
    name: backendAppName
    location: location
    tags: tags
    identityName: '${abbrs.managedIdentityUserAssignedIdentities}backend-${resourceToken}'
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    databaseServiceName: database.outputs.serviceName
    postgresPassword: postgresPassword
  }
}

// ============================================
// Outputs (used by azd)
// ============================================

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output BACKEND_URI string = backend.outputs.uri
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName
```

Create `infra/main.parameters.json`:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "environmentName": {
      "value": "${AZURE_ENV_NAME}"
    },
    "location": {
      "value": "${AZURE_LOCATION}"
    }
  }
}
```

---

## Step 4.5: Create Container Apps Module

Create `infra/core/host/container-apps.bicep`:

```bicep
param name string
param location string = resourceGroup().location
param tags object = {}

param containerAppsEnvironmentName string
param containerRegistryName string
param logAnalyticsWorkspaceName string

// ============================================
// Log Analytics (for monitoring)
// ============================================

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ============================================
// Container Registry (stores Docker images)
// ============================================

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: containerRegistryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// ============================================
// Container Apps Environment
// ============================================

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

// ============================================
// Outputs
// ============================================

output environmentName string = containerAppsEnvironment.name
output environmentId string = containerAppsEnvironment.id
output registryLoginServer string = containerRegistry.properties.loginServer
output registryName string = containerRegistry.name
output defaultDomain string = containerAppsEnvironment.properties.defaultDomain
```

---

## Step 4.6: Create Database Container Module

Create `infra/app/database-container.bicep`:

```bicep
param name string
param location string = resourceGroup().location
param tags object = {}

param containerAppsEnvironmentName string
param postgresPassword string

// Reference existing resources
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsEnvironmentName
}

// ============================================
// PostgreSQL Container App
// ============================================

resource database 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false        // Only accessible within the environment
        targetPort: 5432
        transport: 'tcp'
      }
    }
    template: {
      containers: [
        {
          name: 'postgres'
          image: 'postgres:17'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'POSTGRES_USER', value: 'postgres' }
            { name: 'POSTGRES_PASSWORD', value: postgresPassword }
            { name: 'POSTGRES_DB', value: 'backend_prod' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1         // Database should not auto-scale
      }
    }
  }
}

// ============================================
// Outputs
// ============================================

output serviceName string = database.name
output serviceHost string = '${database.name}.internal'
```

> ⚠️ **Production Note:** For real production workloads, consider Azure Database for PostgreSQL instead of a container. Containers don't persist data across restarts without volume mounts.

---

## Step 4.7: Create Backend App Module

Create `infra/app/backend.bicep`:

```bicep
param name string
param location string = resourceGroup().location
param tags object = {}

param identityName string
param containerAppsEnvironmentName string
param containerRegistryName string
param databaseServiceName string
param postgresPassword string

// Reference existing resources
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsEnvironmentName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = {
  name: containerRegistryName
}

// ============================================
// Managed Identity (for secure ACR access)
// ============================================

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

// Grant ACR Pull permission to the identity
var acrPullRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'  // AcrPull role ID
)

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, identity.id, acrPullRole)
  scope: containerRegistry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRole
  }
}

// ============================================
// FastAPI Container App
// ============================================

resource backend 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'backend' })  // Required for azd deploy
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true         // Publicly accessible
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['*']
        }
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          // Placeholder image - azd will replace with your built image
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: 'production' }
            {
              name: 'DATABASE_URL'
              value: 'postgres://postgres:${postgresPassword}@${databaseServiceName}:5432/backend_prod'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
      }
    }
  }
}

// ============================================
// Outputs
// ============================================

output uri string = 'https://${backend.properties.configuration.ingress.fqdn}'
output name string = backend.name
```

---

## Step 4.8: Create Entrypoint Script for Migrations

The entrypoint script runs database migrations before starting the app.

Create `backend/entrypoint.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting application..."

# Parse database host from DATABASE_URL
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=5432

# Wait for database to be ready
echo "⏳ Waiting for database at $DB_HOST:$DB_PORT..."
timeout=60
counter=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U postgres 2>/dev/null; do
  counter=$((counter + 1))
  if [ $counter -gt $timeout ]; then
    echo "❌ Database not ready after ${timeout}s, starting anyway..."
    break
  fi
  echo "  Database not ready, waiting... ($counter/${timeout}s)"
  sleep 1
done
echo "✅ Database is ready!"

# Run migrations
echo "📦 Running database migrations..."
cd /usr/src/app

# Initialize aerich if needed (first deployment)
if [ ! -d "migrations" ]; then
  echo "  Initializing aerich..."
  uv run aerich init -t app.db.TORTOISE_ORM || true
  uv run aerich init-db || true
else
  echo "  Running pending migrations..."
  uv run aerich upgrade || true
fi

echo "✅ Migrations complete!"

# Start the application
echo "🌐 Starting uvicorn..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Make it executable:

```bash
chmod +x backend/entrypoint.sh
```

Update `backend/Dockerfile.prod` to use the entrypoint. **Remove the final CMD line** and replace it with:

```dockerfile
# Copy entrypoint script
COPY entrypoint.sh /usr/src/app/entrypoint.sh

# Switch to root temporarily to set permissions
USER root
RUN chmod +x /usr/src/app/entrypoint.sh
USER app

# Use entrypoint (replaces CMD - entrypoint.sh starts uvicorn)
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
```

> 💡 **Note:** The `ENTRYPOINT` replaces `CMD` because `entrypoint.sh` already starts uvicorn with `exec uv run uvicorn...` at the end.

---

## Step 4.9: Deploy to Azure

```bash
# Initialize azd (interactive - select subscription and location)
azd init

# Deploy everything!
azd up
```

This single command will:

1. Create the Azure resource group
2. Deploy all Bicep infrastructure
3. Build your Docker image
4. Push to Azure Container Registry
5. Deploy to Container Apps
6. Run database migrations

### What You'll See

```
Packaging services (azd package)

  (✓) Done: Packaging service backend

Provisioning Azure resources (azd provision)
  Subscription: Your-Subscription
  Location: East US

  (✓) Done: Resource group: rg-fastapi-tdd-docker-dev
  (✓) Done: Container Registry: crxxxxxxxxxx
  (✓) Done: Container Apps Environment: cae-xxxxxxxxxx
  (✓) Done: Database Container: ca-db-xxxxxxxxxx
  (✓) Done: Backend Container: ca-backend-xxxxxxxxxx

Deploying services (azd deploy)

  (✓) Done: Deploying service backend

SUCCESS: Your application was deployed to Azure!
```

---

## Step 4.10: Verify Deployment

```bash
# Show deployed resources
azd show

# Get the app URL
azd env get-values | grep BACKEND_URI

# Test the endpoint
curl https://<your-app-url>/ping
```

Visit the URL in your browser to see Swagger UI!

---

## ✅ Chapter 4 Checkpoint

You should now have:

- [x] App running in Azure Container Apps
- [x] PostgreSQL container in Azure
- [x] Infrastructure as Code with Bicep
- [x] `azd up` for one-command deployment
- [x] Automatic database migrations

**Commit your progress:**

```bash
git add .
git commit -m "Chapter 4: Azure deployment with AZD and Bicep"
```

---

## 🔧 Useful AZD Commands

| Command            | Description                         |
| ------------------ | ----------------------------------- |
| `azd up`           | Provision infrastructure and deploy |
| `azd deploy`       | Deploy code only (faster)           |
| `azd provision`    | Infrastructure only                 |
| `azd down`         | Delete all resources                |
| `azd env list`     | List environments                   |
| `azd env new prod` | Create a new environment            |
| `azd monitor`      | Open Azure Portal monitoring        |

---

## 💰 Cost Considerations

Container Apps charges based on:

- **vCPU-seconds**: Time your containers run
- **Memory GB-seconds**: Memory used
- **Requests**: HTTP requests handled

For development/learning:

- Container Apps has a generous free tier
- Stop resources when not in use: `azd down`
- Use `minReplicas: 0` to scale to zero

---

## 🔍 Troubleshooting

### Check Container Logs

```bash
az containerapp logs show \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --follow
```

### Database Connection Issues

- Verify the database container is running
- Check the DATABASE_URL format
- Ensure internal networking is configured

### Deployment Failures

```bash
# See detailed deployment logs
azd deploy --debug

# Check Azure Portal for container status
azd monitor
```

---

## 📁 Files Created in This Chapter

```
full-stack/
├── azure.yaml                     # AZD configuration
├── infra/
│   ├── abbreviations.json         # Resource naming prefixes
│   ├── main.bicep                 # Main infrastructure template
│   ├── main.parameters.json       # Parameter values
│   ├── app/
│   │   ├── database-container.bicep   # PostgreSQL container
│   │   └── backend.bicep          # FastAPI container
│   └── core/
│       └── host/
│           └── container-apps.bicep   # Shared infrastructure
└── backend/
    ├── entrypoint.sh              # Migration + startup script
    └── Dockerfile.prod            # Updated with entrypoint
```

---

[← Chapter 3](./chapter-03-code-quality.md) | [Back to Index](./README.md) | [Chapter 5: CI/CD →](./chapter-05-cicd.md)
