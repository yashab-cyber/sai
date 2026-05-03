"""
S.A.I. Browser Vision — Computer Vision Layer for Browser Automation.

Instead of relying on fragile CSS selectors, this module:
  1. Takes a screenshot of the current browser page
  2. Sends it to the LLM with a structured prompt
  3. Gets back pixel coordinates for interaction
  4. Executes clicks/types at those coordinates

This makes browser automation immune to DOM obfuscation,
dynamic class names, and missing name/id attributes.
"""

import asyncio
import base64
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("SAI.BrowserVision")

# Viewport dimensions — must match the browser context configuration
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720


class BrowserVision:
    """
    Computer Vision pipeline for browser automation.

    Usage:
        vision = BrowserVision(browser, brain)
        result = await vision.analyze_and_act("Click the Sign Up button")
    """

    def __init__(self, browser, brain):
        self.browser = browser
        self.brain = brain

    async def analyze_and_act(self, task_context: str, extra_context: str = "") -> Dict[str, Any]:
        """
        Core pipeline: screenshot → LLM analysis → action with coordinates.

        Args:
            task_context: Description of what the LLM should do (e.g. "Click the Next button")
            extra_context: Additional context like page text, credentials, etc.

        Returns:
            Dict with action, coordinates, status, and message from the LLM.
        """
        screenshot_path = await self._capture_screenshot()
        if not screenshot_path:
            return {"status": "error", "message": "Failed to capture screenshot"}

        prompt = self._build_vision_prompt(task_context, extra_context)

        try:
            resp = self.brain.prompt(
                "Browser Vision — Coordinate-based interaction",
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
                        return {"status": "error", "message": "LLM response not parseable"}
                else:
                    return {"status": "error", "message": "Unexpected LLM response type"}

            return resp

        except Exception as e:
            logger.warning("BrowserVision analysis failed: %s", e)
            return {"status": "error", "message": str(e)}

    async def find_element_coordinates(self, description: str) -> Dict[str, Any]:
        """
        Asks the LLM to locate a specific UI element by its visual description.

        Args:
            description: Human-readable description like "the Month dropdown",
                         "the Sign Up button", "the password input field"

        Returns:
            {"found": True, "x": 640, "y": 300, "element_type": "button", "description": "..."}
        """
        screenshot_path = await self._capture_screenshot()
        if not screenshot_path:
            return {"found": False, "message": "Screenshot failed"}

        prompt = (
            f"You are S.A.I. looking at a browser screenshot (viewport: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}).\n\n"
            f"TASK: Find the UI element described as: \"{description}\"\n\n"
            "If you can see this element, return its CENTER coordinates (x, y) in pixels.\n"
            "The top-left corner of the viewport is (0, 0).\n\n"
            "Respond ONLY in JSON:\n"
            '{"found": true/false, "x": pixel_x, "y": pixel_y, '
            '"element_type": "button|input|select|link|text|checkbox", '
            '"description": "brief description of what you see at that location"}'
        )

        try:
            resp = self.brain.prompt(
                "Element location",
                prompt,
                image_path=screenshot_path,
            )
            if isinstance(resp, str):
                start = resp.find("{")
                end = resp.rfind("}") + 1
                resp = json.loads(resp[start:end])

            return resp
        except Exception as e:
            logger.warning("find_element_coordinates failed: %s", e)
            return {"found": False, "message": str(e)}

    async def get_page_understanding(self) -> Dict[str, Any]:
        """
        Full page analysis — identifies ALL visible interactive elements
        with their coordinates, types, and labels.

        Useful for debugging and understanding what the LLM sees on a page.
        """
        screenshot_path = await self._capture_screenshot()
        if not screenshot_path:
            return {"status": "error", "message": "Screenshot failed"}

        prompt = (
            f"You are S.A.I. looking at a browser screenshot (viewport: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}).\n\n"
            "TASK: List ALL visible interactive UI elements on this page.\n"
            "For each element, provide:\n"
            "  - type: button, input, select/dropdown, link, checkbox, radio\n"
            "  - label: the visible text or placeholder\n"
            "  - x, y: center coordinates in pixels\n"
            "  - state: empty, filled, disabled, active\n\n"
            "Respond ONLY in JSON:\n"
            '{"elements": [\n'
            '  {"type": "input", "label": "Email", "x": 640, "y": 200, "state": "empty"},\n'
            '  {"type": "button", "label": "Sign Up", "x": 640, "y": 450, "state": "active"}\n'
            '], "page_title": "what page this appears to be", '
            '"page_state": "brief description of current page state"}'
        )

        try:
            resp = self.brain.prompt(
                "Page understanding",
                prompt,
                image_path=screenshot_path,
            )
            if isinstance(resp, str):
                start = resp.find("{")
                end = resp.rfind("}") + 1
                resp = json.loads(resp[start:end])
            return resp
        except Exception as e:
            logger.warning("get_page_understanding failed: %s", e)
            return {"status": "error", "elements": [], "message": str(e)}

    # ══════════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════════

    async def _capture_screenshot(self, path: str = "logs/cv_browser_shot.png") -> Optional[str]:
        """Captures a screenshot from the browser page."""
        try:
            if not self.browser.page:
                return None
            await self.browser.page.screenshot(path=path, full_page=False)
            return path
        except Exception as e:
            logger.warning("Screenshot capture failed: %s", e)
            return None

    def _build_vision_prompt(self, task_context: str, extra_context: str = "") -> str:
        """
        Builds the LLM prompt that requests COORDINATE-BASED responses
        instead of CSS selectors.
        """
        prompt = (
            f"You are S.A.I., an autonomous AI looking at a browser screenshot.\n"
            f"The viewport is {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT} pixels.\n"
            f"The top-left corner is (0, 0). The bottom-right is ({VIEWPORT_WIDTH}, {VIEWPORT_HEIGHT}).\n\n"
            f"TASK: {task_context}\n"
        )

        if extra_context:
            prompt += f"\nADDITIONAL CONTEXT:\n{extra_context}\n"

        prompt += (
            "\nINSTRUCTIONS:\n"
            "- Look at the screenshot and identify the element you need to interact with.\n"
            "- Return the CENTER pixel coordinates (x, y) of that element.\n"
            "- Do NOT return CSS selectors — they are unreliable on modern websites.\n"
            "- Be precise with coordinates — estimate where the center of the element is.\n"
            "- For dropdown/select elements, use action 'select_dropdown'.\n\n"
            "Respond ONLY in JSON:\n"
            "{\n"
            '  "action": "click_at|type_at|select_dropdown|press|scroll|wait|otp|navigate",\n'
            '  "x": pixel_x_coordinate,\n'
            '  "y": pixel_y_coordinate,\n'
            '  "text": "text to type (for type_at action)",\n'
            '  "option_text": "option to select (for select_dropdown)",\n'
            '  "key": "key name (for press action)",\n'
            '  "url": "url (for navigate action)",\n'
            '  "seconds": 3,\n'
            '  "status": "ongoing|completed|failed",\n'
            '  "message": "brief description of what you see and what you are doing"\n'
            "}"
        )
        return prompt
