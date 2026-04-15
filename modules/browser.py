import threading
from playwright.async_api import async_playwright
import logging
from typing import Dict, Any, Optional

class BrowserManager:
    """
    Autonomous Browser Control module using Playwright.
    Supports navigation, interaction, and visual analysis.
    Uses threading.local to ensure thread-safety in multi-threaded environments.
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30000, locale: str = "en-US", timezone: str = "UTC"):
        self.logger = logging.getLogger("SAI.Browser")
        self.headless = headless
        self.timeout = timeout
        self.locale = locale
        self.timezone = timezone
        # Use thread-local storage to prevent "cannot switch to a different thread" errors
        self._local = threading.local()

    def _get_local_state(self):
        """Returns the thread-local state, initializing if necessary."""
        if not hasattr(self._local, 'playwright'):
            self._local.playwright = None
            self._local.browser = None
            self._local.context = None
            self._local.page = None
        return self._local

    def _ensure_browser(self):
        """Lazy initialization of the browser for the current thread."""
        state = self._get_local_state()
        if not state.playwright:
            self.logger.info(f"Initializing Playwright for thread {threading.current_thread().name}")
            state.playwright = sync_playwright().start()
            state.browser = state.playwright.chromium.launch(headless=self.headless)
            
            # Use a modern human identity to bypass bot detection (e.g. Chrome 123 on Linux)
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            
            state.context = state.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=user_agent,
                locale=self.locale,
                timezone_id=self.timezone
            )
            state.page = state.context.new_page()
            state.page.set_default_timeout(self.timeout)

    def navigate(self, url: str):
        """Navigates to a URL."""
        try:
            self._ensure_browser()
            state = self._get_local_state()
            self.logger.info(f"Navigating to {url}")
            state.page.goto(url, wait_until="networkidle")
            return {"status": "success", "title": state.page.title(), "url": state.page.url}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search(self, query: str):
        """Perform a web search using DuckDuckGo."""
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = f"https://duckduckgo.com/html/?q={encoded_query}"
        self.logger.info(f"Searching for: {query}")
        return self.navigate(url)

    def click(self, selector: str):
        """Clicks an element by selector with resilience."""
        try:
            state = self._get_local_state()
            # Wait for element to be attached and visible
            state.page.wait_for_selector(selector, state="visible", timeout=self.timeout)
            state.page.click(selector, timeout=self.timeout, force=True)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": f"Click failed on {selector}: {str(e)}"}

    def type_text(self, selector: str, text: str):
        """Robustlly types text by focusing and clicking first. Fallback to keyboard.type."""
        try:
            state = self._get_local_state()
            # Ensure element is ready
            state.page.wait_for_selector(selector, state="visible", timeout=self.timeout)
            
            # Step 1: Try standard fill (fastest)
            try:
                state.page.fill(selector, text, timeout=5000)
                return {"status": "success"}
            except:
                # Step 2: Fallback to click and type (human-like)
                self.logger.info(f"Fill failed on {selector}, falling back to click and type.")
                state.page.click(selector, force=True)
                # Clear existing text if possible (Ctrl+A, Backspace)
                state.page.keyboard.press("Control+A")
                state.page.keyboard.press("Backspace")
                state.page.keyboard.type(text, delay=50) # Slight delay for realism
                return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": f"Type failed on {selector}: {str(e)}"}

    def press_key(self, selector: str, key: str):
        """Presses a keyboard key on an element (e.g. 'Enter', 'Escape')."""
        try:
            state = self._get_local_state()
            if selector:
                state.page.press(selector, key, timeout=self.timeout)
            else:
                state.page.keyboard.press(key)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def wait_for(self, selector: str, state: str = "visible"):
        """Waits for an element to reach a specific state ('visible', 'hidden', 'attached', 'detached')."""
        try:
            st = self._get_local_state()
            if not st.page: self._ensure_browser()
            st.page.wait_for_selector(selector, state=state, timeout=self.timeout)
            return {"status": "success", "selector": selector, "state": state}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def capture_screenshot(self, filename: str = "logs/browser_shot.png"):
        """Captures a screenshot of the current page."""
        try:
            state = self._get_local_state()
            if not state.page: self._ensure_browser()
            state.page.screenshot(path=filename)
            return {"status": "success", "path": filename}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_content(self):
        """Returns the text content of the page."""
        try:
            state = self._get_local_state()
            content = state.page.content()
            return {"status": "success", "content_length": len(content)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def navigate_back(self):
        """Navigates to the previous page in history."""
        try:
            state = self._get_local_state()
            state.page.go_back()
            return {"status": "success", "url": state.page.url}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_interactive_elements(self):
        """Discovers interactive elements on the page for better planning."""
        try:
            state = self._get_local_state()
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
                    found = state.page.query_selector_all(selector)
                    for el in found:
                        try:
                            if el.is_visible():
                                # Extract identifiers
                                aria_label = el.get_attribute("aria-label")
                                title = el.get_attribute("title")
                                placeholder = el.get_attribute("placeholder")
                                text = (el.inner_text() or "").strip()
                                role = el.get_attribute("role")
                                
                                # Create a unique key to prevent duplicates
                                el_id = el.get_attribute("id")
                                name = el.get_attribute("name")
                                
                                discovery_text = (aria_label or title or placeholder or text or name or "")[:60]
                                if not discovery_text: continue
                                
                                # Special Tagging for WhatsApp Message Box
                                is_whatsapp_msg = any(hint in (aria_label or "").lower() for hint in ["type a message", "message"])
                                if is_whatsapp_msg:
                                    discovery_text = f"MESSAGE_INPUT: {discovery_text}"

                                # Deduplicate by discovery text and role
                                key = f"{discovery_text}|{role}|{el.tag_name()}"
                                if key in seen_selectors: continue
                                seen_selectors.add(key)

                                elements.append({
                                    "tag": el.tag_name(),
                                    "text": discovery_text,
                                    "id": el_id,
                                    "role": role,
                                    "name": name,
                                    "value": el.get_attribute("value"),
                                    "class": el.get_attribute("class")
                                })
                        except Exception:
                            # Skip elements that throw security errors (common in cross-origin frames)
                            continue
                except Exception:
                    # Skip problematic selectors or frame access errors
                    continue
            
            # Return a condensed list to avoid token bloat
            return {"status": "success", "elements": elements[:30]} # Increased to 30 elements
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def scrape_page_text(self):
        """Extracts high-quality text content from the current page."""
        try:
            state = self._get_local_state()
            # Simple innerText extraction which is much cleaner than HTML content for LLMs
            text = state.page.evaluate("() => document.body.innerText")
            # Clean up excessive whitespace
            clean_text = "\n".join([line.strip() for line in text.split("\n") if line.strip()])
            return {"status": "success", "text": clean_text[:8000]} # Limit to 8k chars
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def close(self):
        """Closes the browser session for the current thread."""
        state = self._get_local_state()
        if state.browser:
            state.browser.close()
            state.playwright.stop()
            state.playwright = None
            state.browser = None
            return {"status": "success"}
        return {"status": "success", "message": "Browser was not active for this thread."}
