# ============================================================================
# PRODUCTION SECURITY OVERLAY
# ============================================================================
# This file contains infrastructure code for production-grade network security.
# 
# WHY THIS EXISTS:
# For demo purposes, we use public endpoints to ensure fast deployment
# (under 5 minutes). However, for a banking environment like Rabobank, this
# configuration would be uncommented to enable:
#   - Private Endpoints (no public internet exposure)
#   - VNET Integration (Container Apps get private IPs)
#   - Private DNS Zones (internal name resolution)
#
# DEPLOYMENT NOTE:
# Provisioning Private Endpoints + DNS takes 20-40 minutes and is prone to
# timing issues. For live demos, keep this commented and explain the security
# architecture verbally.
# ============================================================================

# Uncomment the following line in variables.tf to enable:
# variable "enable_private_networking" { default = true }

# ============================================================================
# VIRTUAL NETWORK & SUBNETS
# ============================================================================

# resource "azurerm_virtual_network" "main" {
#   name                = "${var.project_name}-vnet-${var.environment}"
#   location            = azurerm_resource_group.main.location
#   resource_group_name = azurerm_resource_group.main.name
#   address_space       = ["10.0.0.0/16"]
#
#   tags = {
#     Environment = var.environment
#     Purpose     = "Network isolation for GenAI workloads"
#   }
# }

# # Subnet for Container Apps (delegated)
# resource "azurerm_subnet" "app" {
#   name                 = "snet-container-apps"
#   resource_group_name  = azurerm_resource_group.main.name
#   virtual_network_name = azurerm_virtual_network.main.name
#   address_prefixes     = ["10.0.1.0/24"]
#
#   # Required delegation for Container Apps Environment
#   delegation {
#     name = "container-apps-delegation"
#     service_delegation {
#       name = "Microsoft.App/environments"
#       actions = [
#         "Microsoft.Network/virtualNetworks/subnets/action"
#       ]
#     }
#   }
# }

# # Subnet for Private Endpoints (data services)
# resource "azurerm_subnet" "data" {
#   name                 = "snet-private-endpoints"
#   resource_group_name  = azurerm_resource_group.main.name
#   virtual_network_name = azurerm_virtual_network.main.name
#   address_prefixes     = ["10.0.2.0/24"]
#
#   # Disable network policies for Private Endpoints
#   private_endpoint_network_policies_enabled = false
# }

# ============================================================================
# PRIVATE DNS ZONES
# ============================================================================
# These zones enable internal name resolution for private endpoints.
# Format: privatelink.<service>.azure.com

# # PostgreSQL Private DNS Zone
# resource "azurerm_private_dns_zone" "postgres" {
#   name                = "privatelink.postgres.database.azure.com"
#   resource_group_name = azurerm_resource_group.main.name
# }

# resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
#   name                  = "postgres-dns-link"
#   resource_group_name   = azurerm_resource_group.main.name
#   private_dns_zone_name = azurerm_private_dns_zone.postgres.name
#   virtual_network_id    = azurerm_virtual_network.main.id
# }

# # Key Vault Private DNS Zone
# resource "azurerm_private_dns_zone" "keyvault" {
#   name                = "privatelink.vaultcore.azure.net"
#   resource_group_name = azurerm_resource_group.main.name
# }

# resource "azurerm_private_dns_zone_virtual_network_link" "keyvault" {
#   name                  = "keyvault-dns-link"
#   resource_group_name   = azurerm_resource_group.main.name
#   private_dns_zone_name = azurerm_private_dns_zone.keyvault.name
#   virtual_network_id    = azurerm_virtual_network.main.id
# }

# # Azure OpenAI Private DNS Zone (if using Azure OpenAI)
# resource "azurerm_private_dns_zone" "openai" {
#   name                = "privatelink.openai.azure.com"
#   resource_group_name = azurerm_resource_group.main.name
# }

# resource "azurerm_private_dns_zone_virtual_network_link" "openai" {
#   name                  = "openai-dns-link"
#   resource_group_name   = azurerm_resource_group.main.name
#   private_dns_zone_name = azurerm_private_dns_zone.openai.name
#   virtual_network_id    = azurerm_virtual_network.main.id
# }

# ============================================================================
# PRIVATE ENDPOINTS
# ============================================================================

# # PostgreSQL Private Endpoint
# resource "azurerm_private_endpoint" "postgres" {
#   name                = "pe-postgres-${var.environment}"
#   location            = azurerm_resource_group.main.location
#   resource_group_name = azurerm_resource_group.main.name
#   subnet_id           = azurerm_subnet.data.id
#
#   private_service_connection {
#     name                           = "psc-postgres"
#     private_connection_resource_id = azurerm_postgresql_flexible_server.main.id
#     subresource_names              = ["postgresqlServer"]
#     is_manual_connection           = false
#   }
#
#   private_dns_zone_group {
#     name                 = "postgres-dns-group"
#     private_dns_zone_ids = [azurerm_private_dns_zone.postgres.id]
#   }
#
#   tags = {
#     Environment = var.environment
#     Purpose     = "Private connectivity to PostgreSQL"
#   }
# }

