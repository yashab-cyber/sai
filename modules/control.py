import logging
import subprocess
from typing import Dict, Any, Optional


class WindowManager:
    """Manages desktop window operations via wmctrl/xdotool."""

    def __init__(self):
        self.logger = logging.getLogger("SAI.Control.Windows")

    def list_windows(self) -> Dict[str, Any]:
        """Lists all open windows."""
        try:
            result = subprocess.run(
                ["wmctrl", "-l"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return {"status": "error", "message": result.stderr}
            windows = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split(None, 3)
                    windows.append({
                        "id": parts[0] if len(parts) > 0 else "",
                        "desktop": parts[1] if len(parts) > 1 else "",
                        "host": parts[2] if len(parts) > 2 else "",
                        "title": parts[3] if len(parts) > 3 else "",
                    })
            return {"status": "success", "windows": windows}
        except FileNotFoundError:
            return {"status": "error", "message": "wmctrl not installed. Install with: sudo apt install wmctrl"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def focus_window(self, title: str) -> Dict[str, Any]:
        """Focuses a window by title fragment."""
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return {"status": "success", "message": f"Focused window matching '{title}'."}
            return {"status": "error", "message": f"No window matching '{title}' found."}
        except FileNotFoundError:
            return {"status": "error", "message": "wmctrl not installed."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_active_window(self) -> Dict[str, Any]:
        """Returns the currently active window title."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return {"status": "success", "title": result.stdout.strip()}
            return {"status": "error", "message": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "message": "xdotool not installed. Install with: sudo apt install xdotool"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def set_layout(self, mode: str) -> Dict[str, Any]:
        """Arranges windows in a preset layout (e.g. 'split')."""
        if mode == "split":
            # Simple side-by-side split using wmctrl
            try:
                result = subprocess.run(
                    ["wmctrl", "-l"], capture_output=True, text=True, timeout=5
                )
                windows = [line.split()[0] for line in result.stdout.strip().split("\n") if line.strip()]
                if len(windows) >= 2:
                    # Get screen size via xdotool
                    size_res = subprocess.run(
                        ["xdotool", "getdisplaygeometry"],
                        capture_output=True, text=True, timeout=5
                    )
                    w, h = 1920, 1080
                    if size_res.returncode == 0:
                        parts = size_res.stdout.strip().split()
                        w, h = int(parts[0]), int(parts[1])

                    half_w = w // 2
                    subprocess.run(["wmctrl", "-i", "-r", windows[0], "-e", f"0,0,0,{half_w},{h}"], timeout=5)
                    subprocess.run(["wmctrl", "-i", "-r", windows[1], "-e", f"0,{half_w},0,{half_w},{h}"], timeout=5)
                    return {"status": "success", "message": "Windows arranged in split layout."}
                return {"status": "error", "message": "Need at least 2 windows for split layout."}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": f"Unknown layout mode: {mode}"}


class ControlManager:
    """Desktop control (mouse, keyboard, windows) for SAI.
    
    Wraps pyautogui for mouse/keyboard and wmctrl/xdotool for window management.
    """

    def __init__(self, executor):
        self.executor = executor
        self.logger = logging.getLogger("SAI.Control")
        self.windows = WindowManager()
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            self.pyautogui = pyautogui
        except Exception:
            self.pyautogui = None

    def mouse_move(self, x: int, y: int) -> Dict[str, Any]:
        """Moves the mouse to (x, y)."""
        if not self.pyautogui:
            return {"status": "error", "message": "pyautogui not available."}
        try:
            self.pyautogui.moveTo(x, y)
            return {"status": "success", "message": f"Mouse moved to ({x}, {y})."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def mouse_click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> Dict[str, Any]:
        """Clicks at (x, y) with the specified button."""
        if not self.pyautogui:
            return {"status": "error", "message": "pyautogui not available."}
        try:
            if x is not None and y is not None:
                self.pyautogui.click(x=x, y=y, button=button)
            else:
                self.pyautogui.click(button=button)
            return {"status": "success", "message": f"Mouse clicked at ({x}, {y}) with {button} button."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def keyboard_type(self, content: str) -> Dict[str, Any]:
        """Types text using the keyboard."""
        if not self.pyautogui:
            return {"status": "error", "message": "pyautogui not available."}
        try:
            self.pyautogui.typewrite(content, interval=0.02)
            return {"status": "success", "message": f"Typed text: '{content[:30]}...'"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def keyboard_press(self, content: str) -> Dict[str, Any]:
        """Presses a key or key combination (e.g. 'enter', 'ctrl+c')."""
        if not self.pyautogui:
            return {"status": "error", "message": "pyautogui not available."}
        try:
            # Handle key combinations like 'ctrl+c'
            if "+" in content:
                keys = [k.strip() for k in content.split("+")]
                self.pyautogui.hotkey(*keys)
            else:
                self.pyautogui.press(content)
            return {"status": "success", "message": f"Key pressed: '{content}'."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def execute_command(self, command):
        """Legacy stub for backward compatibility."""
        if not self.pyautogui:
            return {"status": "ignored"}
        return {"status": "success"}
