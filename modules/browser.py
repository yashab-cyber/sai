import asyncio
import logging
from playwright.async_api import async_playwright
from typing import Dict, Any, Optional

class BrowserManager:
    """
    Autonomous Browser Control module using Playwright (Asynchronous).
    Supports navigation, interaction, and visual analysis.
    """
    
    def __init__(self, headless: bool = True, timeout: int = 60000, locale: str = "en-US", timezone: str = "UTC"):
        self.logger = logging.getLogger("SAI.Browser")
        self.headless = headless
        self.timeout = timeout
        self.locale = locale
        self.timezone = timezone
        
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def _ensure_browser(self):
        """Lazy initialization of the browser."""
        if not self.playwright:
            self.logger.info("Initializing Async Playwright")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=self.headless)
            
            # Use a modern human identity to bypass bot detection
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=user_agent,
                locale=self.locale,
                timezone_id=self.timezone
            )
            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.timeout)

    async def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """
        Navigates to a URL.

        Uses 'domcontentloaded' by default (works on SPAs like Upwork).
        Falls back to 'load' if that also times out before raising.
        """
        try:
            await self._ensure_browser()
            self.logger.info(f"Navigating to {url}")
            try:
                await self.page.goto(url, wait_until=wait_until, timeout=self.timeout)
            except Exception:
                # Fallback: settle for 'load' event (fires even on heavy SPAs)
                self.logger.info("domcontentloaded timed out, retrying with 'load'...")
                await self.page.goto(url, wait_until="load", timeout=self.timeout)
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

    async def close(self):
        """Closes the browser session."""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            self.playwright = None
            self.browser = None
            self.context = None
            self.page = None
            return {"status": "success"}
        return {"status": "success", "message": "Browser was not active."}
