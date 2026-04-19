"""
S.A.I. Complete Email & Google Account Manager.

Full Gmail control: send, read, search, reply, delete, label, draft.
Periodic status reports to admin. Command execution via email.
Google OAuth sign-in support for websites.
"""

import os
import re
import json
import time
import imaplib
import smtplib
import email
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, header
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class EmailManager:
    """
    Complete Gmail control for S.A.I.
    - Send/read/search/reply/delete/label/draft emails
    - Periodic status reports (every 5 minutes)
    - Execute commands received via email
    - OTP/verification code extraction
    - Google account sign-in support
    """

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    IMAP_SERVER = "imap.gmail.com"
    IMAP_PORT = 993

    def __init__(self, sai_instance=None, config: dict = None):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.EmailManager")
        self.config = config or {}

        self.email_address = os.getenv("SAI_EMAIL", "")
        self.email_password = os.getenv("SAI_EMAIL_PASSWORD", "")
        self.admin_email = os.getenv("YOUR_ADMIN_EMAIL", self.email_address)

        # Status report settings
        self._report_interval = self.config.get("report_interval_seconds", 300)  # 5 min
        self._report_thread: Optional[threading.Thread] = None
        self._report_running = False

        # Command polling settings
        self._cmd_poll_interval = self.config.get("cmd_poll_interval_seconds", 30)
        self._cmd_thread: Optional[threading.Thread] = None
        self._cmd_running = False
        self._last_cmd_check = datetime.now()
        self._processed_cmd_ids = set()

        self.logger.info("EmailManager initialized — %s", self.email_address)

    # ══════════════════════════════════════════
    # SENDING
    # ══════════════════════════════════════════

    def send(self, to: str, subject: str, body: str, html: bool = False,
             attachments: List[str] = None, cc: str = "", bcc: str = "") -> dict:
        """Sends an email with optional attachments, CC, BCC."""
        if not self.email_address or not self.email_password:
            return {"status": "error", "message": "Email credentials not configured."}
        try:
            msg = MIMEMultipart("alternative" if html else "mixed")
            msg["From"] = f"S.A.I. <{self.email_address}>"
            msg["To"] = to
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = cc
            if bcc:
                msg["Bcc"] = bcc

            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type))

            # Attachments
            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        part = MIMEBase("application", "octet-stream")
                        with open(filepath, "rb") as f:
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
                        msg.attach(part)

            all_recipients = [to]
            if cc:
                all_recipients.extend(cc.split(","))
            if bcc:
                all_recipients.extend(bcc.split(","))

            server = smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT)
            server.starttls()
            server.login(self.email_address, self.email_password)
            server.send_message(msg)
            server.quit()

            self.logger.info("Email sent to %s: %s", to, subject)
            return {"status": "success", "message": f"Sent to {to}", "subject": subject}
        except Exception as e:
            self.logger.error("Send failed: %s", e)
            return {"status": "error", "message": str(e)}

    def reply(self, original_msg_id: str, body: str, html: bool = False) -> dict:
        """Replies to a specific email by message ID."""
        try:
            # Fetch original to get headers
            original = self._fetch_by_id(original_msg_id)
            if not original:
                return {"status": "error", "message": "Original message not found"}

            to = original.get("from", self.admin_email)
            subject = original.get("subject", "")
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            msg = MIMEMultipart()
            msg["From"] = f"S.A.I. <{self.email_address}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg["In-Reply-To"] = original.get("message_id", "")
            msg["References"] = original.get("message_id", "")
            msg.attach(MIMEText(body, "html" if html else "plain"))

            server = smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT)
            server.starttls()
            server.login(self.email_address, self.email_password)
            server.send_message(msg)
            server.quit()

            return {"status": "success", "message": f"Replied to {to}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def send_html_report(self, to: str, subject: str, sections: Dict[str, str]) -> dict:
        """Sends a formatted HTML status report."""
        html_parts = [
            "<html><body style='font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:20px;'>",
            f"<h1 style='color:#00d4ff;'>🤖 S.A.I. — {subject}</h1>",
            f"<p style='color:#888;'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p><hr>"
        ]
        for title, content in sections.items():
            html_parts.append(f"<h2 style='color:#4fc3f7;'>{title}</h2>")
            html_parts.append(f"<pre style='background:#0d1117;padding:10px;border-radius:5px;'>{content}</pre>")
        html_parts.append("<hr><p style='color:#555;'>— S.A.I. Autonomous Intelligence</p></body></html>")
        return self.send(to, subject, "\n".join(html_parts), html=True)

    # ══════════════════════════════════════════
    # READING
    # ══════════════════════════════════════════

    def read_inbox(self, count: int = 10, folder: str = "INBOX") -> dict:
        """Reads the latest N emails from a folder."""
        try:
            mail = self._imap_connect()
            mail.select(folder)
            _, messages = mail.search(None, "ALL")
            if not messages[0]:
                mail.logout()
                return {"status": "success", "emails": [], "message": "Inbox empty"}

            msg_ids = messages[0].split()
            recent_ids = msg_ids[-count:]
            emails = []
            for msg_id in reversed(recent_ids):
                parsed = self._parse_email(mail, msg_id)
                if parsed:
                    emails.append(parsed)
            mail.logout()
            return {"status": "success", "emails": emails, "count": len(emails)}
        except Exception as e:
            self.logger.error("Read inbox failed: %s", e)
            return {"status": "error", "message": str(e)}

    def read_unread(self, count: int = 10) -> dict:
        """Reads only unread emails."""
        try:
            mail = self._imap_connect()
            mail.select("INBOX")
            _, messages = mail.search(None, "UNSEEN")
            if not messages[0]:
                mail.logout()
                return {"status": "success", "emails": [], "message": "No unread emails"}

            msg_ids = messages[0].split()[-count:]
            emails = []
            for msg_id in reversed(msg_ids):
                parsed = self._parse_email(mail, msg_id)
                if parsed:
                    emails.append(parsed)
            mail.logout()
            return {"status": "success", "emails": emails, "count": len(emails)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search(self, query: str, folder: str = "INBOX", count: int = 10) -> dict:
        """Searches emails by subject, sender, or body content."""
        try:
            mail = self._imap_connect()
            mail.select(folder)
            # IMAP search criteria
            criteria = f'(OR (SUBJECT "{query}") (FROM "{query}"))'
            _, messages = mail.search(None, criteria)
            if not messages[0]:
                mail.logout()
                return {"status": "success", "emails": [], "message": "No matches"}

            msg_ids = messages[0].split()[-count:]
            emails = []
            for msg_id in reversed(msg_ids):
                parsed = self._parse_email(mail, msg_id)
                if parsed:
                    emails.append(parsed)
            mail.logout()
            return {"status": "success", "emails": emails, "count": len(emails)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ══════════════════════════════════════════
    # MANAGEMENT (delete, label, mark, draft)
    # ══════════════════════════════════════════

    def delete(self, msg_uid: str) -> dict:
        """Moves an email to trash."""
        try:
            mail = self._imap_connect()
            mail.select("INBOX")
            mail.store(msg_uid.encode(), "+FLAGS", "\\Deleted")
            mail.expunge()
            mail.logout()
            return {"status": "success", "message": f"Deleted message {msg_uid}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def mark_read(self, msg_uid: str) -> dict:
        """Marks an email as read."""
        try:
            mail = self._imap_connect()
            mail.select("INBOX")
            mail.store(msg_uid.encode(), "+FLAGS", "\\Seen")
            mail.logout()
            return {"status": "success", "message": f"Marked {msg_uid} as read"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def mark_unread(self, msg_uid: str) -> dict:
        """Marks an email as unread."""
        try:
            mail = self._imap_connect()
            mail.select("INBOX")
            mail.store(msg_uid.encode(), "-FLAGS", "\\Seen")
            mail.logout()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_folders(self) -> dict:
        """Lists all Gmail folders/labels."""
        try:
            mail = self._imap_connect()
            _, folders = mail.list()
            folder_names = []
            for f in folders:
                name = f.decode().split('"/"')[-1].strip().strip('"')
                folder_names.append(name)
            mail.logout()
            return {"status": "success", "folders": folder_names}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def save_draft(self, to: str, subject: str, body: str) -> dict:
        """Saves an email as a draft."""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.email_address
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            mail = self._imap_connect()
            mail.append("[Gmail]/Drafts", "\\Draft", None, msg.as_bytes())
            mail.logout()
            return {"status": "success", "message": "Draft saved"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ══════════════════════════════════════════
    # OTP / VERIFICATION CODE EXTRACTION
    # ══════════════════════════════════════════

    def extract_otp(self, wait_seconds: int = 60) -> dict:
        """Waits for a new email containing an OTP/verification code and extracts it."""
        self.logger.info("Waiting up to %ds for OTP email...", wait_seconds)
        start = time.time()
        while time.time() - start < wait_seconds:
            result = self.read_unread(count=3)
            if result.get("status") == "success":
                for mail in result.get("emails", []):
                    body = mail.get("body", "") + " " + mail.get("subject", "")
                    # Common OTP patterns
                    patterns = [
                        r'\b(\d{4,8})\b',  # 4-8 digit codes
                        r'code[:\s]+(\d{4,8})',
                        r'verification[:\s]+(\d{4,8})',
                        r'OTP[:\s]+(\d{4,8})',
                        r'pin[:\s]+(\d{4,8})',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, body, re.IGNORECASE)
                        if match:
                            code = match.group(1)
                            self.logger.info("OTP extracted: %s", code)
                            return {"status": "success", "otp": code, "from": mail.get("from", ""), "subject": mail.get("subject", "")}
            time.sleep(5)
        return {"status": "error", "message": "No OTP found within timeout"}

    def get_google_signin_credentials(self) -> dict:
        """Returns Google account credentials for website sign-in."""
        return {
            "status": "success",
            "email": self.email_address,
            "password": self.email_password,
            "provider": "google",
            "note": "Use these for Google OAuth / Sign-in with Google flows"
        }

    # ══════════════════════════════════════════
    # PERIODIC STATUS REPORTS (every 5 min)
    # ══════════════════════════════════════════

    def start_status_reports(self):
        """Starts sending periodic status reports to admin."""
        if self._report_running:
            return
        self._report_running = True
        self._report_thread = threading.Thread(
            target=self._status_report_loop, daemon=True, name="SAI-StatusReports"
        )
        self._report_thread.start()
        self.logger.info("Status reports started — every %ds to %s", self._report_interval, self.admin_email)

    def stop_status_reports(self):
        """Stops periodic status reports."""
        self._report_running = False

    def _status_report_loop(self):
        """Sends status emails at configured intervals."""
        # Initial delay to let system stabilize
        time.sleep(30)
        while self._report_running:
            try:
                self._send_status_report()
            except Exception as e:
                self.logger.error("Status report failed: %s", e)
            self._sleep_interruptible(self._report_interval)

    def _send_status_report(self):
        """Builds and sends a comprehensive status email."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sections = {}

        # System status
        sections["⚡ System Status"] = f"Time: {now}\nStatus: Online\nEngine: Running"

        # Idle engine status
        if self.sai and hasattr(self.sai, "idle_engine"):
            idle_status = self.sai.idle_engine.get_status()
            lines = [f"{k}: {v}" for k, v in idle_status.items()]
            sections["🔄 Idle Engine"] = "\n".join(lines)

        # GitHub presence
        if self.sai and hasattr(self.sai, "github_presence"):
            gp_status = self.sai.github_presence.get_status()
            lines = [f"{k}: {v}" for k, v in gp_status.items()]
            sections["🐙 GitHub Presence"] = "\n".join(lines)

        # Recent actions from GitHub presence
        if self.sai and hasattr(self.sai, "github_presence"):
            history = self.sai.github_presence.action_history[-5:]
            if history:
                lines = [f"[{h['timestamp']}] {h['action']}" for h in history]
                sections["📋 Recent Actions"] = "\n".join(lines)
            else:
                sections["📋 Recent Actions"] = "No actions executed yet."

        # Is running?
        if self.sai:
            sections["🎯 Current Task"] = "Busy (executing user command)" if self.sai.is_running else "Idle — autonomous mode"

        self.send_html_report(self.admin_email, f"Status Report — {now}", sections)
        self.logger.info("Status report sent to %s", self.admin_email)

    # ══════════════════════════════════════════
    # COMMAND EXECUTION VIA EMAIL
    # ══════════════════════════════════════════

    def start_command_listener(self):
        """Starts polling for command emails from admin."""
        if self._cmd_running:
            return
        self._cmd_running = True
        self._cmd_thread = threading.Thread(
            target=self._command_poll_loop, daemon=True, name="SAI-EmailCommands"
        )
        self._cmd_thread.start()
        self.logger.info("Email command listener started — polling every %ds", self._cmd_poll_interval)

    def stop_command_listener(self):
        """Stops command email polling."""
        self._cmd_running = False

    def _command_poll_loop(self):
        """Polls for command emails and executes them."""
        time.sleep(10)  # Initial delay
        while self._cmd_running:
            try:
                self._check_command_emails()
            except Exception as e:
                self.logger.error("Command poll error: %s", e)
            self._sleep_interruptible(self._cmd_poll_interval)

    def process_pending_commands(self) -> dict:
        """
        Runs on startup — scans ALL unread emails for commands sent while SAI was offline.
        Executes them oldest-first and notifies admin.
        """
        self.logger.info("Checking for pending commands sent while offline...")
        
        if not self.email_address or not self.email_password:
            return {"status": "error", "message": "Email not configured"}

        try:
            mail = self._imap_connect()
            mail.select("INBOX")
            _, messages = mail.search(None, "UNSEEN")
            
            if not messages[0]:
                mail.logout()
                self.logger.info("No pending commands found.")
                return {"status": "success", "pending": 0, "executed": []}

            msg_ids = messages[0].split()  # All unread, oldest first
            pending_commands = []

            cmd_prefixes = ["CMD:", "SAI:", "EXECUTE:", "RUN:"]

            for msg_id in msg_ids:
                parsed = self._parse_email(mail, msg_id)
                if not parsed:
                    continue

                subject = parsed.get("subject", "")
                sender = parsed.get("from", "")
                body = parsed.get("body", "")
                uid = parsed.get("uid", "")

                # Only from admin
                if self.admin_email not in sender and self.email_address not in sender:
                    continue

                # Check for command prefix
                command = None
                for prefix in cmd_prefixes:
                    if subject.upper().startswith(prefix):
                        command = subject[len(prefix):].strip()
                        break
                    if body.strip().upper().startswith(prefix):
                        command = body.strip()[len(prefix):].strip()
                        break

                if command:
                    pending_commands.append({
                        "command": command,
                        "sender": sender,
                        "uid": uid,
                        "date": parsed.get("date", ""),
                        "subject": subject
                    })

            mail.logout()

            if not pending_commands:
                self.logger.info("No pending commands found in unread emails.")
                return {"status": "success", "pending": 0, "executed": []}

            # Notify admin that SAI is back online with pending commands
            self.logger.info("Found %d pending command(s) from while offline!", len(pending_commands))
            self.send(
                self.admin_email,
                f"🤖 S.A.I. Back Online — {len(pending_commands)} Pending Command(s) Found",
                f"Sir, I'm back online and found {len(pending_commands)} command(s) "
                f"you sent while I was offline.\n\n"
                f"Executing them now in order:\n" +
                "\n".join(f"  {i+1}. {c['command']}" for i, c in enumerate(pending_commands)) +
                "\n\nResults will follow in separate emails.\n\n— S.A.I."
            )

            # Execute each pending command (oldest first)
            executed = []
            for cmd_info in pending_commands:
                command = cmd_info["command"]
                sender = cmd_info["sender"]
                uid = cmd_info["uid"]

                self._processed_cmd_ids.add(uid)
                self.logger.info("Executing pending command: %s (sent: %s)", command, cmd_info.get("date", "?"))
                self._execute_email_command(command, sender)
                executed.append(command)

            self.logger.info("All %d pending commands executed.", len(executed))
            return {"status": "success", "pending": len(pending_commands), "executed": executed}

        except Exception as e:
            self.logger.error("Pending command check failed: %s", e)
            return {"status": "error", "message": str(e)}

    def _check_command_emails(self):
        """Checks for unread emails with command prefix from admin."""
        result = self.read_unread(count=5)
        if result.get("status") != "success":
            return

        for mail_item in result.get("emails", []):
            subject = mail_item.get("subject", "")
            sender = mail_item.get("from", "")
            body = mail_item.get("body", "")
            msg_id = mail_item.get("uid", "")

            # Skip if already processed
            if msg_id in self._processed_cmd_ids:
                continue

            # Only accept commands from admin email
            if self.admin_email not in sender and self.email_address not in sender:
                continue

            # Command format: subject starts with "CMD:" or "SAI:" or "EXECUTE:"
            cmd_prefixes = ["CMD:", "SAI:", "EXECUTE:", "RUN:"]
            command = None
            for prefix in cmd_prefixes:
                if subject.upper().startswith(prefix):
                    command = subject[len(prefix):].strip()
                    break
                if body.strip().upper().startswith(prefix):
                    command = body.strip()[len(prefix):].strip()
                    break

            if command:
                self._processed_cmd_ids.add(msg_id)
                self.logger.info("Email command received: %s", command)
                self._execute_email_command(command, sender)

    def _execute_email_command(self, command: str, sender: str):
        """Executes a command and emails the result back."""
        self.logger.info("Executing email command: %s", command)
        result = ""

        try:
            if self.sai and hasattr(self.sai, "executor"):
                # Route through SAI's executor for safety
                exec_result = self.sai.executor.execute_shell(command)
                result = json.dumps(exec_result, indent=2, default=str)
            else:
                # Fallback: direct subprocess
                import subprocess
                proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
                result = f"Exit Code: {proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        except Exception as e:
            result = f"Execution error: {str(e)}"

        # Send result back
        self.send(
            sender, f"Re: Command Result — {command[:50]}",
            f"🤖 S.A.I. Command Execution Report\n\n"
            f"Command: {command}\n"
            f"Time: {datetime.now().isoformat()}\n\n"
            f"Result:\n{result[:5000]}"
        )

    # ══════════════════════════════════════════
    # INTERNAL HELPERS
    # ══════════════════════════════════════════

    def _imap_connect(self) -> imaplib.IMAP4_SSL:
        """Creates and authenticates an IMAP connection."""
        mail = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
        mail.login(self.email_address, self.email_password)
        return mail

    def _parse_email(self, mail: imaplib.IMAP4_SSL, msg_id: bytes) -> Optional[dict]:
        """Parses a single email message."""
        try:
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])

                    # Subject
                    subject_raw = header.decode_header(msg["Subject"] or "")[0][0]
                    subject = subject_raw.decode() if isinstance(subject_raw, bytes) else str(subject_raw)

                    # Body
                    body = ""
                    if msg.is_multipart():
                        for p in msg.walk():
                            if p.get_content_type() == "text/plain":
                                try:
                                    body = p.get_payload(decode=True).decode()
                                    break
                                except Exception:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode()
                        except Exception:
                            pass

                    return {
                        "uid": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
                        "subject": subject,
                        "from": msg.get("From", ""),
                        "to": msg.get("To", ""),
                        "date": msg.get("Date", ""),
                        "message_id": msg.get("Message-ID", ""),
                        "body": body[:2000],
                    }
        except Exception as e:
            self.logger.debug("Parse error for msg %s: %s", msg_id, e)
        return None

    def _fetch_by_id(self, msg_uid: str) -> Optional[dict]:
        """Fetches a single email by UID."""
        try:
            mail = self._imap_connect()
            mail.select("INBOX")
            result = self._parse_email(mail, msg_uid.encode())
            mail.logout()
            return result
        except Exception:
            return None

    def _sleep_interruptible(self, seconds: int):
        """Sleeps in small increments for clean shutdown."""
        elapsed = 0
        while elapsed < seconds and (self._report_running or self._cmd_running):
            time.sleep(min(5, seconds - elapsed))
            elapsed += 5

    def get_status(self) -> dict:
        """Returns email manager diagnostics."""
        return {
            "email": self.email_address,
            "admin": self.admin_email,
            "configured": bool(self.email_address and self.email_password),
            "status_reports_running": self._report_running,
            "command_listener_running": self._cmd_running,
            "report_interval": f"{self._report_interval}s",
            "processed_commands": len(self._processed_cmd_ids),
        }
