"""
S.A.I. Account Registry — Persistent Platform Account Tracker.

Tracks which platforms SAI has already created accounts on,
so it knows whether to SIGN UP (first time) or LOG IN (returning).

Data is persisted as a simple JSON file under the memory directory.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memory", "account_registry.json"
)


class AccountRegistry:
    """
    Persistent registry of all social media / platform accounts.

    Each entry tracks:
        - platform name
        - email used
        - username chosen
        - account_created: bool
        - created_at: timestamp
        - last_login: timestamp
        - has_2fa: bool
        - status: 'active' | 'suspended' | 'unverified' | 'pending'
        - notes: free-form
    """

    def __init__(self, path: str = REGISTRY_PATH):
        self.path = path
        self.logger = logging.getLogger("SAI.AccountRegistry")
        self._accounts: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ══════════════════════════════════════════
    # PERSISTENCE
    # ══════════════════════════════════════════

    def _load(self):
        """Loads accounts from disk."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self._accounts = json.load(f)
                self.logger.info(
                    "Account registry loaded — %d platforms tracked.",
                    len(self._accounts),
                )
            except Exception as e:
                self.logger.warning("Failed to load account registry: %s", e)
                self._accounts = {}
        else:
            self._accounts = {}
            self._save()

    def _save(self):
        """Persists accounts to disk."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            with open(self.path, "w") as f:
                json.dump(self._accounts, f, indent=2, default=str)
        except Exception as e:
            self.logger.error("Failed to save account registry: %s", e)

    # ══════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════

    def has_account(self, platform: str) -> bool:
        """Returns True if an account exists for this platform."""
        key = platform.lower().strip()
        entry = self._accounts.get(key)
        return bool(entry and entry.get("account_created", False))

    def needs_signup(self, platform: str) -> bool:
        """Returns True if SAI needs to create a new account on this platform."""
        return not self.has_account(platform)

    def get_account(self, platform: str) -> Optional[Dict[str, Any]]:
        """Returns account info for a platform, or None."""
        key = platform.lower().strip()
        return self._accounts.get(key)

    def register_account(
        self,
        platform: str,
        email: str,
        username: str = "",
        has_2fa: bool = False,
        status: str = "active",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Registers a newly created account."""
        key = platform.lower().strip()
        now = datetime.now().isoformat()
        entry = {
            "platform": key,
            "email": email,
            "username": username,
            "account_created": True,
            "created_at": now,
            "last_login": now,
            "has_2fa": has_2fa,
            "status": status,
            "notes": notes,
        }
        self._accounts[key] = entry
        self._save()
        self.logger.info("Account registered: %s (user=%s)", key, username)
        return entry

    def update_login(self, platform: str, notes: str = "") -> Dict[str, Any]:
        """Updates the last_login timestamp for an existing account."""
        key = platform.lower().strip()
        if key not in self._accounts:
            return {"status": "error", "message": f"No account registered for {key}"}
        self._accounts[key]["last_login"] = datetime.now().isoformat()
        if notes:
            self._accounts[key]["notes"] = notes
        self._save()
        return self._accounts[key]

    def update_status(self, platform: str, status: str, notes: str = ""):
        """Updates account status (active, suspended, unverified, pending)."""
        key = platform.lower().strip()
        if key in self._accounts:
            self._accounts[key]["status"] = status
            if notes:
                self._accounts[key]["notes"] = notes
            self._save()

    def set_2fa(self, platform: str, has_2fa: bool = True):
        """Marks whether this platform uses 2FA."""
        key = platform.lower().strip()
        if key in self._accounts:
            self._accounts[key]["has_2fa"] = has_2fa
            self._save()

    def list_accounts(self, status_filter: str = "") -> List[Dict[str, Any]]:
        """Lists all registered accounts, optionally filtered by status."""
        accounts = list(self._accounts.values())
        if status_filter:
            accounts = [a for a in accounts if a.get("status") == status_filter]
        return accounts

    def get_summary(self) -> Dict[str, Any]:
        """Returns a summary of the account registry."""
        accounts = list(self._accounts.values())
        return {
            "total_platforms": len(accounts),
            "active": sum(1 for a in accounts if a.get("status") == "active"),
            "pending": sum(1 for a in accounts if a.get("status") == "pending"),
            "with_2fa": sum(1 for a in accounts if a.get("has_2fa")),
            "platforms": [a["platform"] for a in accounts],
        }

    def delete_account(self, platform: str) -> bool:
        """Removes an account from the registry."""
        key = platform.lower().strip()
        if key in self._accounts:
            del self._accounts[key]
            self._save()
            return True
        return False
