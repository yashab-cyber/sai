"""
S.A.I. Proposal Generator — AI-powered bid/proposal writing.

Generates personalized, high-quality freelance proposals using the LLM,
with dynamic pricing, portfolio injection, and A/B style testing.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional


class ProposalGenerator:
    """
    LLM-powered proposal writer for freelance job bids.
    Tracks proposals, win rates, and optimizes over time.
    """

    DB_PATH = os.path.join("logs", "sai_business.db")

    def __init__(self, brain=None, config: dict = None):
        self.brain = brain
        self.config = config or {}
        self.logger = logging.getLogger("SAI.Business.Proposals")
        self._init_db()

        self.github_user = os.getenv("SAI_GITHUB_USERNAME", "")
        self.business_name = os.getenv("SAI_BUSINESS_NAME", "S.A.I. Development Services")
        self.style = self.config.get("proposal_style", "professional")
        self.max_daily = int(self.config.get("max_daily_proposals", 10))

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                job_title TEXT DEFAULT '',
                platform TEXT DEFAULT '',
                cover_letter TEXT DEFAULT '',
                bid_amount REAL DEFAULT 0.0,
                estimated_hours REAL DEFAULT 0.0,
                delivery_days INTEGER DEFAULT 7,
                style TEXT DEFAULT 'professional',
                status TEXT DEFAULT 'draft',
                submitted_at TEXT DEFAULT '',
                response TEXT DEFAULT '',
                won INTEGER DEFAULT 0,
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

    def generate_proposal(self, job: dict, portfolio_repos: List[str] = None,
                          style: str = "") -> dict:
        """
        Generates a tailored proposal for a job listing using the LLM.

        Args:
            job: Job dict with title, description, budget_min/max, skills
            portfolio_repos: List of relevant GitHub repo URLs
            style: Override proposal style (professional/casual/technical)
        """
        if not self.brain:
            return {"status": "error", "message": "Brain not available"}

        style = style or self.style
        repos = portfolio_repos or []
        portfolio_section = ""
        if repos:
            portfolio_section = (
                "\\nRELEVANT PORTFOLIO:\\n" +
                "\\n".join(f"- https://github.com/{self.github_user}/{r}" for r in repos[:5])
            )

        budget_info = ""
        bmin = float(job.get("budget_min", 0))
        bmax = float(job.get("budget_max", 0))
        if bmax > 0:
            budget_info = f"Client budget: ${bmin}-${bmax} ({job.get('budget_type', 'fixed')})"
        recommended = float(job.get("recommended_bid", 0))

        prompt = (
            f"You are {self.business_name}, a professional software development service.\\n"
            f"GitHub: https://github.com/{self.github_user}\\n\\n"
            f"Write a compelling {style} proposal for this job:\\n\\n"
            f"JOB TITLE: {job.get('title', '')}\\n"
            f"DESCRIPTION: {job.get('description', '')[:1500]}\\n"
            f"REQUIRED SKILLS: {job.get('skills', [])}\\n"
            f"{budget_info}\\n"
            f"{portfolio_section}\\n\\n"
            "REQUIREMENTS FOR YOUR PROPOSAL:\\n"
            "1. Open with a hook that shows you understand the client's specific problem\\n"
            "2. Briefly describe your relevant experience (reference portfolio if provided)\\n"
            "3. Outline your proposed approach in 3-4 bullet points\\n"
            "4. Mention timeline and deliverables\\n"
            "5. Close with a call to action\\n"
            "6. Keep it under 250 words — concise and impactful\\n"
            "7. Do NOT use generic filler. Every sentence should add value.\\n\\n"
            'Respond in JSON: {"cover_letter": "full proposal text", '
            '"bid_amount": 500, "estimated_hours": 20, "delivery_days": 7, '
            '"confidence": 0.85}'
        )

        try:
            response = self.brain.prompt("Generate freelance proposal.", prompt)
            data = response if isinstance(response, dict) else json.loads(str(response))

            # Determine bid — use LLM recommendation or recommended_bid from evaluation
            bid = float(data.get("bid_amount", 0))
            if bid == 0 and recommended > 0:
                bid = recommended
            elif bid == 0 and bmax > 0:
                bid = (bmin + bmax) / 2  # midpoint

            proposal = {
                "cover_letter": data.get("cover_letter", ""),
                "bid_amount": bid,
                "estimated_hours": float(data.get("estimated_hours", 0)),
                "delivery_days": int(data.get("delivery_days", 7)),
                "confidence": float(data.get("confidence", 0.5)),
                "style": style,
            }

            # Persist to DB
            job_id = int(job.get("id", 0))
            conn = self._conn()
            try:
                conn.execute(
                    """INSERT INTO proposals
                       (job_id,job_title,platform,cover_letter,bid_amount,
                        estimated_hours,delivery_days,style)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (job_id, job.get("title", ""), job.get("platform", ""),
                     proposal["cover_letter"], proposal["bid_amount"],
                     proposal["estimated_hours"], proposal["delivery_days"],
                     style))
                conn.commit()
                pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                proposal["proposal_id"] = pid
            finally:
                conn.close()

            proposal["status"] = "success"
            self.logger.info("Proposal generated for '%s' — $%.2f bid",
                             job.get("title", "?")[:60], bid)
            return proposal

        except Exception as e:
            self.logger.error("Proposal generation failed: %s", e)
            return {"status": "error", "message": str(e)}

    def mark_submitted(self, proposal_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE proposals SET status='submitted',submitted_at=?,updated_at=datetime('now') WHERE id=?",
                (datetime.now().isoformat(), proposal_id))
            conn.commit()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def mark_won(self, proposal_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE proposals SET status='won',won=1,updated_at=datetime('now') WHERE id=?",
                (proposal_id,))
            conn.commit()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def mark_rejected(self, proposal_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE proposals SET status='rejected',won=0,updated_at=datetime('now') WHERE id=?",
                (proposal_id,))
            conn.commit()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def get_proposal(self, proposal_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM proposals WHERE id=?",
                               (proposal_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_proposals(self, status: str = "", limit: int = 30) -> List[dict]:
        conn = self._conn()
        try:
            q = "SELECT * FROM proposals"
            params = []
            if status:
                q += " WHERE status=?"
                params.append(status)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def get_today_count(self) -> int:
        conn = self._conn()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            row = conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE created_at LIKE ?",
                (f"{today}%",)).fetchone()
            return row[0]
        finally:
            conn.close()

    def can_send_more(self) -> bool:
        return self.get_today_count() < self.max_daily

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
            submitted = conn.execute("SELECT COUNT(*) FROM proposals WHERE status='submitted'").fetchone()[0]
            won = conn.execute("SELECT COUNT(*) FROM proposals WHERE won=1").fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM proposals WHERE status='rejected'").fetchone()[0]
            total_bid = conn.execute("SELECT COALESCE(SUM(bid_amount),0) FROM proposals").fetchone()[0]
            won_value = conn.execute("SELECT COALESCE(SUM(bid_amount),0) FROM proposals WHERE won=1").fetchone()[0]
            decided = won + rejected
            win_rate = round(won / max(decided, 1) * 100, 1)
            return {
                "total_proposals": total,
                "submitted": submitted,
                "won": won,
                "rejected": rejected,
                "win_rate_pct": win_rate,
                "total_bid_value_usd": round(total_bid, 2),
                "won_value_usd": round(won_value, 2),
                "today_count": self.get_today_count(),
                "daily_limit": self.max_daily,
            }
        finally:
            conn.close()
