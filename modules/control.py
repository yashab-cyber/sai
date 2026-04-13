import pyautogui
import pynput
import logging
import time
from typing import Dict, Any

class ControlManager:
    """
    Module for controlling keyboard and mouse input.
    """
    
    def __init__(self, executor):
        self.executor = executor
        self.logger = logging.getLogger("SAI.Control")
        # Enable failsafe: move mouse to upper-left corner to abort
        pyautogui.FAILSAFE = True
        self.mouse = pynput.mouse.Controller()
        self.keyboard = pynput.keyboard.Controller()
        self.windows = WindowManager(executor)

    def mouse_move(self, x: int, y: int, duration: float = 0.25):
        """Moves mouse to absolute coordinates."""
        try:
            self.logger.info(f"Moving mouse to ({x}, {y})")
            pyautogui.moveTo(x, y, duration=duration)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def mouse_click(self, x: int = None, y: int = None, button: str = 'left'):
        """Clicks at current or specified coordinate."""
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
            else:
                pyautogui.click(button=button)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def keyboard_type(self, text: str):
        """Types string at current focus with a safety delay."""
        try:
            self.logger.info(f"Typing text: {text[:20]}...")
            # Brief pause to ensure focus has settled
            time.sleep(0.5)
            pyautogui.write(text, interval=0.05)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def keyboard_press(self, key: str):
        """Presses a specific key (e.g. 'enter', 'esc', 'ctrl')."""
        try:
            time.sleep(0.1)
            pyautogui.press(key)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

class WindowManager:
    """Handles Linux window operations using wmctrl and xdotool."""
    
    def __init__(self, executor):
        self.executor = executor

    def list_windows(self):
        """Returns a list of all visible windows."""
        res = self.executor.execute_shell("wmctrl -l")
        if res["status"] == "success":
            lines = res["stdout"].strip().split("\n")
            windows = []
            for line in lines:
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append({"id": parts[0], "desktop": parts[1], "title": parts[3]})
            return {"status": "success", "windows": windows}
        return res

    def focus_window(self, title: str):
        """Focuses a window by its title fragment."""
        # Use wmctrl to activate the window
        res = self.executor.execute_shell(f"wmctrl -a '{title}'")
        # OS switch delay
        time.sleep(0.5)
        return res

    def get_active_window(self):
        """Returns the title of the currently focused window."""
        res = self.executor.execute_shell("xdotool getactivewindow getwindowname")
        if res["status"] == "success":
            return {"status": "success", "title": res["stdout"].strip()}
        return res

    def move_window(self, title: str, x: int, y: int):
        """Moves a window to absolute coordinates using xdotool."""
        return self.executor.execute_shell(f"xdotool search --name '{title}' windowmove {x} {y}")

    def resize_window(self, title: str, width: int, height: int):
        """Resizes a window to absolute dimensions using xdotool."""
        return self.executor.execute_shell(f"xdotool search --name '{title}' windowsize {width} {height}")

    def minimize_all(self):
        """Clears the desktop by minimizing all active windows."""
        return self.executor.execute_shell("xdotool key alt+d")

    def set_layout(self, mode: str):
        """Presets for common window layouts (e.g., 'split')."""
        if mode == "split":
            # Example: Browser Left, Editor Right
            self.resize_window("Chromium", 640, 720)
            self.move_window("Chromium", 0, 0)
            self.resize_window("Mousepad", 640, 720)
            self.move_window("Mousepad", 640, 0)
            return {"status": "success", "layout": "split"}
        return {"status": "error", "message": "Unknown layout mode."}
