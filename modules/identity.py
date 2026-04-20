import os
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import logging
import subprocess
import requests
import json

class IdentityManager:
    """
    Manages S.A.I.'s digital identity (Email and GitHub credentials).
    Allows S.A.I. to read verification codes (OTPs), send alerts to its admin,
    and publish code to GitHub autonomously.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SAI.Identity")
        self.email_address = os.getenv("SAI_EMAIL", "")
        self.email_password = os.getenv("SAI_EMAIL_PASSWORD", "")
        self.admin_email = os.getenv("YOUR_ADMIN_EMAIL", "")
        self.github_user = os.getenv("SAI_GITHUB_USERNAME", "")
        self.github_token = os.getenv("SAI_GITHUB_TOKEN", "")

    def send_email(self, subject: str, target_email: str = None, body: str = "") -> dict:
        """Sends an email from S.A.I.'s account."""
        if not self.email_address or not self.email_password:
            return {"status": "error", "message": "Email credentials not found in .env"}
            
        target = target_email if target_email else self.admin_email
        if not target:
            return {"status": "error", "message": "No target email specified or configured."}

        try:
            msg = MIMEMultipart()
            msg["From"] = self.email_address
            msg["To"] = target
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            # Standard Gmail SMTP server
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(self.email_address, self.email_password)
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Email sent successfully to {target}")
            return {"status": "success", "message": f"Email sent to {target}"}
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return {"status": "error", "message": str(e)}

    def read_latest_emails(self, count: int = 5) -> dict:
        """Connects via IMAP to read recent emails (useful for OTP extraction)."""
        if not self.email_address or not self.email_password:
            return {"status": "error", "message": "Email credentials not found in .env"}

        try:
            # Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.email_address, self.email_password)
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages[0]:
                return {"status": "info", "message": "Inbox is empty or cannot be read."}

            msg_ids = messages[0].split()
            recent_ids = msg_ids[-count:]
            
            emails_data = []
            for msg_id in reversed(recent_ids):
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = email.header.decode_header(msg["Subject"])[0][0]
                        if isinstance(subject, bytes):
                            subject = subject.decode()
                            
                        # Extract basic text
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    try:
                                        body = part.get_payload(decode=True).decode()
                                        break
                                    except Exception:
                                        pass
                        else:
                            try:
                                body = msg.get_payload(decode=True).decode()
                            except Exception:
                                pass
                                
                        emails_data.append({
                            "subject": subject,
                            "from": msg.get("From"),
                            "date": msg.get("Date"),
                            "snippet": body[:500] # First 500 chars (usually contains the OTP)
                        })
            
            mail.logout()
            return {"status": "success", "emails": emails_data}
        except Exception as e:
            self.logger.error(f"Failed to read emails: {e}")
            return {"status": "error", "message": str(e)}

    def github_publish(self, repo_url: str, branch: str, commit_message: str, path: str = ".") -> dict:
        """Pushes current workspace branch to target repo."""
        if not self.github_token or not self.github_user:
            return {"status": "error", "message": "GitHub credentials missing in .env"}

        try:
            # Format the URL to embed auth token: https://user:token@github.com/org/repo.git
            if "https://" in repo_url:
                auth_url = repo_url.replace("https://", f"https://{self.github_user}:{self.github_token}@")
            else:
                auth_url = repo_url

            # Execute git commands safely
            subprocess.run(["git", "config", "--global", "user.name", "S.A.I. Autonomous Agent"], check=False)
            subprocess.run(["git", "config", "--global", "user.email", self.email_address], check=False)
            
            # Using workspace dir
            subprocess.run(["git", "add", "."], cwd=path, check=True)
            subprocess.run(["git", "commit", "-m", commit_message], cwd=path, check=False) # may fail if nothing to commit
            push_res = subprocess.run(
                ["git", "push", auth_url, branch], 
                cwd=path, 
                capture_output=True, 
                text=True
            )
            
            if push_res.returncode == 0:
                self.logger.info("Successfully published code to GitHub.")
                return {"status": "success", "message": "Code published to GitHub!"}
            else:
                return {"status": "error", "message": push_res.stderr}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def github_api_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """
        Executes a direct GitHub REST API call.
        Enables S.A.I. to manage profile bio, create repos, change settings, manage issues, etc.
        Endpoint should be relative to https://api.github.com/ (e.g., 'user', 'user/repos')
        """
        if not self.github_token:
            return {"status": "error", "message": "GitHub credentials missing in .env"}

        url = f"https://api.github.com/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            method = method.upper()
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                return {"status": "error", "message": f"Unsupported HTTP method: {method}"}

            try:
                response_json = response.json()
            except ValueError:
                response_json = {"raw_text": response.text}

            if response.status_code >= 400:
                return {"status": "error", "code": response.status_code, "response": response_json}
                
            return {"status": "success", "code": response.status_code, "data": response_json}
        except Exception as e:
            return {"status": "error", "message": str(e)}