# 📋 Interview Cheatsheet

Quick reference for common commands used in this project.

---

## 1. 🖥️ Terminal (PowerShell / Bash)

```powershell
# Set Python path (Windows PowerShell)
$env:PYTHONPATH = "."

# Set Python path (Linux/Mac)
export PYTHONPATH=.

# Run Streamlit locally
streamlit run app/main.py

# Run FastAPI locally
uvicorn app.api.main:app --reload --port 8000

# Check which process uses a port (Windows)
netstat -ano | findstr :8501
taskkill /F /PID <PID>

# Check which process uses a port (Linux/Mac)
lsof -i :8501
kill -9 <PID>

# Create virtual environment
python -m venv .venv

# Activate venv (Windows)
.\.venv\Scripts\Activate

# Activate venv (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Freeze current dependencies
pip freeze > requirements.txt
```

---

## 2. 🐳 Docker

```bash
# Build and start all services
docker-compose up -d --build

# Build and start specific services
docker-compose up -d --build app api

# Start services (without rebuild)
docker-compose up -d

# Stop all services
docker-compose down

# Stop and remove volumes (CAUTION: deletes DB data!)
docker-compose down -v

# View running containers
docker-compose ps
docker ps

# View logs (all services)
docker-compose logs -f

# View logs (specific service)
docker-compose logs -f app
docker-compose logs -f api
docker-compose logs -f db

# Restart a specific service
docker-compose restart app

# Execute command inside container
docker exec -it genai-app bash
docker exec -it genai-api bash
docker exec -it genai-postgres bash

# Remove all stopped containers
docker container prune

# Remove all unused images
docker image prune -a

# Remove all unused volumes
docker volume prune

# Full cleanup (CAUTION!)
docker system prune -a --volumes
```

---

## 3. 🔧 Git

```bash
# Clone repository
git clone <repo-url>

# Check status
git status

# Add all changes
git add .

# Commit with message
git commit -m "feat: add new feature"

# Push to remote
git push origin main

# Pull latest changes
git pull origin main

# Create new branch
git checkout -b feature/new-feature

# Switch branch
git checkout main

# Merge branch
git merge feature/new-feature

# View commit history
git log --oneline

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Stash changes
git stash
git stash pop

# View diff
git diff
git diff --staged
```

### Conventional Commit Prefixes
| Prefix | Description |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation |
| `style:` | Formatting (no code change) |
| `refactor:` | Code restructuring |
| `test:` | Adding tests |
| `chore:` | Maintenance tasks |

---

## 4. ☁️ Azure CLI

```powershell
# Login to Azure
az login

# Set subscription
az account set --subscription "<subscription-id>"

# List subscriptions
az account list --output table

# Check current subscription
az account show --query name -o tsv
```

### Container Apps

```powershell
# List Container Apps
az containerapp list --resource-group $RG_NAME --output table

# Show Container App details
az containerapp show --name genai-api --resource-group $RG_NAME

# View logs (live)
az containerapp logs show --name genai-api --resource-group $RG_NAME --follow

# View last 50 log lines
az containerapp logs show --name genai-api --resource-group $RG_NAME --tail 50

# Restart Container App
az containerapp revision restart --name genai-api --resource-group $RG_NAME `
  --revision $(az containerapp revision list --name genai-api --resource-group $RG_NAME --query "[0].name" -o tsv)

# Update Container App image
az containerapp update --name genai-api --resource-group $RG_NAME --image $ACR_URL/genai-api:latest

# Scale Container App
az containerapp update --name genai-api --resource-group $RG_NAME --min-replicas 1 --max-replicas 3
```

### Key Vault

```powershell
# List secrets
az keyvault secret list --vault-name $KV_NAME --output table

# Get secret value
az keyvault secret show --vault-name $KV_NAME --name "AZURE-OPENAI-API-KEY" --query value -o tsv

# Set secret value
az keyvault secret set --vault-name $KV_NAME --name "AZURE-OPENAI-API-KEY" --value "sk-xxx"

# List deleted (soft-deleted) Key Vaults
az keyvault list-deleted --query "[].name" -o table

# Purge deleted Key Vault
az keyvault purge --name $KV_NAME --no-wait
```

### Container Registry (ACR)

```powershell
# Login to ACR
az acr login --name $ACR_NAME

