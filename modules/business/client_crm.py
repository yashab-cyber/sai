"""
S.A.I. Client Relationship Manager (CRM).

Tracks client profiles, communication history, satisfaction scores,
and preferred-client detection for prioritizing returning customers.
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional


class ClientCRM:
    """Lightweight CRM for tracking freelance client relationships."""

    DB_PATH = os.path.join("logs", "sai_business.db")

    def __init__(self, brain=None):
        self.brain = brain
        self.logger = logging.getLogger("SAI.Business.CRM")
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT DEFAULT '',
                platform TEXT DEFAULT '',
                platform_username TEXT DEFAULT '',
                country TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                total_projects INTEGER DEFAULT 0,
                total_revenue_usd REAL DEFAULT 0.0,
                avg_rating REAL DEFAULT 0.0,
                is_preferred INTEGER DEFAULT 0,
                first_contact TEXT DEFAULT '',
                last_contact TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                direction TEXT DEFAULT 'outbound',
                channel TEXT DEFAULT 'email',
                subject TEXT DEFAULT '',
                content TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (client_id) REFERENCES clients(id)
            )
        """)
        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def add_client(self, name: str, email: str = "", platform: str = "",
                   platform_username: str = "", country: str = "", notes: str = "") -> dict:
        conn = self._conn()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO clients (name,email,platform,platform_username,country,notes,first_contact,last_contact) VALUES (?,?,?,?,?,?,?,?)",
                (name, email, platform, platform_username, country, notes, now, now))
            conn.commit()
            cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"status": "success", "client_id": cid, "name": name}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def get_client(self, client_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def find_client(self, name: str = "", email: str = "", platform_username: str = "") -> Optional[dict]:
        conn = self._conn()
        try:
            if email:
                row = conn.execute("SELECT * FROM clients WHERE email=?", (email,)).fetchone()
                if row: return dict(row)
            if platform_username:
                row = conn.execute("SELECT * FROM clients WHERE platform_username=?", (platform_username,)).fetchone()
                if row: return dict(row)
            if name:
                row = conn.execute("SELECT * FROM clients WHERE name LIKE ?", (f"%{name}%",)).fetchone()
                if row: return dict(row)
            return None
        finally:
            conn.close()

    def get_or_create_client(self, name: str, email: str = "", platform: str = "", platform_username: str = "") -> dict:
        existing = self.find_client(name=name, email=email, platform_username=platform_username)
        if existing:
            return {"status": "success", "client_id": existing["id"], "name": existing["name"], "existing": True}
        return self.add_client(name=name, email=email, platform=platform, platform_username=platform_username)

    def update_client_stats(self, client_id: int, revenue: float = 0.0, rating: float = 0.0):
        conn = self._conn()
        try:
            client = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            if not client: return
            tp = client["total_projects"] + 1
            tr = client["total_revenue_usd"] + revenue
            avg = rating if rating > 0 and client["avg_rating"] == 0 else (
                (client["avg_rating"] * client["total_projects"] + rating) / tp if rating > 0 else client["avg_rating"])
            pref = 1 if (tp >= 3 or tr >= 500) else 0
            conn.execute("UPDATE clients SET total_projects=?,total_revenue_usd=?,avg_rating=?,is_preferred=?,last_contact=?,updated_at=datetime('now') WHERE id=?",
                         (tp, tr, round(avg, 2), pref, datetime.now().isoformat(), client_id))
            conn.commit()
        finally:
            conn.close()

    def list_clients(self, preferred_only: bool = False, limit: int = 50) -> List[dict]:
        conn = self._conn()
        try:
            q = "SELECT * FROM clients"
            if preferred_only: q += " WHERE is_preferred=1"
            q += " ORDER BY last_contact DESC LIMIT ?"
            return [dict(r) for r in conn.execute(q, (limit,)).fetchall()]
        finally:
            conn.close()

    def log_communication(self, client_id: int, direction: str = "outbound",
                          channel: str = "email", subject: str = "", content: str = "") -> dict:
        conn = self._conn()
        try:
            conn.execute("INSERT INTO communications (client_id,direction,channel,subject,content) VALUES (?,?,?,?,?)",
                         (client_id, direction, channel, subject, content[:5000]))
            conn.execute("UPDATE clients SET last_contact=?,updated_at=datetime('now') WHERE id=?",
                         (datetime.now().isoformat(), client_id))
            conn.commit()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def get_communication_history(self, client_id: int, limit: int = 20) -> List[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM communications WHERE client_id=? ORDER BY created_at DESC LIMIT ?",
                (client_id, limit)).fetchall()]
        finally:
            conn.close()

    def get_summary(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
            preferred = conn.execute("SELECT COUNT(*) FROM clients WHERE is_preferred=1").fetchone()[0]
            revenue = conn.execute("SELECT COALESCE(SUM(total_revenue_usd),0) FROM clients").fetchone()[0]
            comms = conn.execute("SELECT COUNT(*) FROM communications").fetchone()[0]
            return {"total_clients": total, "preferred_clients": preferred,
                    "total_revenue_usd": round(revenue, 2), "total_communications": comms}
        finally:
            conn.close()
