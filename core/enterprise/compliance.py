"""Compliance management and PII detection for Phoenix-Evo enterprise features."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# PII patterns for detection
PII_PATTERNS = {
    "email": (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "Email address"),
    "phone_us": (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', "US phone number"),
    "ssn": (r'\b\d{3}-\d{2}-\d{4}\b', "Social Security Number"),
    "credit_card": (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', "Credit card number"),
    "ip_address": (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', "IP address"),
    "date_of_birth": (r'\b\d{2}/\d{2}/\d{4}\b', "Date of birth"),
    "zip_code": (r'\b\d{5}(?:-\d{4})?\b', "ZIP code"),
}


@dataclass
class PIIDetection:
    """Result of PII detection."""
    pii_type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class ComplianceViolation:
    """A compliance violation."""
    violation_id: str
    rule_id: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    resource_type: str
    resource_id: str
    detected_at: float = 0.0
    remediation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComplianceManager:
    """Manages compliance rules and detects violations."""

    def __init__(self):
        self._rules: Dict[str, Dict[str, Any]] = {}
        self._violations: List[ComplianceViolation] = []
        self._violation_counter = 0

    def add_rule(
        self,
        rule_id: str,
        description: str,
        severity: str = "medium",
        check_fn: Optional[Any] = None,
    ) -> None:
        """Add a compliance rule."""
        self._rules[rule_id] = {
            "rule_id": rule_id,
            "description": description,
            "severity": severity,
            "check_fn": check_fn,
        }

    def check_compliance(
        self,
        data: Dict[str, Any],
        resource_type: str = "",
        resource_id: str = "",
    ) -> List[ComplianceViolation]:
        """Check data against all compliance rules."""
        violations = []

        # Check for PII
        pii_results = detect_pii(str(data))
        if pii_results:
            self._violation_counter += 1
            violation = ComplianceViolation(
                violation_id=f"viol_{self._violation_counter:06d}",
                rule_id="pii_detection",
                severity="high",
                description=f"PII detected: {', '.join(p.pii_type for p in pii_results)}",
                resource_type=resource_type,
                resource_id=resource_id,
                remediation="Redact or encrypt PII before processing",
            )
            violations.append(violation)
            self._violations.append(violation)

        # Check custom rules
        for rule_id, rule in self._rules.items():
            check_fn = rule.get("check_fn")
            if check_fn:
                try:
                    if check_fn(data):
                        self._violation_counter += 1
                        violation = ComplianceViolation(
                            violation_id=f"viol_{self._violation_counter:06d}",
                            rule_id=rule_id,
                            severity=rule.get("severity", "medium"),
                            description=rule.get("description", ""),
                            resource_type=resource_type,
                            resource_id=resource_id,
                        )
                        violations.append(violation)
                        self._violations.append(violation)
                except Exception:
                    pass

        return violations

    def get_violations(
        self,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[ComplianceViolation]:
        """Get compliance violations."""
        violations = self._violations
        if severity:
            violations = [v for v in violations if v.severity == severity]
        return violations[-limit:]

    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate a compliance report."""
        severity_counts = {}
        for v in self._violations:
            severity_counts[v.severity] = severity_counts.get(v.severity, 0) + 1

        return {
            "total_violations": len(self._violations),
            "by_severity": severity_counts,
            "rules_configured": len(self._rules),
        }


def detect_pii(text: str) -> List[PIIDetection]:
    """Detect PII in text.

    Args:
        text: Text to scan for PII.

    Returns:
        List of PIIDetection objects.
    """
    detections = []
    for pii_type, (pattern, description) in PII_PATTERNS.items():
        for match in re.finditer(pattern, text):
            detections.append(PIIDetection(
                pii_type=pii_type,
                value=match.group(),
                start=match.start(),
                end=match.end(),
            ))
    return detections


def redact_pii(text: str, replacement: str = "[REDACTED]") -> Tuple[str, int]:
    """Redact PII from text.

    Args:
        text: Text to redact.
        replacement: Replacement string for PII.

    Returns:
        Tuple of (redacted_text, count_of_redactions).
    """
    count = 0
    for pii_type, (pattern, _) in PII_PATTERNS.items():
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            count += len(re.findall(pattern, text))
            text = new_text
    return text, count
