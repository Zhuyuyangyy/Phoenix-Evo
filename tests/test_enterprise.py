"""Tests for enterprise features."""

import pytest

from core.enterprise.rbac import (
    Permission, RBACManager, Role, User, ROLE_PERMISSIONS,
)
from core.enterprise.tenant import Organization, TenantManager, Workspace, Project
from core.enterprise.audit import AuditEvent, AuditLog
from core.enterprise.policy_engine import Policy, PolicyEffect, PolicyEngine
from core.enterprise.compliance import (
    ComplianceManager, ComplianceViolation, PIIDetection, detect_pii, redact_pii,
)
from core.enterprise.dashboard import DashboardProvider


class TestRole:
    def test_all_roles(self):
        assert len(Role) == 6

    def test_role_values(self):
        assert Role.SUPER_ADMIN.value == "super_admin"
        assert Role.VIEWER.value == "viewer"


class TestPermission:
    def test_permissions_exist(self):
        assert Permission.SKILL_READ is not None
        assert Permission.SYSTEM_CONFIG is not None
        assert Permission.USER_MANAGE is not None


class TestUser:
    def test_create(self):
        user = User(user_id="u1", username="test", roles=[Role.VIEWER])
        assert user.active is True

    def test_to_dict(self):
        user = User(user_id="u1", username="test", roles=[Role.ADMIN])
        d = user.to_dict()
        assert d["username"] == "test"
        assert "admin" in d["roles"]


class TestRBACManager:
    def test_add_and_get_user(self):
        mgr = RBACManager()
        user = User(user_id="u1", username="test", roles=[Role.VIEWER])
        mgr.add_user(user)
        assert mgr.get_user("u1") is not None

    def test_check_permission_viewer(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="test", roles=[Role.VIEWER]))
        assert mgr.check_permission("u1", Permission.SKILL_READ)
        assert not mgr.check_permission("u1", Permission.SKILL_WRITE)

    def test_check_permission_admin(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="admin", roles=[Role.ADMIN]))
        assert mgr.check_permission("u1", Permission.SKILL_WRITE)
        assert mgr.check_permission("u1", Permission.USER_MANAGE)

    def test_check_permission_super_admin(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="super", roles=[Role.SUPER_ADMIN]))
        assert mgr.check_permission("u1", Permission.SYSTEM_CONFIG)

    def test_assign_role(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="test", roles=[]))
        mgr.assign_role("u1", Role.EDITOR)
        assert mgr.check_permission("u1", Permission.SKILL_WRITE)

    def test_revoke_role(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="test", roles=[Role.ADMIN]))
        mgr.revoke_role("u1", Role.ADMIN)
        assert not mgr.check_permission("u1", Permission.SKILL_DELETE)

    def test_grant_additional_permission(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="test", roles=[Role.VIEWER]))
        mgr.grant_permission("u1", Permission.SKILL_WRITE)
        assert mgr.check_permission("u1", Permission.SKILL_WRITE)

    def test_inactive_user(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="test", roles=[Role.ADMIN], active=False))
        assert not mgr.check_permission("u1", Permission.SKILL_READ)

    def test_remove_user(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="test", roles=[Role.VIEWER]))
        assert mgr.remove_user("u1")
        assert mgr.get_user("u1") is None

    def test_list_users_by_role(self):
        mgr = RBACManager()
        mgr.add_user(User(user_id="u1", username="a", roles=[Role.ADMIN]))
        mgr.add_user(User(user_id="u2", username="b", roles=[Role.VIEWER]))
        admins = mgr.list_users(role=Role.ADMIN)
        assert len(admins) == 1


class TestTenantManager:
    def test_create_organization(self):
        mgr = TenantManager()
        org = mgr.create_organization("TestOrg")
        assert org.name == "TestOrg"
        assert org.org_id.startswith("org_")

    def test_create_workspace(self):
        mgr = TenantManager()
        org = mgr.create_organization("TestOrg")
        ws = mgr.create_workspace(org.org_id, "Dev")
        assert ws is not None
        assert ws.name == "Dev"

    def test_create_project(self):
        mgr = TenantManager()
        org = mgr.create_organization("TestOrg")
        ws = mgr.create_workspace(org.org_id, "Dev")
        proj = mgr.create_project(ws.workspace_id, "Phoenix")
        assert proj is not None

    def test_tenant_hierarchy(self):
        mgr = TenantManager()
        org = mgr.create_organization("TestOrg")
        ws = mgr.create_workspace(org.org_id, "Dev")
        mgr.create_project(ws.workspace_id, "P1")
        hierarchy = mgr.get_tenant_hierarchy(org.org_id)
        assert "organization" in hierarchy
        assert len(hierarchy["workspaces"]) == 1

    def test_delete_organization(self):
        mgr = TenantManager()
        org = mgr.create_organization("TestOrg")
        mgr.create_workspace(org.org_id, "Dev")
        assert mgr.delete_organization(org.org_id)
        assert mgr.get_organization(org.org_id) is None

    def test_nonexistent_workspace(self):
        mgr = TenantManager()
        result = mgr.create_workspace("nonexistent", "Test")
        assert result is None


