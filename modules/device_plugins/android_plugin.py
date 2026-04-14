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
            "open_app (Launch apps by package name)",
            "am_intent (Send Android intents)",
            "battery (Get battery status)",
            "send_sms (Send SMS messages)",
            "tts (Text-to-speech output)"
        ]

    def validate_command(self, command: str, params: dict) -> tuple[bool, str]:
        valid_commands = ["shell", "am_intent", "open_app", "battery", "send_sms", "tts"]
        
        if command not in valid_commands:
            return False, f"Invalid command '{command}' for Android node. Supported: {valid_commands}"
            
        if command == "shell" and not (params.get("cmd") or params.get("command")):
            return False, "Missing 'cmd' parameter for Android shell."
            
        if command == "am_intent" and not params.get("intent"):
            return False, "Missing 'intent' (e.g. android.intent.action.VIEW) for Android device."
            
        if command == "open_app" and not params.get("package"):
            return False, "Missing 'package' (e.g. com.whatsapp) for open_app."
            
        if command == "send_sms" and not (params.get("number") and params.get("text")):
            return False, "Missing 'number' or 'text' for send_sms."
            
        return True, ""
