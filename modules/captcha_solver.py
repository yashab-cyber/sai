"""
S.A.I. CAPTCHA Solver — Multi-layer CAPTCHA detection and solving.

Layers (applied in order):
  1. Stealth    — human-like browser fingerprint to avoid triggering CAPTCHAs
  2. Detection  — identify CAPTCHA type from page DOM / screenshot
  3. Vision     — LLM analyses screenshot and solves image/text CAPTCHAs
  4. API        — 2Captcha / CapSolver cloud fallback (if key in .env)
  5. Wait+Retry — Cloudflare 5s challenge (just wait)
"""

import os
import re
import asyncio
import base64
import logging
import random
from typing import Optional, Dict, Any

logger = logging.getLogger("SAI.CaptchaSolver")

# ── CAPTCHA type signatures ──────────────────────────────────────────────────

CAPTCHA_SIGNATURES = {
    "recaptcha_v2": [
        "g-recaptcha", "www.google.com/recaptcha", "recaptcha/api2",
    ],
    "recaptcha_v3": [
        "grecaptcha.execute", "recaptcha/releases",
    ],
    "hcaptcha": [
        "hcaptcha.com", "h-captcha", "data-sitekey",
    ],
    "turnstile": [
        "challenges.cloudflare.com", "cf-turnstile", "turnstile/v0",
    ],
    "cloudflare_5s": [
        "Checking your browser", "cf-browser-verification",
        "Just a moment", "DDoS protection by Cloudflare",
    ],
    "image_grid": [
        "Select all squares", "Click verify", "I'm not a robot",
        "select all images", "click on all",
    ],
    "text_captcha": [
        "Enter the characters", "Type the text", "captcha-image",
        "captchaImage", "verification code",
    ],
    "funcaptcha": [
        "arkoselabs.com", "funcaptcha", "fc-iframe-wrap",
    ],
}


