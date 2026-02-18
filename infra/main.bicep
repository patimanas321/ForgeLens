targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, staging, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Azure OpenAI endpoint URL')
param azureOpenAIEndpoint string = ''

@description('GPT model deployment name')
param gptDeployment string = 'gpt-4o'

@description('DALL-E model deployment name')
param dalleDeployment string = 'dall-e-3'

@description('NewsAPI.org API key (optional)')
@secure()
param newsApiKey string = ''

@description('GNews.io API key (optional)')
@secure()
param gnewsApiKey string = ''

@description('NewsData.io API key (optional)')
@secure()
param newsDataApiKey string = ''

@description('Instagram username (optional)')
@secure()
param instagramUsername string = ''

@description('Instagram password (optional)')
@secure()
param instagramPassword string = ''

// Tags for all resources
var tags = {
  'azd-env-name': environmentName
  'app': 'forgelens'
  'environment': environmentName
}

// Generate unique suffix for resource names
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// Resource group
resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// Container Apps Environment with Log Analytics
module containerAppsEnvironment './modules/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  scope: rg
  params: {
    name: 'cae-${resourceToken}'
    location: location
    tags: tags
  }
}

// Container Registry
module containerRegistry './modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: rg
  params: {
    name: 'cr${resourceToken}'
    location: location
    tags: tags
  }
}

// ForgeLens API Container App
module api './modules/container-app.bicep' = {
  name: 'forgelens-api'
  scope: rg
  params: {
    name: 'forgelens-api'
    location: location
    tags: tags
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.id
    containerRegistryName: containerRegistry.outputs.name
    imageName: 'forgelens-api'
    targetPort: 8080
    env: [
      {
        name: 'ASPNETCORE_ENVIRONMENT'
        value: 'Production'
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: azureOpenAIEndpoint
      }
      {
        name: 'AZURE_OPENAI_DEPLOYMENT'
        value: gptDeployment
      }
      {
        name: 'AZURE_OPENAI_DALLE_DEPLOYMENT'
        value: dalleDeployment
      }
      {
        name: 'OUTPUT_DIRECTORY'
        value: '/app/artifacts/images'
      }
      {
        name: 'NEWS_API_KEY'
        secretRef: 'news-api-key'
      }
      {
        name: 'GNEWS_API_KEY'
        secretRef: 'gnews-api-key'
      }
      {
        name: 'NEWSDATA_API_KEY'
        secretRef: 'newsdata-api-key'
      }
      {
        name: 'INSTAGRAM_USERNAME'
        secretRef: 'instagram-username'
      }
      {
        name: 'INSTAGRAM_PASSWORD'
        secretRef: 'instagram-password'
      }
    ]
    secrets: [
      {
        name: 'news-api-key'
        value: newsApiKey
      }
      {
        name: 'gnews-api-key'
        value: gnewsApiKey
      }
      {
        name: 'newsdata-api-key'
        value: newsDataApiKey
      }
      {
        name: 'instagram-username'
        value: instagramUsername
      }
      {
        name: 'instagram-password'
        value: instagramPassword
      }
    ]
  }
}

// Scheduled Job for twice-daily runs
module scheduledJob './modules/container-app-job.bicep' = {
  name: 'forgelens-scheduler'
  scope: rg
  params: {
    name: 'forgelens-scheduler'
    location: location
    tags: tags
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.id
    containerRegistryName: containerRegistry.outputs.name
    imageName: 'forgelens-api'
    schedule: '0 9,18 * * *'  // 9 AM and 6 PM UTC daily
    apiUrl: api.outputs.uri
  }
}

// Outputs
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvironment.outputs.name
output SERVICE_API_URI string = api.outputs.uri
output SERVICE_API_NAME string = api.outputs.name
