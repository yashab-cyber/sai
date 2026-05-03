import asyncio
import logging
import random
from playwright.async_api import async_playwright
from typing import Dict, Any, Optional
from modules.captcha_solver import CaptchaSolver, make_stealth_context

class BrowserManager:
    """
    Autonomous Browser Control module using Playwright (Asynchronous).
    Supports navigation, interaction, and visual analysis.
    """
    
    def __init__(self, headless: bool = True, timeout: int = 60000,
                 locale: str = "en-US", timezone: str = "UTC", brain=None):
        self.logger = logging.getLogger("SAI.Browser")
        self.headless = headless
        self.timeout = timeout
        self.locale = locale
        self.timezone = timezone
        self.brain = brain

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.captcha_solver: Optional[CaptchaSolver] = None

    async def _ensure_browser(self):
        """Lazy initialization of the browser with stealth fingerprinting."""
        if not self.playwright:
            self.logger.info("Initializing Async Playwright (stealth mode)")
            self.playwright = await async_playwright().start()
            self.browser, self.context = await make_stealth_context(
                self.playwright,
                headless=self.headless,
                locale=self.locale,
                timezone=self.timezone,
            )
            # Persistent context may already have pages from previous sessions
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            self.page.set_default_timeout(self.timeout)
            # Attach CAPTCHA solver
            self.captcha_solver = CaptchaSolver(self, brain=self.brain)
            self.logger.info("Browser ready (stealth + CAPTCHA solver attached)")

    async def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """
        Navigates to a URL, then auto-detects and solves any CAPTCHA.
        Uses 'domcontentloaded' by default (works on SPAs like Upwork).
        """
        try:
            await self._ensure_browser()
            self.logger.info(f"Navigating to {url}")
            try:
                await self.page.goto(url, wait_until=wait_until, timeout=self.timeout)
            except Exception:
                self.logger.info("domcontentloaded timed out, retrying with 'load'...")
                await self.page.goto(url, wait_until="load", timeout=self.timeout)

            # ── Auto-solve CAPTCHA if one appeared ──
            if self.captcha_solver:
                captcha_result = await self.captcha_solver.solve_if_present()
                if captcha_result.get("type") and not captcha_result.get("solved"):
                    self.logger.warning(
                        "CAPTCHA '%s' could not be solved automatically (method: %s)",
                        captcha_result["type"], captcha_result.get("method"),
                    )
                elif captcha_result.get("type"):
                    self.logger.info(
                        "CAPTCHA '%s' solved via %s",
                        captcha_result["type"], captcha_result.get("method"),
                    )

            return {"status": "success", "title": await self.page.title(), "url": self.page.url}
        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def search(self, query: str):
        """Perform a web search using DuckDuckGo."""
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = f"https://duckduckgo.com/html/?q={encoded_query}"
        self.logger.info(f"Searching for: {query}")
        return await self.navigate(url)

    async def click(self, selector: str):
        """Clicks an element by selector with resilience."""
        try:
            await self._ensure_browser()
            # Wait for element to be attached and visible
            await self.page.wait_for_selector(selector, state="visible", timeout=self.timeout)
            await self.page.click(selector, timeout=self.timeout, force=True)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": f"Click failed on {selector}: {str(e)}"}

    async def type_text(self, selector: str, text: str):
        """Robustly types text by focusing and clicking first. Fallback to keyboard.type."""
        try:
            await self._ensure_browser()
            # Ensure element is ready
            await self.page.wait_for_selector(selector, state="visible", timeout=self.timeout)
            
            # Step 1: Try standard fill (fastest)
            try:
                await self.page.fill(selector, text, timeout=5000)
                return {"status": "success"}
            except Exception:
                # Step 2: Fallback to click and type (human-like)
                self.logger.info(f"Fill failed on {selector}, falling back to click and type.")
                await self.page.click(selector, force=True)
                # Clear existing text if possible (Ctrl+A, Backspace)
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.press("Backspace")
                await self.page.keyboard.type(text, delay=50) # Slight delay for realism
                return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": f"Type failed on {selector}: {str(e)}"}

    async def press_key(self, selector: str, key: str):
        """Presses a keyboard key on an element (e.g. 'Enter', 'Escape')."""
        try:
            await self._ensure_browser()
            if selector:
                await self.page.press(selector, key, timeout=self.timeout)
            else:
                await self.page.keyboard.press(key)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def wait_for(self, selector: str, state: str = "visible"):
        """Waits for an element to reach a specific state ('visible', 'hidden', 'attached', 'detached')."""
        try:
            await self._ensure_browser()
            await self.page.wait_for_selector(selector, state=state, timeout=self.timeout)
            return {"status": "success", "selector": selector, "state": state}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def capture_screenshot(self, filename: str = "logs/browser_shot.png"):
        """Captures a screenshot of the current page."""
        try:
            await self._ensure_browser()
            await self.page.screenshot(path=filename)
            return {"status": "success", "path": filename}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_content(self):
        """Returns the text content of the page."""
        try:
            await self._ensure_browser()
            content = await self.page.content()
            return {"status": "success", "content_length": len(content)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def navigate_back(self):
        """Navigates to the previous page in history."""
        try:
            await self._ensure_browser()
            await self.page.go_back()
            return {"status": "success", "url": self.page.url}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_interactive_elements(self):
        """Discovers interactive elements on the page for better planning."""
        try:
            await self._ensure_browser()
            # Advanced selector list to catch modern web elements
            selectors = [
                "button", "input", "select", "a", 
                "[role='button']", "[role='link']", "[role='checkbox']", 
                "[role='tab']", "[role='menuitem']", "[role='gridcell']",
                "[aria-label]", "[title]", "[placeholder]"
            ]
            elements = []
            
            seen_selectors = set()
            for selector in selectors:
                try:
                    found = await self.page.query_selector_all(selector)
                    for el in found:
                        try:
                            if await el.is_visible():
                                # Extract identifiers
                                aria_label = await el.get_attribute("aria-label")
                                title = await el.get_attribute("title")
                                placeholder = await el.get_attribute("placeholder")
                                text = (await el.inner_text() or "").strip()
                                role = await el.get_attribute("role")
                                
                                # Create a unique key to prevent duplicates
                                el_id = await el.get_attribute("id")
                                name = await el.get_attribute("name")
                                
                                discovery_text = (aria_label or title or placeholder or text or name or "")[:60]
                                if not discovery_text: continue
                                
                                # Special Tagging for WhatsApp Message Box
                                is_whatsapp_msg = any(hint in (aria_label or "").lower() for hint in ["type a message", "message"])
                                if is_whatsapp_msg:
                                    discovery_text = f"MESSAGE_INPUT: {discovery_text}"

                                # Deduplicate by discovery text and role
                                key = f"{discovery_text}|{role}|{await el.evaluate('el => el.tagName')}"
                                if key in seen_selectors: continue
                                seen_selectors.add(key)

                                elements.append({
                                    "tag": await el.evaluate('el => el.tagName'),
                                    "text": discovery_text,
                                    "id": el_id,
                                    "role": role,
                                    "name": name,
                                    "value": await el.get_attribute("value"),
                                    "class": await el.get_attribute("class")
                                })
                        except Exception:
                            continue
                except Exception:
                    continue
            
            return {"status": "success", "elements": elements[:30]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def scrape_page_text(self):
        """Extracts high-quality text content from the current page."""
        try:
            await self._ensure_browser()
            text = await self.page.evaluate("() => document.body.innerText")
            clean_text = "\n".join([line.strip() for line in text.split("\n") if line.strip()])
            return {"status": "success", "text": clean_text[:8000]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ══════════════════════════════════════════════════════════════════════
    # COORDINATE-BASED INTERACTION (Computer Vision)
    # These methods bypass CSS selectors entirely — they click/type at
    # pixel coordinates on the viewport, making them immune to DOM changes.
    # ══════════════════════════════════════════════════════════════════════

    async def click_at_coordinates(self, x: int, y: int) -> Dict[str, Any]:
        """
        Clicks at exact pixel coordinates on the page.
        Uses human-like mouse movement for stealth.
        """
        try:
            await self._ensure_browser()
            # Move to position with natural curve, then click
            await self.page.mouse.move(x, y, steps=random.randint(5, 12))
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await self.page.mouse.click(x, y)
            self.logger.info("CV click at (%d, %d)", x, y)
            return {"status": "success", "x": x, "y": y}
        except Exception as e:
            return {"status": "error", "message": f"CV click failed at ({x},{y}): {e}"}

    async def type_at_coordinates(self, x: int, y: int, text: str) -> Dict[str, Any]:
        """
        Clicks at coordinates to focus an input, then types text via keyboard.
        Works on any input field regardless of its DOM attributes.
        """
        try:
            await self._ensure_browser()
            # Click to focus the element
            await self.page.mouse.click(x, y)
            await asyncio.sleep(0.3)
            # Clear any existing text
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await asyncio.sleep(0.1)
            # Type with human-like delay
            await self.page.keyboard.type(text, delay=random.randint(30, 80))
            self.logger.info("CV type at (%d, %d): '%s'", x, y, text[:30])
            return {"status": "success", "x": x, "y": y, "text": text}
        except Exception as e:
            return {"status": "error", "message": f"CV type failed at ({x},{y}): {e}"}

    async def select_option_visually(self, x: int, y: int, option_text: str) -> Dict[str, Any]:
        """
        Handles <select> dropdowns by clicking at coordinates to open them,
        then selecting an option by its visible text.
        Falls back to keyboard arrow navigation if direct selection fails.
        """
        try:
            await self._ensure_browser()

            # Strategy 1: Find <select> element near the coordinates via JS
            # evaluate() returns raw JSON (not a handle), so null check works correctly
            select_info = await self.page.evaluate(
                """(coords) => {
                    const elements = document.querySelectorAll('select');
                    for (const el of elements) {
                        const rect = el.getBoundingClientRect();
                        const dx = Math.abs(rect.x + rect.width/2 - coords.x);
                        const dy = Math.abs(rect.y + rect.height/2 - coords.y);
                        if (dx < 150 && dy < 50) {
                            // Return a unique selector for this element
                            const title = el.getAttribute('title') || '';
                            const ariaLabel = el.getAttribute('aria-label') || '';
                            const name = el.getAttribute('name') || '';
                            const idx = Array.from(document.querySelectorAll('select')).indexOf(el);
                            return {found: true, title, ariaLabel, name, index: idx};
                        }
                    }
                    return {found: false};
                }""",
                {"x": x, "y": y},
            )

            if select_info and select_info.get("found"):
                # Re-query the select element by its index among all selects
                idx = select_info["index"]
                selects = await self.page.query_selector_all("select")
                if idx < len(selects):
                    try:
                        await selects[idx].select_option(label=option_text)
                        self.logger.info("CV select at (%d, %d): '%s' via native select", x, y, option_text)
                        return {"status": "success", "x": x, "y": y, "option": option_text, "method": "native"}
                    except Exception:
                        # Try by value instead of label
                        try:
                            await selects[idx].select_option(value=option_text)
                            self.logger.info("CV select at (%d, %d): '%s' via value", x, y, option_text)
                            return {"status": "success", "x": x, "y": y, "option": option_text, "method": "native_value"}
                        except Exception:
                            pass

            # Strategy 2: Click to open dropdown, then click the option text
            await self.page.mouse.click(x, y)
            await asyncio.sleep(0.5)
            option_loc = self.page.get_by_text(option_text, exact=True)
            if await option_loc.count() > 0:
                await option_loc.first.click()
                self.logger.info("CV select at (%d, %d): '%s' via text click", x, y, option_text)
                return {"status": "success", "x": x, "y": y, "option": option_text, "method": "text_click"}

            return {"status": "error", "message": f"Could not find option '{option_text}' near ({x},{y})"}
        except Exception as e:
            return {"status": "error", "message": f"CV select failed at ({x},{y}): {e}"}

    async def close(self):
        """Closes the browser session gracefully."""
        try:
            if self.context:
                await self.context.close()
        except Exception as e:
            self.logger.debug("Context close: %s", e)
        try:
            # For non-persistent contexts, browser != context
            if self.browser and self.browser is not self.context:
                await self.browser.close()
        except Exception as e:
            self.logger.debug("Browser close: %s", e)
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            self.logger.debug("Playwright stop: %s", e)

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        return {"status": "success"}