# Build image in Azure (NO Docker Desktop needed!)
az acr build --registry $ACR_NAME --image genai-api:latest --file Dockerfile.api .
az acr build --registry $ACR_NAME --image genai-app:latest --file Dockerfile .

# List images in ACR
az acr repository list --name $ACR_NAME --output table

# Show image tags
az acr repository show-tags --name $ACR_NAME --repository genai-api --output table
```

### PostgreSQL

```powershell
# List PostgreSQL servers
az postgres flexible-server list --resource-group $RG_NAME --output table

# Show server status
az postgres flexible-server show --name $PG_NAME --resource-group $RG_NAME --query "state" -o tsv

# Add firewall rule (allow your IP)
az postgres flexible-server firewall-rule create `
  --resource-group $RG_NAME --name $PG_NAME `
  --rule-name AllowMyIP --start-ip-address <your-ip> --end-ip-address <your-ip>
```

### Resource Providers

```powershell
# Register provider
az provider register --namespace Microsoft.App

# Check registration status
az provider show -n Microsoft.App --query "registrationState" -o tsv

# List all registered providers
az provider list --query "[?registrationState=='Registered'].namespace" -o table
```

### Resource Groups

```powershell
# Create resource group
az group create --name rg-genai-dev --location westeurope

# Delete resource group (CAUTION!)
az group delete --name rg-genai-dev --yes --no-wait

# Check deletion status
az group show --name rg-genai-dev --query "properties.provisioningState" -o tsv
```

---

## 5. 🏗️ Terraform

### Basic Commands

```powershell
# Initialize Terraform
terraform init

# Upgrade providers
terraform init -upgrade

# Validate configuration
terraform validate

# Format files
terraform fmt -recursive

# Plan changes (preview)
terraform plan

# Apply changes
terraform apply

# Apply with auto-approve (CAUTION!)
terraform apply -auto-approve

# Destroy infrastructure (CAUTION!)
terraform destroy

# Destroy specific resource
terraform destroy -target=azurerm_container_app.api
```

### State Management

```powershell
# Show current state
terraform show

# List resources in state
terraform state list

# Remove resource from state (doesn't delete in Azure!)
terraform state rm azurerm_key_vault.main

# Import existing resource into state
terraform import azurerm_key_vault.main "/subscriptions/xxx/resourceGroups/rg-genai-dev/providers/Microsoft.KeyVault/vaults/genai-kv-xxx"

# Clear state (start fresh)
Remove-Item terraform.tfstate, terraform.tfstate.backup -Force
```

### Outputs

```powershell
# Get all outputs
terraform output

# Get specific output
terraform output -raw acr_name
terraform output -raw api_url
terraform output -raw app_url
terraform output -raw resource_group_name

# Save outputs to variables
$RG_NAME = terraform output -raw resource_group_name
$ACR_NAME = terraform output -raw acr_name
$ACR_URL = terraform output -raw acr_login_server
$API_URL = terraform output -raw api_url
$APP_URL = terraform output -raw app_url
```

### Troubleshooting

```powershell
# If state lock error
Remove-Item .terraform.tfstate.lock.info -Force

# If plan is slow (10+ min), check provider has:
# skip_provider_registration = true

# If "resource already exists" error - import it:
terraform import azurerm_resource_group.main "/subscriptions/xxx/resourceGroups/rg-genai-dev"

# If region restricted for PostgreSQL, change location:
# location = "westeurope"  # instead of "eastus"
```

---

## 6. 🚀 Full Azure Deploy Script

```powershell
# === AZURE DEPLOY SCRIPT ===

# 0. Set secrets (via env vars, NOT in files!)
$env:TF_VAR_db_admin_password = "MyStr0ng!P@ssw0rd2024"
$env:TF_VAR_openai_api_key = "sk-proj-xxx"

# 1. Terraform
cd c:\Users\zamko\Documents\vlzm\kyc-analyzer\infra
terraform init
terraform apply -auto-approve

# 2. Get outputs
$RG_NAME = terraform output -raw resource_group_name
$ACR_NAME = terraform output -raw acr_name

# 3. Build images in Azure (no Docker Desktop needed!)
cd c:\Users\zamko\Documents\vlzm\kyc-analyzer
az acr build --registry $ACR_NAME --image genai-api:latest --file Dockerfile.api .
az acr build --registry $ACR_NAME --image genai-app:latest --file Dockerfile .

