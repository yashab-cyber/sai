import logging

class CommandRouter:
    """
    Step 1/3: Command Routing System.
    Bridges high-level LLM task planning into concrete multi-device execution logic.
    Decides the optimal path: Direct Command > Vision Automation > Safe Fallback.
    """
    def __init__(self, sai_instance):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.Router")

    def route_task(self, intent: dict) -> dict:
        """
        Takes a structured intent from the planner.
        Example intent: {"action": "send_message", "app": "whatsapp", "target": "Dad", "message": "Hi"}
        """
        # 1. Device Discovery & Selection
        device_id, device_type, error = self._select_best_device(intent.get("app"))
        if error:
            return {"status": "error", "message": error}

        # 2. Update S.A.I.'s Focus State
        self.sai.state_manager.set_focus(device_id, intent.get("app"))

        # 3. Strategy Compilation (Direct Command vs Vision Hybrid)
        execution_mode, steps = self._build_execution_strategy(device_id, device_type, intent)

        route_plan = {
            "device_id": device_id,
            "device_type": device_type,
            "execution_mode": execution_mode,
            "steps": steps
        }
        
        self.logger.info(f"Routed Task Plan: {route_plan}")
        return {"status": "success", "plan": route_plan}

    def _select_best_device(self, required_app: str) -> tuple[str, str, str]:
        """Finds the right device based on app/capability requirements."""
        connected_devices = self.sai.device_manager.devices
        if not connected_devices:
            return None, None, "No devices connected to S.A.I. Hub."

        # Simplistic selection heuristic: if it's WhatsApp, prefer mobile natively.
        for d_id, data in connected_devices.items():
            if required_app == "whatsapp" and data.get("type") == "android":
                return d_id, data["type"], None
            # Otherwise just use whatever we have for generic ops
            if data.get("type") == "windows" and required_app != "whatsapp":
                return d_id, data["type"], None
        
        # Fallback to the first available
        fallback_id = list(connected_devices.keys())[0]
        return fallback_id, connected_devices[fallback_id].get("type"), None

    def _build_execution_strategy(self, device_id: str, device_type: str, intent: dict) -> tuple[str, list]:
        """
        Determines the Hybrid Intelligence fallback hierarchy.
        Returns: execution_mode string, and a list of step execution lambdas or markers.
        """
        plugin = getattr(self.sai.device_manager, 'plugins', {}).get(device_type)
        caps = plugin.get_capabilities() if plugin else []
        
        steps = []
        mode = "vision_hybrid"

        # Example: WhatsApp Message Logic
        if intent.get("action") == "send_message" and intent.get("app") == "whatsapp":
            if device_type == "android" and any("am_intent" in str(c) for c in caps):
                # 1. Command Strategy: We can use AM intents natively to speed up!
                mode = "command_first_vision_fallback"
                steps.append({"type": "command", "cmd": "open_app", "params": {"package": "com.whatsapp"}})
                steps.append({"type": "vision", "target": "search_icon", "action": "click_template"})
                steps.append({"type": "interaction", "action": "type", "text": intent.get("target")})
                steps.append({"type": "vision", "target": intent.get("target"), "action": "click_text"})
                steps.append({"type": "interaction", "action": "type", "text": intent.get("message")})
                steps.append({"type": "interaction", "action": "click", "x": 0, "y": 0, "dynamic": "send_button"})
            else:
                # Windows Desktop UI strategy
                mode = "pure_vision"
                steps.append({"type": "command", "cmd": "open_app", "params": {"app_name": "whatsapp"}})
                steps.append({"type": "vision", "target": "search_icon", "action": "click_template"})
                steps.append({"type": "interaction", "action": "type", "text": intent.get("message")})
                
        return mode, steps
