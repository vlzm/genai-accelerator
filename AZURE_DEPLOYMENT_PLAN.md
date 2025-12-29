# 🚀 Azure Deployment Plan - KYC Analyzer

**Goal**: Deploy KYC Analyzer to Azure securely and cost-effectively.  
**Time Estimate**: 30-45 minutes (after initial setup)

---

## ⚠️ COST PROTECTION (DO THIS FIRST!)

### Step 1: Set Budget Alert (5 min)

1. Go to [Azure Portal](https://portal.azure.com)
2. Search for **"Cost Management + Billing"**
3. Click **"Budgets"** → **"+ Add"**
4. Configure:
   - **Name**: `kyc-analyzer-budget`
   - **Amount**: `$10` (or your limit)
   - **Reset period**: Monthly
5. Add **Alert conditions**:
   - At 50% → Email alert
   - At 80% → Email alert
   - At 100% → Email alert
6. Enter your email and click **Create**

### Step 2: Use Free/Cheap Resources

| Resource | Free Tier / Cheap Option | Monthly Cost |
|----------|--------------------------|--------------|
| Container Apps | First 2M requests free | ~$0-5 |
| PostgreSQL Flexible | Burstable B1ms (1 vCPU, 2GB) | ~$12-15 |
| Key Vault | 10,000 operations free | ~$0 |
| Container Registry | Basic tier | ~$5 |
| **Total Estimate** | | **~$15-25/month** |

### Step 3: Destroy After Testing!

```bash
# ALWAYS destroy resources after testing!
terraform destroy -auto-approve
```

---

## 📋 QUICK DEPLOYMENT CHECKLIST

```
□ Step 0: Install prerequisites (Azure CLI, Terraform)
□ Step 1: Login to Azure & set subscription
□ Step 2: Create Terraform files
□ Step 3: Run terraform init & apply
□ Step 4: Build & push Docker images
□ Step 5: Verify deployment
□ Step 6: DESTROY resources when done!
```

---

## 🛠️ PREREQUISITES (One-time setup)

### Install Azure CLI

```powershell
# Windows (PowerShell as Admin)
winget install Microsoft.AzureCLI

# Or download from: https://aka.ms/installazurecliwindows
```

### Install Terraform

```powershell
# Windows (PowerShell as Admin)
winget install HashiCorp.Terraform

# Or download from: https://www.terraform.io/downloads
```

### Verify installations

```bash
az --version
terraform --version
```

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Azure Login (2 min)

```bash
# Login to Azure
az login

# List subscriptions
az account list --output table

# Set your subscription (use the ID from above)
az account set --subscription "<subscription-id>"

# Verify
az account show --output table
```

### Step 2: Create Terraform Structure (5 min)

Create folder `infra/` with these files:

```
infra/
├── main.tf           # Main resources
├── variables.tf      # Input variables
├── outputs.tf        # Output values
└── terraform.tfvars  # Your values (DON'T COMMIT!)
```

### Step 3: Run Terraform (10-15 min)

```bash
cd infra

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply (creates resources)
terraform apply

# Save outputs for later
terraform output -json > ../azure-outputs.json
```

### Step 4: Build & Push Docker Images (5 min)

```bash
# Get ACR login credentials from Terraform output
ACR_NAME=$(terraform output -raw acr_name)
ACR_LOGIN_SERVER=$(terraform output -raw acr_login_server)

# Login to ACR
az acr login --name $ACR_NAME

# Build and push images
docker build -t $ACR_LOGIN_SERVER/kyc-app:latest -f Dockerfile .
docker build -t $ACR_LOGIN_SERVER/kyc-api:latest -f Dockerfile.api .

docker push $ACR_LOGIN_SERVER/kyc-app:latest
docker push $ACR_LOGIN_SERVER/kyc-api:latest
```

### Step 5: Verify Deployment (2 min)

```bash
# Get app URLs from Terraform output
terraform output app_url
terraform output api_url

# Test endpoints
curl $(terraform output -raw api_url)/health
```

### Step 6: CLEANUP (Important!)

```bash
# Destroy ALL resources to stop billing
terraform destroy -auto-approve

# Verify no resources left
az group list --output table
```

---

## 📁 TERRAFORM FILES

### `infra/variables.tf`

```hcl
variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "kyc"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"  # Cheapest region
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "db_admin_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}
```

### `infra/terraform.tfvars` (CREATE THIS - DON'T COMMIT!)

```hcl
project_name      = "kyc"
location          = "eastus"
environment       = "dev"
db_admin_password = "YourSecurePassword123!"  # Change this!
openai_api_key    = "sk-xxx"                  # Your OpenAI key
```

### `infra/main.tf`

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
}

