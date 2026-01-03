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

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "openai_model" {
  description = "OpenAI model to use"
  type        = string
  default     = "gpt-4.1"
}
