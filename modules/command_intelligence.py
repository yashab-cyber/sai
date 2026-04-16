import re
from typing import Dict, List, Any


class CommandIntelligence:
    """Intent and task decomposition layer for SAI command routing."""

    def classify_intent(self, user_input: str) -> Dict[str, Any]:
        text = (user_input or "").strip().lower()

        if any(k in text for k in ["whatsapp", "message", "sms", "send"]):
            return {"intent": "messaging", "confidence": 0.85}
        if any(k in text for k in ["open", "launch", "start app"]):
            return {"intent": "app_control", "confidence": 0.75}
        if any(k in text for k in ["read screen", "what is on screen", "screen text"]):
            return {"intent": "screen_understanding", "confidence": 0.8}
        if any(k in text for k in ["tap", "click", "type"]):
            return {"intent": "ui_interaction", "confidence": 0.7}

        return {"intent": "general", "confidence": 0.5}

    def decompose_task(self, user_input: str) -> List[Dict[str, Any]]:
        text = (user_input or "").strip().lower()
        intent = self.classify_intent(text)["intent"]

        if intent == "messaging":
            return [
                {"action": "open_app", "target": "com.whatsapp"},
                {"action": "get_screen_text"},
                {"action": "type", "text": self._extract_message(text) or "Hello"},
            ]
        if intent == "app_control":
            package = self._extract_package(text)
            return [{"action": "open_app", "target": package or "com.android.settings"}]
        if intent == "screen_understanding":
            return [{"action": "get_screen_text"}]
        if intent == "ui_interaction":
            steps = []
            if "tap" in text or "click" in text:
                steps.append({"action": "tap", "x": 500, "y": 500})
            if "type" in text:
                steps.append({"action": "type", "text": self._extract_message(text) or ""})
            return steps or [{"action": "get_screen_text"}]

        return [{"action": "get_screen_text"}]

    def build_execution_plan(self, user_input: str, vision_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        intent_meta = self.classify_intent(user_input)
        steps = self.decompose_task(user_input)

        # Optional vision-aware enrichment of plan
        if vision_data and isinstance(vision_data, dict):
            ui_elements = vision_data.get("ui_elements", []) or []
            steps = self._apply_vision_guidance(user_input, steps, ui_elements)

        return {
            "intent": intent_meta["intent"],
            "confidence": intent_meta["confidence"],
            "steps": steps,
        }

    def _apply_vision_guidance(self, user_input: str, steps: List[Dict[str, Any]], ui_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adjusts generic steps into coordinate-specific actions when vision context is available."""
        text = (user_input or "").lower()
        enriched: List[Dict[str, Any]] = []

        for step in steps:
            action = step.get("action")
            if action in ("tap", "find_contact"):
                target = step.get("target") or step.get("name") or ""
                match = self._best_element_match(target or ("send" if "send" in text else ""), ui_elements)
                if match and match.get("center"):
                    cx, cy = match["center"]
                    enriched.append({"action": "tap", "x": int(cx), "y": int(cy), "target": match.get("text", "")})
                    continue

            if action == "type":
                # Keep as-is; type step can run after focus tap from above.
                enriched.append(step)
                continue

            if action == "open_app":
                enriched.append(step)
                continue

            enriched.append(step)

        return enriched

    def _best_element_match(self, query: str, ui_elements: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        if not query:
            return None
        best = None
        best_score = 0.0
        q = query.lower().strip()

        for element in ui_elements:
            et = str(element.get("text", "")).lower().strip()
            if not et:
                continue
            score = 1.0 if q in et else 0.0
            if score > best_score:
                best = element
                best_score = score

        return best

    def _extract_message(self, text: str) -> str:
        match = re.search(r"(?:message|say|send)\s+(.+)$", text)
        if match:
            return match.group(1).strip(" \"'")
        return ""

    def _extract_package(self, text: str) -> str:
        # Extend mapping as needed.
        package_map = {
            "whatsapp": "com.whatsapp",
            "settings": "com.android.settings",
            "youtube": "com.google.android.youtube",
            "chrome": "com.android.chrome",
        }
        for key, pkg in package_map.items():
            if key in text:
                return pkg
        return ""
