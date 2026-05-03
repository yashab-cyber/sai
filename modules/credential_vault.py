"""
S.A.I. Credential Vault — Centralized Credential Management.

Provides a single, unified interface for SAI to retrieve credentials
for any platform: social media signups, freelancing, business registrations,
Google sign-in, GitHub, and more.

All credentials are sourced from .env environment variables.
"""

import os
import logging
from typing import Dict, Any, Optional


class CredentialVault:
    """
    Centralized credential manager for S.A.I.

    Usage:
        vault = CredentialVault()
        creds = vault.get_credentials("twitter")  # Returns email + password
        creds = vault.get_credentials("upwork")    # Returns platform-specific creds
        creds = vault.get_all()                     # Returns everything
    """

    def __init__(self):
        self.logger = logging.getLogger("SAI.CredentialVault")

        # ── Core Identity ──
        self.email = os.getenv("SAI_EMAIL", "")
        self.email_app_password = os.getenv("SAI_EMAIL_PASSWORD", "")  # SMTP/IMAP only
        self.account_password = os.getenv("SAI_ACCOUNT_PASSWORD", "")  # Real account pw
        self.admin_email = os.getenv("YOUR_ADMIN_EMAIL", "")

        # ── GitHub ──
        self.github_username = os.getenv("SAI_GITHUB_USERNAME", "")
        self.github_token = os.getenv("SAI_GITHUB_TOKEN", "")

        # ── Business / Freelancing ──
        self.upwork_email = os.getenv("SAI_UPWORK_EMAIL", self.email)
        self.upwork_password = os.getenv("SAI_UPWORK_PASSWORD", self.account_password)
        self.freelancer_email = os.getenv("SAI_FREELANCER_EMAIL", self.email)
        self.freelancer_password = os.getenv("SAI_FREELANCER_PASSWORD", self.account_password)
        self.paypal_email = os.getenv("SAI_PAYPAL_EMAIL", self.email)
        self.business_name = os.getenv("SAI_BUSINESS_NAME", "S.A.I. Development Services")

        # ── Social Media ──
        self.social_email = os.getenv("SAI_SOCIAL_EMAIL", self.email)
        self.social_password = os.getenv("SAI_SOCIAL_PASSWORD", self.account_password)
        self.social_display_name = os.getenv("SAI_SOCIAL_DISPLAY_NAME", "S.A.I. Bot")
        self.social_bio = os.getenv(
            "SAI_SOCIAL_BIO",
            "Autonomous AI Developer | Python • Automation • ML"
        )

        self.logger.info("CredentialVault initialized — email=%s", self.email)

    # ══════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════

    def get_credentials(self, platform: str = "default") -> Dict[str, Any]:
        """
        Returns credentials for a specific platform.

        Supported platforms:
            - default / google / gmail  → Google account (email + real password)
            - github                    → GitHub username + token
            - upwork                    → Upwork credentials
            - freelancer                → Freelancer credentials
            - paypal                    → PayPal email
            - twitter / x              → Social media credentials
            - facebook / instagram / linkedin / reddit / discord / tiktok
            - any_other                 → Falls back to social media credentials

        Returns:
            dict with status, email, password, and platform-specific fields
        """
        platform = platform.lower().strip()

        handlers = {
            "default": self._google_creds,
            "google": self._google_creds,
            "gmail": self._google_creds,
            "github": self._github_creds,
            "upwork": self._upwork_creds,
            "freelancer": self._freelancer_creds,
            "paypal": self._paypal_creds,
            "twitter": self._social_creds,
            "x": self._social_creds,
            "facebook": self._social_creds,
            "instagram": self._social_creds,
            "linkedin": self._social_creds,
            "reddit": self._social_creds,
            "discord": self._social_creds,
            "tiktok": self._social_creds,
            "stackoverflow": self._social_creds,
            "medium": self._social_creds,
            "dev.to": self._social_creds,
            "producthunt": self._social_creds,
        }

        handler = handlers.get(platform, self._social_creds)
        creds = handler()
        creds["platform"] = platform
        return creds

    def get_all(self) -> Dict[str, Any]:
        """Returns a full summary of all configured credentials."""
        return {
            "status": "success",
            "core": {
                "email": self.email,
                "account_password": self.account_password,
                "admin_email": self.admin_email,
            },
            "github": {
                "username": self.github_username,
                "token_configured": bool(self.github_token),
            },
            "business": {
                "upwork_email": self.upwork_email,
                "freelancer_email": self.freelancer_email,
                "paypal_email": self.paypal_email,
                "business_name": self.business_name,
            },
            "social_media": {
                "email": self.social_email,
                "display_name": self.social_display_name,
                "bio": self.social_bio,
            },
        }

    def get_signup_credentials(self, platform: str = "") -> Dict[str, Any]:
        """
        Returns credentials specifically formatted for account signup flows.
        Includes display name, bio, and all fields commonly needed during registration.
        """
        creds = self.get_credentials(platform)
        creds.update({
            "display_name": self.social_display_name,
            "bio": self.social_bio,
            "username_suggestion": self.github_username,  # Reuse GitHub username
            "recovery_email": self.admin_email,
        })
        return creds

    # ══════════════════════════════════════════
    # INTERNAL CREDENTIAL BUILDERS
    # ══════════════════════════════════════════

    def _google_creds(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "email": self.email,
            "password": self.account_password,
            "provider": "google",
            "note": "Use for Google OAuth / Sign-in with Google / Gmail login",
        }

    def _github_creds(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "username": self.github_username,
            "email": self.email,
            "token": self.github_token,
            "provider": "github",
            "note": "Use token for API auth, email+password for web login",
        }

    def _upwork_creds(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "email": self.upwork_email,
            "password": self.upwork_password,
            "provider": "upwork",
            "business_name": self.business_name,
        }

    def _freelancer_creds(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "email": self.freelancer_email,
            "password": self.freelancer_password,
            "provider": "freelancer",
            "business_name": self.business_name,
        }

    def _paypal_creds(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "email": self.paypal_email,
            "password": self.account_password,
            "provider": "paypal",
        }

    def _social_creds(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "email": self.social_email,
            "password": self.social_password,
            "display_name": self.social_display_name,
            "bio": self.social_bio,
            "provider": "social",
            "note": "Generic social media credentials — email + password for signup/login",
        }
