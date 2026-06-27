"""Multi-tenant management for Phoenix-Evo enterprise features."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Organization:
    """An organization (top-level tenant)."""
    org_id: str
    name: str
    display_name: str = ""
    plan: str = "free"  # free, pro, enterprise
    active: bool = True
    settings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workspace:
    """A workspace within an organization."""
    workspace_id: str
    org_id: str
    name: str
    description: str = ""
    active: bool = True
    settings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Project:
    """A project within a workspace."""
    project_id: str
    workspace_id: str
    name: str
    description: str = ""
    active: bool = True
    settings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class TenantManager:
    """Manages multi-tenant organizations, workspaces, and projects."""

    def __init__(self):
        self._organizations: dict[str, Organization] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._projects: dict[str, Project] = {}

    # Organization management
    def create_organization(
        self,
        name: str,
        display_name: str = "",
        plan: str = "free",
    ) -> Organization:
        """Create a new organization."""
        org_id = f"org_{uuid.uuid4().hex[:8]}"
        org = Organization(
            org_id=org_id,
            name=name,
            display_name=display_name or name,
            plan=plan,
        )
        self._organizations[org_id] = org
        return org

    def get_organization(self, org_id: str) -> Organization | None:
        """Get an organization by ID."""
        return self._organizations.get(org_id)

    def list_organizations(self) -> list[Organization]:
        """List all organizations."""
        return list(self._organizations.values())

    def update_organization(self, org_id: str, **kwargs: Any) -> bool:
        """Update organization properties."""
        org = self._organizations.get(org_id)
        if not org:
            return False
        for k, v in kwargs.items():
            if hasattr(org, k):
                setattr(org, k, v)
        return True

    def delete_organization(self, org_id: str) -> bool:
        """Delete an organization and all its workspaces/projects."""
        # Delete associated workspaces
        ws_to_delete = [
            ws_id for ws_id, ws in self._workspaces.items()
            if ws.org_id == org_id
        ]
        for ws_id in ws_to_delete:
            self.delete_workspace(ws_id)

        if org_id in self._organizations:
            del self._organizations[org_id]
            return True
        return False

    # Workspace management
    def create_workspace(
        self,
        org_id: str,
        name: str,
        description: str = "",
    ) -> Workspace | None:
        """Create a new workspace in an organization."""
        if org_id not in self._organizations:
            return None
        ws_id = f"ws_{uuid.uuid4().hex[:8]}"
        ws = Workspace(
            workspace_id=ws_id,
            org_id=org_id,
            name=name,
            description=description,
        )
        self._workspaces[ws_id] = ws
        return ws

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        """Get a workspace by ID."""
        return self._workspaces.get(workspace_id)

    def list_workspaces(self, org_id: str) -> list[Workspace]:
        """List workspaces in an organization."""
        return [ws for ws in self._workspaces.values() if ws.org_id == org_id]

    def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace and all its projects."""
        proj_to_delete = [
            p_id for p_id, p in self._projects.items()
            if p.workspace_id == workspace_id
        ]
        for p_id in proj_to_delete:
            del self._projects[p_id]

        if workspace_id in self._workspaces:
            del self._workspaces[workspace_id]
            return True
        return False

    # Project management
    def create_project(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
    ) -> Project | None:
        """Create a new project in a workspace."""
        if workspace_id not in self._workspaces:
            return None
        proj_id = f"proj_{uuid.uuid4().hex[:8]}"
        proj = Project(
            project_id=proj_id,
            workspace_id=workspace_id,
            name=name,
            description=description,
        )
        self._projects[proj_id] = proj
        return proj

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def list_projects(self, workspace_id: str) -> list[Project]:
        """List projects in a workspace."""
        return [p for p in self._projects.values() if p.workspace_id == workspace_id]

    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        if project_id in self._projects:
            del self._projects[project_id]
            return True
        return False

    def get_tenant_hierarchy(self, org_id: str) -> dict[str, Any]:
        """Get the full tenant hierarchy for an organization."""
        org = self._organizations.get(org_id)
        if not org:
            return {}

        workspaces = self.list_workspaces(org_id)
        return {
            "organization": {
                "org_id": org.org_id,
                "name": org.name,
                "plan": org.plan,
            },
            "workspaces": [
                {
                    "workspace_id": ws.workspace_id,
                    "name": ws.name,
                    "projects": [
                        {"project_id": p.project_id, "name": p.name}
                        for p in self.list_projects(ws.workspace_id)
                    ],
                }
                for ws in workspaces
            ],
        }
