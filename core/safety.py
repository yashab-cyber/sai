import os
import logging
from typing import List, Optional

class SafetyManager:
    """
    Enforces strict safeguards for the SAI system.
    Prevents unauthorized file access and execution of dangerous commands.
    """
    
    # Paths that are absolutely off-limits for modification by the AI
    IMMUTABLE_PATHS = ["/core/"]
    
    # Directories where the AI is allowed to operate
    ALLOWED_WORKSPACES = ["/workspace/", "/modules/", "/tests/", "/logs/", "/web/", "/core/"]
    
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
    
    # Whitelist of allowed shell commands strictly for host UI or generic operations
    ALLOWED_COMMANDS = [
        "ls", "cat", "echo", "pwd", "date", "grep", "find", "git",
        "mkdir", "rm", "cp", "mv", "touch", "chmod", "curl", "wget",
        "mousepad", "firefox", "chromium", "gnome-terminal", "code",
        "wmctrl", "xdotool", "free", "df", "uptime", "scrot", "sensors",
        "pip", "pip3", "python3", "npm", "node",
        "flake8", "black", "pytest",
    ]

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
        
        # Check if it starts with base_dir
        if not abs_path.startswith(self.base_dir):
            raise PermissionError(f"Access denied: Path {path} is outside the SAI root.")

        # Check for immutable core protection (only for writes, unless authorized)
        rel_path = os.path.relpath(abs_path, self.base_dir)
        is_core = any(rel_path.startswith(p.strip("/")) for p in self.IMMUTABLE_PATHS)
        
        if is_write and is_core and not allow_core:
            raise PermissionError(
                f"Access denied: Modification of {rel_path} is forbidden. "
                "This is a core system file. To modify core logic, use authorized_evolution."
            )

        # Check if it's in an allowed area
        allowed = any(rel_path.startswith(p.strip("/")) for p in self.ALLOWED_WORKSPACES)
        if not allowed:
             # Basic files at root like requirements.txt or config.yaml are allowed
             if os.path.dirname(rel_path) == "":
                 return abs_path
             raise PermissionError(f"Access denied: {rel_path} is not in a permitted directory.")

        return abs_path

    def is_command_safe(self, command: str) -> bool:
        """
        Checks if a shell command is in the whitelist.
        """
        base_cmd = command.split()[0] if command else ""
        if base_cmd in self.ALLOWED_COMMANDS:
            self.logger.debug(f"Command validated: {command}")
            return True
        
        self.logger.warning(f"BLOCKED dangerous command: {command}")
        return False

    def validate_package(self, package_name: str) -> bool:
        """
        Checks if a package is whitelisted.
        """
        if package_name in self.ALLOWED_PACKAGES:
            return True
        self.logger.warning(f"BLOCKED unauthorized package: {package_name}")
        return False

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

