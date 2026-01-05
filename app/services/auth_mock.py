"""
Mock Identity Provider for local development.

In production, this would be replaced by Azure Entra ID (Azure AD) integration.
This module simulates user authentication and authorization for demo purposes.

Implements:
- RBAC (Role-Based Access Control): admin, senior_analyst, analyst, viewer
- ABAC (Attribute-Based Access Control): region
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    SENIOR_ANALYST = "senior_analyst"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Region(str, Enum):
    """Geographic regions for ABAC."""
    GLOBAL = "Global"
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"


class Permission(str, Enum):
    """Available permissions in the system."""
    VIEW = "view"
    ANALYZE = "analyze"
    VIEW_SENSITIVE = "view_sensitive"
    VIEW_ALL_REGIONS = "view_all_regions"
    MANAGE_USERS = "manage_users"
    EXPORT_DATA = "export_data"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: {
        Permission.VIEW,
        Permission.ANALYZE,
        Permission.VIEW_SENSITIVE,
        Permission.VIEW_ALL_REGIONS,
        Permission.MANAGE_USERS,
        Permission.EXPORT_DATA,
    },
    UserRole.SENIOR_ANALYST: {
        Permission.VIEW,
        Permission.ANALYZE,
        Permission.VIEW_SENSITIVE,
        Permission.VIEW_ALL_REGIONS,
        Permission.EXPORT_DATA,
    },
    UserRole.ANALYST: {
        Permission.VIEW,
        Permission.ANALYZE,
        Permission.VIEW_SENSITIVE,
    },
    UserRole.VIEWER: {
        Permission.VIEW,
    },
}


class UserProfile(BaseModel):
    """
    User profile model representing authenticated user.
    
    In production, these claims would come from Azure Entra ID token.
    """
    id: str
    username: str
    email: str
    role: UserRole
    region: Region
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission (RBAC)."""
        return permission in ROLE_PERMISSIONS.get(self.role, set())
    
    def can_access_region(self, target_region: str) -> bool:
        """Check if user can access data from a specific region (ABAC)."""
        if self.has_permission(Permission.VIEW_ALL_REGIONS):
            return True
        return self.region.value == target_region or self.region == Region.GLOBAL
    
    def can_view_score(self, score: int) -> bool:
        """Check if user can view results with given score (ABAC)."""
        if self.has_permission(Permission.VIEW_SENSITIVE):
            return True
        # Users without VIEW_SENSITIVE can only see scores below 70
        return score < 70
    
    def get_max_visible_score(self) -> int:
        """Returns maximum score this user can view."""
        if self.has_permission(Permission.VIEW_SENSITIVE):
            return 100
        return 69  # Can't see 70+


# Mock users database (in production: Azure Entra ID)
MOCK_USERS: dict[str, UserProfile] = {
    "admin_global": UserProfile(
        id="usr_001",
        username="Alice Administrator",
        email="alice.admin@example.com",
        role=UserRole.ADMIN,
        region=Region.GLOBAL,
    ),
    "senior_global": UserProfile(
        id="usr_002",
        username="Bob Senior Analyst",
        email="bob.senior@example.com",
        role=UserRole.SENIOR_ANALYST,
        region=Region.GLOBAL,
    ),
    "analyst_south": UserProfile(
        id="usr_003",
        username="Carol Analyst (South)",
        email="carol.analyst@example.com",
        role=UserRole.ANALYST,
        region=Region.SOUTH,
    ),
    "analyst_north": UserProfile(
        id="usr_004",
        username="David Analyst (North)",
        email="david.analyst@example.com",
        role=UserRole.ANALYST,
        region=Region.NORTH,
    ),
    "viewer_south": UserProfile(
        id="usr_005",
        username="Eve Viewer (South)",
        email="eve.viewer@example.com",
        role=UserRole.VIEWER,
        region=Region.SOUTH,
    ),
}


def get_current_user(user_key: str) -> Optional[UserProfile]:
    """
    Get user profile by key.
    
    In production, this would decode and validate Azure Entra ID token.
    
    Args:
        user_key: User identifier key
        
    Returns:
        UserProfile or None if not found
    """
    return MOCK_USERS.get(user_key)


def get_all_users() -> dict[str, UserProfile]:
    """Returns all mock users for the identity simulator."""
    return MOCK_USERS


def check_permission(user: UserProfile, permission: Permission) -> bool:
    """
    Check if user has permission. Raises exception if not.
    
    Args:
        user: Current user profile
        permission: Required permission
        
    Returns:
        True if has permission
        
    Raises:
        PermissionError: If user lacks permission
    """
    if not user.has_permission(permission):
        raise PermissionError(
            f"Access denied. User '{user.username}' with role '{user.role.value}' "
            f"does not have permission '{permission.value}'."
        )
    return True
