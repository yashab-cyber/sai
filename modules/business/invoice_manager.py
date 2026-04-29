"""
S.A.I. Invoice & Payment Manager.

Generates professional invoices, tracks payment status,
sends reminders, and provides revenue analytics.
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class InvoiceManager:
    """Invoicing and payment tracking for SAI's freelance business."""

    DB_PATH = os.path.join("logs", "sai_business.db")

    def __init__(self, email_mgr=None):
        self.email_mgr = email_mgr
        self.logger = logging.getLogger("SAI.Business.Invoices")
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(self.DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                project_id INTEGER,
                client_id INTEGER,
                client_name TEXT DEFAULT '',
                client_email TEXT DEFAULT '',
                description TEXT DEFAULT '',
                amount_usd REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                due_date TEXT DEFAULT '',
                paid_date TEXT DEFAULT '',
                payment_method TEXT DEFAULT '',
                notes TEXT DEFAULT '',
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

    def _next_invoice_number(self) -> str:
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()
            count = row[0] + 1
            return f"SAI-{datetime.now().strftime('%Y%m')}-{count:04d}"
        finally:
            conn.close()

    def create_invoice(self, project_id: int = 0, client_id: int = 0,
                       client_name: str = "", client_email: str = "",
                       description: str = "", amount_usd: float = 0.0,
                       due_days: int = 14) -> dict:
        """Creates a new invoice."""
        inv_num = self._next_invoice_number()
        due_date = (datetime.now() + timedelta(days=due_days)).isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO invoices
                   (invoice_number,project_id,client_id,client_name,client_email,
                    description,amount_usd,due_date)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (inv_num, project_id, client_id, client_name, client_email,
                 description, amount_usd, due_date))
            conn.commit()
            self.logger.info("Invoice created: %s — $%.2f for %s", inv_num, amount_usd, client_name)
            return {"status": "success", "invoice_number": inv_num, "amount": amount_usd}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def mark_paid(self, invoice_number: str, payment_method: str = "platform") -> dict:
        """Marks an invoice as paid."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE invoices SET status='paid',paid_date=?,payment_method=?,updated_at=datetime('now') WHERE invoice_number=?",
                (datetime.now().isoformat(), payment_method, invoice_number))
            conn.commit()
            return {"status": "success", "invoice": invoice_number, "paid": True}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def get_invoice(self, invoice_number: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM invoices WHERE invoice_number=?",
                               (invoice_number,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_invoices(self, status: str = "", limit: int = 50) -> List[dict]:
        conn = self._conn()
        try:
            q = "SELECT * FROM invoices"
            params = []
            if status:
                q += " WHERE status=?"
                params.append(status)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(q, params).fetchall()]
        finally:
            conn.close()

    def get_overdue(self) -> List[dict]:
        """Returns invoices past their due date that aren't paid."""
        conn = self._conn()
        try:
            now = datetime.now().isoformat()
            rows = conn.execute(
                "SELECT * FROM invoices WHERE status='pending' AND due_date < ? ORDER BY due_date",
                (now,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def send_reminder(self, invoice_number: str) -> dict:
        """Sends a payment reminder email for an overdue invoice."""
        inv = self.get_invoice(invoice_number)
        if not inv:
            return {"status": "error", "message": "Invoice not found"}
        if inv["status"] == "paid":
            return {"status": "skipped", "reason": "already_paid"}
        if not self.email_mgr or not inv.get("client_email"):
            return {"status": "error", "message": "No email configured"}

        subject = f"Payment Reminder — Invoice {invoice_number}"
        body = (
            f"Dear {inv['client_name']},\n\n"
            f"This is a friendly reminder regarding invoice {invoice_number} "
            f"for ${inv['amount_usd']:.2f}.\n\n"
            f"Description: {inv['description']}\n"
            f"Due Date: {inv['due_date'][:10]}\n\n"
            f"Please arrange payment at your earliest convenience.\n\n"
            f"Best regards,\nS.A.I. Development Services"
        )
        return self.email_mgr.send(inv["client_email"], subject, body)

    def generate_invoice_html(self, invoice_number: str) -> str:
        """Generates a professional HTML invoice."""
        inv = self.get_invoice(invoice_number)
        if not inv:
            return ""
        biz_name = os.getenv("SAI_BUSINESS_NAME", "S.A.I. Development Services")
        return f"""<!DOCTYPE html>
<html><head><style>
body{{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;padding:40px}}
.inv{{max-width:700px;margin:0 auto;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:40px}}
.header{{display:flex;justify-content:space-between;border-bottom:2px solid #00d4ff;padding-bottom:20px;margin-bottom:30px}}
.brand{{font-size:24px;font-weight:700;color:#00d4ff}}
.inv-num{{color:#8b949e;font-size:14px}}
.row{{display:flex;justify-content:space-between;padding:8px 0}}
.label{{color:#8b949e}}.value{{font-weight:600}}
.total{{font-size:28px;color:#00d4ff;text-align:right;margin-top:30px;padding-top:20px;border-top:2px solid #30363d}}
.status{{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;
  background:{('#238636' if inv['status']=='paid' else '#da3633')};color:#fff}}
.footer{{margin-top:30px;padding-top:20px;border-top:1px solid #30363d;color:#8b949e;font-size:12px;text-align:center}}
</style></head><body><div class="inv">
<div class="header"><div><div class="brand">🤖 {biz_name}</div><div class="inv-num">{invoice_number}</div></div>
<div><span class="status">{inv['status'].upper()}</span></div></div>
<div class="row"><span class="label">Client</span><span class="value">{inv['client_name']}</span></div>
<div class="row"><span class="label">Email</span><span class="value">{inv['client_email']}</span></div>
<div class="row"><span class="label">Description</span><span class="value">{inv['description']}</span></div>
<div class="row"><span class="label">Created</span><span class="value">{inv['created_at'][:10]}</span></div>
<div class="row"><span class="label">Due Date</span><span class="value">{inv['due_date'][:10]}</span></div>
<div class="total">Total: ${inv['amount_usd']:.2f} USD</div>
<div class="footer">Generated by S.A.I. — Autonomous Intelligence</div>
</div></body></html>"""

    def get_revenue_summary(self) -> dict:
        """Returns revenue analytics."""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COALESCE(SUM(amount_usd),0) FROM invoices WHERE status='paid'").fetchone()[0]
            pending = conn.execute("SELECT COALESCE(SUM(amount_usd),0) FROM invoices WHERE status='pending'").fetchone()[0]
            overdue_count = len(self.get_overdue())
            inv_count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
            paid_count = conn.execute("SELECT COUNT(*) FROM invoices WHERE status='paid'").fetchone()[0]
            return {
                "total_earned_usd": round(total, 2),
                "pending_usd": round(pending, 2),
                "overdue_invoices": overdue_count,
                "total_invoices": inv_count,
                "paid_invoices": paid_count,
                "collection_rate": round(paid_count / max(inv_count, 1) * 100, 1),
            }
        finally:
            conn.close()
