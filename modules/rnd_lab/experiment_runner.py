import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ExperimentRunner:
    """
    Takes a structured plan and executes it using the SandboxManager.
    Stores raw outputs for validation.
    """

    def __init__(self, sandbox_manager=None):
        self.sandbox_manager = sandbox_manager

    def run_plan(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Executes an experiment plan step-by-step.
        """
        if not self.sandbox_manager:
            raise ValueError("SandboxManager must be provided.")

        logger.info(f"Running experiment plan for goal: {plan.get('goal')}")
        results = []

        for step in plan.get("steps", []):
            action = step.get("action", "Unknown action")
            command = step.get("command")
            
            if not command:
                logger.warning(f"Skipping step {step.get('step_id')} due to missing command.")
                continue
                
            logger.info(f"Executing step {step.get('step_id')}: {action}")
            result = self.sandbox_manager.run_command(command)
            
            # Store step info with result
            step_result = {
                "step_id": step.get("step_id"),
                "action": action,
                "command": command,
                "output": result
            }
            results.append(step_result)

            if not result.get("success"):
                logger.error(f"Execution failed on step {step.get('step_id')}")
                # We can stop or continue depending on configuration, 
                # but typically a failure means we shouldn't proceed cleanly
                break
                
        return results
