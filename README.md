# **Azure GenAI Accelerator 🚀**

A production-ready template for building GenAI-powered applications on Azure. Provides a secure, scalable foundation with enterprise-grade features out of the box.

## **🏗 Architecture**

### **High-Level Design**

The system is designed with security and scalability in mind:

* **App:** Python monolith (Streamlit UI + FastAPI REST API) running in **Azure Container Apps**
* **Database:** PostgreSQL Flexible Server (stores requests and analysis results)
* **AI:** Multi-provider support (Azure OpenAI, OpenAI, Anthropic, Ollama)
* **Security:**
  * **Network:** Designed for VNET Injection & Private Endpoints
  * **Identity:** 100% Passwordless. Uses **Managed Identities** to fetch secrets from Key Vault

### **Azure Infrastructure Diagram**

```mermaid
flowchart TB
    subgraph Azure["☁️ Azure Subscription"]
        subgraph RG["📦 Resource Group (rg-genai-dev)"]
            
            subgraph Compute["🖥️ Compute Layer"]
                CAE["🌐 Container Apps Environment<br/>─────────────<br/>genai-env-dev"]
                
                subgraph Apps["Container Apps"]
                    API["⚡ genai-api<br/>─────────────<br/>FastAPI :8000<br/>RBAC/ABAC + Managed Identity"]
                    UI["🖥️ genai-app<br/>─────────────<br/>Streamlit :8501<br/>Identity Simulator"]
                end
            end
            
            subgraph Data["💾 Data Layer"]
                PG["🐘 PostgreSQL Flexible Server<br/>─────────────<br/>genai-pg-xxx<br/>pgvector enabled"]
                DB[(app_db)]
            end
            
            subgraph Security["🔐 Security Layer"]
                KV["🔑 Key Vault<br/>─────────────<br/>genai-kv-xxx<br/>• AZURE-OPENAI-API-KEY<br/>• DATABASE-PASSWORD"]
            end
            
            subgraph Registry["📦 Container Registry"]
                ACR["🐳 Azure Container Registry<br/>─────────────<br/>genaiacrxxx<br/>• genai-api:latest<br/>• genai-app:latest"]
            end
            
            subgraph Monitoring["📊 Monitoring"]
                LA["📈 Log Analytics Workspace<br/>─────────────<br/>genai-logs-dev<br/>Container logs & metrics"]
            end
        end
    end
    
    subgraph External["🌍 External Services"]
        LLM["🤖 LLM Provider<br/>─────────────<br/>OpenAI API<br/>Azure OpenAI<br/>Anthropic"]
    end
    
    User["👤 User"]
    CICD["🔄 GitHub Actions<br/>─────────────<br/>CI/CD Pipeline"]

    User -->|HTTPS| UI
    User -->|HTTPS| API
    UI --> API
    
    API -->|"🔐 Managed Identity"| KV
    UI -->|"🔐 Managed Identity"| KV
    
    API --> PG
    UI --> PG
    PG --> DB
    
    API -->|"API Key from KV"| LLM
    
    CAE --> LA
    API --> LA
    UI --> LA
    
    CICD -->|"docker push"| ACR
    ACR -->|"pull image"| API
    ACR -->|"pull image"| UI

    style RG fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style Compute fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style Data fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    style Security fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    style Registry fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Monitoring fill:#e0f7fa,stroke:#00838f,stroke-width:2px
    style External fill:#fafafa,stroke:#616161,stroke-width:2px
```

### **Local Development Diagram (Docker Compose)**

