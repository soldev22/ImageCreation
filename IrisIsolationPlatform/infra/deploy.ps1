param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [Parameter(Mandatory = $true)][SecureString]$PostgresAdminPassword,
    [string]$Location = "uksouth",
    [string]$EnvironmentName = "dev"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$plainPassword = [System.Net.NetworkCredential]::new("", $PostgresAdminPassword).Password

az group create --name $ResourceGroup --location $Location --output none
az deployment group validate --resource-group $ResourceGroup --template-file "$PSScriptRoot/main.bicep" --parameters environmentName=$EnvironmentName location=$Location postgresAdminPassword=$plainPassword | Out-Null
$deployment = az deployment group create --resource-group $ResourceGroup --template-file "$PSScriptRoot/main.bicep" --parameters environmentName=$EnvironmentName location=$Location postgresAdminPassword=$plainPassword --query properties.outputs | ConvertFrom-Json

$registry = $deployment.registryName.value
$apiName = $deployment.apiName.value
$webName = $deployment.webName.value
$apiUrl = $deployment.apiUrl.value

az acr build --registry $registry --image iris-api:latest "$root/backend"
az acr build --registry $registry --image iris-web:latest --build-arg "VITE_API_URL=$apiUrl/api/v1" "$root/frontend"
az containerapp update --name $apiName --resource-group $ResourceGroup --image "$registry.azurecr.io/iris-api:latest" --output none
az containerapp update --name $webName --resource-group $ResourceGroup --image "$registry.azurecr.io/iris-web:latest" --output none

Write-Host "API: $apiUrl"
Write-Host "Web: $($deployment.webUrl.value)"