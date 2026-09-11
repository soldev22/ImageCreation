@description('Deployment environment name used in deterministic resource names.')
param environmentName string = 'dev'

@description('Azure region. Revalidate service availability before deployment.')
param location string = 'uksouth'

@secure()
@minLength(16)
param postgresAdminPassword string

@description('PostgreSQL administrator login.')
param postgresAdminLogin string = 'irisadmin'

@description('Allowed browser origin; update after the web app FQDN is known.')
param allowedOrigin string = 'https://localhost'

var resourceToken = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var acrName = 'azcr${resourceToken}'
var identityName = 'azid${resourceToken}'
var storageName = 'azst${resourceToken}'
var vaultName = 'azkv${resourceToken}'
var postgresName = 'azpg${resourceToken}'
var environmentResourceName = 'azcae${resourceToken}'
var apiName = 'azapi${resourceToken}'
var webName = 'azweb${resourceToken}'
var logName = 'azlog${resourceToken}'
var databaseName = 'iris'
var postgresConnection = 'postgresql+asyncpg://${postgresAdminLogin}:${postgresAdminPassword}@${postgresName}.postgres.database.azure.com:5432/${databaseName}?ssl=require'

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'AcrPull')
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_ZRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource imageContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'iris-images'
  properties: { publicAccess: 'None' }
}

resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, 'StorageBlobDataContributor')
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: vaultName
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    publicNetworkAccess: 'Enabled'
  }
}

resource secretsOfficer 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, 'KeyVaultSecretsOfficer')
  scope: vault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  }
}

resource postgresSecret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = {
  parent: vault
  name: 'postgres-connection'
  properties: { value: postgresConnection }
  dependsOn: [secretsOfficer]
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresName
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '17'
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    authConfig: { activeDirectoryAuth: 'Disabled', passwordAuth: 'Enabled' }
    backup: { backupRetentionDays: 14, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    storage: { storageSizeGB: 32 }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: databaseName
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

resource azureServicesFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logName
  location: location
  properties: {
    retentionInDays: 30
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
    sku: { name: 'PerGB2018' }
  }
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentResourceName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource api 'Microsoft.App/containerApps@2025-01-01' = {
  name: apiName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: containerEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        corsPolicy: { allowedOrigins: [allowedOrigin], allowedMethods: ['GET', 'POST'], allowedHeaders: ['Authorization', 'Content-Type', 'X-Correlation-ID'] }
      }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
      secrets: [{ name: 'postgres-connection', keyVaultUrl: postgresSecret.properties.secretUri, identity: identity.id }]
    }
    template: {
      containers: [{
        name: 'api'
        image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        resources: { cpu: json('1.0'), memory: '2Gi' }
        env: [
          { name: 'IRIS_ENVIRONMENT', value: 'production' }
          { name: 'IRIS_DATABASE_URL', secretRef: 'postgres-connection' }
          { name: 'IRIS_STORAGE_BACKEND', value: 'azure' }
          { name: 'IRIS_AZURE_STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
          { name: 'IRIS_ALLOWED_ORIGINS', value: allowedOrigin }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 5, rules: [{ name: 'http', http: { metadata: { concurrentRequests: '10' } } }] }
    }
  }
  dependsOn: [acrPull, blobContributor, secretsOfficer, database, azureServicesFirewall]
}

resource web 'Microsoft.App/containerApps@2025-01-01' = {
  name: webName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: containerEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8080, transport: 'auto', allowInsecure: false, corsPolicy: { allowedOrigins: [allowedOrigin], allowedMethods: ['GET'], allowedHeaders: ['*'] } }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
    }
    template: {
      containers: [{ name: 'web', image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest', resources: { cpu: json('0.5'), memory: '1Gi' } }]
      scale: { minReplicas: 1, maxReplicas: 3, rules: [{ name: 'http', http: { metadata: { concurrentRequests: '50' } } }] }
    }
  }
  dependsOn: [acrPull]
}

output apiName string = api.name
output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output webName string = web.name
output webUrl string = 'https://${web.properties.configuration.ingress.fqdn}'
output registryName string = registry.name
output identityClientId string = identity.properties.clientId
output storageAccountName string = storage.name
output postgresServerName string = postgres.name
