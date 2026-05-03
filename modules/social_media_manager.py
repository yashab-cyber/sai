"""
S.A.I. Social Media Manager — Autonomous Account Lifecycle.

Handles the full flow for any platform:
  1. Check AccountRegistry → does SAI already have an account?
  2. If NO  → run signup flow via Browser + Brain (LLM-guided)
  3. If YES → run login flow
  4. Handle 2FA/OTP by reading SAI's Gmail inbox automatically
  5. Update AccountRegistry with result

The actual browser interactions are delegated to the LLM Brain,
which analyses screenshots and decides what to click/type next.
This module orchestrates the high-level flow and provides the
credentials + OTP pipeline.
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional

from modules.account_registry import AccountRegistry
from modules.credential_vault import CredentialVault


# ── Platform Configuration ──────────────────────────────────────────────

PLATFORM_CONFIG = {
    "twitter": {
        "name": "Twitter / X",
        "signup_url": "https://x.com/i/flow/signup",
        "login_url": "https://x.com/i/flow/login",
        "home_url": "https://x.com/home",
        "has_google_signin": True,
        "typical_2fa": True,
    },
    "x": {
        "name": "Twitter / X",
        "signup_url": "https://x.com/i/flow/signup",
        "login_url": "https://x.com/i/flow/login",
        "home_url": "https://x.com/home",
        "has_google_signin": True,
        "typical_2fa": True,
        "alias_of": "twitter",
    },
    "facebook": {
        "name": "Facebook",
        "signup_url": "https://www.facebook.com/r.php",
        "login_url": "https://www.facebook.com/login",
        "home_url": "https://www.facebook.com/",
        "has_google_signin": False,
        "typical_2fa": True,
    },
    "instagram": {
        "name": "Instagram",
        "signup_url": "https://www.instagram.com/accounts/emailsignup/",
        "login_url": "https://www.instagram.com/accounts/login/",
        "home_url": "https://www.instagram.com/",
        "has_google_signin": False,
        "typical_2fa": True,
    },
    "linkedin": {
        "name": "LinkedIn",
        "signup_url": "https://www.linkedin.com/signup",
        "login_url": "https://www.linkedin.com/login",
        "home_url": "https://www.linkedin.com/feed/",
        "has_google_signin": True,
        "typical_2fa": True,
    },
    "reddit": {
        "name": "Reddit",
        "signup_url": "https://www.reddit.com/register/",
        "login_url": "https://www.reddit.com/login/",
        "home_url": "https://www.reddit.com/",
        "has_google_signin": True,
        "typical_2fa": False,
    },
    "discord": {
        "name": "Discord",
        "signup_url": "https://discord.com/register",
        "login_url": "https://discord.com/login",
        "home_url": "https://discord.com/channels/@me",
        "has_google_signin": False,
        "typical_2fa": True,
    },
    "tiktok": {
        "name": "TikTok",
        "signup_url": "https://www.tiktok.com/signup",
        "login_url": "https://www.tiktok.com/login",
        "home_url": "https://www.tiktok.com/foryou",
        "has_google_signin": True,
        "typical_2fa": False,
    },
    "github": {
        "name": "GitHub",
        "signup_url": "https://github.com/signup",
        "login_url": "https://github.com/login",
        "home_url": "https://github.com/",
        "has_google_signin": False,
        "typical_2fa": True,
    },
    "stackoverflow": {
        "name": "Stack Overflow",
        "signup_url": "https://stackoverflow.com/users/signup",
        "login_url": "https://stackoverflow.com/users/login",
        "home_url": "https://stackoverflow.com/",
        "has_google_signin": True,
        "typical_2fa": False,
    },
    "medium": {
        "name": "Medium",
        "signup_url": "https://medium.com/m/signin?operation=register",
        "login_url": "https://medium.com/m/signin",
        "home_url": "https://medium.com/",
        "has_google_signin": True,
        "typical_2fa": False,
    },
    "producthunt": {
        "name": "Product Hunt",
        "signup_url": "https://www.producthunt.com/",
        "login_url": "https://www.producthunt.com/",
        "home_url": "https://www.producthunt.com/",
        "has_google_signin": True,
        "typical_2fa": False,
    },
    "devto": {
        "name": "Dev.to",
        "signup_url": "https://dev.to/enter",
        "login_url": "https://dev.to/enter",
        "home_url": "https://dev.to/",
        "has_google_signin": False,
        "typical_2fa": False,
    },
    "upwork": {
        "name": "Upwork",
        "signup_url": "https://www.upwork.com/nx/signup/",
        "login_url": "https://www.upwork.com/ab/account-security/login",
        "home_url": "https://www.upwork.com/nx/find-work/",
        "has_google_signin": True,
        "typical_2fa": True,
    },
    "freelancer": {
        "name": "Freelancer",
        "signup_url": "https://www.freelancer.com/signup",
        "login_url": "https://www.freelancer.com/login",
        "home_url": "https://www.freelancer.com/dashboard",
        "has_google_signin": True,
        "typical_2fa": False,
    },
}


class SocialMediaManager:
    """
    Orchestrates autonomous social media account creation, login, and management.

    Flow:
        1. Check registry → signup or login?
        2. Navigate to platform URL
        3. Use LLM Brain to guide browser interactions (screenshot → action loop)
        4. If OTP/2FA needed → read email → extract code → enter it
        5. Update registry with result
    """

    def __init__(self, browser=None, brain=None, email_mgr=None,
                 credential_vault: CredentialVault = None,
                 account_registry: AccountRegistry = None):
        self.browser = browser
        self.brain = brain
        self.email_mgr = email_mgr
        self.vault = credential_vault or CredentialVault()
        self.registry = account_registry or AccountRegistry()
        self.logger = logging.getLogger("SAI.SocialMedia")

    # ══════════════════════════════════════════
    # MAIN ENTRY POINTS
    # ══════════════════════════════════════════

    async def access_platform(self, platform: str) -> Dict[str, Any]:
        """
        Smart entry point — automatically decides signup vs login.
        Returns the result of the operation.
        """
        platform = self._resolve_alias(platform)
        config = PLATFORM_CONFIG.get(platform)
        if not config:
            return {
                "status": "error",
                "message": f"Unknown platform: {platform}. "
                           f"Supported: {', '.join(PLATFORM_CONFIG.keys())}",
            }

        if self.registry.needs_signup(platform):
            self.logger.info("[%s] No account found — initiating SIGNUP flow.", platform)
            return await self.signup(platform)
        else:
            self.logger.info("[%s] Account exists — initiating LOGIN flow.", platform)
            return await self.login(platform)

    async def signup(self, platform: str) -> Dict[str, Any]:
        """Creates a new account on the platform using LLM-guided browser automation."""
        platform = self._resolve_alias(platform)
        config = PLATFORM_CONFIG.get(platform)
        if not config:
            return {"status": "error", "message": f"Unknown platform: {platform}"}

        creds = self.vault.get_signup_credentials(platform)
        url = config["signup_url"]

        self.logger.info("[SIGNUP] %s — navigating to %s", config["name"], url)

        # Navigate to signup page
        nav_result = await self.browser.navigate(url)
        if nav_result.get("status") != "success":
            return {"status": "error", "message": f"Failed to load {url}: {nav_result}"}

        # Run the LLM-guided interaction loop
        result = await self._run_auth_loop(
            platform=platform,
            config=config,
            creds=creds,
            mode="signup",
            max_iterations=20,
        )

        if result.get("status") == "success":
            # Register the account
            self.registry.register_account(
                platform=platform,
                email=creds.get("email", ""),
                username=creds.get("username_suggestion", ""),
                has_2fa=config.get("typical_2fa", False),
                status="active",
                notes=f"Auto-created by SAI on {self._now()}",
            )
            self.logger.info("[SIGNUP] ✅ %s account created successfully!", config["name"])

        return result

    async def login(self, platform: str) -> Dict[str, Any]:
        """Logs into an existing account on the platform."""
        platform = self._resolve_alias(platform)
        config = PLATFORM_CONFIG.get(platform)
        if not config:
            return {"status": "error", "message": f"Unknown platform: {platform}"}

        creds = self.vault.get_credentials(platform)
        account = self.registry.get_account(platform)

        # ── API-Based Login (skip browser for platforms with API tokens) ──
        # GitHub has a personal access token — no need for browser login
        if platform == "github":
            return await self._login_via_api_github()

        # ── Browser-Based Login ──
        url = config["login_url"]
        self.logger.info("[LOGIN] %s — navigating to %s", config["name"], url)

        nav_result = await self.browser.navigate(url)
        if nav_result.get("status") != "success":
            return {"status": "error", "message": f"Failed to load {url}: {nav_result}"}

        result = await self._run_auth_loop(
            platform=platform,
            config=config,
            creds=creds,
            mode="login",
            max_iterations=15,
        )

        if result.get("status") == "success":
            self.registry.update_login(platform, notes=f"Login at {self._now()}")
            self.logger.info("[LOGIN] ✅ %s login successful!", config["name"])
            result["message"] = (
                f"LOGIN COMPLETE — Successfully logged into {config['name']} via headless browser. "
                f"The browser session is authenticated. "
                f"DO NOT try to login again via desktop controls. "
                f"To make changes, use the appropriate API tools."
            )

        return result

    async def _login_via_api_github(self) -> Dict[str, Any]:
        """
        GitHub login via API token — no browser needed.
        Verifies the token works and returns authenticated user info.
        """
        import os, requests
        token = os.getenv("SAI_GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")
        if not token:
            return {"status": "error", "message": "No GITHUB_TOKEN configured in .env"}

        self.logger.info("[LOGIN] GitHub — verifying API token (no browser needed)")
        try:
            resp = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                timeout=10,
            )
            if resp.status_code == 200:
                user = resp.json()
                self.registry.update_login("github", notes=f"API login at {self._now()}")
                self.logger.info("[LOGIN] ✅ GitHub API login verified — user: %s", user.get("login"))
                return {
                    "status": "success",
                    "platform": "github",
                    "mode": "login",
                    "message": (
                        f"LOGIN COMPLETE — Authenticated as '{user.get('login')}' via GitHub API token. "
                        f"You have {user.get('public_repos', 0)} public repos, "
                        f"{user.get('followers', 0)} followers. "
                        f"Use 'github.presence' or 'identity.github.api' to make changes."
                    ),
                    "user": user.get("login"),
                    "repos": user.get("public_repos", 0),
                }
            else:
                return {
                    "status": "error",
                    "platform": "github",
                    "message": f"GitHub API token invalid (HTTP {resp.status_code}): {resp.text[:200]}",
                }
        except Exception as e:
            return {"status": "error", "platform": "github", "message": f"GitHub API error: {e}"}

    async def handle_otp(self, platform: str = "", wait_seconds: int = 90) -> Dict[str, Any]:
        """
        Waits for an OTP email, extracts the code, and types it into the browser.
        Called automatically during signup/login when 2FA is detected.
        """
        if not self.email_mgr:
            return {"status": "error", "message": "Email manager not available for OTP"}

        self.logger.info("[OTP] Waiting up to %ds for verification code...", wait_seconds)
        otp_result = self.email_mgr.extract_otp(wait_seconds=wait_seconds)

        if otp_result.get("status") != "success":
            return {"status": "error", "message": "OTP not received in time", "detail": otp_result}

        otp_code = otp_result.get("otp", "")
        self.logger.info("[OTP] ✅ Code extracted: %s (from: %s)", otp_code, otp_result.get("from", ""))

        # Type the OTP into the current page
        if self.brain and self.browser and self.browser.page:
            # Ask LLM to find the OTP input field and enter it
            try:
                screenshot_bytes = await self.browser.page.screenshot(full_page=False)
                import base64
                b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                prompt = (
                    f"You are S.A.I. looking at a browser page that is asking for a verification code / OTP.\n"
                    f"The OTP code is: {otp_code}\n\n"
                    "Find the input field for the verification code and tell me the CSS selector.\n"
                    "If there are multiple digit boxes (one per digit), list all selectors.\n\n"
                    'Respond in JSON: {"selectors": ["css_selector"], "type": "single_field|digit_boxes"}'
                )

                try:
                    resp = self.brain.prompt_with_image(prompt, b64)
                except AttributeError:
                    resp = self.brain.prompt("Find OTP input field.", prompt)

                if isinstance(resp, str):
                    import json
                    start = resp.find("{")
                    end = resp.rfind("}") + 1
                    resp = json.loads(resp[start:end])

                input_type = resp.get("type", "single_field")
                selectors = resp.get("selectors", [])

                if input_type == "digit_boxes" and len(selectors) >= len(otp_code):
                    for i, digit in enumerate(otp_code):
                        await self.browser.type_text(selectors[i], digit)
                elif selectors:
                    await self.browser.type_text(selectors[0], otp_code)
                else:
                    # Fallback: try common selectors
                    for sel in ["input[name*='code']", "input[name*='otp']",
                                "input[name*='verify']", "input[type='tel']",
                                "input[name*='pin']", "input[autocomplete='one-time-code']"]:
                        try:
                            await self.browser.page.wait_for_selector(sel, timeout=3000)
                            await self.browser.type_text(sel, otp_code)
                            break
                        except Exception:
                            continue

                # Press Enter or click verify/submit
                await asyncio.sleep(1)
                await self.browser.page.keyboard.press("Enter")

            except Exception as e:
                self.logger.warning("[OTP] Auto-enter failed: %s — code is: %s", e, otp_code)

        if platform:
            self.registry.set_2fa(platform, True)

        return {
            "status": "success",
            "otp": otp_code,
            "from": otp_result.get("from", ""),
            "subject": otp_result.get("subject", ""),
        }

    # ══════════════════════════════════════════
    # LLM-GUIDED BROWSER INTERACTION LOOP
    # ══════════════════════════════════════════

    async def _run_auth_loop(
        self,
        platform: str,
        config: Dict[str, Any],
        creds: Dict[str, Any],
        mode: str,  # "signup" or "login"
        max_iterations: int = 15,
    ) -> Dict[str, Any]:
        """
        Core loop: deterministic pre-fill → screenshot → LLM decides action → execute → repeat.
        Handles OTP automatically when detected.
        """
        if not self.brain:
            return {"status": "error", "message": "Brain not available for guided interaction"}

        import json

        otp_attempted = False
        screenshot_path = "logs/social_auth_shot.png"

        # ── PHASE 1: Deterministic Pre-Fill ──
        # Try to fill known input fields directly before LLM guidance.
        prefill_done = await self._deterministic_prefill(platform, creds, mode)
        if prefill_done:
            self.logger.info("[%s] Deterministic pre-fill completed — credentials entered.", platform)

        # ── PHASE 2: LLM-Guided Loop ──
        for iteration in range(1, max_iterations + 1):
            self.logger.info("[%s] %s iteration %d/%d", platform, mode.upper(), iteration, max_iterations)

            await asyncio.sleep(2)  # Allow page to settle

            # Save screenshot to disk so Brain can see it
            try:
                await self.browser.page.screenshot(path=screenshot_path, full_page=False)
            except Exception as e:
                self.logger.warning("[%s] Screenshot failed: %s", platform, e)
                screenshot_path = None

            # Also get page text + interactive elements for context
            page_text = ""
            page_url = ""
            try:
                page_url = self.browser.page.url
                text_result = await self.browser.scrape_page_text()
                page_text = text_result.get("text", "")[:2000]
            except Exception:
                pass

            # Check if we already landed on the home/dashboard page
            home_url = config.get("home_url", "")
            login_url = config.get("login_url", "")
            signup_url = config.get("signup_url", "")
            # Exclude auth pages — prevent false positive (e.g. github.com/ ⊂ github.com/login)
            auth_keywords = ["login", "signin", "signup", "register", "session", "auth", "password"]
            on_auth_page = any(kw in page_url.lower() for kw in auth_keywords)
            if home_url and not on_auth_page and home_url.rstrip("/") in page_url.rstrip("/"):
                self.logger.info("[%s] ✅ Detected home page URL — login successful!", platform)
                return {"status": "success", "platform": platform, "mode": mode,
                        "message": f"Successfully reached {config['name']} home page"}

            # Build context prompt
            prompt = self._build_auth_prompt(
                platform, config, creds, mode, iteration, otp_attempted,
                page_text=page_text, page_url=page_url,
            )

            # Ask Brain WITH the screenshot
            try:
                resp = self.brain.prompt(
                    f"Social media {mode} — {config['name']} step {iteration}",
                    prompt,
                    image_path=screenshot_path,
                )

                if not isinstance(resp, dict):
                    if isinstance(resp, str):
                        start = resp.find("{")
                        end = resp.rfind("}") + 1
                        if start >= 0 and end > start:
                            resp = json.loads(resp[start:end])
                        else:
                            continue
                    else:
                        continue

            except Exception as e:
                self.logger.warning("[%s] Brain response error: %s", platform, e)
                continue

            action = resp.get("action", "")
            status = resp.get("status", "ongoing")
            message = resp.get("message", "")
            self.logger.info("[%s] Brain → action=%s status=%s msg=%s", platform, action, status, message[:80])

            # Check completion
            if status == "completed":
                return {"status": "success", "platform": platform, "mode": mode,
                        "message": resp.get("message", f"{mode} completed")}

            if status == "failed":
                return {"status": "error", "platform": platform, "mode": mode,
                        "message": resp.get("message", f"{mode} failed")}

            # Execute action
            try:
                if action == "click":
                    selector = resp.get("selector", "")
                    if selector:
                        result = await self.browser.click(selector)
                        self.logger.info("[%s] Click %s → %s", platform, selector, result.get("status"))

                elif action == "type":
                    selector = resp.get("selector", "")
                    text = resp.get("text", "")
                    if selector and text:
                        result = await self.browser.type_text(selector, text)
                        self.logger.info("[%s] Type into %s → %s", platform, selector, result.get("status"))

                elif action == "press":
                    key = resp.get("key", "Enter")
                    await self.browser.page.keyboard.press(key)
                    self.logger.info("[%s] Press key: %s", platform, key)

                elif action == "wait":
                    wait_time = min(resp.get("seconds", 3), 10)
                    await asyncio.sleep(wait_time)

                elif action == "otp":
                    if not otp_attempted:
                        otp_result = await self.handle_otp(platform=platform, wait_seconds=90)
                        otp_attempted = True
                        if otp_result.get("status") != "success":
                            return {"status": "error", "platform": platform,
                                    "message": f"OTP verification failed: {otp_result.get('message')}"}

                elif action == "navigate":
                    url = resp.get("url", "")
                    if url:
                        await self.browser.navigate(url)

            except Exception as e:
                self.logger.warning("[%s] Action '%s' failed: %s", platform, action, e)

        return {"status": "error", "platform": platform, "mode": mode,
                "message": f"Max iterations ({max_iterations}) reached without completion"}

    async def _deterministic_prefill(
        self, platform: str, creds: Dict[str, Any], mode: str
    ) -> bool:
        """
        Tries to fill email/password fields using known CSS selectors
        before falling back to LLM. Returns True if any field was filled.
        """
        email = creds.get("email", "")
        password = creds.get("password", "")
        filled = False

        # Common email/username selectors across platforms
        email_selectors = [
            "input[name='login']",           # GitHub
            "input[name='email']",           # Generic
            "input[name='username']",        # Generic
            "input[type='email']",           # Generic
            "input[name='session[username_or_email]']",  # Twitter
            "input[id='login_field']",       # GitHub
            "input[id='email']",             # Facebook
            "#identifierId",                 # Google
        ]

        password_selectors = [
            "input[name='password']",        # Generic
            "input[type='password']",        # Generic
            "input[name='session[password]']",  # Twitter
            "input[id='password']",          # GitHub
        ]

        # Try filling email
        for sel in email_selectors:
            try:
                el = await self.browser.page.query_selector(sel)
                if el and await el.is_visible():
                    # Use page.fill() directly for reliability
                    await self.browser.page.fill(sel, email)
                    self.logger.info("[%s] Pre-filled email into %s", platform, sel)
                    filled = True
                    break
            except Exception:
                continue

        # Try filling password — use page.fill() directly, not type_text
        # page.fill() handles special chars like @ reliably
        for sel in password_selectors:
            try:
                el = await self.browser.page.query_selector(sel)
                if el and await el.is_visible():
                    await self.browser.page.click(sel)  # Focus the field first
                    await self.browser.page.fill(sel, password)
                    self.logger.info("[%s] Pre-filled password into %s", platform, sel)
                    filled = True
                    break
            except Exception as e:
                self.logger.debug("[%s] Password fill failed for %s: %s", platform, sel, e)
                continue

        # If signup, try display name
        if mode == "signup":
            display_name = creds.get("display_name", "")
            name_selectors = [
                "input[name='name']", "input[name='display_name']",
                "input[name='full_name']", "input[name='fullName']",
                "input[id='name']",
            ]
            for sel in name_selectors:
                try:
                    el = await self.browser.page.query_selector(sel)
                    if el and await el.is_visible():
                        await self.browser.type_text(sel, display_name)
                        self.logger.info("[%s] Pre-filled name into %s", platform, sel)
                        break
                except Exception:
                    continue

        # Try clicking submit button
        if filled:
            await asyncio.sleep(0.5)
            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']",
                "input[name='commit']",       # GitHub
                "button[data-testid='login-button']",
                "button:has-text('Sign in')",
                "button:has-text('Log in')",
                "button:has-text('Sign up')",
                "button:has-text('Next')",
            ]
            for sel in submit_selectors:
                try:
                    el = await self.browser.page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        self.logger.info("[%s] Clicked submit: %s", platform, sel)
                        # Wait for page to redirect after login
                        await asyncio.sleep(3)
                        break
                except Exception:
                    continue

        return filled

    def _build_auth_prompt(
        self, platform: str, config: dict, creds: dict, mode: str,
        iteration: int, otp_attempted: bool,
        page_text: str = "", page_url: str = "",
    ) -> str:
        """Builds the LLM prompt for guided auth interactions."""
        email = creds.get("email", "")
        password = creds.get("password", "")
        display_name = creds.get("display_name", "")
        username = creds.get("username_suggestion", "")
        bio = creds.get("bio", "")

        action_type = "SIGN UP (create a new account)" if mode == "signup" else "LOG IN (existing account)"

        prompt = (
            f"You are S.A.I., an autonomous AI. You are looking at a browser screenshot.\n"
            f"TASK: {action_type} on {config['name']}.\n\n"
            f"CREDENTIALS TO USE:\n"
            f"  Email: {email}\n"
            f"  Password: {password}\n"
        )
        if mode == "signup":
            prompt += (
                f"  Display Name: {display_name}\n"
                f"  Username: {username}\n"
                f"  Bio: {bio}\n"
            )
        prompt += (
            f"\nCurrent URL: {page_url}\n"
            f"Iteration: {iteration}\n"
            f"OTP already attempted: {otp_attempted}\n"
        )
        if page_text:
            prompt += f"\nVISIBLE PAGE TEXT (first 2000 chars):\n{page_text[:2000]}\n"
        prompt += (
            "\nINSTRUCTIONS:\n"
            "- Analyse the screenshot AND the page text to understand what page/form is shown.\n"
            "- Decide the SINGLE best next action to take.\n"
            "- If credentials are already filled in, just click the submit/sign-in button.\n"
            "- If you see a verification/OTP code request, use action='otp' (SAI will read email).\n"
            "- If signup/login appears complete (home page, dashboard, feed visible), set status='completed'.\n"
            "- If there is an error or block, set status='failed' with explanation.\n"
            "- NEVER use 'Sign in with Google' — Google blocks automated browsers. Always use the platform's own email+password form.\n"
            "- Do NOT navigate to accounts.google.com — it will fail with 'browser not secure'.\n"
            "- EXCEPTION: If you see Google Sign-in and the Google account is ALREADY logged in (no password needed), you may click it.\n\n"
            "Respond ONLY in JSON:\n"
            '{"action": "click|type|press|wait|otp|navigate",\n'
            ' "selector": "css_selector (for click/type)",\n'
            ' "text": "text to type (for type action)",\n'
            ' "key": "key name (for press action)",\n'
            ' "url": "url (for navigate action)",\n'
            ' "seconds": 3,\n'
            ' "status": "ongoing|completed|failed",\n'
            ' "message": "brief description of what you see/did"}'
        )
        return prompt

    # ══════════════════════════════════════════
    # GOOGLE SESSION BOOTSTRAP
    # ══════════════════════════════════════════

    async def bootstrap_google_session(self) -> Dict[str, Any]:
        """
        Opens a VISIBLE browser so the user can log into Google manually.
        After login, the session is persisted in the browser profile.
        All future 'Sign in with Google' flows will auto-use it.
        """
        from playwright.async_api import async_playwright
        from modules.captcha_solver import make_stealth_context

        self.logger.info("[GOOGLE] Opening visible browser for Google login...")

        pw = await async_playwright().start()
        # Launch NON-headless so the user can interact
        browser, context = await make_stealth_context(
            pw, headless=False, locale="en-US", timezone="UTC"
        )

        if context.pages:
            page = context.pages[0]
        else:
            page = await context.new_page()

        await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")

        self.logger.info(
            "[GOOGLE] Visible browser opened at accounts.google.com. "
            "Please log in manually. Waiting up to 5 minutes..."
        )

        # Wait for the user to complete login (detect redirect to myaccount.google.com)
        try:
            for _ in range(300):  # 5 minutes max
                await asyncio.sleep(1)
                url = page.url
                if "myaccount.google.com" in url or "google.com/search" in url:
                    self.logger.info("[GOOGLE] ✅ Google login detected! Session saved.")
                    await context.close()
                    await pw.stop()
                    return {
                        "status": "success",
                        "message": (
                            "Google session saved to persistent browser profile. "
                            "All future 'Sign in with Google' on any platform will auto-use this session."
                        ),
                    }
        except Exception as e:
            self.logger.warning("[GOOGLE] Bootstrap error: %s", e)

        await context.close()
        await pw.stop()
        return {
            "status": "error",
            "message": "Google login timed out (5 min). Please try again.",
        }

    # ══════════════════════════════════════════
    # STATUS & INFO
    # ══════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Returns current social media account status."""
        return {
            "registry": self.registry.get_summary(),
            "accounts": self.registry.list_accounts(),
            "supported_platforms": list(PLATFORM_CONFIG.keys()),
        }

    def list_platforms(self) -> Dict[str, Any]:
        """Lists all supported platforms with account status."""
        platforms = []
        for key, config in PLATFORM_CONFIG.items():
            if config.get("alias_of"):
                continue
            has_account = self.registry.has_account(key)
            account = self.registry.get_account(key) or {}
            platforms.append({
                "platform": key,
                "name": config["name"],
                "has_account": has_account,
                "status": account.get("status", "no_account"),
                "last_login": account.get("last_login", "never"),
                "has_2fa": account.get("has_2fa", config.get("typical_2fa", False)),
                "has_google_signin": config.get("has_google_signin", False),
            })
        return {"status": "success", "platforms": platforms}

    # ══════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════

    def _resolve_alias(self, platform: str) -> str:
        """Resolves platform aliases (e.g., 'x' → 'twitter')."""
        key = platform.lower().strip()
        config = PLATFORM_CONFIG.get(key, {})
        return config.get("alias_of", key)

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().isoformat()
