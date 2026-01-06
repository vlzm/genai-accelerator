terraform {
  required_version = ">= 1.5.0"

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
  name                = "${var.project_name}acr${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic" # Cheapest tier ~$5/month
  admin_enabled       = true    # For simple auth
}

# ============================================
# KEY VAULT (for secrets)
# ============================================
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
      "Get", "List", "Set", "Delete", "Purge", "Recover"
    ]
  }
}

# Store OpenAI API key in Key Vault
resource "azurerm_key_vault_secret" "openai_key" {
  name         = "openai-api-key"
  value        = var.openai_api_key
  key_vault_id = azurerm_key_vault.main.id
}

# Store DB password in Key Vault
resource "azurerm_key_vault_secret" "db_password" {
  name         = "db-admin-password"
  value        = var.db_admin_password
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
  administrator_login    = "appdbadmin"
  administrator_password = var.db_admin_password

  # Cheapest tier: Burstable B1ms (~$12/month)
  sku_name   = "B_Standard_B1ms"
  storage_mb = 32768 # 32GB minimum

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
  name      = "app_db"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
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
    min_replicas = 0 # Scale to zero when not in use (saves money!)
    max_replicas = 1

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/genai-api:latest"
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
        value = var.openai_model
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
      image  = "${azurerm_container_registry.main.login_server}/genai-app:latest"
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
        value = var.openai_model
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