class CaptchaSolver:
    """
    Detects and solves CAPTCHAs encountered during browser automation.
    Works as a wrapper around BrowserManager — call solve_if_present()
    after any navigation that might trigger a CAPTCHA gate.
    """

    def __init__(self, browser, brain=None):
        self.browser = browser
        self.brain = brain
        self._two_captcha_key = os.getenv("TWO_CAPTCHA_API_KEY", "")
        self._capsolver_key = os.getenv("CAPSOLVER_API_KEY", "")

    # ════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ════════════════════════════════════════════════════════════════════════

    async def solve_if_present(self, timeout: int = 30) -> Dict[str, Any]:
        """
        Main entry-point. Call this after every navigation.
        Returns {"solved": True/False, "type": captcha_type, "method": how}
        """
        captcha_type = await self._detect()
        if not captcha_type:
            return {"solved": True, "type": None, "method": "none_detected"}

        logger.info("CAPTCHA detected: %s — attempting solve...", captcha_type)

        # Layer 1: Cloudflare 5-second JS challenge — just wait
        if captcha_type == "cloudflare_5s":
            return await self._solve_cloudflare_wait()

        # Layer 2: Try API solver (2Captcha / CapSolver) — fastest for reCAPTCHA
        if captcha_type in ("recaptcha_v2", "hcaptcha", "turnstile", "funcaptcha"):
            api_result = await self._solve_via_api(captcha_type)
            if api_result.get("solved"):
                return api_result

        # Layer 3: Vision-based solving via LLM screenshot analysis
        vision_result = await self._solve_via_vision(captcha_type)
        if vision_result.get("solved"):
            return vision_result

        logger.warning("Could not solve CAPTCHA type: %s", captcha_type)
        return {"solved": False, "type": captcha_type, "method": "all_failed"}

    # ════════════════════════════════════════════════════════════════════════
    # DETECTION
    # ════════════════════════════════════════════════════════════════════════

    async def _detect(self) -> Optional[str]:
        """Checks current page HTML + text for CAPTCHA signatures."""
        try:
            page = self.browser.page
            if not page:
                return None

            html = await page.content()
            text = await page.evaluate("() => document.body?.innerText || ''")
            combined = (html + text).lower()

            for captcha_type, signatures in CAPTCHA_SIGNATURES.items():
                if any(sig.lower() in combined for sig in signatures):
                    return captcha_type

            # Also check page title
            title = await page.title()
            if any(s in title for s in ["Just a moment", "Attention Required", "Security Check"]):
                return "cloudflare_5s"

            return None
        except Exception as e:
            logger.debug("CAPTCHA detection error: %s", e)
            return None

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 1: CLOUDFLARE WAIT
    # ════════════════════════════════════════════════════════════════════════

    async def _solve_cloudflare_wait(self) -> Dict[str, Any]:
        """Waits for Cloudflare 5-second JS challenge to auto-complete."""
        logger.info("Cloudflare challenge detected — waiting 8s for auto-complete...")
        await asyncio.sleep(8)
        # Check if still blocked
        still_blocked = await self._detect()
        if not still_blocked:
            logger.info("Cloudflare challenge passed.")
            return {"solved": True, "type": "cloudflare_5s", "method": "wait"}
        # Try moving mouse to simulate human
        await self._human_mouse_movement()
        await asyncio.sleep(5)
        still_blocked = await self._detect()
        return {
            "solved": not bool(still_blocked),
            "type": "cloudflare_5s",
            "method": "wait+mouse",
        }

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 2: API SOLVER
    # ════════════════════════════════════════════════════════════════════════

    async def _solve_via_api(self, captcha_type: str) -> Dict[str, Any]:
        """Routes to 2Captcha or CapSolver cloud API."""
        if self._capsolver_key:
            return await self._capsolver(captcha_type)
        if self._two_captcha_key:
            return await self._two_captcha(captcha_type)
        return {"solved": False, "reason": "no_api_key"}

    async def _get_sitekey(self) -> str:
        """Extracts the CAPTCHA sitekey from the current page."""
        try:
            page = self.browser.page
            # Try common sitekey attributes
            for attr in ["data-sitekey", "data-site-key"]:
                el = await page.query_selector(f"[{attr}]")
                if el:
                    key = await el.get_attribute(attr)
                    if key:
                        return key
            # Fallback: regex in HTML
            html = await page.content()
            m = re.search(r'["\']sitekey["\']\s*:\s*["\']([^"\']+)["\']', html)
            if m:
                return m.group(1)
            m = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if m:
                return m.group(1)
        except Exception:
            pass
        return ""

    async def _capsolver(self, captcha_type: str) -> Dict[str, Any]:
        """Solves via CapSolver API (supports reCAPTCHA v2/v3, hCaptcha, Turnstile)."""
        try:
            import httpx
            sitekey = await self._get_sitekey()
            page_url = self.browser.page.url

            task_map = {
                "recaptcha_v2": "ReCaptchaV2Task",
                "hcaptcha": "HCaptchaTask",
                "turnstile": "AntiTurnstileTaskProxyLess",
                "funcaptcha": "FunCaptchaTask",
            }
            task_type = task_map.get(captcha_type, "ReCaptchaV2Task")

            payload = {
                "clientKey": self._capsolver_key,
                "task": {
                    "type": task_type,
                    "websiteURL": page_url,
                    "websiteKey": sitekey,
                },
            }

            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post("https://api.capsolver.com/createTask", json=payload)
                data = r.json()
                task_id = data.get("taskId")
                if not task_id:
                    return {"solved": False, "reason": f"CapSolver task creation failed: {data}"}

                logger.info("CapSolver task created: %s", task_id)
                for _ in range(24):  # Poll up to 2 min
                    await asyncio.sleep(5)
                    poll = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self._capsolver_key, "taskId": task_id},
                    )
                    result = poll.json()
                    if result.get("status") == "ready":
                        token = result.get("solution", {}).get("gRecaptchaResponse", "")
                        if token:
                            await self._inject_token(captcha_type, token)
                            return {"solved": True, "type": captcha_type, "method": "capsolver"}
                        break

        except Exception as e:
            logger.warning("CapSolver failed: %s", e)
        return {"solved": False, "reason": "capsolver_failed"}

    async def _two_captcha(self, captcha_type: str) -> Dict[str, Any]:
        """Solves via 2Captcha API."""
        try:
            import httpx
            sitekey = await self._get_sitekey()
            page_url = self.browser.page.url

            method_map = {
                "recaptcha_v2": ("userrecaptcha", {"googlekey": sitekey, "pageurl": page_url}),
                "hcaptcha": ("hcaptcha", {"sitekey": sitekey, "pageurl": page_url}),
                "turnstile": ("turnstile", {"sitekey": sitekey, "pageurl": page_url}),
            }
            if captcha_type not in method_map:
                return {"solved": False, "reason": "unsupported_type_2captcha"}

            method, params = method_map[captcha_type]
            params["key"] = self._two_captcha_key
            params["method"] = method
            params["json"] = 1

            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.get("https://2captcha.com/in.php", params=params)
                data = r.json()
                if data.get("status") != 1:
                    return {"solved": False, "reason": f"2Captcha submit failed: {data}"}

                captcha_id = data["request"]
                logger.info("2Captcha task submitted: %s", captcha_id)

                for _ in range(24):
                    await asyncio.sleep(5)
                    poll = await client.get(
                        "https://2captcha.com/res.php",
                        params={"key": self._two_captcha_key, "action": "get",
                                "id": captcha_id, "json": 1},
                    )
                    result = poll.json()
                    if result.get("status") == 1:
                        token = result.get("request", "")
                        await self._inject_token(captcha_type, token)
                        return {"solved": True, "type": captcha_type, "method": "2captcha"}
                    if result.get("request") != "CAPCHA_NOT_READY":
                        break

        except Exception as e:
            logger.warning("2Captcha failed: %s", e)
        return {"solved": False, "reason": "2captcha_failed"}

    async def _inject_token(self, captcha_type: str, token: str):
        """Injects a solved CAPTCHA token into the page and submits."""
        page = self.browser.page
        try:
            if captcha_type in ("recaptcha_v2", "recaptcha_v3"):
                await page.evaluate(
                    f'document.getElementById("g-recaptcha-response").innerHTML="{token}";'
                )
                await page.evaluate(
                    "if(typeof ___grecaptcha_cfg!=='undefined'){Object.values(___grecaptcha_cfg.clients||{}).forEach(c=>{if(c&&c.aa&&c.aa.callback)c.aa.callback(arguments[0]);});}", token
                )
            elif captcha_type == "hcaptcha":
                await page.evaluate(
                    f'document.querySelector("[name=h-captcha-response]").value="{token}";'
                )
                await page.evaluate("if(window.hcaptcha)window.hcaptcha.execute();")
            elif captcha_type == "turnstile":
                await page.evaluate(
                    f'document.querySelector("[name=cf-turnstile-response]").value="{token}";'
                )
            # Try to find and click submit button
            for selector in ["[type=submit]", "button[data-action='submit']", "#recaptcha-verify-button"]:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    break
            await asyncio.sleep(2)
        except Exception as e:
            logger.debug("Token injection error: %s", e)

    # ════════════════════════════════════════════════════════════════════════
    # LAYER 3: VISION — LLM SCREENSHOT ANALYSIS
    # ════════════════════════════════════════════════════════════════════════

    async def _solve_via_vision(self, captcha_type: str) -> Dict[str, Any]:
        """Takes a screenshot and asks the LLM what to do to solve the CAPTCHA."""
        if not self.brain:
            return {"solved": False, "reason": "no_brain"}

        try:
            page = self.browser.page
            screenshot_bytes = await page.screenshot(full_page=False)
            b64_img = base64.b64encode(screenshot_bytes).decode("utf-8")

            # Handle simple checkbox/button CAPTCHAs first
            if captcha_type in ("recaptcha_v2", "hcaptcha", "turnstile"):
                # Try clicking the checkbox
                for selector in [
                    ".recaptcha-checkbox", "#recaptcha-anchor",
                    "[id*='checkbox']", ".hcaptcha-logo",
                    "iframe[src*='recaptcha']", "iframe[src*='hcaptcha']",
                ]:
                    try:
                        frame_el = await page.query_selector(selector)
                        if frame_el:
                            frame = await frame_el.content_frame()
                            if frame:
                                checkbox = await frame.query_selector(".recaptcha-checkbox-border, .checkbox")
                                if checkbox:
                                    await self._human_mouse_movement()
                                    await checkbox.click()
                                    await asyncio.sleep(3)
                                    # Check if solved (no more CAPTCHA)
                                    if not await self._detect():
                                        return {"solved": True, "type": captcha_type, "method": "checkbox_click"}
                    except Exception:
                        pass

            # Ask LLM to analyse screenshot and guide next action
            prompt = (
                f"You are S.A.I. looking at a browser screenshot. A CAPTCHA of type '{captcha_type}' is blocking progress.\n"
                "Analyse the screenshot carefully and tell me:\n"
                "1. What exactly is shown (checkbox, image grid, text challenge, slider, etc.)\n"
                "2. The precise CSS selector or coordinates to click/interact with\n"
                "3. If it is an image grid CAPTCHA, which grid cells to click (by position: top-left, top-center, etc.)\n"
                "4. If it is a text CAPTCHA, what text do you see in the CAPTCHA image\n\n"
                "Respond in JSON:\n"
                '{"captcha_visible": true/false, "action": "click|type|wait|unsolvable", '
                '"selector": "css selector or null", "text_answer": "if text captcha", '
                '"grid_cells": ["top-left","top-center"], "reasoning": "brief"}'
            )

            # Use brain with vision if supported
            try:
                response = self.brain.prompt_with_image(prompt, b64_img)
            except AttributeError:
                response = self.brain.prompt("CAPTCHA analysis.", prompt)

            if isinstance(response, str):
                import json
                try:
                    start = response.find("{")
                    end = response.rfind("}") + 1
                    response = json.loads(response[start:end])
                except Exception:
                    return {"solved": False, "reason": "llm_parse_failed"}

            if not response.get("captcha_visible", True):
                return {"solved": True, "type": captcha_type, "method": "vision_not_visible"}

            action = response.get("action", "")
            selector = response.get("selector", "")

            if action == "click" and selector:
                try:
                    await self._human_mouse_movement()
                    await page.click(selector, timeout=5000)
                    await asyncio.sleep(3)
                    if not await self._detect():
                        return {"solved": True, "type": captcha_type, "method": "vision_click"}
                except Exception as e:
                    logger.debug("Vision click failed: %s", e)

            if action == "type" and response.get("text_answer") and selector:
                try:
                    await page.fill(selector, response["text_answer"])
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(2)
                    if not await self._detect():
                        return {"solved": True, "type": captcha_type, "method": "vision_type"}
                except Exception as e:
                    logger.debug("Vision type failed: %s", e)

        except Exception as e:
            logger.warning("Vision solve failed: %s", e)

        return {"solved": False, "type": captcha_type, "method": "vision_failed"}

    # ════════════════════════════════════════════════════════════════════════
    # STEALTH HELPERS
    # ════════════════════════════════════════════════════════════════════════

    async def _human_mouse_movement(self):
        """Moves the mouse in a natural curve to simulate human behaviour."""
        try:
            page = self.browser.page
            # Generate Bezier-like random path
            for _ in range(random.randint(3, 6)):
                x = random.randint(100, 1180)
                y = random.randint(100, 620)
                await page.mouse.move(x, y, steps=random.randint(8, 20))
                await asyncio.sleep(random.uniform(0.05, 0.2))
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
# STEALTH CONTEXT FACTORY
# Replaces plain browser context with an anti-bot fingerprint
# ════════════════════════════════════════════════════════════════════════════

