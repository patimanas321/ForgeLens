@description('Name of the Container App Job')
param name string

@description('Location for the resource')
param location string

@description('Tags for the resource')
param tags object = {}

@description('Container Apps Environment ID')
param containerAppsEnvironmentId string

@description('Container Registry name')
param containerRegistryName string

@description('Container image name')
param imageName string

@description('Cron schedule expression')
param schedule string = '0 9,18 * * *'

@description('API URL to call')
param apiUrl string

// Get reference to container registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = {
  name: containerRegistryName
}

// Container App Job - runs workflow on schedule
resource containerAppJob 'Microsoft.App/jobs@2023-05-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      replicaTimeout: 1800 // 30 minutes max
      replicaRetryLimit: 1
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: schedule
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'scheduler'
          image: 'curlimages/curl:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          command: [
            '/bin/sh'
            '-c'
            'curl -X POST "${API_URL}/api/workflow/run" -H "Content-Type: application/json" -d \'{"category": "technology", "dryRun": false}\' --max-time 1800'
          ]
          env: [
            {
              name: 'API_URL'
              value: apiUrl
            }
          ]
        }
      ]
    }
  }
}

output id string = containerAppJob.id
output name string = containerAppJob.name
