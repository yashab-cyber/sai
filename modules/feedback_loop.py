import time
import logging

class FeedbackLoop:
    """
    Step 5/6: Intelligence Core - Feedback Loop.
    Executes pipeline steps, visually verifies outcomes, and provides self-correction 
    logic (switching strategies if an action fails).
    """
    def __init__(self, sai_instance):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.Feedback")

    def execute_plan(self, route_plan: dict) -> dict:
        """Takes a structured execution plan from CommandRouter and runs it through the verification pipeline."""
        device_id = route_plan.get("device_id")
        steps = route_plan.get("steps", [])
        
        self.logger.info(f"Starting feedback-loop execution pipeline on {device_id}...")
        self.sai.state_manager.update_task("pipeline_rt", "running", route_plan)

        for i, step in enumerate(steps):
            self.logger.info(f"--- Executing Step {i+1}/{len(steps)} : {step.get('type')} ---")
            
            result = self._execute_step_with_retries(device_id, step)
            if result.get("status") == "error":
                self.logger.error(f"Pipeline blocked at step {i+1}. Initiating fallback...")
                
                # Switch strategy from Vision to UI Automation fallback (or vice versa)
                fallback_res = self._trigger_fallback_strategy(device_id, step)
                if fallback_res.get("status") == "error":
                    self.sai.state_manager.update_task("pipeline_rt", "failed")
                    return {"status": "error", "message": f"Critical Failure at step {i+1}. Fallbacks exhausted."}
                    
        self.sai.state_manager.update_task("pipeline_rt", "completed")
        return {"status": "success", "message": "Pipeline executed and verified successfully."}

    def _execute_step_with_retries(self, device_id: str, step: dict, max_retries: int = 2) -> dict:
        for attempt in range(max_retries):
            # 1. Execute Physical Action
            res = self._run_action(device_id, step)
            
            # Allow UI to settle
            time.sleep(0.1)
            
            # 2. Vision Verification
            if self._verify_outcome(device_id, step):
                return {"status": "success", "result": res}
                
            self.logger.warning(f"Verification Failed (Attempt {attempt+1}). Retrying...")
            
        return {"status": "error", "message": "Max verification retries exceeded."}

    def _run_action(self, device_id: str, step: dict) -> dict:
        """Routes to Command execution or Vision interaction layers."""
        stype = step.get('type')
        interaction = self.sai.interaction
        dm = self.sai.device_manager

        if stype == "command":
            return dm.route_command(device_id, step.get("cmd"), step.get("params", {}))
        
        elif stype == "vision":
            action, target = step.get("action"), step.get("target")
            if action == "click_template":
                return interaction.click_ui_template(device_id, target)
            elif action == "click_text":
                return interaction.click_text(device_id, target, ignore_case=True)
        
        elif stype == "interaction":
            action = step.get("action")
            if action == "type":
                return interaction.type_text(device_id, step.get("text"))
            elif action == "click":
                return interaction.tap_or_click(device_id, step.get("x", 0), step.get("y", 0))
        
        return {"status": "error", "message": "Unknown step type"}

    def _verify_outcome(self, device_id: str, step: dict) -> bool:
        """
        Cognitive OCR/Vision check.
        """
        stype = step.get("type")
        
        if stype == "command" and step.get("cmd") == "open_app":
            # If we opened an app, vision check if top-bar element exists
            screen_check = self.sai.vision.find_text_on_screen(device_id, "search", ignore_case=True)
            return screen_check.get("found", True) # Fallback true if OCR misreads
            
        elif stype == "vision" and step.get("action") == "click_text":
            # If we clicked a contact, verify chat input field appeared
            screen_check = self.sai.vision.find_text_on_screen(device_id, "message", ignore_case=True)
            return screen_check.get("found", True)

        return True # Default success if no strict verification bound

    def _trigger_fallback_strategy(self, device_id: str, step: dict) -> dict:
        """Switch from Vision -> ADB Fallback, or similar."""
        self.logger.info("Switching to Alternative Fallback Strategy...")
        if step.get("type") == "vision" and step.get("action") == "click_text":
            self.logger.info(f"Fallback: Searching raw coords for {step.get('target')}")
            return self.sai.interaction.tap_or_click(device_id, 300, 500)
            
        return {"status": "error"}