# ============================================
# RESOURCE GROUP
# ============================================
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# ============================================
# CONTAINER REGISTRY (for Docker images)
# ============================================
resource "azurerm_container_registry" "main" {
  name                = "${var.project_name}acr${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"  # Cheapest tier ~$5/month
  admin_enabled       = true     # For simple auth
}

# ============================================
# KEY VAULT (for secrets)
# ============================================
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = "${var.project_name}-kv-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Allow current user to manage secrets
  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = [
      "Get", "List", "Set", "Delete", "Purge"
    ]
  }
}

# Store OpenAI API key in Key Vault
resource "azurerm_key_vault_secret" "openai_key" {
  name         = "openai-api-key"
  value        = var.openai_api_key
  key_vault_id = azurerm_key_vault.main.id
}

# ============================================
# POSTGRESQL FLEXIBLE SERVER
# ============================================
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "${var.project_name}-postgres-${var.environment}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = "kycadmin"
  administrator_password = var.db_admin_password
  
  # Cheapest tier: Burstable B1ms (~$12/month)
  sku_name               = "B_Standard_B1ms"
  storage_mb             = 32768  # 32GB minimum
  
  # Allow Azure services to connect
  zone = "1"
}

# Firewall rule - allow Azure services
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Create database
resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "kyc_db"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Enable pgvector extension
resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "vector"
}

# ============================================
# LOG ANALYTICS (for Container Apps)
# ============================================
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.project_name}-logs-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# ============================================
# CONTAINER APPS ENVIRONMENT
# ============================================
resource "azurerm_container_app_environment" "main" {
  name                       = "${var.project_name}-env-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

# ============================================
# CONTAINER APP - API (FastAPI)
# ============================================
resource "azurerm_container_app" "api" {
  name                         = "${var.project_name}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    min_replicas = 0  # Scale to zero when not in use (saves money!)
    max_replicas = 1

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/kyc-api:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "ENV"
        value = "production"
      }
      env {
        name  = "DATABASE_HOST"
        value = azurerm_postgresql_flexible_server.main.fqdn
      }
      env {
        name  = "DATABASE_PORT"
        value = "5432"
      }
      env {
        name  = "DATABASE_NAME"
        value = azurerm_postgresql_flexible_server_database.main.name
      }
      env {
        name  = "DATABASE_USER"
        value = azurerm_postgresql_flexible_server.main.administrator_login
      }
      env {
        name        = "DATABASE_PASSWORD"
        secret_name = "db-password"
      }
      env {
        name  = "LLM_PROVIDER"
        value = "openai"
      }
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-key"
      }
      env {
        name  = "OPENAI_MODEL"
        value = "gpt-4.1"
      }
    }
  }

  secret {
    name  = "db-password"
    value = var.db_admin_password
  }

  secret {
    name  = "openai-key"
    value = var.openai_api_key
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }
}

