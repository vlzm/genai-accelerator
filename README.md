# **Azure GenAI Accelerator 🚀**

A production-ready template for building GenAI-powered applications on Azure. Provides a secure, scalable foundation with enterprise-grade features out of the box.

## **🏗 Architecture**

### **High-Level Design**

The system is designed with security and scalability in mind:

* **App:** Python monolith (Streamlit UI + FastAPI REST API) running in **Azure Container Apps**
* **Database:** PostgreSQL Flexible Server (stores requessts and analysis results)
* **AI:** Multi-provider support (Azure OpenAI, OpenAI, Anthropic, Ollama)
* **Security:**
  * **Network:** Designed for VNET Injection & Private Endpoints
  * **Identity:** 100% Passwordless. Uses **Managed Identities** to fetch secrets from Key Vault

### **Security Features**

1. **No Hardcoded Secrets:** Uses DefaultAzureCredential for automatic switching between local env vars (dev) and Managed Identity (cloud)
2. **Network Isolation:** Terraform code supports private endpoint configuration
3. **RBAC:** Role-based permissions (Admin → Senior Analyst → Analyst → Viewer)
4. **ABAC:** Attribute-based filtering (group isolation, score visibility)

## **✨ Key Features**

- 🔐 **Zero Trust Security** - Managed Identity, Key Vault integration
- 🤖 **Multi-LLM Support** - Azure OpenAI, OpenAI, Anthropic, Ollama
- 👤 **RBAC/ABAC Demo** - Role & attribute-based access control
- 🔍 **LLM Observability** - Full tracing for debugging
- 👍 **Human Feedback Loop** - Collect feedback for model improvement
- 🛡️ **Validation Checks** - Automated quality assessment
- 🏗️ **Infrastructure as Code** - Terraform for Azure deployment

## **🚀 Quick Start (Local)**

**Prerequisites:** Docker & Docker Compose

### 1. Clone and configure

```bash
git clone https://github.com/your-org/genai-accelerator.git
cd genai-accelerator
```

### 2. Set up environment

Create a `.env` file (gitignored for security):

```env
# Required: Choose your LLM provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1

# Or use Azure OpenAI
# LLM_PROVIDER=azure
# AZURE_OPENAI_ENDPOINT=https://...
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# Or use Anthropic
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=...

# Or use Ollama (free, local)
# LLM_PROVIDER=ollama
# OLLAMA_MODEL=llama3.2
```

### 3. Run with Docker Compose

```bash
docker-compose up --build
```

- **UI:** http://localhost:8501
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## **☁️ Cloud Deployment (Azure)**

Infrastructure is defined in Terraform for reproducibility.

### Prerequisites

1. **Azure CLI** installed and configured (`az login`)
2. **Terraform** v1.5.0 or higher
3. **Docker** for building images

### Step 1: Configure Terraform Variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
# Required
project_name      = "genai"         # Your project name
environment       = "dev"           # dev, staging, prod
db_admin_password = "YourStrongP@ssw0rd123!"

# LLM Configuration (choose one provider)
llm_provider   = "openai"           # openai, azure, anthropic, ollama
openai_api_key = "sk-..."           # Your API key

# Azure OpenAI (if llm_provider=azure)
# azure_openai_endpoint        = "https://your-resource.openai.azure.com/"
# azure_openai_deployment_name = "gpt-4"
```

### Step 2: Provision Infrastructure

```bash
az login
terraform init
terraform plan    # Review changes
terraform apply   # Create resources
```

This creates:
- **Resource Group** - Logical container for all resources
- **Container Registry (ACR)** - Private Docker registry
- **Key Vault** - Secure secret storage
- **PostgreSQL Flexible Server** - Database with pgvector extension
- **Container Apps Environment** - Serverless container platform
- **Container Apps** - API and UI applications with Managed Identity

### Step 3: Build and Push Docker Images

```bash
# Get ACR name from Terraform output
ACR_NAME=$(terraform output -raw acr_name)
ACR_URL=$(terraform output -raw acr_login_server)

# Login to ACR
az acr login --name $ACR_NAME

# Build and push API
docker build -f Dockerfile.api -t $ACR_URL/genai-api:latest .
docker push $ACR_URL/genai-api:latest

# Build and push UI
docker build -t $ACR_URL/genai-app:latest .
docker push $ACR_URL/genai-app:latest
```

### Step 4: Trigger Container App Deployment

```bash
RG_NAME=$(terraform output -raw resource_group_name)

# Update API Container App
az containerapp update \
  --name genai-api \
  --resource-group $RG_NAME \
  --image $ACR_URL/genai-api:latest

# Update UI Container App
az containerapp update \
  --name genai-app \
  --resource-group $RG_NAME \
  --image $ACR_URL/genai-app:latest
