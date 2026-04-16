import requests
import json
import logging
import os
import base64
import io
import time
from typing import Optional, Dict, Any
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured error codes returned by this module.  Every public method
# returns a dict with at least {"status": …} so callers never have to
# handle raw exceptions.
# ---------------------------------------------------------------------------
ERR_CONNECTION = "COMPANION_UNREACHABLE"
ERR_TIMEOUT = "COMPANION_TIMEOUT"
ERR_HTTP = "COMPANION_HTTP_ERROR"
ERR_SCREENSHOT_DENIED = "SCREENSHOT_PERMISSION_DENIED"
ERR_SCREENSHOT_EMPTY = "SCREENSHOT_EMPTY"


class AndroidCompanionClient:
    """
    Client to communicate with the SAI Android Companion App.
    Replaces Termux:API with a robust HTTP-based local server approach.

    Resilience guarantees:
    - Every public method returns a structured dict, never raises.
    - Transient failures are retried with exponential back-off.
    - A lightweight ``is_healthy()`` call is available for pre-flight checks.
    """

    # Retry configuration
    MAX_RETRIES = 2
    BASE_BACKOFF_SEC = 0.4          # 0.4s → 0.8s → 1.6s

    def __init__(self, host: str = None, port: int = 8080, token: Optional[str] = None):
        if host is None:
            env_host = os.getenv("SAI_ANDROID_HOST")
            if env_host:
                host = env_host
            else:
                # When connected to a phone hotspot, the phone is the default gateway.
                gateway = self._get_default_gateway()
                host = gateway if gateway else "127.0.0.1"

        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.token = token or os.getenv("SAI_ANDROID_TOKEN", "jarvis_network_key")

        # Cached health state for fast lookups between heartbeats
        self._last_health: Optional[Dict[str, Any]] = None
        self._last_health_ts: float = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_default_gateway(self) -> Optional[str]:
        """Attempts to find the default gateway on Linux systems (the hotspot host)."""
        try:
            import socket, struct
            with open("/proc/net/route") as fh:
                for line in fh:
                    fields = line.strip().split()
                    if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                        continue
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
        except Exception:
            pass
        return None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST with retry + exponential back-off.  Never raises."""
        return self._request_with_retry("POST", endpoint, json_data=data)

    def _get(self, endpoint: str) -> Dict[str, Any]:
        """GET with retry + exponential back-off.  Never raises."""
        return self._request_with_retry("GET", endpoint)

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Core HTTP dispatcher with structured error handling and retries."""
        url = f"{self.base_url}/{endpoint}"
        last_error = ""

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                if method == "POST":
                    resp = self.session.post(
                        url, json=json_data, headers=self._headers(), timeout=8.0
                    )
                else:
                    resp = self.session.get(
                        url, headers=self._headers(), timeout=8.0
                    )

                # ---- Handle non-2xx gracefully ----
                if resp.status_code >= 500:
                    # Server-side crash — decode body if possible, else synthetic
                    try:
                        body = resp.json()
                    except Exception:
                        body = {}
                    error_code = body.get("error", ERR_HTTP)
                    error_msg = body.get("message", f"HTTP {resp.status_code} from {endpoint}")
                    last_error = error_msg
                    logger.warning(
                        "Companion HTTP %s on %s (attempt %d/%d): %s",
                        resp.status_code, endpoint, attempt + 1,
                        self.MAX_RETRIES + 1, error_msg,
                    )
                    # Retry on 5xx
                    if attempt < self.MAX_RETRIES:
                        time.sleep(self.BASE_BACKOFF_SEC * (2 ** attempt))
                        continue
                    return {"status": "failed", "error": error_code, "message": error_msg}

                if resp.status_code >= 400:
                    try:
                        body = resp.json()
                    except Exception:
                        body = {"message": resp.text[:200]}
                    return {"status": "failed", "error": ERR_HTTP, "message": body.get("message", f"HTTP {resp.status_code}")}

                # ---- Success path ----
                return resp.json()

            except requests.exceptions.ConnectionError:
                last_error = f"Connection refused: {url}"
                logger.warning("Companion unreachable (attempt %d/%d): %s", attempt + 1, self.MAX_RETRIES + 1, url)
            except requests.exceptions.Timeout:
                last_error = f"Timeout reaching {url}"
                logger.warning("Companion timeout (attempt %d/%d): %s", attempt + 1, self.MAX_RETRIES + 1, url)
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.warning("Companion request error (attempt %d/%d): %s", attempt + 1, self.MAX_RETRIES + 1, e)

            if attempt < self.MAX_RETRIES:
                time.sleep(self.BASE_BACKOFF_SEC * (2 ** attempt))

        return {"status": "failed", "error": ERR_CONNECTION, "message": last_error}

    # ------------------------------------------------------------------
    # Health / connectivity
    # ------------------------------------------------------------------

    def is_healthy(self, cache_ttl: float = 5.0) -> bool:
        """
        Lightweight health check.  Tries ``/health`` first (new endpoint),
        falls back to a HEAD on the base URL.  Caches result for *cache_ttl*
        seconds to avoid spamming the device.
        """
        now = time.time()
        if self._last_health and (now - self._last_health_ts) < cache_ttl:
            return self._last_health.get("status") == "ok"

        try:
            resp = self.session.get(
                f"{self.base_url}/health",
                headers=self._headers(),
                timeout=3.0,
            )
            if resp.status_code == 200:
                self._last_health = resp.json()
                self._last_health_ts = now
                return self._last_health.get("status") == "ok"
        except Exception:
            pass

        # Fallback: try a lightweight GET to any known endpoint
        try:
            resp = self.session.get(
                f"{self.base_url}/state/screen_text",
                headers=self._headers(),
                timeout=3.0,
            )
            healthy = resp.status_code < 500
            self._last_health = {"status": "ok" if healthy else "degraded"}
            self._last_health_ts = now
            return healthy
        except Exception:
            self._last_health = {"status": "unreachable"}
            self._last_health_ts = now
            return False

    def get_health_details(self) -> Dict[str, Any]:
        """Returns cached health info dict, or probes if stale."""
        self.is_healthy(cache_ttl=5.0)
        return dict(self._last_health or {"status": "unknown"})

    # ------------------------------------------------------------------
    # Core Actions
    # ------------------------------------------------------------------

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

    def get_screenshot_base64(self) -> str:
        """
        Captures a screenshot from Android accessibility screenshot pipeline.
        Returns base64 string on success, empty string on failure.
        Never raises.
        """
        res = self._get("state/screenshot")
        if res.get("status") == "failed":
            error = res.get("error", "UNKNOWN")
            logger.warning("Screenshot capture failed: %s — %s", error, res.get("message", ""))
            return ""
        return res.get("image_base64", "")

    def get_screenshot_image(self) -> Optional[Image.Image]:
        """Returns screenshot as a PIL image when available."""
        b64_img = self.get_screenshot_base64()
        if not b64_img:
            return None
        try:
            raw = base64.b64decode(b64_img)
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            logger.error(f"Failed decoding screenshot payload: {exc}")
            return None

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

    def get_screenshot_base64(self):
        return self.client.get_screenshot_base64()

    def get_screenshot_image(self):
        return self.client.get_screenshot_image()

    def send_message(self, app: str, contact: str, message: str):
        return self.client.send_message(app, contact, message)

    def is_healthy(self) -> bool:
        return self.client.is_healthy()
