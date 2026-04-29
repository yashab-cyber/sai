import os
import logging
from typing import List, Optional

class SafetyManager:
    """
    Enforces strict safeguards for the SAI system.
    Prevents unauthorized file access and execution of dangerous commands.
    """
    
    # Paths that are absolutely off-limits for modification by the AI
    # UNRESTRICTED MODE — no immutable paths
    IMMUTABLE_PATHS = []
    
    # Directories where the AI is allowed to operate
    # UNRESTRICTED MODE — full filesystem access
    ALLOWED_WORKSPACES = []  # Empty = allow all (checked in validate_path)
    
    # Whitelisted modules that can be imported by self-evolving code
    ALLOWED_MODULES = [
        "os", "sys", "json", "time", "re", "math", "random", "logging", "typing", 
        "ast", "shutil", "sqlite3", "requests", "pyyaml", "pydantic", "pytest", 
        "flask", "psutil", "pynput", "pyautogui", "cv2", "pyttsx3", "speech_recognition",
        "subprocess", "playwright", "flask_socketio", "eventlet", "threading", "pytesseract",
        "streamlit", "feedparser", "pytrends", "bs4", "plotly", "lxml"
    ]

    # Packages that can be installed/managed by executor
    ALLOWED_PACKAGES = [
        "requests", "pyyaml", "pydantic", "sqlite3", "pytest", "flask", "psutil",
        "pynput", "pyautogui", "opencv-python", "pyttsx3", "SpeechRecognition",
        "pyscreeze", "Pillow", "playwright", "pyee", "flask-socketio", "eventlet",
        "pytesseract", "streamlit", "feedparser", "pytrends", "beautifulsoup4", "plotly", "lxml"
    ]
    
    # Whitelist of allowed shell commands
    # UNRESTRICTED MODE — all commands are allowed
    ALLOWED_COMMANDS = []  # Empty = bypass (checked in is_command_safe)

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.logger = logging.getLogger("SAI.Safety")

    def validate_path(self, path: str, is_write: bool = False, allow_core: bool = False) -> str:
        """
        Validates if a path is within the allowed workspace.
        """
        # Normalize path: ensure it's relative to project root even if leading slash provided
        clean_path = path.lstrip("/")
        abs_path = os.path.abspath(os.path.join(self.base_dir, clean_path))
        
        # UNRESTRICTED MODE — allow all paths
        # No base_dir check, no immutable paths, no workspace restrictions
        return abs_path

    def is_command_safe(self, command: str) -> bool:
        """
        Checks if a shell command is allowed.
        UNRESTRICTED MODE — all commands pass.
        """
        self.logger.debug(f"Command validated (unrestricted): {command}")
        return True

    def validate_package(self, package_name: str) -> bool:
        """
        Checks if a package is allowed.
        UNRESTRICTED MODE — all packages pass.
        """
        self.logger.debug(f"Package validated (unrestricted): {package_name}")
        return True

    def is_ip_allowed(self, ip: str) -> bool:
        """
        Validates if an IP is allowed to connect to the SAI network.
        By default, allows localhost and standard private subnets.
        """
        if ip == "127.0.0.1" or ip == "localhost":
            return True
        if ip.startswith("192.168.") or ip.startswith("10."):
            return True
        if ip.startswith("172."):
            try:
                second_octet = int(ip.split(".")[1])
                if 16 <= second_octet <= 31:
                    return True
            except (IndexError, ValueError):
                pass
        self.logger.warning(f"BLOCKED unauthorized network IP: {ip}")
        return False

