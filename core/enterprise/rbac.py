"""Role-Based Access Control for Phoenix-Evo enterprise features."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    AUDITOR = "auditor"
    API_USER = "api_user"


class Permission(Enum):
    # Skill permissions
    SKILL_READ = "skill:read"
    SKILL_WRITE = "skill:write"
    SKILL_DELETE = "skill:delete"
    SKILL_PUBLISH = "skill:publish"
    # Agent permissions
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    AGENT_EXECUTE = "agent:execute"
    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_AUDIT = "system:audit"
    # User permissions
    USER_MANAGE = "user:manage"
    # Data permissions
    DATA_EXPORT = "data:export"
    DATA_IMPORT = "data:import"


# Default role-permission mappings
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),  # All permissions
    Role.ADMIN: {
        Permission.SKILL_READ, Permission.SKILL_WRITE, Permission.SKILL_DELETE, Permission.SKILL_PUBLISH,
        Permission.AGENT_READ, Permission.AGENT_WRITE, Permission.AGENT_EXECUTE,
        Permission.SYSTEM_CONFIG, Permission.SYSTEM_AUDIT,
        Permission.USER_MANAGE,
        Permission.DATA_EXPORT, Permission.DATA_IMPORT,
    },
    Role.EDITOR: {
        Permission.SKILL_READ, Permission.SKILL_WRITE, Permission.SKILL_PUBLISH,
        Permission.AGENT_READ, Permission.AGENT_EXECUTE,
        Permission.DATA_IMPORT,
    },
    Role.VIEWER: {
        Permission.SKILL_READ,
        Permission.AGENT_READ,
    },
    Role.AUDITOR: {
        Permission.SKILL_READ,
        Permission.AGENT_READ,
        Permission.SYSTEM_AUDIT,
        Permission.DATA_EXPORT,
    },
    Role.API_USER: {
        Permission.SKILL_READ, Permission.SKILL_WRITE,
        Permission.AGENT_READ, Permission.AGENT_EXECUTE,
    },
}


@dataclass
class User:
    """A user in the RBAC system."""
    user_id: str
    username: str
    email: str = ""
    roles: list[Role] = field(default_factory=list)
    additional_permissions: set[Permission] = field(default_factory=set)
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "roles": [r.value for r in self.roles],
            "additional_permissions": [p.value for p in self.additional_permissions],
            "active": self.active,
        }


class RBACManager:
    """Manages Role-Based Access Control."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self._role_permissions: dict[Role, set[Permission]] = dict(ROLE_PERMISSIONS)

    def add_user(self, user: User) -> None:
        """Add a user to the system."""
        self._users[user.user_id] = user

    def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        return self._users.get(user_id)

    def remove_user(self, user_id: str) -> bool:
        """Remove a user."""
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if a user has a specific permission."""
        user = self._users.get(user_id)
        if not user or not user.active:
            return False

        # Check additional permissions
        if permission in user.additional_permissions:
            return True

        # Check role-based permissions
        return any(permission in self._role_permissions.get(role, set()) for role in user.roles)

    def get_user_permissions(self, user_id: str) -> set[Permission]:
        """Get all permissions for a user."""
        user = self._users.get(user_id)
        if not user or not user.active:
            return set()

        permissions = set(user.additional_permissions)
        for role in user.roles:
            permissions.update(self._role_permissions.get(role, set()))
        return permissions

    def assign_role(self, user_id: str, role: Role) -> bool:
        """Assign a role to a user."""
        user = self._users.get(user_id)
        if not user:
            return False
        if role not in user.roles:
            user.roles.append(role)
        return True

    def revoke_role(self, user_id: str, role: Role) -> bool:
        """Revoke a role from a user."""
        user = self._users.get(user_id)
        if not user:
            return False
        if role in user.roles:
            user.roles.remove(role)
        return True

    def grant_permission(self, user_id: str, permission: Permission) -> bool:
        """Grant an additional permission to a user."""
        user = self._users.get(user_id)
        if not user:
            return False
        user.additional_permissions.add(permission)
        return True

    def set_role_permissions(self, role: Role, permissions: set[Permission]) -> None:
        """Set the permissions for a role."""
        self._role_permissions[role] = permissions

    def list_users(self, role: Role | None = None) -> list[User]:
        """List users, optionally filtered by role."""
        users = list(self._users.values())
        if role:
            users = [u for u in users if role in u.roles]
        return users
