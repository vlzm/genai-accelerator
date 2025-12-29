# deploy.ps1 - Quick Azure deployment script
# Run from project root: .\deploy.ps1

param(
    [switch]$Destroy,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  KYC Analyzer - Azure Deployment Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if terraform.tfvars exists
if (-not (Test-Path "infra/terraform.tfvars")) {
    Write-Host "❌ Error: infra/terraform.tfvars not found!" -ForegroundColor Red
    Write-Host "   Copy infra/terraform.tfvars.example to infra/terraform.tfvars" -ForegroundColor Yellow
    Write-Host "   and fill in your values." -ForegroundColor Yellow
    exit 1
}

# Destroy mode
if ($Destroy) {
    Write-Host "🗑️  Destroying Azure resources..." -ForegroundColor Yellow
    Set-Location infra
    terraform destroy -auto-approve
    Set-Location ..
    Write-Host ""
    Write-Host "✅ Resources destroyed!" -ForegroundColor Green
    exit 0
}

# Step 1: Terraform
Write-Host "📦 Step 1: Running Terraform..." -ForegroundColor Cyan
Set-Location infra

terraform init
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Terraform init failed!" -ForegroundColor Red
    Set-Location ..
    exit 1
}

terraform apply -auto-approve
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Terraform apply failed!" -ForegroundColor Red
    Set-Location ..
    exit 1
}

# Step 2: Get outputs
Write-Host ""
Write-Host "📋 Step 2: Getting Terraform outputs..." -ForegroundColor Cyan
$ACR_NAME = terraform output -raw acr_name
$ACR_SERVER = terraform output -raw acr_login_server
$APP_URL = terraform output -raw app_url
$API_URL = terraform output -raw api_url

Set-Location ..

if (-not $SkipBuild) {
    # Step 3: Login to ACR
    Write-Host ""
    Write-Host "🔐 Step 3: Logging into Container Registry..." -ForegroundColor Cyan
    az acr login --name $ACR_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ACR login failed!" -ForegroundColor Red
        exit 1
    }

    # Step 4: Build and push images
    Write-Host ""
    Write-Host "🐳 Step 4: Building and pushing Docker images..." -ForegroundColor Cyan
    
    Write-Host "   Building kyc-app..." -ForegroundColor Gray
    docker build -t "$ACR_SERVER/kyc-app:latest" -f Dockerfile .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker build (app) failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "   Building kyc-api..." -ForegroundColor Gray
    docker build -t "$ACR_SERVER/kyc-api:latest" -f Dockerfile.api .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker build (api) failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "   Pushing images..." -ForegroundColor Gray
    docker push "$ACR_SERVER/kyc-app:latest"
    docker push "$ACR_SERVER/kyc-api:latest"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker push failed!" -ForegroundColor Red
        exit 1
    }

    # Step 5: Restart Container Apps to pull new images
    Write-Host ""
    Write-Host "🔄 Step 5: Restarting Container Apps..." -ForegroundColor Cyan
    $RG_NAME = "rg-kyc-dev"
    az containerapp revision restart --name kyc-app --resource-group $RG_NAME 2>$null
    az containerapp revision restart --name kyc-api --resource-group $RG_NAME 2>$null
}

# Done!
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  ✅ Deployment Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  📱 App URL: $APP_URL" -ForegroundColor Yellow
Write-Host "  🔌 API URL: $API_URL" -ForegroundColor Yellow
Write-Host "  📚 API Docs: $API_URL/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ⚠️  Don't forget to destroy resources when done:" -ForegroundColor Red
Write-Host "      .\deploy.ps1 -Destroy" -ForegroundColor Red
Write-Host ""

