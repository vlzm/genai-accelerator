terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }

  # Skip auto-registration of ALL providers (would check ~60 providers = 10-20 min)
  # We explicitly register only the providers we need below
  skip_provider_registration = true
}

# ============================================
# RESOURCE PROVIDER REGISTRATION
# ============================================
# Explicitly register only the Azure providers we need
# This is idempotent - safe to run multiple times
# First apply on a new subscription will register them (~1-2 min each)

resource "azurerm_resource_provider_registration" "app" {
  name = "Microsoft.App" # Container Apps
}

resource "azurerm_resource_provider_registration" "containerregistry" {
  name = "Microsoft.ContainerRegistry"
}

resource "azurerm_resource_provider_registration" "keyvault" {
  name = "Microsoft.KeyVault"
}

resource "azurerm_resource_provider_registration" "postgresql" {
  name = "Microsoft.DBforPostgreSQL"
}

resource "azurerm_resource_provider_registration" "operationalinsights" {
  name = "Microsoft.OperationalInsights" # Log Analytics
}

# ============================================
# RANDOM SUFFIX (for globally unique resource names)
# ============================================
resource "random_string" "suffix" {
  length  = 6
  lower   = true
  upper   = false
  numeric = true
  special = false
}

# ============================================
# DATA SOURCES
# ============================================
data "azurerm_client_config" "current" {}

# ============================================
# RESOURCE GROUP
# ============================================
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location

  tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }
}

# ============================================
# CONTAINER REGISTRY (for Docker images)
# ============================================
resource "azurerm_container_registry" "main" {
  name                = "${var.project_name}acr${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic" # Cheapest tier ~$5/month
  admin_enabled       = true    # For simple auth

  depends_on = [azurerm_resource_provider_registration.containerregistry]
}

# ============================================
# KEY VAULT (for secrets)
# ============================================
resource "azurerm_key_vault" "main" {
  name                = "${var.project_name}-kv-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Enable RBAC for Key Vault (alternative to access policies)
  # We use access_policy for simplicity in this setup
  
  # Allow current user (Terraform deployer) to manage secrets
  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = [
      "Get", "List", "Set", "Delete", "Purge", "Recover"
    ]
  }

  depends_on = [azurerm_resource_provider_registration.keyvault]
}

# Store OpenAI API key in Key Vault
# Using the name that matches app/services/secret_manager.py expectations
resource "azurerm_key_vault_secret" "openai_key" {
  name         = "AZURE-OPENAI-API-KEY"
  value        = var.openai_api_key
  key_vault_id = azurerm_key_vault.main.id
}

# Store DB password in Key Vault
# Using the name that matches app/services/secret_manager.py expectations
resource "azurerm_key_vault_secret" "db_password" {
  name         = "DATABASE-PASSWORD"
  value        = var.db_admin_password
  key_vault_id = azurerm_key_vault.main.id
}

# Store Anthropic API key in Key Vault (optional, only if using anthropic provider)
resource "azurerm_key_vault_secret" "anthropic_key" {
  count        = var.anthropic_api_key != "" ? 1 : 0
  name         = "ANTHROPIC-API-KEY"
  value        = var.anthropic_api_key
  key_vault_id = azurerm_key_vault.main.id
}

# ============================================
# POSTGRESQL FLEXIBLE SERVER
# ============================================
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "${var.project_name}-pg-${random_string.suffix.result}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = "appdbadmin"
  administrator_password = var.db_admin_password

  # Cheapest tier: Burstable B1ms (~$12/month)
  sku_name   = "B_Standard_B1ms"
  storage_mb = 32768 # 32GB minimum

  zone = "1"

  depends_on = [azurerm_resource_provider_registration.postgresql]
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
  name      = "app_db"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Enable pgvector extension for RAG support
resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR"
}

# Require SSL connections (security best practice)
resource "azurerm_postgresql_flexible_server_configuration" "ssl" {
  name      = "require_secure_transport"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "ON"
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

  depends_on = [azurerm_resource_provider_registration.operationalinsights]
}

