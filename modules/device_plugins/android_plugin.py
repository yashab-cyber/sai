from .base import BaseDevicePlugin

class AndroidDevicePlugin(BaseDevicePlugin):
    """
    S.A.I. Android Termux Node Plugin.
    """
    @property
    def device_type(self) -> str:
        return "android"

    def get_capabilities(self) -> list:
        return [
            "shell (Execute Termux bash commands natively)",
            "am_intent (Send Android intent directly to OS)"
        ]

    def validate_command(self, command: str, params: dict) -> tuple[bool, str]:
        valid_commands = ["shell", "am_intent"]
        
        if command not in valid_commands:
            return False, f"Invalid command '{command}' for Android node. Supported: {valid_commands}"
            
        if command == "shell" and not params.get("cmd"):
            return False, "Missing 'cmd' parameter for Android shell."
            
        if command == "am_intent" and not params.get("intent"):
            return False, "Missing 'intent' (e.g. android.intent.action.VIEW) for Android device."
            
        return True, ""
