# **Technical Design Document: Secure KYC/AML Analyzer**

## **1\. Project Overview**

* **Name:** Secure KYC/AML Analyzer  
* **Business Goal:** An internal compliance tool for detecting risk in transaction comments using GenAI.  
* **Critical Constraint:** Handling PII (Personally Identifiable Information) requires strict network isolation and zero-trust identity management.

## **2\. Architectural Strategy (MVP vs Production)**

To balance the strict 2-hour timeline with high-security requirements, I have designed a roadmap that starts with a functional MVP and scales to a fully isolated Production environment.

### **2.1 Target Production Architecture (The Goal)**

* **Compute:** Azure Container Apps inside a VNET.  
* **Database:** PostgreSQL Flexible Server with **Private Endpoint** (No public access).  
* **Auth:** Full Managed Identity (AD Token) for DB connection.  
* **Network:** All traffic remains within the Azure Backbone.

### **2.2 Interview MVP Architecture (The Demo)**

* **Compute:** Azure Container Apps.  
* **Database:** PostgreSQL Flexible Server with **Firewall Rules** (Allowing only Azure Services).  
  * *Reasoning:* Private Endpoint deployment takes \~45+ minutes, which exceeds the interview window. The Firewall Rule strategy allows for a live demo within 15 minutes while maintaining a secure baseline.  
* **Auth:** Managed Identity used to fetch secrets from **Azure Key Vault**.  
  * *Reasoning:* Using Key Vault is "Enterprise Secure" (no secrets in code) but less brittle to implement quickly than raw AD Token injection into SQLAlchemy drivers.

## **3\. Technology Stack**

* **Language:** Python 3.11+  
* **UI/Logic:** **Streamlit** (Acting as a monolithic app for MVP, consuming internal Service classes).  
* **Database:** **SQLModel** (SQLAlchemy \+ Pydantic).  
* **AI:** **Azure OpenAI** (via custom wrapper, no LangChain).  
* **Infrastructure:** **Terraform**.  
* **Containerization:** Docker (Slim-buster based).

## **4\. Security Implementation Details**

### **4.1 Identity Management (No Hardcoded Secrets)**

We strictly follow the **Zero Trust** principle. No passwords or API keys are stored in the codebase or environment variables.

1. **App Identity:** The Container App is assigned a SystemAssigned Managed Identity.  
2. **Access:** This Identity is granted Key Vault Secrets User role via Terraform.  
3. **Runtime:** The application uses DefaultAzureCredential to authenticate against Key Vault and retrieve the Database Password and OpenAI Key at runtime.

### **4.2 Network Security**

* **MVP:** PostgreSQL public\_network\_access\_enabled \= true BUT restricted via start\_ip\_address \= 0.0.0.0 (Azure Services Only).  
* **Production Code (Commented out):** The Terraform file contains the azurerm\_private\_endpoint block definition to demonstrate knowledge of strict isolation.

## **5\. Implementation Structure**

The project follows a **Service-Repository pattern** to ensure logic can be easily moved to a separate FastAPI backend in the future.

/  
├── app/  
│   ├── main.py           \# Streamlit Entrypoint  
│   ├── models.py         \# SQLModel Database Schema  
│   ├── database.py       \# DB Connection (Key Vault logic)  
│   ├── services/  
│   │   ├── llm\_service.py   \# Custom OpenAI Wrapper (System Prompts, JSON mode)  
│   │   ├── risk\_engine.py   \# Business Logic (Risk scoring)  
│   │   └── secret\_manager.py \# Wrapper for Key Vault  
│   └── .dockerignore  
├── infra/  
│   ├── main.tf           \# All resources definition  
│   ├── iam.tf            \# Role Assignments (RBAC)  
│   └── output.tf  
├── Dockerfile            \# Single stage for speed  
├── requirements.txt  
└── README.md

## **6\. Key Code Patterns**

### **A. Database Connection (Hybrid Auth)**

The code detects the environment. Local dev uses env vars; Cloud uses Managed Identity.

\# app/services/secret\_manager.py  
from azure.identity import DefaultAzureCredential  
from azure.keyvault.secrets import SecretClient  
import os

def get\_secret(secret\_name: str) \-\> str:  
    \# LOCAL DEV: Fallback to environment variable if configured  
    if os.getenv("ENV") \== "LOCAL":  
        return os.environ.get(secret\_name)  
          
    \# CLOUD PROD: Use Managed Identity  
    credential \= DefaultAzureCredential()  
    client \= SecretClient(vault\_url="https://\<vault\>.vault.azure.net", credential=credential)  
    return client.get\_secret(secret\_name).value

### **B. LLM Wrapper (Control & Observability)**

We avoid LangChain to ensure we handle Azure 429 Too Many Requests errors and maintain full control over the System Prompt.

\# app/services/llm\_service.py  
\# Custom implementation using openai\>=1.0.0  
\# Features:  
\# 1\. Enforces JSON output for structured parsing.  
\# 2\. Sanitizes PII before sending (Mock implementation).  
\# 3\. Implements basic retry logic.

## **7\. Development Roadmap (Execution Plan)**

This project was executed in 3 phases within the 2-hour assessment window.

### **Phase 1: Local Core (0-45 min)**

* **Goal:** Validate business logic (LLM Wrapper, Pydantic parsing) and DB schema.  
* **Env:** Python App runs on **Host (venv)** \+ Database runs in **Docker**.  
* **Auth:** Uses .env file (gitignored) for OpenAI Keys and DB password.

### **Phase 2: Containerization (45-60 min)**

* **Goal:** Ensure reproducibility and prepare for Cloud deployment.  
* **Action:** Packaged the Python App into a Dockerfile and validated the build.  
* **Result:** Application runs in full isolation on localhost:8501.

### **Phase 3: Cloud Infrastructure & Security (60-120 min)**

* **Goal:** Provision secure infrastructure.  
* **Action:** Wrote Terraform manifests for Azure Container Apps and Flexible Postgres.  
* **Security Switch:** Implemented DefaultAzureCredential logic to switch from .env (Local) to Managed Identity (Cloud).

## **8\. How to Run**

### **Option A: Local Development (Docker Compose)**

*Simulates the environment without Azure dependency.*

\# 1\. Create a .env file with your keys (not committed)  
\# 2\. Run the stack  
docker-compose up \--build

### **Option B: Deployment (Azure)**

*Deploys the secure infrastructure.*

1. **Infrastructure:**  
   cd infra  
   \# Requires: az login  
   terraform init && terraform apply \-auto-approve

2. **Code Delivery:**  
   az acr login \--name \<acr\_name\>  
   docker build \-t \<acr\_name\>.azurecr.io/kyc-analyzer:v1 .  
   docker push \<acr\_name\>.azurecr.io/kyc-analyzer:v1  
