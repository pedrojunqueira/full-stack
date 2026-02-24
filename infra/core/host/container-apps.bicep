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
