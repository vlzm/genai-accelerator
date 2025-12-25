# **Secure KYC/AML Analyzer 🛡️**

A GenAI-powered compliance tool for analyzing suspicious transaction comments, built with **Zero Trust** architecture principles.

**Context:** This project was developed as a 2-hour technical assessment. It demonstrates a secure, scalable MVP for handling sensitive PII data in a banking environment.

## **🏗 Architecture**

### **High-Level Design**

The system is designed to run in a strictly isolated environment to protect banking secrets.

* **App:** Python monolith (Streamlit UI \+ FastAPI logic) running in **Azure Container Apps**.  
* **Database:** PostgreSQL Flexible Server (Stores risk reports).  
* **AI:** Azure OpenAI (via custom wrapper for control & privacy).  
* **Security:**  
  * **Network:** Designed for VNET Injection & Private Endpoints.  
  * **Identity:** 100% Passwordless. Uses **Managed Identities** to fetch secrets from Key Vault.

### **Security Features (The "Why")**

1. **No Hardcoded Secrets:** The app uses DefaultAzureCredential. It automatically switches between local env vars (dev) and Managed Identity (cloud).  
2. **Network Isolation:** In the Terraform code, I've outlined the private\_endpoint configuration. For this demo (due to time constraints), it uses strict Firewall Rules (Azure Services Only).  
3. **PII Handling:** Input text is sanitized before storage (mock implementation in llm\_service.py).

## **🚀 Quick Start (Local)**

**Prerequisites:** Docker & Docker Compose.

1. **Clone the repo:**  
   git clone \[https://github.com/vlzm/kyc-analyzer.git\](https://github.com/vlzm/kyc-analyzer.git)  
   cd kyc-analyzer

2. Configure Environment (Local only):  
   Create a .env file (this file is gitignored for security):  
   AZURE\_OPENAI\_API\_KEY=sk-...  
   AZURE\_OPENAI\_ENDPOINT=https://...  
   DATABASE\_URL=postgresql://user:pass@db:5432/kyc\_db  
   ENV=LOCAL

3. **Run with Docker Compose:**  
   docker-compose up \--build

   Access the UI at http://localhost:8501.

## **☁️ Cloud Deployment (Azure)**

Infrastructure is defined in Terraform to ensure reproducibility.

1. **Provision Infrastructure:**  
   cd infra  
   az login  
   terraform init  
   terraform apply

   *Creates: RG, VNET, Key Vault, Postgres Flexible, Container Apps Environment.*  
2. **Deploy Application:**  
   az acr login \--name \<your\_registry\>  
   docker build \-t \<registry\>.azurecr.io/kyc-analyzer:v1 .  
   docker push \<registry\>.azurecr.io/kyc-analyzer:v1  
   \# Update Container App revision via Portal or CLI

## **🛠 Tech Stack**

* **Python 3.11**  
* **Streamlit** (UI)  
* **SQLModel** (ORM)  
* **Azure OpenAI SDK** (Logic)  
* **Terraform** (IaC)  
* **Docker** (Containerization)

## **📅 Execution Roadmap (2-Hour Timeline)**

To deliver a working artifact within the time limit, I followed a phased approach:

* **Phase 1: Local Core (0-45m)** ✅  
  * Implemented LLM wrapper with JSON mode enforcement.  
  * Designed DB schema using SQLModel.  
  * Verified logic locally with Docker Compose.  
* **Phase 2: Containerization (45-60m)** ✅  
  * Created optimized Dockerfile.  
  * Ensured statelessness for Cloud deployment.  
* **Phase 3: Infrastructure & Security (60-120m)** 🚧  
  * Wrote Terraform for Azure resources.  
  * Implemented DefaultAzureCredential logic.  
  * *Note on Network:* Full Private Endpoint deployment takes \~45 mins, so I used "Allow Azure Services" firewall rule for the demo to ensure connectivity within the interview window.

## **📂 Project Structure**

/  
├── app/                  \# Application Source  
│   ├── main.py           \# Entrypoint  
│   ├── services/         \# Business Logic (LLM, Secret Mgr)  
│   └── models.py         \# DB Schema  
├── infra/                \# Terraform (IaC)  
├── Dockerfile            \# Container definition  
├── docker-compose.yml    \# Local dev environment  
└── README.md  
