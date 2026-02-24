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