# 4. Restart Container Apps
az containerapp revision restart --name genai-api --resource-group $RG_NAME `
  --revision $(az containerapp revision list --name genai-api --resource-group $RG_NAME --query "[0].name" -o tsv)
az containerapp revision restart --name genai-app --resource-group $RG_NAME `
  --revision $(az containerapp revision list --name genai-app --resource-group $RG_NAME --query "[0].name" -o tsv)

# 5. Show URLs
cd c:\Users\zamko\Documents\vlzm\kyc-analyzer\infra
Write-Host "`n=== DEPLOYMENT COMPLETE ===" -ForegroundColor Green
Write-Host "API: $(terraform output -raw api_url)/docs" -ForegroundColor Cyan
Write-Host "APP: $(terraform output -raw app_url)" -ForegroundColor Cyan
```

---

## 7. 🗑️ Cleanup Script

```powershell
# Delete all Azure resources
az group delete --name rg-genai-dev --yes --no-wait

# Clear Terraform state
cd c:\Users\zamko\Documents\vlzm\kyc-analyzer\infra
Remove-Item terraform.tfstate, terraform.tfstate.backup -Force -ErrorAction SilentlyContinue

# Purge soft-deleted Key Vault (optional)
az keyvault purge --name genai-kv-xxx --no-wait
```

---

## 8. 🐘 PostgreSQL

```bash
# Connect via psql (inside container)
docker exec -it genai-postgres psql -U appdbadmin -d app_db
```

```sql
-- List all databases
\l

-- Connect to database
\c app_db

-- List all tables
\dt

-- Describe table structure
\d requests
\d analysis_results

-- Show all records
SELECT * FROM requests;
SELECT * FROM analysis_results;

-- Exit psql
\q
```

---

## 9. 🔐 Environment Variables

### Local Development (.env file)

```env
ENV=local
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=app_db
DATABASE_USER=appdbadmin
DATABASE_PASSWORD=your_password

# LLM Provider (choose one)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4.1

# Or Azure OpenAI
# LLM_PROVIDER=azure
# AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
# AZURE_OPENAI_API_KEY=xxx
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# RAG (optional)
RAG_ENABLED=true
EMBEDDING_MODEL=text-embedding-3-small
```

### Terraform Variables (via env, NOT in files!)

```powershell
$env:TF_VAR_db_admin_password = "MyStr0ng!P@ssw0rd2024"
$env:TF_VAR_openai_api_key = "sk-proj-xxx"
```

---

## 10. 📊 Quick URLs

| Service | Local | Azure |
|---------|-------|-------|
| Streamlit UI | http://localhost:8501 | `terraform output app_url` |
| FastAPI Docs | http://localhost:8000/docs | `terraform output api_url`/docs |
| PostgreSQL | localhost:5432 | `terraform output postgres_host` |

---

## 11. 🔧 Common Issues & Fixes

| Problem | Solution |
|---------|----------|
| Terraform plan slow (10+ min) | Add `skip_provider_registration = true` to provider |
| "LocationIsOfferRestricted" | Change `location = "westeurope"` in tfvars |
| "MissingSubscriptionRegistration" | `az provider register --namespace Microsoft.App` |
| "resource already exists" | `terraform import <resource> <id>` |
| State lock error | `Remove-Item .terraform.tfstate.lock.info -Force` |
| ACR login fails (no Docker) | Use `az acr build` instead of docker build |
| Container App not starting | Check logs: `az containerapp logs show --name xxx ...` |
| Key Vault "already exists" | Purge: `az keyvault purge --name xxx` |

---

## 12. 🎯 Interview Quick Answers

### "Why skip_provider_registration?"
> Azure provider by default registers ~60 providers on each plan = 10-20 min. With skip + explicit registration of only needed providers, plan takes seconds.

### "Why random suffix in resource names?"
> ACR, Key Vault, PostgreSQL require globally unique names. Random suffix prevents conflicts.

### "Why Managed Identity instead of secrets?"
> Zero Trust security. No passwords stored anywhere. Container App gets temporary tokens via Azure AD.

### "Why OIDC in CI/CD?"
> No long-lived secrets in GitHub. Token generated on-the-fly, expires in minutes.

### "Why scale-to-zero?"
> Cost optimization. Pay only when app is used. Cold start ~30-60 sec.

### "How to rollback deployment?"
> Each image tagged with git SHA. Run: `az containerapp update --image xxx:previous_sha`

---

💡 **Tip:** Keep this file open during interviews for quick reference!