```

### Step 5: Get Application URLs

```bash
terraform output app_url   # Streamlit UI
terraform output api_url   # FastAPI API
```

### CI/CD (GitHub Actions)

The project includes a production-ready CI/CD pipeline. To enable:

1. **Configure Azure OIDC** (passwordless authentication):
   ```bash
   # Create App Registration with federated credentials
   # See: https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure
   ```

2. **Add GitHub Secrets**:
   - `AZURE_CLIENT_ID` - App registration client ID
   - `AZURE_TENANT_ID` - Azure AD tenant ID
   - `AZURE_SUBSCRIPTION_ID` - Azure subscription ID

3. **Push to main branch** - Pipeline automatically builds, tests, and deploys

### Security Features

| Feature | Description |
|---------|-------------|
| Managed Identity | Container Apps authenticate to Key Vault without secrets |
| Key Vault | All API keys and passwords stored securely |
| SSL/TLS | Database connections require SSL |
| OIDC | CI/CD uses passwordless Azure authentication |

## **🛠 Tech Stack**

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| UI | Streamlit |
| API | FastAPI |
| ORM | SQLModel |
| Database | PostgreSQL |
| AI | OpenAI SDK (multi-provider) |
| Infrastructure | Terraform |
| Containers | Docker |

## **📂 Project Structure**

```
/
├── app/                          # Application Source
│   ├── main.py                   # Streamlit entrypoint
│   ├── models.py                 # SQLModel DB schema
│   ├── database.py               # DB connection logic
│   ├── api/                      # FastAPI REST API
│   │   ├── main.py               # API entrypoint
│   │   └── schemas.py            # Pydantic schemas
│   └── services/                 # Business logic
│       ├── processor.py          # Core processing logic
│       ├── validation.py         # Quality checks
│       ├── llm_service.py        # LLM orchestration
│       ├── rag_service.py        # RAG (Retrieval-Augmented Generation)
│       ├── secret_manager.py     # Azure Key Vault integration
│       ├── auth_mock.py          # Mock identity provider
│       ├── llm/                  # LLM providers
│       │   ├── base.py           # Base provider interface
│       │   ├── factory.py        # Provider factory
│       │   ├── openai_provider.py
│       │   ├── azure_provider.py
│       │   ├── anthropic_provider.py
│       │   └── ollama_provider.py
│       └── tools/                # Function calling tools
│           └── definitions.py
├── infra/                        # Terraform (IaC)
│   ├── main.tf                   # Main infrastructure
│   ├── variables.tf              # Input variables
│   ├── outputs.tf                # Output values
│   └── terraform.tfvars.example  # Example config
├── notebooks/                    # Jupyter notebooks
│   ├── test_pipeline.ipynb       # Pipeline testing
│   └── test_chat_mode.ipynb      # Chat mode testing
├── .github/workflows/            # CI/CD
│   └── ci-cd.yml                 # GitHub Actions pipeline
├── Dockerfile                    # Streamlit container
├── Dockerfile.api                # FastAPI container
├── docker-compose.yml            # Local development
├── requirements.txt              # Python dependencies
└── SPEC.md                       # Project specification
```

## **🔧 Customization**

### Adding Your Business Logic

1. **Modify the system prompt** in `app/services/llm/base.py`:
   ```python
   DEFAULT_SYSTEM_PROMPT = """Your custom prompt here..."""
   ```

2. **Update the models** in `app/models.py` for your data structure

3. **Extend the processor** in `app/services/processor.py` with your logic

4. **Add tools** (optional) in `app/services/tools/definitions.py` for function calling

### LLM Provider Configuration

| Provider | Environment Variables |
|----------|----------------------|
| OpenAI | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Azure OpenAI | `LLM_PROVIDER=azure`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME` |
| Anthropic | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| Ollama | `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

## **📊 Observability Features**

- **LLM Tracing:** Full input/output logging for debugging
- **Validation Checks:** Automated quality assessment of responses
- **Human Feedback:** 👍/👎 buttons for collecting training data
- **Evaluation Dashboard:** Track model accuracy over time

## **🔐 Security Model**

### RBAC (Role-Based Access Control)

| Role | VIEW | ANALYZE | VIEW_SENSITIVE | VIEW_ALL_GROUPS | EXPORT |
|------|------|---------|----------------|-----------------|--------|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| Senior Analyst | ✅ | ✅ | ✅ | ✅ | ✅ |
| Analyst | ✅ | ✅ | ✅ | ❌ | ❌ |
| Viewer | ✅ | ❌ | ❌ | ❌ | ❌ |

### ABAC (Attribute-Based Access Control)

| Attribute | Description | Example |
|-----------|-------------|---------|
| `user.group` | Data isolation by group | Analyst in Group A sees only Group A data |
| `score >= 70` | High score visibility | Viewers can't see scores ≥ 70 |

### Demo Users (Mock Identity)

Use the Identity Simulator in the sidebar to switch between:
- `admin_default` - Full access
- `senior_default` - Full access
- `analyst_a` - Group A only
- `analyst_b` - Group B only
- `viewer_a` - View only, Group A

## **📝 License**

MIT License - Use freely for any purpose.
