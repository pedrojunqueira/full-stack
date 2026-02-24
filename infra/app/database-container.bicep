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
