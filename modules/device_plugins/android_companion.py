import requests
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class AndroidCompanionClient:
    """
    Client to communicate with the SAI Android Companion App.
    Replaces Termux:API with a robust HTTP-based local server approach.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = self.session.post(f"{self.base_url}/{endpoint}", json=data, timeout=5.0)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with Android Companion App: {e}")
            return {"status": "error", "message": str(e)}

    def _get(self, endpoint: str) -> Dict[str, Any]:
        try:
            response = self.session.get(f"{self.base_url}/{endpoint}", timeout=5.0)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with Android Companion App: {e}")
            return {"status": "error", "message": str(e)}

    # --- Core Actions ---

    def open_app(self, package_name: str) -> bool:
        """Opens an app via Intent, Shizuku, or ADB (decided by the Android router)"""
        res = self._post("action/open_app", {"package": package_name})
        return res.get("status") == "success"

    def tap(self, x: int, y: int) -> bool:
        """Taps the screen using Accessibility Service or Shizuku"""
        res = self._post("action/tap", {"x": x, "y": y})
        return res.get("status") == "success"

    def type_text(self, text: str) -> bool:
        """Types text into the currently focused input field"""
        res = self._post("action/type", {"text": text})
        return res.get("status") == "success"

    def get_screen_text(self) -> str:
        """Extracts text currently visible on screen via Accessibility Tree"""
        res = self._get("state/screen_text")
        return res.get("data", "")

    def send_message(self, app: str, contact: str, message: str) -> bool:
        """High-level automation macro to send a message"""
        res = self._post("macro/send_message", {
            "app": app,
            "contact": contact,
            "message": message
        })
        return res.get("status") == "success"

class DeviceControl:
    """
    Abstract interface for device control. 
    Routes commands to the AndroidCompanionClient under the hood.
    """
    def __init__(self):
        self.client = AndroidCompanionClient()
        
    def open_app(self, app_name: str):
        return self.client.open_app(app_name)

    def tap(self, x: int, y: int):
        return self.client.tap(x, y)

    def type(self, text: str):
        return self.client.type_text(text)

    def get_screen_text(self):
        return self.client.get_screen_text()

    def send_message(self, app: str, contact: str, message: str):
        return self.client.send_message(app, contact, message)