class TestAuditLog:
    def test_record_event(self):
        log = AuditLog()
        event = log.record("login", "u1", "user", "u1", "login")
        assert event.event_id.startswith("audit_")

    def test_verify_chain(self):
        log = AuditLog()
        log.record("login", "u1", "user", "u1", "login")
        log.record("action", "u1", "skill", "s1", "execute")
        result = log.verify_chain()
        assert result["valid"] is True

    def test_chain_tampering_detected(self):
        log = AuditLog()
        log.record("login", "u1", "user", "u1", "login")
        # Tamper with the event
        log._events[0].action = "tampered"
        result = log.verify_chain()
        assert result["valid"] is False

    def test_query_events(self):
        log = AuditLog()
        log.record("login", "u1", "user", "u1", "login")
        log.record("action", "u2", "skill", "s1", "execute")
        events = log.get_events(actor_id="u1")
        assert len(events) == 1

    def test_export(self):
        log = AuditLog()
        log.record("login", "u1", "user", "u1", "login")
        exported = log.export()
        assert len(exported) == 1


class TestPolicyEngine:
    def test_allow_policy(self):
        engine = PolicyEngine(default_effect=PolicyEffect.DENY)
        engine.add_policy(Policy(
            policy_id="p1", name="Allow Read",
            effect=PolicyEffect.ALLOW, resource_type="skill", action="read",
        ))
        result = engine.evaluate("skill", "read")
        assert result["allowed"] is True

    def test_deny_policy(self):
        engine = PolicyEngine()
        engine.add_policy(Policy(
            policy_id="p1", name="Deny Delete",
            effect=PolicyEffect.DENY, resource_type="skill", action="delete",
        ))
        result = engine.evaluate("skill", "delete")
        assert result["allowed"] is False

    def test_priority(self):
        engine = PolicyEngine(default_effect=PolicyEffect.DENY)
        engine.add_policy(Policy(policy_id="p1", name="Deny", effect=PolicyEffect.DENY,
                                  resource_type="skill", action="read", priority=1))
        engine.add_policy(Policy(policy_id="p2", name="Allow", effect=PolicyEffect.ALLOW,
                                  resource_type="skill", action="read", priority=10))
        result = engine.evaluate("skill", "read")
        assert result["allowed"] is True

    def test_wildcard(self):
        engine = PolicyEngine(default_effect=PolicyEffect.DENY)
        engine.add_policy(Policy(policy_id="p1", name="Allow All",
                                  effect=PolicyEffect.ALLOW, resource_type="*", action="*"))
        result = engine.evaluate("anything", "anyaction")
        assert result["allowed"] is True


class TestCompliance:
    def test_detect_email(self):
        results = detect_pii("Contact us at user@example.com")
        assert any(r.pii_type == "email" for r in results)

    def test_detect_ssn(self):
        results = detect_pii("SSN: 123-45-6789")
        assert any(r.pii_type == "ssn" for r in results)

    def test_detect_phone(self):
        results = detect_pii("Call 555-123-4567")
        assert any(r.pii_type == "phone_us" for r in results)

    def test_redact_pii(self):
        text, count = redact_pii("Email: user@example.com and SSN: 123-45-6789")
        assert count > 0
        assert "user@example.com" not in text

    def test_compliance_manager(self):
        mgr = ComplianceManager()
        violations = mgr.check_compliance({"email": "user@example.com"})
        assert len(violations) > 0

    def test_compliance_report(self):
        mgr = ComplianceManager()
        mgr.check_compliance({"email": "user@example.com"})
        report = mgr.get_compliance_report()
        assert report["total_violations"] > 0


class TestDashboardProvider:
    def test_push_and_get_metric(self):
        dp = DashboardProvider()
        dp.push_metric("cpu", 0.5)
        dp.push_metric("cpu", 0.7)
        data = dp.get_metric("cpu")
        assert len(data) == 2

    def test_metric_summary(self):
        dp = DashboardProvider()
        dp.push_metric("latency", 100)
        dp.push_metric("latency", 200)
        summary = dp.get_metric_summary("latency")
        assert summary["mean"] == 150.0

    def test_register_widget(self):
        dp = DashboardProvider()
        dp.register_widget("w1", "chart", {"metric": "cpu"})
        widgets = dp.list_widgets()
        assert len(widgets) == 1

    def test_dashboard_data(self):
        dp = DashboardProvider()
        dp.push_metric("test", 1.0)
        data = dp.get_dashboard_data()
        assert "metrics" in data
