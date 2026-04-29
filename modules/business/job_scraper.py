"""
S.A.I. Job Scraper — Multi-platform freelance job discovery.

Uses SAI's BrowserManager (Playwright) to scrape job listings from
Upwork, Freelancer, and LinkedIn. Stores discovered jobs in SQLite
with deduplication via URL hashing.
"""

import os
import hashlib
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional


class JobScraper:
    """
    Platform-agnostic job scraper for freelance marketplaces.
    Discovers and stores job listings matching SAI's skill profile.
    """

    DB_PATH = os.path.join("logs", "sai_business.db")

    # Platform search URL templates
    PLATFORM_URLS = {
        "upwork": "https://www.upwork.com/nx/search/jobs/?q={query}&sort=recency",
        "freelancer": "https://www.freelancer.com/jobs/?keyword={query}&order_field=time_updated",
        "linkedin": "https://www.linkedin.com/jobs/search/?keywords={query}&sortBy=DD",
    }

    def __init__(self, browser=None, brain=None, config: dict = None):
        self.browser = browser
        self.brain = brain
        self.config = config or {}
        self.logger = logging.getLogger("SAI.Business.JobScraper")
        self._init_db()

        self.skill_focus = self.config.get("skill_focus", [
            "python", "automation", "web-scraping", "api-development", "ai-ml",
        ])
        self.min_budget = float(self.config.get("min_budget_usd", 50))
        self.platforms = self.config.get("platforms", ["upwork", "freelancer"])

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT UNIQUE NOT NULL,
                platform TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                url TEXT DEFAULT '',
                budget_min REAL DEFAULT 0,
                budget_max REAL DEFAULT 0,
                budget_type TEXT DEFAULT 'fixed',
                skills TEXT DEFAULT '[]',
                client_name TEXT DEFAULT '',
                client_rating REAL DEFAULT 0,
                client_spend TEXT DEFAULT '',
                deadline TEXT DEFAULT '',
                posted_at TEXT DEFAULT '',
                status TEXT DEFAULT 'new',
                fit_score REAL DEFAULT 0.0,
                fit_reason TEXT DEFAULT '',
                proposal_id INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    # ══════════════════════════════════════════
    # JOB DISCOVERY
    # ══════════════════════════════════════════

    async def discover_jobs(self, query: str = "", platform: str = "upwork",
                            max_jobs: int = 10) -> dict:
        """
        Scrapes a freelance platform for job listings.
        Uses BrowserManager for automation and Brain for parsing.
        """
        if not self.browser:
            return {"status": "error", "message": "Browser not available"}

        if not query:
            query = " ".join(self.skill_focus[:3])

        url_template = self.PLATFORM_URLS.get(platform)
        if not url_template:
            return {"status": "error", "message": f"Unknown platform: {platform}"}

        import urllib.parse
        search_url = url_template.format(query=urllib.parse.quote(query))
        self.logger.info("[JobScraper] Searching %s: %s", platform, query)

        try:
            # Navigate to job listing page
            nav_result = await self.browser.navigate(search_url)
            if nav_result.get("status") != "success":
                return {"status": "error", "message": f"Navigation failed: {nav_result}"}

            # Wait for content to load
            import asyncio
            await asyncio.sleep(3)

            # Scrape visible text content
            page_text = await self.browser.scrape_page_text()
            text_content = page_text.get("text", "") if isinstance(page_text, dict) else str(page_text)

            if not text_content or len(text_content) < 100:
                return {"status": "error", "message": "No content scraped from page"}

            # Use LLM to extract structured job data from raw page text
            jobs = self._parse_jobs_with_llm(text_content, platform, max_jobs)

            # Store discovered jobs
            stored = 0
            for job in jobs:
                if self._store_job(job):
                    stored += 1

            self.logger.info("[JobScraper] Found %d jobs, stored %d new on %s",
                             len(jobs), stored, platform)
            return {
                "status": "success",
                "platform": platform,
                "query": query,
                "found": len(jobs),
                "new_stored": stored,
            }
        except Exception as e:
            self.logger.error("[JobScraper] Scrape failed: %s", e)
            return {"status": "error", "message": str(e)}

    def _parse_jobs_with_llm(self, page_text: str, platform: str,
                              max_jobs: int) -> List[dict]:
        """Uses LLM to extract structured job listings from raw page text."""
        if not self.brain:
            return []

        import json
        prompt = (
            f"You are S.A.I., parsing job listings from {platform}.\\n"
            f"Extract up to {max_jobs} job listings from this page text.\\n\\n"
            f"PAGE TEXT (truncated):\\n{page_text[:6000]}\\n\\n"
            "For each job, extract:\\n"
            "- title: job title\\n"
            "- description: brief description (max 300 chars)\\n"
            "- budget_min: minimum budget USD (0 if not listed)\\n"
            "- budget_max: maximum budget USD (0 if not listed)\\n"
            "- budget_type: 'fixed' or 'hourly'\\n"
            "- skills: list of required skills\\n"
            "- url: job URL if visible (else empty string)\\n\\n"
            'Respond in JSON: {"jobs": [{"title":"...","description":"...","budget_min":0,'
            '"budget_max":0,"budget_type":"fixed","skills":["s1"],"url":""}]}'
        )
        try:
            response = self.brain.prompt("Extract job listings from page.", prompt)
            data = response if isinstance(response, dict) else json.loads(str(response))
            jobs = data.get("jobs", [])
            for job in jobs:
                job["platform"] = platform
            return jobs
        except Exception as e:
            self.logger.warning("[JobScraper] LLM parse failed: %s", e)
            return []

    def _store_job(self, job: dict) -> bool:
        """Stores a job if it's new (deduplication via URL/title hash)."""
        url = job.get("url", "")
        title = job.get("title", "")
        hash_input = url if url else f"{job.get('platform', '')}:{title}"
        url_hash = self._url_hash(hash_input)

        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM jobs WHERE url_hash=?",
                                    (url_hash,)).fetchone()
            if existing:
                return False

            import json
            skills = json.dumps(job.get("skills", []))
            conn.execute(
                """INSERT INTO jobs (url_hash,platform,title,description,url,
                   budget_min,budget_max,budget_type,skills,posted_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (url_hash, job.get("platform", ""), title,
                 job.get("description", "")[:2000], url,
                 float(job.get("budget_min", 0)),
                 float(job.get("budget_max", 0)),
                 job.get("budget_type", "fixed"), skills,
                 datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            self.logger.debug("Store job failed: %s", e)
            return False
        finally:
            conn.close()

    # ══════════════════════════════════════════
    # JOB EVALUATION
    # ══════════════════════════════════════════

    def evaluate_job(self, job_id: int) -> dict:
        """Uses LLM to score how well a job fits SAI's capabilities."""
        job = self.get_job(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}
        if not self.brain:
            return {"status": "error", "message": "Brain not available"}

        import json
        prompt = (
            "You are S.A.I., an autonomous AI agent evaluating a freelance job.\\n"
            f"YOUR SKILLS: {', '.join(self.skill_focus)}\\n"
            f"MIN BUDGET: ${self.min_budget}\\n\\n"
            f"JOB TITLE: {job['title']}\\n"
            f"DESCRIPTION: {job['description'][:1000]}\\n"
            f"BUDGET: ${job['budget_min']}-${job['budget_max']} ({job['budget_type']})\\n"
            f"SKILLS REQUIRED: {job['skills']}\\n\\n"
            "Score this job 0-100 on fit (skills match, budget, feasibility).\\n"
            "100 = perfect fit, 0 = no match.\\n"
            'Respond in JSON: {"score": 75, "reason": "why it fits or doesn\'t", '
            '"recommended_bid": 500, "estimated_hours": 20, "should_bid": true}'
        )
        try:
            response = self.brain.prompt("Evaluate job fit.", prompt)
            data = response if isinstance(response, dict) else json.loads(str(response))
            score = float(data.get("score", 0))

            # Update job record
            conn = self._conn()
            try:
                conn.execute(
                    "UPDATE jobs SET fit_score=?,fit_reason=?,status='evaluated',updated_at=datetime('now') WHERE id=?",
                    (score, data.get("reason", "")[:500], job_id))
                conn.commit()
            finally:
                conn.close()

            return {"status": "success", "job_id": job_id, **data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ══════════════════════════════════════════
    # QUERIES
    # ══════════════════════════════════════════

    def get_job(self, job_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_jobs(self, status: str = "", platform: str = "",
                  min_score: float = 0, limit: int = 30) -> List[dict]:
        conn = self._conn()
        try:
            q = "SELECT * FROM jobs WHERE 1=1"
            params = []
            if status:
                q += " AND status=?"
                params.append(status)
            if platform:
                q += " AND platform=?"
                params.append(platform)
            if min_score > 0:
                q += " AND fit_score>=?"
                params.append(min_score)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def get_new_jobs(self, limit: int = 20) -> List[dict]:
        """Returns jobs that haven't been evaluated yet."""
        return self.list_jobs(status="new", limit=limit)

    def get_top_jobs(self, min_score: float = 60, limit: int = 10) -> List[dict]:
        """Returns highest-scoring evaluated jobs."""
        return self.list_jobs(min_score=min_score, limit=limit)

    def update_job_status(self, job_id: int, status: str):
        conn = self._conn()
        try:
            conn.execute("UPDATE jobs SET status=?,updated_at=datetime('now') WHERE id=?",
                         (status, job_id))
            conn.commit()
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            by_status = {}
            for row in conn.execute("SELECT status,COUNT(*) as c FROM jobs GROUP BY status"):
                by_status[row["status"]] = row["c"]
            avg_score = conn.execute(
                "SELECT COALESCE(AVG(fit_score),0) FROM jobs WHERE fit_score>0"
            ).fetchone()[0]
            return {"total_jobs": total, "by_status": by_status,
                    "avg_fit_score": round(avg_score, 1)}
        finally:
            conn.close()
