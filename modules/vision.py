import cv2
import numpy as np
import pyautogui
import logging
import pytesseract
from PIL import Image
from typing import Dict, Any, Optional

class VisionManager:
    """
    Module for screen analysis and vision capabilities.
    """

    def __init__(self):
        self.logger = logging.getLogger("SAI.Vision")

    def capture_screen(self, filename: str = "logs/screenshot.png"):
        """Captures entire screen to a file."""
        try:
            path = filename
            pyautogui.screenshot(path)
            self.logger.info(f"Screen captured to {path}")
            return {"status": "success", "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def find_image(self, template_path: str, confidence: float = 0.8):
        """Finds an image template on the current screen."""
        try:
            location = pyautogui.locateOnScreen(template_path, confidence=confidence)
            if location:
                return {
                    "status": "success",
                    "found": True,
                    "location": {
                        "x": location.left,
                        "y": location.top,
                        "w": location.width,
                        "h": location.height
                    },
                    "center": {
                        "x": location.left + location.width // 2,
                        "y": location.top + location.height // 2
                    }
                }
            return {"status": "success", "found": False}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_screen_size(self):
        """Returns the resolution of the primary monitor."""
        size = pyautogui.size()
        return {"width": size.width, "height": size.height}

    def ocr_image(self, image_path: str):
        """
        Extracts text from an image file using OCR (Tesseract).

        :param image_path: Path to the image file.
        :return: Dictionary containing the OCR result or error.
        """
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='eng')
            return {"status": "success", "text": text}
        except Exception as e:
            self.logger.error(f"OCR error: {e}")
            return {"status": "error", "message": str(e)}