STEALTH_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# JavaScript injected into every page to mask automation fingerprints
STEALTH_JS = """
// Hide webdriver flag
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
// Fake plugins array
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
// Fake languages
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
// Fake chrome runtime
window.chrome = {runtime: {}};
// Override permissions
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
    ? Promise.resolve({state: Notification.permission})
    : origQuery(params);
// Canvas fingerprint noise
const origGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type, ...args) {
    const ctx = origGetContext.call(this, type, ...args);
    if (type === '2d') {
        const origFillText = ctx.fillText.bind(ctx);
        ctx.fillText = function(...a) {
            origFillText(...a);
            ctx.fillRect(0, 0, 0, 0); // tiny noise
        };
    }
    return ctx;
};
"""


async def make_stealth_context(playwright, headless: bool = True,
                               locale: str = "en-US", timezone: str = "UTC"):
    """
    Creates a Chromium browser context with full stealth fingerprinting
    and PERSISTENT user data directory to preserve login sessions.

    This means:
      - Google Sign-in works: log in once, session saved forever
      - 'Sign in with Google' on Reddit, Medium, etc. auto-uses saved session
      - Cookies, localStorage, and auth tokens persist across SAI restarts
    """
    import os
    ua = random.choice(STEALTH_USER_AGENTS)

    # Persistent profile directory — stores cookies/sessions
    user_data_dir = os.path.join(os.path.dirname(__file__), "..", "memory", "browser_profile")
    os.makedirs(user_data_dir, exist_ok=True)

    # launch_persistent_context = browser + context in one (with cookie persistence)
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--window-size=1280,720",
            "--disable-extensions",
            "--disable-component-extensions-with-background-pages",
            "--disable-default-apps",
            "--disable-features=TranslateUI",
        ],
        viewport={"width": 1280, "height": 720},
        user_agent=ua,
        locale=locale,
        timezone_id=timezone,
        java_script_enabled=True,
        permissions=["geolocation"],
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        ignore_default_args=["--enable-automation"],
    )

    # Inject stealth JS on every page before any scripts run
    await context.add_init_script(STEALTH_JS)

    # For compatibility with BrowserManager (which expects browser + context)
    # The persistent context acts as both browser and context
    return context, context