```mermaid
flowchart TB
    subgraph Local["🖥️ Local Machine (Docker Compose)"]
        
        subgraph Containers["🐳 Docker Containers"]
            API["⚡ genai-api<br/>─────────────<br/>FastAPI :8000<br/>RBAC/ABAC enabled"]
            UI["🖥️ genai-app<br/>─────────────<br/>Streamlit :8501<br/>Identity Simulator"]
            PG["🐘 postgres<br/>─────────────<br/>PostgreSQL :5432<br/>pgvector extension"]
        end
        
        subgraph Volumes["💾 Docker Volumes"]
            PGDATA[("postgres_data<br/>─────────────<br/>Persistent DB storage")]
        end
        
        subgraph Config["⚙️ Configuration"]
            ENV[".env file<br/>─────────────<br/>• OPENAI_API_KEY<br/>• LLM_PROVIDER<br/>• DATABASE_URL"]
            CODE["./app<br/>─────────────<br/>Mounted source code<br/>(live reload)"]
        end
    end
    
    subgraph External["🌍 External Services"]
        LLM["🤖 LLM Provider<br/>─────────────<br/>OpenAI API<br/>Anthropic<br/>Ollama (local)"]
    end
    
    User["👤 Developer"]
    Browser["🌐 Browser"]

    User -->|"docker-compose up"| Containers
    Browser -->|"http://localhost:8501"| UI
    Browser -->|"http://localhost:8000/docs"| API
    
    UI -->|"internal network"| API
    API --> PG
    PG --> PGDATA
    
    ENV -.->|"environment"| API
    ENV -.->|"environment"| UI
    CODE -.->|"volume mount"| API
    CODE -.->|"volume mount"| UI
    
    API -->|"API Key from .env"| LLM

    style Local fill:#fff8e1,stroke:#ff8f00,stroke-width:2px
    style Containers fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style Volumes fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style Config fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    style External fill:#fafafa,stroke:#616161,stroke-width:2px
```

### **Comparison: Local vs Azure**

| Aspect | Local (Docker Compose) | Azure (Container Apps) |
|--------|------------------------|------------------------|
| **Secrets** | `.env` file | Key Vault + Managed Identity |
| **Database** | Docker container | PostgreSQL Flexible Server |
| **Logs** | `docker logs` | Log Analytics Workspace |
| **Images** | Local build | Azure Container Registry |
| **Scaling** | Manual | Auto-scaling (0-N replicas) |
| **Cost** | Free | ~$20-25/month |
| **SSL/TLS** | Not included | Automatic HTTPS |
| **Auth** | Mock Identity Provider | Azure Entra ID (production) |
| **RBAC/ABAC** | ✅ Same logic | ✅ Same logic |
| **Use Case** | Development | Production |

### **Request Processing Flow**

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant UI as 🖥️ Streamlit UI
    participant API as ⚡ FastAPI Backend
    participant LLM as 🤖 LLM Provider
    participant VAL as ✅ Validator
    participant DB as 🐘 PostgreSQL

    User->>UI: Enter input text
    UI->>API: POST /analyze
    
    rect rgb(255, 243, 224)
        Note over API: 🔐 RBAC: User has ANALYZE permission?
        Note over API: 🏷️ ABAC: User.group matches data?
    end
    
    API->>DB: Create Request record
    DB-->>API: request_id
    
    API->>LLM: Analyze input (JSON mode)
    
    rect rgb(240, 248, 255)
        Note over API,LLM: 🔧 Optional: Tool/Function Calling
        LLM-->>API: Tool call request
        API->>API: Execute tool (lookup_database, etc.)
        API->>LLM: Tool result
    end
    
    LLM-->>API: {score, categories, reasoning}
    
    API->>VAL: Run validation checks
    VAL-->>API: validation_status (PASS/FAIL)
    
    API->>DB: Save AnalysisResult<br/>(with LLM trace & validation)
    DB-->>API: result_id
    
    API-->>UI: Return JSON response
    
    rect rgb(255, 243, 224)
        Note over UI: 🏷️ ABAC: Filter by group<br/>Hide scores > 70 for Viewers
    end
    
    UI-->>User: Display result card<br/>(color-coded by score)
    
    Note over User,UI: 👍/👎 Human Feedback Loop
    User->>UI: Submit feedback
    UI->>API: POST /feedback
    API->>DB: Update feedback fields
```

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
