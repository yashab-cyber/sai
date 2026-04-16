import cv2
import numpy as np
import pyautogui
import logging
import pytesseract
from PIL import Image
import base64
import io
from typing import Dict, Any, Optional

class VisionManager:
    """
    Module for screen analysis and vision capabilities.
    """

    
    def __init__(self, sai_instance=None):
        self.logger = logging.getLogger("SAI.Vision")
        self.sai = sai_instance


    
    def get_device_screen(self, device_id: str, as_cv2: bool = True):
        """
        Retrieves the most recent screenshot from a connected remote agent.
        Returns it as an OpenCV numpy array (BGR) or PIL Image.
        """
        if not self.sai or not hasattr(self.sai, 'device_manager'):
            return {"status": "error", "message": "Device Manager not linked to Vision module."}
            
        frames = self.sai.device_manager.latest_frames
        if device_id not in frames:
            return {"status": "error", "message": f"No recent frame available from {device_id}."}
            
        b64_data = frames[device_id]
        
        try:
            img_bytes = base64.b64decode(b64_data)
            pil_image = Image.open(io.BytesIO(img_bytes))
            
            if not as_cv2:
                return {"status": "success", "image": pil_image}
                
            # Convert PIL to OpenCV format (RGB -> BGR)
            open_cv_image = np.array(pil_image)
            open_cv_image = open_cv_image[:, :, ::-1].copy() 
            
            return {"status": "success", "image": open_cv_image, "shape": open_cv_image.shape}
            
        except Exception as e:
            self.logger.error(f"Failed to decode remote frame from {device_id}: {e}")
            return {"status": "error", "message": str(e)}

    def capture_screen(self, filename: str = "logs/screenshot.png"):
        """Captures entire screen to a file."""
        try:
            import os as _os
            path = filename
            # Remove existing file to prevent scrot 'already exists' warnings
            if _os.path.exists(path):
                _os.remove(path)
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
    def find_ui_template(self, device_id: str, template_path: str, threshold: float = 0.8) -> dict:
        """Finds a UI element template on the specified device's screen."""
        screen_res = self.get_device_screen(device_id, as_cv2=True)
        if screen_res["status"] == "error":
            return screen_res

        screen_img = screen_res["image"]
        template = cv2.imread(template_path)
        if template is None:
            return {"status": "error", "message": f"Could not load template {template_path}"}

        # Convert to grayscale for matching
        screen_gray = cv2.cvtColor(screen_img, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        res = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = template_gray.shape
            top_left = max_loc
            center_x = top_left[0] + w // 2
            center_y = top_left[1] + h // 2
            return {
                "status": "success",
                "found": True,
                "confidence": float(max_val),
                "center": {"x": center_x, "y": center_y},
                "bounds": {"x": top_left[0], "y": top_left[1], "w": w, "h": h}
            }
        return {"status": "success", "found": False, "confidence": float(max_val)}

    def find_text_on_screen(self, device_id: str, target_text: str, ignore_case: bool = True) -> dict:
        """Finds specific text on the device's screen using OCR and returns its coordinates."""
        screen_res = self.get_device_screen(device_id, as_cv2=True)
        if screen_res["status"] == "error":
            return screen_res

        screen_img = screen_res["image"]
        rgb_img = cv2.cvtColor(screen_img, cv2.COLOR_BGR2RGB)

        try:
            data = pytesseract.image_to_data(rgb_img, output_type=pytesseract.Output.DICT)
            target = target_text.lower() if ignore_case else target_text
            
            matches = []
            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                if not word:
                    continue
                
                check_word = word.lower() if ignore_case else word
                if target in check_word or check_word in target:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    matches.append({
                        "text": word,
                        "center": {"x": x + w//2, "y": y + h//2},
                        "bounds": {"x": x, "y": y, "w": w, "h": h}
                    })
            
            if matches:
                # Return the best match (first one for now)
                return {
                    "status": "success", 
                    "found": True, 
                    "matches": matches,
                    "center": matches[0]["center"]
                }

            return {"status": "success", "found": False}
        except Exception as e:
            self.logger.error(f"OCR Find Text error: {e}")
            return {"status": "error", "message": str(e)}

