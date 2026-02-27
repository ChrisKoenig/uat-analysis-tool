// ============================================================================
// GCS Infrastructure — Main Deployment
// Provisions ALL Azure resources for the GCS UAT Management System.
//
// Usage:
//   az deployment sub create \
//     --location northcentralus \
//     --template-file infrastructure/bicep/main.bicep \
//     --parameters infrastructure/bicep/main.bicepparam
//
// Resources created:
//   - Resource Group
//   - Cosmos DB (NoSQL) with 10 containers
//   - Azure OpenAI with GPT-4o + Embedding deployments
//   - Key Vault (RBAC-enabled)
//   - Storage Account + blob container
//   - Application Insights + Log Analytics
//   - Container Registry (ACR)
//   - Container Apps Environment + 4 Container Apps
//   - User-assigned Managed Identity
// ============================================================================

targetScope = 'subscription'

// ── Parameters ──────────────────────────────────────────────────────────────

@description('Azure region for all resources')
param location string = 'northcentralus'

@description('Environment label (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Short project name — used in resource naming')
@maxLength(6)
param projectName string = 'gcs'

@description('Owner email — applied as a tag on every resource')
param owner string

@description('Azure AD tenant for user-facing MSAL authentication')
param msalTenantId string

@description('MSAL app registration client ID')
param msalClientId string

@description('IP addresses to allowlist on Key Vault firewall (CIDR, e.g. 73.169.198.241/32)')
param kvAllowedIps string[] = []

@description('Azure OpenAI model deployments to create')
type openAiDeploymentType = {
  @description('Deployment name (referenced in app config)')
  name: string
  @description('Model name, e.g. gpt-4o or text-embedding-3-large')
  model: string
  @description('Model version, e.g. 2024-08-06')
  version: string
  @description('Capacity in thousands of tokens-per-minute')
  capacity: int
  @description('SKU name — Standard, GlobalStandard, etc.')
  skuName: string
}

param openAiDeployments openAiDeploymentType[] = [
  {
    name: 'gpt-4o-standard'
    model: 'gpt-4o'
    version: '2024-08-06'
    capacity: 30
    skuName: 'GlobalStandard'
  }
  {
    name: 'text-embedding-3-large'
    model: 'text-embedding-3-large'
    version: '1'
    capacity: 120
    skuName: 'Standard'
  }
]

// ── Resource Group ──────────────────────────────────────────────────────────

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${projectName}-${environment}'
  location: location
  tags: {
    Environment: environment
    Project: projectName
    Owner: owner
    Purpose: 'AI-Powered UAT Management System'
  }
}

// ── Module: All resources inside the RG ─────────────────────────────────────

module resources 'resources.bicep' = {
  scope: rg
  params: {
    location: location
    environment: environment
    projectName: projectName
    owner: owner
    msalTenantId: msalTenantId
    msalClientId: msalClientId
    kvAllowedIps: kvAllowedIps
    openAiDeployments: openAiDeployments
  }
}

// ── Outputs (consumed by deploy script & app config) ────────────────────────

output resourceGroupName string = rg.name

// Identity
output managedIdentityName string = resources.outputs.managedIdentityName
output managedIdentityClientId string = resources.outputs.managedIdentityClientId
output managedIdentityPrincipalId string = resources.outputs.managedIdentityPrincipalId

// Data
output cosmosAccountName string = resources.outputs.cosmosAccountName
output cosmosEndpoint string = resources.outputs.cosmosEndpoint
output cosmosDatabaseName string = resources.outputs.cosmosDatabaseName

// AI
output openAiAccountName string = resources.outputs.openAiAccountName
output openAiEndpoint string = resources.outputs.openAiEndpoint

// Security
output keyVaultName string = resources.outputs.keyVaultName
output keyVaultUri string = resources.outputs.keyVaultUri

// Storage
output storageAccountName string = resources.outputs.storageAccountName

// Monitoring
output appInsightsName string = resources.outputs.appInsightsName
output appInsightsConnectionString string = resources.outputs.appInsightsConnectionString
output logAnalyticsName string = resources.outputs.logAnalyticsName

// Containers
output containerRegistryName string = resources.outputs.containerRegistryName
output containerRegistryLoginServer string = resources.outputs.containerRegistryLoginServer
output containerAppsEnvName string = resources.outputs.containerAppsEnvName
