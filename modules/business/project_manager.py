"""
S.A.I. Project Manager — Client project lifecycle management.

Manages projects from acceptance through delivery and payment.
Lifecycle: accepted → in_progress → review → delivered → paid
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class ProjectManager:
    """Manages freelance client projects from acceptance to delivery."""

    DB_PATH = os.path.join("logs", "sai_business.db")

    def __init__(self, brain=None, identity=None, email_mgr=None, config: dict = None):
        self.brain = brain
        self.identity = identity
        self.email_mgr = email_mgr
        self.config = config or {}
        self.logger = logging.getLogger("SAI.Business.Projects")
        self.github_user = os.getenv("SAI_GITHUB_USERNAME", "")
        self.max_concurrent = int(self.config.get("max_concurrent_projects", 3))
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                client_name TEXT DEFAULT '',
                client_email TEXT DEFAULT '',
                client_id INTEGER DEFAULT 0,
                platform TEXT DEFAULT '',
                proposal_id INTEGER DEFAULT 0,
                budget_usd REAL DEFAULT 0.0,
                status TEXT DEFAULT 'accepted',
                priority INTEGER DEFAULT 5,
                repo_name TEXT DEFAULT '',
                repo_url TEXT DEFAULT '',
                deadline TEXT DEFAULT '',
                started_at TEXT DEFAULT '',
                delivered_at TEXT DEFAULT '',
                paid_at TEXT DEFAULT '',
                tasks_json TEXT DEFAULT '[]',
                progress_pct INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS project_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                due_date TEXT DEFAULT '',
                completed_at TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    # ══════════════════════════════════════════
    # PROJECT LIFECYCLE
    # ══════════════════════════════════════════

    def create_project(self, title: str, description: str = "", client_name: str = "",
                       client_email: str = "", budget_usd: float = 0.0,
                       deadline: str = "", platform: str = "",
                       proposal_id: int = 0) -> dict:
        """Creates a new project in 'accepted' status."""
        active_count = len(self.list_projects(status="in_progress"))
        if active_count >= self.max_concurrent:
            return {"status": "error", "message": f"Max concurrent projects ({self.max_concurrent}) reached"}

        if not deadline:
            deadline = (datetime.now() + timedelta(days=14)).isoformat()

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO projects (title,description,client_name,client_email,
                   budget_usd,deadline,platform,proposal_id)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (title, description[:5000], client_name, client_email,
                 budget_usd, deadline, platform, proposal_id))
            conn.commit()
            pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self.logger.info("Project created: #%d — %s ($%.2f)", pid, title, budget_usd)
            return {"status": "success", "project_id": pid, "title": title}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def start_project(self, project_id: int) -> dict:
        """Transitions project to in_progress and creates a GitHub repo."""
        project = self.get_project(project_id)
        if not project:
            return {"status": "error", "message": "Project not found"}
        if project["status"] != "accepted":
            return {"status": "error", "message": f"Cannot start project in '{project['status']}' status"}

        # Create private GitHub repo for the project
        repo_name = f"client-{project_id}-{project['title'][:30].lower().replace(' ', '-')}"
        repo_url = ""
        if self.identity and self.github_user:
            try:
                result = self.identity.github_api_request("POST", "user/repos", {
                    "name": repo_name,
                    "description": f"Client project: {project['title']}",
                    "private": True, "auto_init": True,
                })
                if result.get("status") == "success":
                    repo_url = f"https://github.com/{self.github_user}/{repo_name}"
            except Exception as e:
                self.logger.warning("Repo creation failed: %s", e)

        # Break down project into tasks using LLM
        tasks = self._generate_task_breakdown(project)

        conn = self._conn()
        try:
            conn.execute(
                """UPDATE projects SET status='in_progress',started_at=?,
                   repo_name=?,repo_url=?,tasks_json=?,updated_at=datetime('now')
                   WHERE id=?""",
                (datetime.now().isoformat(), repo_name, repo_url,
                 json.dumps(tasks), project_id))
            conn.commit()

            # Notify client
            if project.get("client_email") and self.email_mgr:
                self.email_mgr.send(
                    to=project["client_email"],
                    subject=f"Project Started — {project['title']}",
                    body=(f"Hello {project['client_name']},\n\n"
                          f"I've started working on your project: {project['title']}.\n"
                          f"I'll keep you updated on progress.\n\n"
                          f"Best regards,\nS.A.I. Development Services"))

            return {"status": "success", "project_id": project_id,
                    "repo": repo_name, "tasks": len(tasks)}
        finally:
            conn.close()

    def work_on_project(self, project_id: int) -> dict:
        """Progresses work on an active project."""
        project = self.get_project(project_id)
        if not project:
            return {"status": "error", "message": "Project not found"}
        if project["status"] != "in_progress":
            return {"status": "skipped", "reason": f"Project status is '{project['status']}'"}

        tasks = json.loads(project.get("tasks_json", "[]"))
        pending = [t for t in tasks if t.get("status") != "done"]
        if not pending:
            return self._mark_ready_for_review(project_id)

        # Work on the next pending task
        current_task = pending[0]
        current_task["status"] = "done"

        # Update progress
        done_count = sum(1 for t in tasks if t.get("status") == "done")
        progress = int(done_count / max(len(tasks), 1) * 100)

        conn = self._conn()
        try:
            conn.execute(
                "UPDATE projects SET tasks_json=?,progress_pct=?,updated_at=datetime('now') WHERE id=?",
                (json.dumps(tasks), progress, project_id))
            conn.commit()

            self.logger.info("Project #%d progress: %d%% (%s)", project_id, progress,
                             current_task.get("title", ""))

            if progress >= 100:
                return self._mark_ready_for_review(project_id)

            return {"status": "success", "progress": progress,
                    "task_completed": current_task.get("title", ""),
                    "remaining": len(pending) - 1}
        finally:
            conn.close()

    def deliver_project(self, project_id: int) -> dict:
        """Marks project as delivered."""
        conn = self._conn()
        try:
            project = self.get_project(project_id)
            if not project:
                return {"status": "error", "message": "Project not found"}

            conn.execute(
                "UPDATE projects SET status='delivered',delivered_at=?,progress_pct=100,updated_at=datetime('now') WHERE id=?",
                (datetime.now().isoformat(), project_id))
            conn.commit()

            # Notify client
            if project.get("client_email") and self.email_mgr:
                self.email_mgr.send(
                    to=project["client_email"],
                    subject=f"Project Delivered — {project['title']}",
                    body=(f"Hello {project['client_name']},\n\n"
                          f"Your project '{project['title']}' has been completed and delivered.\n"
                          f"Please review and let me know if any adjustments are needed.\n\n"
                          f"Best regards,\nS.A.I. Development Services"))

            return {"status": "success", "project_id": project_id, "delivered": True}
        finally:
            conn.close()

    def mark_paid(self, project_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE projects SET status='paid',paid_at=?,updated_at=datetime('now') WHERE id=?",
                (datetime.now().isoformat(), project_id))
            conn.commit()
            return {"status": "success", "project_id": project_id}
        finally:
            conn.close()

    # ══════════════════════════════════════════
    # QUERIES
    # ══════════════════════════════════════════

    def get_project(self, project_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_projects(self, status: str = "", limit: int = 20) -> List[dict]:
        conn = self._conn()
        try:
            q = "SELECT * FROM projects"
            params = []
            if status:
                q += " WHERE status=?"
                params.append(status)
            q += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM projects WHERE status='in_progress'").fetchone()[0]
            delivered = conn.execute("SELECT COUNT(*) FROM projects WHERE status='delivered'").fetchone()[0]
            paid = conn.execute("SELECT COUNT(*) FROM projects WHERE status='paid'").fetchone()[0]
            revenue = conn.execute("SELECT COALESCE(SUM(budget_usd),0) FROM projects WHERE status='paid'").fetchone()[0]
            return {"total_projects": total, "active": active, "delivered": delivered,
                    "paid": paid, "total_revenue_usd": round(revenue, 2)}
        finally:
            conn.close()

    # ══════════════════════════════════════════
    # MILESTONES
    # ══════════════════════════════════════════

    def add_milestone(self, project_id: int, title: str, description: str = "",
                      due_date: str = "") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO project_milestones (project_id,title,description,due_date) VALUES (?,?,?,?)",
                (project_id, title, description, due_date))
            conn.commit()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def complete_milestone(self, milestone_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE project_milestones SET status='completed',completed_at=? WHERE id=?",
                (datetime.now().isoformat(), milestone_id))
            conn.commit()
            return {"status": "success"}
        finally:
            conn.close()

    def list_milestones(self, project_id: int) -> List[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM project_milestones WHERE project_id=? ORDER BY created_at",
                (project_id,)).fetchall()]
        finally:
            conn.close()

    # ══════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════

    def _generate_task_breakdown(self, project: dict) -> List[dict]:
        """Uses LLM to break project into tasks."""
        if not self.brain:
            return [{"title": "Complete project", "status": "pending"}]
        try:
            prompt = (
                f"Break this software project into 3-6 implementation tasks:\\n"
                f"TITLE: {project.get('title', '')}\\n"
                f"DESCRIPTION: {project.get('description', '')[:1000]}\\n\\n"
                'Respond JSON: {{"tasks": [{{"title": "task name", "status": "pending"}}]}}'
            )
            response = self.brain.prompt("Break project into tasks.", prompt)
            data = response if isinstance(response, dict) else json.loads(str(response))
            tasks = data.get("tasks", [])
            if tasks:
                return tasks
        except Exception as e:
            self.logger.warning("Task breakdown failed: %s", e)
        return [{"title": "Implement project requirements", "status": "pending"},
                {"title": "Write tests", "status": "pending"},
                {"title": "Write documentation", "status": "pending"}]

    def _mark_ready_for_review(self, project_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE projects SET status='review',progress_pct=100,updated_at=datetime('now') WHERE id=?",
                (project_id,))
            conn.commit()
            return {"status": "success", "action": "ready_for_review", "progress": 100}
        finally:
            conn.close()
