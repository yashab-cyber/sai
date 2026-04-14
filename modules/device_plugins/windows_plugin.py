from .base import BaseDevicePlugin

class WindowsDevicePlugin(BaseDevicePlugin):
    """
    S.A.I. Windows Desktop Node Plugin.
    """
    @property
    def device_type(self) -> str:
        return "windows"

    def get_capabilities(self) -> list:
        return [
            "shell (Execute unprivileged Windows CMD/PowerShell)",
            "open_app (Start desktop apps)",
            "mouse_move (params: {x, y})",
            "mouse_click (params: {button='left'})",
            "type_text (params: {text})",
            "press_key (params: {key})"
        ]

    def validate_command(self, command: str, params: dict) -> tuple[bool, str]:
        valid_commands = ["shell", "open_app", "mouse_move", "mouse_click", "type_text", "press_key"]
        
        if command not in valid_commands:
            return False, f"Invalid command '{command}' for Windows node."
            
        if command == "shell" and not params.get("cmd"):
            return False, "Missing 'cmd' parameter for shell."
        
        if command == "open_app" and not params.get("app_name"):
            return False, "Missing 'app_name' parameter for open_app."
            
        return True, ""
