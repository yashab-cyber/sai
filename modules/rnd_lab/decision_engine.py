import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DecisionEngine:
    """
    After the report is generated, deduces the next step:
    integrate, retry, discard, or escalate.
    """
    
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider

    def decide(self, plan: Dict[str, Any], validation: Dict[str, Any], retry_count: int) -> Dict[str, Any]:
        """
        Decides the next action. Returns a dict:
        {"action": str, "reason": str}
        Valid actions: "integrate", "retry", "discard", "escalate"
        """
        logger.info(f"Deciding next step for goal: {plan.get('goal')}")

        if validation.get("success", False):
            return {
                "action": "integrate",
                "reason": f"Experiment was successful: {validation.get('reasoning')}. Recommend integration."
            }

        # Analyze failure with AI if we have attempts left
        if retry_count < 3 and self.ai_provider:
            system_prompt = """
            You are an R&D Decision Engine. An experiment failed.
            You must decide if we should retry (re-run with modifications), or discard it entirely.
            
            Inputs: Experiment Plan, Evaluation Reason, Current Retry Count.
            Outputs MUST be JSON matching this schema:
            {
                "action": "retry" or "discard" or "escalate",
                "reason": "Explain logically why retrying makes sense, or why it should be dropped."
            }
            """
            
            user_query = f"""
            Goal: {plan.get('goal')}
            Failure Reason: {validation.get('reasoning')}
            Retry Count: {retry_count}/3
            """
            
            try:
                decision = self.ai_provider.prompt(system_prompt, user_query)
                if "action" in decision and "reason" in decision:
                    if decision["action"] not in ["retry", "discard", "escalate"]:
                        decision["action"] = "retry" # sanitize bad llm output
                    return decision
            except Exception as e:
                logger.error(f"Decision logic parsing error: {e}. Falling back to default retry logic.")

        # Default heuristic behavior
        if retry_count < 3:
            return {
                "action": "retry",
                "reason": f"Experiment failed: {validation.get('reasoning')}. We have {3 - retry_count} retries left."
            }
        
        return {
            "action": "discard",
            "reason": "Max retries reached. Discarding experiment. Will record learnings to avoid repetition."
        }
