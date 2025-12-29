# 🚀 KYC Analyzer - Command Cheat Sheet

Quick reference for common commands used in this project.

---

## 1. Terminal (PowerShell / Bash)

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

## 2. Docker

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
docker exec -it kyc-app bash
docker exec -it kyc-api bash
docker exec -it kyc-postgres bash

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

## 3. Git

```bash
# Clone repository
git clone <repo-url>

# Check status
git status

# Add all changes
git add .

# Add specific file
git add <filename>

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

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Stash changes
git stash
git stash pop

# View diff
git diff
git diff --staged

# Conventional Commit Prefixes
# feat:     New feature
# fix:      Bug fix
# docs:     Documentation
# style:    Formatting (no code change)
# refactor: Code restructuring
# test:     Adding tests
# chore:    Maintenance tasks
```

---

## 4. Azure CLI

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "<subscription-id>"

# List subscriptions
az account list --output table

# --- Container Apps ---

# List Container Apps
az containerapp list --resource-group <rg-name> --output table

# Show Container App details
az containerapp show --name <app-name> --resource-group <rg-name>

# View Container App logs
az containerapp logs show --name <app-name> --resource-group <rg-name> --follow

# Restart Container App
az containerapp revision restart --name <app-name> --resource-group <rg-name>

# --- Key Vault ---

# List secrets in Key Vault
az keyvault secret list --vault-name <vault-name> --output table

# Get secret value
az keyvault secret show --vault-name <vault-name> --name <secret-name> --query value -o tsv

# Set secret value
az keyvault secret set --vault-name <vault-name> --name <secret-name> --value "<value>"

# --- PostgreSQL Flexible Server ---

# List PostgreSQL servers
az postgres flexible-server list --output table

# Connect to PostgreSQL (requires firewall rule)
az postgres flexible-server connect -n <server-name> -u <admin-user> -d <database>

# --- Managed Identity ---

# List user-assigned identities
az identity list --resource-group <rg-name> --output table

# Assign identity to Container App
az containerapp identity assign --name <app-name> --resource-group <rg-name> --user-assigned <identity-id>

# --- Resource Groups ---

# Create resource group
az group create --name <rg-name> --location eastus

# Delete resource group (CAUTION!)
az group delete --name <rg-name> --yes --no-wait
```

---

## 5. SQL (PostgreSQL)

```bash
# Connect via psql (inside container)
docker exec -it kyc-postgres psql -U kyc_user -d kyc_db

# Connect via psql (from host, if exposed)
psql -h localhost -p 5432 -U kyc_user -d kyc_db
```

```sql
-- List all databases
\l

-- Connect to database
\c kyc_db

-- List all tables
\dt

-- Describe table structure
\d transactions
\d risk_reports

-- Show all transactions
SELECT * FROM transactions;

-- Show all risk reports
SELECT * FROM risk_reports;

-- Show reports with high risk
SELECT id, transaction_id, risk_score, risk_level, region 
FROM risk_reports 
WHERE risk_level IN ('HIGH', 'CRITICAL')
ORDER BY risk_score DESC;

-- Show reports needing review (guardrail failed or no feedback)
SELECT id, risk_score, risk_level, guardrail_status, human_feedback 
FROM risk_reports 
WHERE guardrail_status != 'PASS' OR human_feedback IS NULL;

-- Count reports by risk level
SELECT risk_level, COUNT(*) as count 
FROM risk_reports 
GROUP BY risk_level 
ORDER BY count DESC;

-- Count feedback stats
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN human_feedback = true THEN 1 ELSE 0 END) as positive,
    SUM(CASE WHEN human_feedback = false THEN 1 ELSE 0 END) as negative
FROM risk_reports 
WHERE human_feedback IS NOT NULL;

-- Show transactions by region
SELECT region, COUNT(*) as count 
FROM transactions 
GROUP BY region;

-- Delete all data (CAUTION!)
TRUNCATE transactions CASCADE;
TRUNCATE risk_reports CASCADE;

-- Exit psql
\q
```

---

## 6. Terraform (Infrastructure)

```bash
# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Plan changes (preview)
terraform plan

# Apply changes
terraform apply

# Apply with auto-approve (CAUTION!)
terraform apply -auto-approve

# Destroy infrastructure (CAUTION!)
terraform destroy

# Show current state
terraform show

# List resources in state
terraform state list

# Format Terraform files
terraform fmt -recursive

# Import existing resource
terraform import <resource_type>.<name> <resource_id>
```

---

## 7. Quick Project Commands

```bash
# === FULL LOCAL SETUP ===
docker-compose down -v          # Clean start
docker-compose up -d --build    # Build everything

# === ACCESS POINTS ===
# Streamlit UI:  http://localhost:8501
# FastAPI Docs:  http://localhost:8000/docs
# PostgreSQL:    localhost:5432

# === VIEW LOGS ===
docker-compose logs -f app      # Streamlit logs
docker-compose logs -f api      # FastAPI logs
docker-compose logs -f db       # PostgreSQL logs

# === DATABASE ACCESS ===
docker exec -it kyc-postgres psql -U kyc_user -d kyc_db

# === REBUILD AFTER CODE CHANGES ===
docker-compose up -d --build app api
```

---

## 8. Environment Variables

```bash
# Required for local development (.env file)
ENV=local
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=kyc_db
DATABASE_USER=kyc_user
DATABASE_PASSWORD=kyc_secure_password_123

# LLM Provider (choose one)
LLM_PROVIDER=openai              # Options: azure, openai, anthropic, ollama
OPENAI_API_KEY=sk-xxx            # For OpenAI
OPENAI_MODEL=gpt-4.1             # Model to use

# Azure OpenAI (alternative)
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# RAG (optional)
RAG_ENABLED=true
EMBEDDING_MODEL=text-embedding-3-small
```

---

💡 **Tip**: Keep this file open during interviews for quick reference!