# ============================================
# CONTAINER APPS ENVIRONMENT
# ============================================
resource "azurerm_container_app_environment" "main" {
  name                       = "${var.project_name}-env-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  depends_on = [azurerm_resource_provider_registration.app]
}

# ============================================
# CONTAINER APP - API (FastAPI)
# ============================================
resource "azurerm_container_app" "api" {
  name                         = "${var.project_name}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  # System-assigned Managed Identity for Key Vault access
  # Security: Uses passwordless authentication to Azure services
  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = 0 # Scale to zero when not in use (saves money!)
    max_replicas = 2

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/genai-api:latest"
      cpu    = 0.5
      memory = "1Gi"

      # Environment mode - triggers Key Vault secret fetching
      env {
        name  = "ENV"
        value = "CLOUD"
      }
      
      # Key Vault URL for secret retrieval via Managed Identity
      env {
        name  = "AZURE_KEYVAULT_URL"
        value = azurerm_key_vault.main.vault_uri
      }

      # Database connection (password fetched from Key Vault in cloud mode)
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
      # Note: DATABASE_PASSWORD is fetched from Key Vault via Managed Identity
      # Not passed as env var - see secret_manager.py get_database_password()

      # LLM Provider configuration
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      env {
        name  = "OPENAI_MODEL"
        value = var.openai_model
      }
      # Note: OPENAI_API_KEY is fetched from Key Vault via Managed Identity
      
      # Azure OpenAI settings (if using azure provider)
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.azure_openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_NAME"
        value = var.azure_openai_deployment_name
      }

      # RAG / Vector Search settings
      env {
        name  = "RAG_ENABLED"
        value = tostring(var.rag_enabled)
      }
      env {
        name  = "EMBEDDING_MODEL"
        value = var.embedding_model
      }
    }
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
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
}

# Key Vault access policy for API Container App
# Security: Allows Container App to read secrets using its Managed Identity
resource "azurerm_key_vault_access_policy" "api" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_container_app.api.identity[0].principal_id

  secret_permissions = [
    "Get", "List"
  ]
}

# ============================================
# CONTAINER APP - UI (Streamlit)
# ============================================
resource "azurerm_container_app" "app" {
  name                         = "${var.project_name}-app"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  # System-assigned Managed Identity for Key Vault access
  # Security: Uses passwordless authentication to Azure services
  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "app"
      image  = "${azurerm_container_registry.main.login_server}/genai-app:latest"
      cpu    = 0.5
      memory = "1Gi"

      # Environment mode - triggers Key Vault secret fetching
      env {
        name  = "ENV"
        value = "CLOUD"
      }
      
      # Key Vault URL for secret retrieval via Managed Identity
      env {
        name  = "AZURE_KEYVAULT_URL"
        value = azurerm_key_vault.main.vault_uri
      }

      # Database connection (password fetched from Key Vault in cloud mode)
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
      # Note: DATABASE_PASSWORD is fetched from Key Vault via Managed Identity
      # Not passed as env var - see secret_manager.py get_database_password()

      # LLM Provider configuration
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      env {
        name  = "OPENAI_MODEL"
        value = var.openai_model
      }
      # Note: OPENAI_API_KEY is fetched from Key Vault via Managed Identity
      
      # Azure OpenAI settings (if using azure provider)
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.azure_openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_NAME"
        value = var.azure_openai_deployment_name
      }

      # RAG / Vector Search settings
      env {
        name  = "RAG_ENABLED"
        value = tostring(var.rag_enabled)
      }
      env {
        name  = "EMBEDDING_MODEL"
        value = var.embedding_model
      }
    }
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
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
}

# Key Vault access policy for UI Container App
# Security: Allows Container App to read secrets using its Managed Identity
resource "azurerm_key_vault_access_policy" "app" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_container_app.app.identity[0].principal_id

  secret_permissions = [
    "Get", "List"
  ]
}
