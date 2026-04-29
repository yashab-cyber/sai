"""
S.A.I. Business Engine — Autonomous Revenue Generation Orchestrator.

Central coordinator for SAI's freelance business operations.
Composes: JobScraper, ProposalGenerator, ProjectManager, ClientCRM,
InvoiceManager, and BusinessDashboard into a unified business pipeline.

Analogous to GitHubPresence but for revenue generation.
"""

import os
import random
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional


class BusinessEngine:
    """
    Main orchestrator for SAI's autonomous business operations.
    Manages the full freelance lifecycle: discover → bid → deliver → invoice.
    """

    # Weighted actions — selected probabilistically during idle business cycles
    BUSINESS_ACTIONS = [
        {"name": "find_jobs",        "weight": 40},
        {"name": "evaluate_jobs",    "weight": 20},
        {"name": "send_proposals",   "weight": 20},
        {"name": "deliver_project",  "weight": 10},
        {"name": "follow_up",        "weight": 5},
        {"name": "update_portfolio", "weight": 5},
    ]

    def __init__(self, brain=None, memory=None, browser=None,
                 email_mgr=None, identity=None, config: dict = None):
        self.brain = brain
        self.memory = memory
        self.browser = browser
        self.email_mgr = email_mgr
        self.identity = identity
        self.config = config or {}
        self.logger = logging.getLogger("SAI.BusinessEngine")

        self._enabled = self.config.get("enabled", True)
        self._actions_executed = 0
        self._last_action_time = 0
        self.action_history: List[Dict[str, Any]] = []

        # Initialize sub-modules
        self._init_submodules()
        self.logger.info("BusinessEngine initialized — enabled=%s", self._enabled)

    def _init_submodules(self):
        """Lazily initialize business sub-modules."""
        from modules.business.job_scraper import JobScraper
        from modules.business.proposal_generator import ProposalGenerator
        from modules.business.project_manager import ProjectManager
        from modules.business.client_crm import ClientCRM
        from modules.business.invoice_manager import InvoiceManager
        from modules.business.business_dashboard import BusinessDashboard

        self.scraper = JobScraper(
            browser=self.browser,
            brain=self.brain,
            config=self.config,
        )
        self.proposals = ProposalGenerator(
            brain=self.brain,
            config=self.config,
        )
        self.project_mgr = ProjectManager(
            brain=self.brain,
            identity=self.identity,
            email_mgr=self.email_mgr,
            config=self.config,
        )
        self.crm = ClientCRM(brain=self.brain)
        self.invoices = InvoiceManager(email_mgr=self.email_mgr)
        self.dashboard = BusinessDashboard(
            scraper=self.scraper,
            proposals=self.proposals,
            crm=self.crm,
            invoices=self.invoices,
            projects=self.project_mgr,
        )

    # ══════════════════════════════════════════
    # IDLE ENGINE ENTRY POINT
    # ══════════════════════════════════════════

    def run_business_action(self) -> Dict[str, Any]:
        """
        Main entry point — called by IdleEngine during business-allocated idle time.
        Selects a weighted random business action and executes it.
        """
        if not self._enabled:
            return {"status": "skipped", "reason": "business_engine_disabled"}

        # Select action
        actions = [a for a in self.BUSINESS_ACTIONS if a["weight"] > 0]
        if not actions:
            return {"status": "skipped", "reason": "no_actions_configured"}

        weights = [a["weight"] for a in actions]
        selected = random.choices(actions, weights=weights, k=1)[0]
        action_name = selected["name"]

        self.logger.info("Business action selected: %s", action_name)

        try:
            handler = getattr(self, f"_action_{action_name}", None)
            if not handler:
                return {"status": "error", "message": f"No handler for: {action_name}"}

            result = handler()
            self._actions_executed += 1
            self._last_action_time = datetime.now().timestamp()
            self._record_action(action_name, result)

            return {
                "status": result.get("status", "unknown") if isinstance(result, dict) else "unknown",
                "action": action_name,
                "result": result,
            }
        except Exception as e:
            self.logger.error("Business action '%s' failed: %s", action_name, e)
            return {"status": "error", "action": action_name, "message": str(e)}

    # ══════════════════════════════════════════
    # ACTION HANDLERS
    # ══════════════════════════════════════════

    def _action_find_jobs(self) -> dict:
        """Scrapes freelance platforms for new job listings."""
        platforms = self.config.get("platforms", ["upwork", "freelancer"])
        platform = random.choice(platforms)
        skill_focus = self.config.get("skill_focus", ["python", "automation"])
        query = " ".join(random.sample(skill_focus, min(3, len(skill_focus))))

        self.logger.info("Scanning %s for: %s", platform, query)

        # discover_jobs is async — wrap in asyncio.run()
        try:
            result = asyncio.run(
                self.scraper.discover_jobs(query=query, platform=platform, max_jobs=10)
            )
            return result
        except RuntimeError:
            # Already in an event loop — use nest_asyncio or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    lambda: asyncio.run(
                        self.scraper.discover_jobs(query=query, platform=platform, max_jobs=10)
                    )
                )
                return future.result(timeout=120)

    def _action_evaluate_jobs(self) -> dict:
        """Evaluates unevaluated jobs using LLM scoring."""
        new_jobs = self.scraper.get_new_jobs(limit=5)
        if not new_jobs:
            return {"status": "skipped", "reason": "no_unevaluated_jobs"}

        evaluated = 0
        for job in new_jobs:
            result = self.scraper.evaluate_job(job["id"])
            if result.get("status") == "success":
                evaluated += 1

        return {"status": "success", "evaluated": evaluated, "total_new": len(new_jobs)}

    def _action_send_proposals(self) -> dict:
        """Generates and queues proposals for top-scoring jobs."""
        if not self.proposals.can_send_more():
            return {"status": "skipped", "reason": "daily_proposal_limit_reached"}

        top_jobs = self.scraper.get_top_jobs(min_score=60, limit=5)
        if not top_jobs:
            return {"status": "skipped", "reason": "no_high_scoring_jobs"}

        # Pick a random top job that doesn't already have a proposal
        sent = 0
        for job in top_jobs:
            if job.get("proposal_id", 0) > 0:
                continue  # Already has a proposal

            # Get relevant portfolio repos
            portfolio = self._get_relevant_repos(job)

            result = self.proposals.generate_proposal(job, portfolio_repos=portfolio)
            if result.get("status") == "success":
                # Link proposal to job
                proposal_id = result.get("proposal_id", 0)
                if proposal_id:
                    self.scraper.update_job_status(job["id"], "proposal_sent")
                sent += 1

            if not self.proposals.can_send_more():
                break

        return {"status": "success", "proposals_sent": sent}

    def _action_deliver_project(self) -> dict:
        """Works on active projects."""
        active = self.project_mgr.list_projects(status="in_progress")
        if not active:
            # Check for accepted projects that need starting
            accepted = self.project_mgr.list_projects(status="accepted")
            if accepted:
                project = accepted[0]
                return self.project_mgr.start_project(project["id"])
            return {"status": "skipped", "reason": "no_active_projects"}

        # Work on the highest priority active project
        project = active[0]
        return self.project_mgr.work_on_project(project["id"])

    def _action_follow_up(self) -> dict:
        """Follows up on pending proposals and overdue invoices."""
        results = {"proposals_followed_up": 0, "reminders_sent": 0}

        # Check for overdue invoices
        overdue = self.invoices.get_overdue()
        for inv in overdue[:3]:
            reminder = self.invoices.send_reminder(inv["invoice_number"])
            if reminder.get("status") == "success":
                results["reminders_sent"] += 1

        return {"status": "success", **results}

    def _action_update_portfolio(self) -> dict:
        """Updates SAI's freelancer profile descriptions with latest stats."""
        stats = self.dashboard.get_full_summary()
        proposals = stats.get("proposals", {})
        projects = stats.get("projects", {})

        summary = (
            f"Portfolio update: {proposals.get('won', 0)} projects won, "
            f"{projects.get('total_projects', 0)} total projects, "
            f"Win rate: {proposals.get('win_rate_pct', 0)}%"
        )
        self.logger.info(summary)
        return {"status": "success", "summary": summary}

    # ══════════════════════════════════════════
    # TOOL DISPATCH METHODS (called from sai.py)
    # ══════════════════════════════════════════

    def find_jobs(self, platform: str = "", query: str = "") -> dict:
        """Manual job search trigger."""
        platforms = [platform] if platform else self.config.get("platforms", ["upwork"])
        results = []
        for p in platforms:
            try:
                result = asyncio.run(
                    self.scraper.discover_jobs(query=query, platform=p, max_jobs=15)
                )
                results.append(result)
            except RuntimeError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        lambda pl=p: asyncio.run(
                            self.scraper.discover_jobs(query=query, platform=pl, max_jobs=15)
                        )
                    )
                    results.append(future.result(timeout=120))

        return {"status": "success", "results": results}

    def send_proposal(self, job_id: int = 0, style: str = "") -> dict:
        """Generates a proposal for a specific job."""
        if job_id:
            job = self.scraper.get_job(job_id)
            if not job:
                return {"status": "error", "message": f"Job #{job_id} not found"}
            portfolio = self._get_relevant_repos(job)
            return self.proposals.generate_proposal(job, portfolio_repos=portfolio, style=style)

        # Auto-select best job
        top = self.scraper.get_top_jobs(min_score=50, limit=1)
        if not top:
            return {"status": "error", "message": "No suitable jobs found"}
        portfolio = self._get_relevant_repos(top[0])
        return self.proposals.generate_proposal(top[0], portfolio_repos=portfolio, style=style)

    def manage_projects(self, action: str = "list", project_id: int = 0, **kwargs) -> dict:
        """Project management dispatch."""
        if action == "list":
            projects = self.project_mgr.list_projects(
                status=kwargs.get("status", ""), limit=kwargs.get("limit", 20)
            )
            return {"status": "success", "projects": projects, "count": len(projects)}
        elif action == "create":
            return self.project_mgr.create_project(**kwargs)
        elif action == "start" and project_id:
            return self.project_mgr.start_project(project_id)
        elif action == "work" and project_id:
            return self.project_mgr.work_on_project(project_id)
        elif action == "deliver" and project_id:
            return self.project_mgr.deliver_project(project_id)
        elif action == "status" and project_id:
            project = self.project_mgr.get_project(project_id)
            return {"status": "success", "project": project} if project else {"status": "error", "message": "Not found"}
        return {"status": "error", "message": f"Unknown project action: {action}"}

    def manage_invoices(self, action: str = "list", **kwargs) -> dict:
        """Invoice management dispatch."""
        if action == "list":
            invoices = self.invoices.list_invoices(
                status=kwargs.get("status", ""), limit=kwargs.get("limit", 50)
            )
            return {"status": "success", "invoices": invoices, "count": len(invoices)}
        elif action == "create":
            return self.invoices.create_invoice(**kwargs)
        elif action == "pay":
            return self.invoices.mark_paid(
                kwargs.get("invoice_number", ""),
                kwargs.get("payment_method", "platform")
            )
        elif action == "remind":
            return self.invoices.send_reminder(kwargs.get("invoice_number", ""))
        elif action == "revenue":
            return self.invoices.get_revenue_summary()
        return {"status": "error", "message": f"Unknown invoice action: {action}"}

    def get_analytics(self) -> dict:
        """Returns comprehensive business analytics."""
        return self.dashboard.get_full_summary()

    # ══════════════════════════════════════════
    # STATUS & HELPERS
    # ══════════════════════════════════════════

    def get_status(self) -> dict:
        """Returns business engine diagnostics for status reports."""
        try:
            revenue = self.invoices.get_revenue_summary()
            proposal_stats = self.proposals.get_stats()
            project_stats = self.project_mgr.get_stats()
            client_stats = self.crm.get_summary()
            job_stats = self.scraper.get_stats()
        except Exception as e:
            self.logger.debug("Status fetch partial failure: %s", e)
            revenue = proposal_stats = project_stats = client_stats = job_stats = {}

        return {
            "enabled": self._enabled,
            "actions_executed": self._actions_executed,
            "last_action_time": (
                datetime.fromtimestamp(self._last_action_time).isoformat()
                if self._last_action_time else None
            ),
            "revenue": revenue,
            "proposals": proposal_stats,
            "projects": project_stats,
            "clients": client_stats,
            "jobs": job_stats,
        }

    def _get_relevant_repos(self, job: dict) -> List[str]:
        """Finds relevant GitHub repos to include in proposals."""
        if not self.identity:
            return []
        try:
            github_user = os.getenv("SAI_GITHUB_USERNAME", "")
            result = self.identity.github_api_request(
                "GET", f"users/{github_user}/repos?sort=updated&per_page=10"
            )
            if result.get("status") == "success":
                repos = result.get("data", [])
                return [r.get("name", "") for r in repos[:5] if isinstance(r, dict)]
        except Exception:
            pass
        return []

    def _record_action(self, action_name: str, result: dict):
        """Records action to history and semantic memory."""
        record = {
            "action": action_name,
            "timestamp": datetime.now().isoformat(),
            "status": result.get("status", "unknown") if isinstance(result, dict) else "unknown",
        }
        self.action_history.append(record)
        # Cap history to last 50 entries
        if len(self.action_history) > 50:
            self.action_history = self.action_history[-50:]

        try:
            if self.memory and self.brain:
                content = f"Business action: {action_name} — {str(result)[:300]}"
                embedding = self.brain.get_embedding(content)
                self.memory.save_semantic_memory(
                    content, embedding,
                    {"type": "business_action", "action": action_name}
                )
        except Exception as e:
            self.logger.debug("Failed to persist business action to memory: %s", e)

    def get_pending_work(self) -> Dict[str, Any]:
        """Returns pending business work state for pause/resume support."""
        active_projects = []
        try:
            active_projects = self.project_mgr.list_projects(status="in_progress")
        except Exception:
            pass
        return {
            "active_projects": len(active_projects),
            "actions_executed": self._actions_executed,
        }

    def restore_pending_work(self, state: Dict[str, Any]):
        """Restores business engine state after resume."""
        self.logger.info("Business engine state restored.")