# ============================================
# CONTAINER APP - UI (Streamlit)
# ============================================
resource "azurerm_container_app" "app" {
  name                         = "${var.project_name}-app"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "app"
      image  = "${azurerm_container_registry.main.login_server}/kyc-app:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "ENV"
        value = "production"
      }
      env {
        name  = "DATABASE_HOST"
        value = azurerm_postgresql_flexible_server.main.fqdn
      }
      env {
        name  = "DATABASE_PORT"
        value = "5432"
      }
      env {
        name  = "DATABASE_NAME"
        value = azurerm_postgresql_flexible_server_database.main.name
      }
      env {
        name  = "DATABASE_USER"
        value = azurerm_postgresql_flexible_server.main.administrator_login
      }
      env {
        name        = "DATABASE_PASSWORD"
        secret_name = "db-password"
      }
      env {
        name  = "LLM_PROVIDER"
        value = "openai"
      }
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-key"
      }
      env {
        name  = "OPENAI_MODEL"
        value = "gpt-4.1"
      }
      env {
        name  = "RAG_ENABLED"
        value = "true"
      }
    }
  }

  secret {
    name  = "db-password"
    value = var.db_admin_password
  }

  secret {
    name  = "openai-key"
    value = var.openai_api_key
  }

  ingress {
    external_enabled = true
    target_port      = 8501

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }
}
```

### `infra/outputs.tf`

```hcl
output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "app_url" {
  value = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "api_url" {
  value = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "postgres_host" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "keyvault_name" {
  value = azurerm_key_vault.main.name
}
```

### `infra/.gitignore` (IMPORTANT!)

```
*.tfvars
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl
```

---

## 🏃 QUICK DEPLOY SCRIPT

Create `deploy.ps1` for one-click deployment:

```powershell
# deploy.ps1 - Quick Azure deployment script

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting Azure Deployment..." -ForegroundColor Cyan

# Step 1: Terraform
Set-Location infra
terraform init
terraform apply -auto-approve

# Step 2: Get outputs
$ACR_NAME = terraform output -raw acr_name
$ACR_SERVER = terraform output -raw acr_login_server

# Step 3: Build & Push
Set-Location ..
az acr login --name $ACR_NAME

docker build -t "$ACR_SERVER/kyc-app:latest" -f Dockerfile .
docker build -t "$ACR_SERVER/kyc-api:latest" -f Dockerfile.api .

docker push "$ACR_SERVER/kyc-app:latest"
docker push "$ACR_SERVER/kyc-api:latest"

# Step 4: Show URLs
Set-Location infra
Write-Host ""
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "📱 App URL: $(terraform output -raw app_url)" -ForegroundColor Yellow
Write-Host "🔌 API URL: $(terraform output -raw api_url)" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  Don't forget to run 'terraform destroy' when done!" -ForegroundColor Red
```

---

## 🎯 INTERVIEW STRATEGY (2-hour limit)

### If asked to deploy to Azure during interview:

| Phase | Time | Action |
|-------|------|--------|
| **Prep** | Before | Have Terraform files ready, Azure CLI logged in |
| **1** | 5 min | Create Resource Group manually in Portal |
| **2** | 10 min | `terraform apply` (while explaining architecture) |
| **3** | 5 min | Push Docker images |
| **4** | 5 min | Verify & demo |
| **5** | End | `terraform destroy` |

### Pro Tips:
1. **Pre-create terraform.tfvars** with your secrets before interview
2. **Test the deployment once** before the interview day
3. **Keep this plan open** during interview for quick reference
4. **Explain WHY** as you go (security, cost, architecture decisions)

---

## 🔒 SECURITY NOTES (For Interview Discussion)

Explain these points during deployment:

1. **Secrets in Key Vault** - "We store API keys in Key Vault, not in code"
2. **Managed Identity** - "In production, we'd use Managed Identity instead of passwords"
3. **Private Networking** - "PostgreSQL uses Azure-internal networking, no public exposure"
4. **Minimal Permissions** - "Container Apps only get the secrets they need"
5. **Scale to Zero** - "min_replicas=0 saves costs when not in use"

---

## 💰 COST SUMMARY

| Resource | Tier | Estimated Cost |
|----------|------|----------------|
| Container Apps | Consumption | $0-5/month |
| PostgreSQL | B1ms Burstable | ~$12/month |
| Container Registry | Basic | ~$5/month |
| Key Vault | Standard | ~$0/month |
| Log Analytics | Pay-per-GB | ~$0-2/month |
| **TOTAL** | | **~$17-25/month** |

⚠️ **ALWAYS run `terraform destroy` after testing!**

---

## 🆘 TROUBLESHOOTING

### "Container App won't start"
```bash
# Check logs
az containerapp logs show --name kyc-app --resource-group rg-kyc-dev --follow
```

### "Can't connect to PostgreSQL"
```bash
# Check firewall rules
az postgres flexible-server firewall-rule list --resource-group rg-kyc-dev --server-name kyc-postgres-dev
```

### "Terraform state locked"
```bash
# Force unlock (use with caution)
terraform force-unlock <LOCK_ID>
```

### "ACR login failed"
```bash
# Get credentials manually
az acr credential show --name kycacrdev
```

