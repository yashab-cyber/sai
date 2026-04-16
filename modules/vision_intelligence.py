import base64
import io
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image


class VisionIntelligence:
    """Phase-2 screen understanding: OCR + UI element extraction + fuzzy matching."""

    def __init__(self):
        self.logger = logging.getLogger("SAI.VisionIntelligence")

    def parse_screenshot_base64(self, image_b64: str) -> Dict[str, Any]:
        if not image_b64:
            return {"status": "failed", "message": "Empty image payload", "ui_elements": []}

        try:
            raw = base64.b64decode(image_b64)
            pil = Image.open(io.BytesIO(raw)).convert("RGB")
            return self.parse_pil_image(pil)
        except Exception as exc:
            self.logger.error("Vision parse failed: %s", exc)
            return {"status": "failed", "message": str(exc), "ui_elements": []}

    def parse_pil_image(self, image: Image.Image) -> Dict[str, Any]:
        np_img = np.array(image)
        gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)

        # Improve OCR legibility on mixed mobile UIs
        proc = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

        data = pytesseract.image_to_data(proc, output_type=pytesseract.Output.DICT)
        elements: List[Dict[str, Any]] = []

        for i in range(len(data.get("text", []))):
            txt = (data["text"][i] or "").strip()
            conf = float(data.get("conf", ["-1"])[i])
            if not txt or conf < 35:
                continue

            x, y, w, h = (
                int(data["left"][i]),
                int(data["top"][i]),
                int(data["width"][i]),
                int(data["height"][i]),
            )

            el_type = "text"
            lower = txt.lower()
            if any(k in lower for k in ["send", "ok", "next", "done", "open"]):
                el_type = "button"
            if any(k in lower for k in ["type", "message", "search", "enter"]):
                el_type = "input"

            elements.append(
                {
                    "text": txt,
                    "bounds": [x, y, x + w, y + h],
                    "type": el_type,
                    "confidence": conf,
                    "center": [x + (w // 2), y + (h // 2)],
                }
            )

        full_text = " ".join([e["text"] for e in elements])

        return {
            "status": "success",
            "message": "screen parsed",
            "ui_elements": elements,
            "text": full_text,
            "count": len(elements),
        }

    def find_best_match(self, query: str, ui_elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        best = None
        best_score = 0.0
        q = query.lower().strip()

        for el in ui_elements:
            text = str(el.get("text", "")).lower().strip()
            if not text:
                continue
            score = SequenceMatcher(None, q, text).ratio()
            if q in text:
                score = max(score, 0.95)
            if score > best_score:
                best = el
                best_score = score

        if best_score < 0.45:
            return None
        result = dict(best)
        result["match_score"] = best_score
        return result