# # Key Vault Private Endpoint
# resource "azurerm_private_endpoint" "keyvault" {
#   name                = "pe-keyvault-${var.environment}"
#   location            = azurerm_resource_group.main.location
#   resource_group_name = azurerm_resource_group.main.name
#   subnet_id           = azurerm_subnet.data.id
#
#   private_service_connection {
#     name                           = "psc-keyvault"
#     private_connection_resource_id = azurerm_key_vault.main.id
#     subresource_names              = ["vault"]
#     is_manual_connection           = false
#   }
#
#   private_dns_zone_group {
#     name                 = "keyvault-dns-group"
#     private_dns_zone_ids = [azurerm_private_dns_zone.keyvault.id]
#   }
#
#   tags = {
#     Environment = var.environment
#     Purpose     = "Private connectivity to Key Vault"
#   }
# }

# # Azure OpenAI Private Endpoint (uncomment if using Azure OpenAI)
# # resource "azurerm_private_endpoint" "openai" {
# #   name                = "pe-openai-${var.environment}"
# #   location            = azurerm_resource_group.main.location
# #   resource_group_name = azurerm_resource_group.main.name
# #   subnet_id           = azurerm_subnet.data.id
# #
# #   private_service_connection {
# #     name                           = "psc-openai"
# #     private_connection_resource_id = azurerm_cognitive_account.openai.id
# #     subresource_names              = ["account"]
# #     is_manual_connection           = false
# #   }
# #
# #   private_dns_zone_group {
# #     name                 = "openai-dns-group"
# #     private_dns_zone_ids = [azurerm_private_dns_zone.openai.id]
# #   }
# # }

# ============================================================================
# CONTAINER APPS VNET INTEGRATION
# ============================================================================
# To enable VNET integration, modify the Container Apps Environment in main.tf:
#
# resource "azurerm_container_app_environment" "main" {
#   name                       = "${var.project_name}-env-${var.environment}"
#   location                   = azurerm_resource_group.main.location
#   resource_group_name        = azurerm_resource_group.main.name
#   log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
#
#   # VNET Integration (uncomment for production)
#   infrastructure_subnet_id       = azurerm_subnet.app.id
#   internal_load_balancer_enabled = true  # No public IP
# }

# ============================================================================
# DISABLE PUBLIC ACCESS (Production hardening)
# ============================================================================

# # Disable public access on PostgreSQL
# # In main.tf, add to azurerm_postgresql_flexible_server:
# #   public_network_access_enabled = false

# # Disable public access on Key Vault
# # In main.tf, add to azurerm_key_vault:
# #   network_acls {
# #     default_action = "Deny"
# #     bypass         = "AzureServices"
# #   }

# ============================================================================
# NETWORK SECURITY GROUPS (Optional - defense in depth)
# ============================================================================

# resource "azurerm_network_security_group" "app" {
#   name                = "nsg-container-apps-${var.environment}"
#   location            = azurerm_resource_group.main.location
#   resource_group_name = azurerm_resource_group.main.name
#
#   # Allow HTTPS inbound from Azure Front Door / Application Gateway only
#   security_rule {
#     name                       = "AllowHTTPS"
#     priority                   = 100
#     direction                  = "Inbound"
#     access                     = "Allow"
#     protocol                   = "Tcp"
#     source_port_range          = "*"
#     destination_port_range     = "443"
#     source_address_prefix      = "AzureFrontDoor.Backend"
#     destination_address_prefix = "*"
#   }
#
#   # Deny all other inbound traffic
#   security_rule {
#     name                       = "DenyAllInbound"
#     priority                   = 4096
#     direction                  = "Inbound"
#     access                     = "Deny"
#     protocol                   = "*"
#     source_port_range          = "*"
#     destination_port_range     = "*"
#     source_address_prefix      = "*"
#     destination_address_prefix = "*"
#   }
# }

# resource "azurerm_subnet_network_security_group_association" "app" {
#   subnet_id                 = azurerm_subnet.app.id
#   network_security_group_id = azurerm_network_security_group.app.id
# }

# ============================================================================
# SUMMARY: Production Checklist
# ============================================================================
# To enable full production security, uncomment and apply:
#
# 1. [ ] VNET + Subnets (snet-app, snet-data)
# 2. [ ] Private DNS Zones (postgres, keyvault, openai)
# 3. [ ] Private Endpoints (postgres, keyvault)
# 4. [ ] Container Apps VNET Integration (internal_load_balancer_enabled)
# 5. [ ] Disable public access on PostgreSQL and Key Vault
# 6. [ ] NSG rules for defense in depth
#
# Estimated deployment time: 25-40 minutes (DNS propagation is slow)
# ============================================================================
