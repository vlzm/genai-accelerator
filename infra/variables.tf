variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "genai"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus" # Cheapest region
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

# ============================================
# LLM Provider Configuration
# ============================================
variable "llm_provider" {
  description = "LLM provider to use: openai, azure, anthropic, ollama"
  type        = string
  default     = "openai"
  
  validation {
    condition     = contains(["openai", "azure", "anthropic", "ollama"], var.llm_provider)
    error_message = "LLM provider must be one of: openai, azure, anthropic, ollama"
  }
}

variable "openai_api_key" {
  description = "OpenAI API key (also used for Azure OpenAI if using azure provider)"
  type        = string
  sensitive   = true
}

variable "openai_model" {
  description = "OpenAI model to use"
  type        = string
  default     = "gpt-4.1"
}

# ============================================
# Azure OpenAI Configuration (optional)
# ============================================
variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint URL (required if llm_provider=azure)"
  type        = string
  default     = ""
}

variable "azure_openai_deployment_name" {
  description = "Azure OpenAI deployment name"
  type        = string
  default     = "gpt-4"
}

# ============================================
# Anthropic Configuration (optional)
# ============================================
variable "anthropic_api_key" {
  description = "Anthropic API key (required if llm_provider=anthropic)"
  type        = string
  sensitive   = true
  default     = ""
}

# ============================================
# RAG / Vector Search Configuration
# ============================================
variable "rag_enabled" {
  description = "Enable RAG/Vector search functionality"
  type        = bool
  default     = true
}

variable "embedding_model" {
  description = "Embedding model for vector search"
  type        = string
  default     = "text-embedding-3-small"
}

# ============================================
# Production Security (Network Isolation)
# ============================================
variable "enable_private_networking" {
  description = "Enable VNET integration, Private Endpoints, and Private DNS Zones. Increases deployment time significantly (25-40 min)."
  type        = bool
  default     = false # Set to true for production deployments
}

variable "vnet_address_space" {
  description = "Address space for the Virtual Network"
  type        = string
  default     = "10.0.0.0/16"
}

variable "app_subnet_prefix" {
  description = "Address prefix for Container Apps subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "data_subnet_prefix" {
  description = "Address prefix for Private Endpoints subnet"
  type        = string
  default     = "10.0.2.0/24"
}
