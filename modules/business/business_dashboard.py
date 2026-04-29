"""
S.A.I. Business Dashboard — Revenue and performance analytics.

Aggregates data from all business sub-modules into unified analytics
for status reports, dashboard display, and decision making.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class BusinessDashboard:
    """Aggregates business analytics from all sub-modules."""

    def __init__(self, scraper=None, proposals=None, crm=None,
                 invoices=None, projects=None):
        self.scraper = scraper
        self.proposals = proposals
        self.crm = crm
        self.invoices = invoices
        self.projects = projects
        self.logger = logging.getLogger("SAI.Business.Dashboard")

    def get_full_summary(self) -> dict:
        """Returns comprehensive business analytics."""
        summary = {
            "generated_at": datetime.now().isoformat(),
            "revenue": self._safe_call(self._get_revenue),
            "pipeline": self._safe_call(self._get_pipeline),
            "clients": self._safe_call(self._get_client_metrics),
            "proposals": self._safe_call(self._get_proposal_metrics),
            "projects": self._safe_call(self._get_project_metrics),
        }
        return summary

    def _get_revenue(self) -> dict:
        """Revenue tracking metrics."""
        if not self.invoices:
            return {}
        rev = self.invoices.get_revenue_summary()
        proj_stats = self.projects.get_stats() if self.projects else {}
        return {
            "total_earned_usd": rev.get("total_earned_usd", 0),
            "pending_usd": rev.get("pending_usd", 0),
            "overdue_invoices": rev.get("overdue_invoices", 0),
            "total_invoices": rev.get("total_invoices", 0),
            "collection_rate_pct": rev.get("collection_rate", 0),
            "project_revenue_usd": proj_stats.get("total_revenue_usd", 0),
        }

    def _get_pipeline(self) -> dict:
        """Job discovery pipeline metrics."""
        if not self.scraper:
            return {}
        stats = self.scraper.get_stats()
        return {
            "total_jobs_discovered": stats.get("total_jobs", 0),
            "jobs_by_status": stats.get("by_status", {}),
            "avg_fit_score": stats.get("avg_fit_score", 0),
        }

    def _get_client_metrics(self) -> dict:
        """Client relationship metrics."""
        if not self.crm:
            return {}
        return self.crm.get_summary()

    def _get_proposal_metrics(self) -> dict:
        """Proposal performance metrics."""
        if not self.proposals:
            return {}
        stats = self.proposals.get_stats()
        return {
            "total_proposals": stats.get("total_proposals", 0),
            "submitted": stats.get("submitted", 0),
            "won": stats.get("won", 0),
            "rejected": stats.get("rejected", 0),
            "win_rate_pct": stats.get("win_rate_pct", 0),
            "total_bid_value_usd": stats.get("total_bid_value_usd", 0),
            "won_value_usd": stats.get("won_value_usd", 0),
            "today_proposals": stats.get("today_count", 0),
            "daily_limit": stats.get("daily_limit", 10),
        }

    def _get_project_metrics(self) -> dict:
        """Project delivery metrics."""
        if not self.projects:
            return {}
        return self.projects.get_stats()

    def _safe_call(self, func) -> dict:
        """Wraps analytics calls to prevent one failure from crashing the whole report."""
        try:
            return func()
        except Exception as e:
            self.logger.debug("Dashboard metric failed: %s", e)
            return {"error": str(e)}
