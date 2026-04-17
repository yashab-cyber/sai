import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ExperimentPlanner:
    """
    Converts user intent into a structured experiment plan.
    """

    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider

    def generate_plan(self, intent: str) -> Dict[str, Any]:
        """
        Generates an experiment plan based on the intent.
        This calls the S.A.I. Brain LLM to generate the structured plan.
        """
        logger.info(f"Generating plan for intent: {intent}")
        
        system_prompt = """
        You are an Autonomous Experiment Planner for S.A.I.'s Research & Development Lab.
        You must convert the user's intent into a structured JSON experiment plan to run inside an isolated Docker sandbox.
        
        Output MUST be valid JSON with the following schema:
        {
            "type": "code | research | system | external",
            "goal": "...",
            "hypothesis": "...",
            "method": "...",
            "tools": ["python", "pip", "curl", "etc"],
            "steps": [
                {
                    "step_id": 1,
                    "action": "Description of what is happening",
                    "command": "Valid bash command to run inside standard debian/ubuntu container"
                }
            ],
            "success_criteria": "State measurable conditions for success"
        }
        """
        
        if self.ai_provider:
            try:
                # Call the Brain API cleanly
                plan = self.ai_provider.prompt(system_prompt, intent)
                if plan and "steps" in plan:
                    return plan
                else:
                    logger.warning("LLM response did not contain 'steps'. Falling back to default plan.")
            except Exception as e:
                logger.error(f"Failed to generate plan securely: {e}")

        # Fallback stub (mock) if no AI provider available or call failed
        logger.warning("Using fallback plan generator.")
        return {
            "type": "research", 
            "goal": intent,
            "hypothesis": f"We can resolve '{intent}' by exploring established methodologies.",
            "method": "Execute a standard evaluation protocol script.",
            "tools": ["python", "pip"],
            "steps": [
                {
                    "step_id": 1,
                    "action": "Write evaluation script",
                    "command": "echo 'print(\"Test complete.\")' > evaluate.py"
                },
                {
                    "step_id": 2,
                    "action": "Run evaluation script",
                    "command": "python evaluate.py"
                }
            ],
            "success_criteria": "Completion of execution without errors."
        }
