"""Dashboard data provider for Phoenix-Evo enterprise features."""

from __future__ import annotations

from typing import Any


class DashboardProvider:
    """Provides data for enterprise dashboards."""

    def __init__(self):
        self._metrics: dict[str, list[dict[str, Any]]] = {}
        self._widgets: dict[str, dict[str, Any]] = {}

    def register_widget(self, widget_id: str, widget_type: str, config: dict[str, Any]) -> None:
        """Register a dashboard widget."""
        self._widgets[widget_id] = {
            "widget_id": widget_id,
            "type": widget_type,
            "config": config,
        }

    def push_metric(self, metric_name: str, value: Any, tags: dict[str, str] | None = None) -> None:
        """Push a metric data point."""
        import time
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []
        self._metrics[metric_name].append({
            "value": value,
            "timestamp": time.time(),
            "tags": tags or {},
        })

    def get_metric(self, metric_name: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent metric data points."""
        data = self._metrics.get(metric_name, [])
        return data[-limit:]

    def get_metric_summary(self, metric_name: str) -> dict[str, Any]:
        """Get a summary of a metric."""
        data = self._metrics.get(metric_name, [])
        if not data:
            return {"count": 0, "latest": None}

        values = [d["value"] for d in data if isinstance(d["value"], (int, float))]
        if not values:
            return {"count": len(data), "latest": data[-1]["value"]}

        return {
            "count": len(data),
            "latest": data[-1]["value"],
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get all dashboard data."""
        return {
            "widgets": self._widgets,
            "metrics": {
                name: self.get_metric_summary(name)
                for name in self._metrics
            },
        }

    def get_widget_data(self, widget_id: str) -> dict[str, Any] | None:
        """Get data for a specific widget."""
        widget = self._widgets.get(widget_id)
        if not widget:
            return None

        metric_name = widget.get("config", {}).get("metric")
        if metric_name:
            return {
                "widget": widget,
                "data": self.get_metric(metric_name),
            }
        return {"widget": widget, "data": []}

    def list_widgets(self) -> list[dict[str, Any]]:
        """List all registered widgets."""
        return list(self._widgets.values())
