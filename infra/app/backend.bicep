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
