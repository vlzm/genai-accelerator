output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "acr_name" {
  description = "Name of the Container Registry"
  value       = azurerm_container_registry.main.name
}

output "acr_login_server" {
  description = "Login server URL for Container Registry"
  value       = azurerm_container_registry.main.login_server
}

output "app_url" {
  description = "URL of the Streamlit application"
  value       = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "api_url" {
  description = "URL of the FastAPI application"
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "postgres_host" {
  description = "PostgreSQL server hostname"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "postgres_database" {
  description = "PostgreSQL database name"
  value       = azurerm_postgresql_flexible_server_database.main.name
}

output "keyvault_name" {
  description = "Name of the Key Vault"
  value       = azurerm_key_vault.main.name
}

output "keyvault_uri" {
  description = "URI of the Key Vault"
  value       = azurerm_key_vault.main.vault_uri
}

