# **Technical Design Document: Azure GenAI Accelerator**

## **1. Project Overview**

* **Name:** Azure GenAI Accelerator
* **Purpose:** A production-ready template for building GenAI-powered applications on Azure
* **Key Features:** Multi-LLM support, enterprise security, observability, human feedback loop

## **2. Architectural Strategy**

### **2.1 Target Production Architecture**

* **Compute:** Azure Container Apps inside a VNET
* **Database:** PostgreSQL Flexible Server with **Private Endpoint** (No public access)
* **Auth:** Full Managed Identity (AD Token) for DB connection
* **Network:** All traffic remains within the Azure Backbone

### **2.2 Local Development Architecture**

* **Compute:** Docker Compose
* **Database:** PostgreSQL container with local password auth
* **Auth:** Environment variables for API keys
* **AI:** Configurable LLM provider (OpenAI, Azure, Anthropic, Ollama)

## **3. Technology Stack**

* **Language:** Python 3.11+
* **UI:** Streamlit
* **API:** FastAPI
* **Database:** SQLModel (SQLAlchemy + Pydantic)
* **AI:** Multi-provider support via custom wrapper (no LangChain)
* **Infrastructure:** Terraform
* **Containerization:** Docker (multi-stage builds)

## **4. Security Implementation**

### **4.1 Identity Management (No Hardcoded Secrets)**

Zero Trust principle - no passwords or API keys in codebase.

1. **App Identity:** Container App uses SystemAssigned Managed Identity
2. **Access:** Identity granted Key Vault Secrets User role via Terraform
3. **Runtime:** Application uses DefaultAzureCredential for Key Vault access

### **4.2 Network Security**

* **Local:** PostgreSQL exposed on localhost only
* **Production:** Private Endpoint for PostgreSQL (no public access)

### **4.3 Access Control**

* **RBAC:** Role-based permissions (Admin, Senior, Officer, Viewer)
* **ABAC:** Attribute-based filtering (Region, Clearance Level)

## **5. Project Structure**

```
/
├── app/
│   ├── main.py               # Streamlit UI entrypoint
│   ├── api/
│   │   ├── main.py           # FastAPI REST API
│   │   └── schemas.py        # API request/response schemas
│   ├── models.py             # SQLModel database models
│   ├── database.py           # Database connection logic
│   └── services/
│       ├── processor.py      # Core business logic
│       ├── validation.py     # Output quality checks
│       ├── llm_service.py    # High-level LLM interface
│       ├── llm/
│       │   ├── base.py       # Abstract provider base
│       │   ├── openai_provider.py
│       │   ├── azure_provider.py
│       │   ├── anthropic_provider.py
│       │   └── ollama_provider.py
│       ├── auth_mock.py      # Mock identity provider
│       ├── secret_manager.py # Key Vault wrapper
│       └── tools/            # LLM function calling (examples)
├── infra/
│   ├── main.tf               # Azure resources
│   ├── variables.tf          # Terraform variables
│   └── outputs.tf            # Terraform outputs
├── Dockerfile                # Streamlit container
├── Dockerfile.api            # FastAPI container
├── docker-compose.yml        # Local development
└── requirements.txt          # Python dependencies
```

## **6. Key Patterns**

### **A. Database Connection (Hybrid Auth)**

```python
# app/services/secret_manager.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os

def get_secret(secret_name: str) -> str:
    # LOCAL DEV: Fallback to environment variable
    if os.getenv("ENV") == "LOCAL":
        return os.environ.get(secret_name)
    
    # CLOUD PROD: Use Managed Identity
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url="https://<vault>.vault.azure.net", credential=credential)
    return client.get_secret(secret_name).value
```

### **B. LLM Provider Abstraction**

```python
# All providers implement BaseLLMProvider
class BaseLLMProvider(ABC):
    @abstractmethod
    def _call_api(self, messages, temperature, max_tokens) -> str:
        pass
    
    def analyze(self, input_text, context=None) -> LLMResponse:
        # Common analysis logic with tracing
        pass
```

### **C. Observability**

Every analysis includes:
- **LLM Trace:** Full input/output for debugging
- **Validation Status:** Automated quality checks
- **Human Feedback:** Fields for collecting training data

## **7. Configuration**

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment mode | `LOCAL` |
| `LLM_PROVIDER` | AI provider | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `DATABASE_HOST` | PostgreSQL host | `db` |
| `DATABASE_PASSWORD` | DB password | - |

### LLM Providers

| Provider | Config Variables |
|----------|-----------------|
| openai | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| azure | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME` |
| anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

## **8. Customization Guide**

### Adding Your Use Case

1. **System Prompt:** Edit `DEFAULT_SYSTEM_PROMPT` in `app/services/llm/base.py`
2. **Data Models:** Modify `Request` and `AnalysisResult` in `app/models.py`
3. **Processing Logic:** Extend `Processor` in `app/services/processor.py`
4. **Validation Rules:** Add checks in `app/services/validation.py`
5. **Tools (optional):** Define function calling tools in `app/services/tools/`

### Adding a New LLM Provider

1. Create `app/services/llm/new_provider.py` extending `BaseLLMProvider`
2. Implement `_call_api()` and `get_model_version()`
3. Register in `app/services/llm/factory.py`

## **9. Running the Application**

### Local Development

```bash
# Start all services
docker-compose up --build

# UI: http://localhost:8501
# API: http://localhost:8000/docs
```

### Azure Deployment

```bash
cd infra
terraform init
terraform apply -auto-approve
```

## **10. API Reference**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Submit data for AI analysis |
| `/results` | GET | List analysis results |
| `/results/{id}` | GET | Get specific result |
| `/feedback` | POST | Submit human feedback |
| `/feedback/stats` | GET | Model evaluation stats |
| `/health` | GET | Health check |
