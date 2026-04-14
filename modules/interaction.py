import time
import logging
from typing import Optional, Dict

class InteractionEngine:
    """
    Step 3 & 4: Dynamic Interaction and Feedback Loop Engine.
    Converts detected UI elements coordinates into actual clicks and keystrokes 
    on the remote devices via the DeviceManager payload router.
    """
    def __init__(self, sai_instance):
        self.logger = logging.getLogger("SAI.Interaction")
        self.sai = sai_instance

    def tap_or_click(self, device_id: str, x: int, y: int) -> dict:
        """Sends a click/tap command to the remote device at (x, y)"""
        device_info = self.sai.device_manager.devices.get(device_id)
        if not device_info:
            return {"status": "error", "message": "Device not found."}

        dtype = device_info.get("type", "unknown")
        
        if dtype == "windows":
            return self.sai.device_manager.queue_command(
                device_id, "mouse_click", {"button": "left", "x": x, "y": y}
            )
        elif dtype == "android":
            # For Termux we can use 'shell' with input tap if device has root/adb access
            cmd = f"su -c input tap {x} {y}"
            # Fallback to non-su if needed, but input tap usually requires su or ADB shell
            return self.sai.device_manager.queue_command(
                device_id, "shell", {"cmd": cmd}
            )
        else:
            return {"status": "error", "message": f"Unsupported device type: {dtype}"}

    def type_text(self, device_id: str, text: str) -> dict:
        """Sends a type command to the remote device"""
        device_info = self.sai.device_manager.devices.get(device_id)
        if not device_info:
            return {"status": "error", "message": "Device not found."}

        dtype = device_info.get("type", "unknown")
        
        if dtype == "windows":
            return self.sai.device_manager.queue_command(
                device_id, "type_text", {"text": text}
            )
        elif dtype == "android":
            # Android input text needs escaping spaces
            # safe_text = text.replace(" ", "%s")
            cmd = f'su -c input text "{text}"'
            return self.sai.device_manager.queue_command(
                device_id, "shell", {"cmd": cmd}
            )
        else:
            return {"status": "error", "message": f"Unsupported device type: {dtype}"}

    def click_ui_template(self, device_id: str, template_path: str, threshold: float = 0.8) -> dict:
        """Step 3/4: Vision-to-Action. Detects a template and clicks it."""
        res = self.sai.vision.find_ui_template(device_id, template_path, threshold)
        if res.get("status") == "success" and res.get("found"):
            x, y = res["center"]["x"], res["center"]["y"]
            self.logger.info(f"Interaction Engine: Found template {template_path} at ({x}, {y})")
            return self.tap_or_click(device_id, int(x), int(y))
        return {"status": "error", "message": "Template not found on screen.", "vision_result": res}

    def click_text(self, device_id: str, target_text: str, ignore_case: bool = True) -> dict:
        """Step 3/4: Vision-to-Action. Detects text via OCR and clicks it."""
        res = self.sai.vision.find_text_on_screen(device_id, target_text, ignore_case)
        if res.get("status") == "success" and res.get("found"):
            x, y = res["center"]["x"], res["center"]["y"]
            self.logger.info(f"Interaction Engine: Found text '{target_text}' at ({x}, {y})")
            return self.tap_or_click(device_id, int(x), int(y))
        return {"status": "error", "message": f"Text '{target_text}' not found.", "vision_result": res}


    def execute_with_verification(self, device_id: str, action_func, verify_func, max_retries: int = 3, delay: float = 3.0) -> dict:
        """
        Step 4/6: Feedback Loop Structure.
        Executes a vision action and verifies if the expected screen state appears.
        """
        for attempt in range(max_retries):
            # 1. Execute action (e.g. click Contact)
            action_res = action_func()
            if action_res.get("status") == "error":
                self.logger.warning(f"Interaction attempt {attempt+1} action failed: {action_res}")
            
            # Allow time for screen/app to load
            time.sleep(delay)
            
            # 2. Capture and Verify (e.g. check if Chat text is now visible)
            if verify_func():
                return {"status": "success", "message": f"Action succeeded and verified on attempt {attempt+1}"}
                
            self.logger.info(f"Verification failed on attempt {attempt+1}. Retrying...")
            
        return {"status": "error", "message": "Failed to verify action completion after max retries."}


    def execute_with_verification(self, device_id: str, action_func, verify_func, max_retries: int = 3, delay: float = 3.0) -> dict:
        """
        Step 4/6: Feedback Loop Structure.
        Executes a vision action and verifies if the expected screen state appears.
        """
        for attempt in range(max_retries):
            # 1. Execute action (e.g. click Contact)
            action_res = action_func()
            if action_res.get("status") == "error":
                self.logger.warning(f"Interaction attempt {attempt+1} action failed: {action_res}")
            
            # Allow time for screen/app to load
            time.sleep(delay)
            
            # 2. Capture and Verify (e.g. check if Chat text is now visible)
            if verify_func():
                return {"status": "success", "message": f"Action succeeded and verified on attempt {attempt+1}"}
                
            self.logger.info(f"Verification failed on attempt {attempt+1}. Retrying...")
            
        return {"status": "error", "message": "Failed to verify action completion after max retries."}

