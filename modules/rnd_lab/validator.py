import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class Validator:
    """
    Verifies execution success, parses test results and metrics,
    and compares against success_criteria.
    """

    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider

    def validate(self, plan: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates the raw results of an experiment plan execution versus success_criteria.
        Returns a dict: {"success": bool, "reasoning": str, "metrics": Any}
        """
        logger.info(f"Validating experiment for goal: {plan.get('goal')}")

        all_steps_successful = all(r.get("output", {}).get("success") for r in results)
        
        # Use AI to analyze the outputs against success criteria
        if self.ai_provider:
            stdout_text = "\n".join([f"Step {r.get('step_id')}: " + r.get('output', {}).get('stdout', '') for r in results])
            stderr_text = "\n".join([f"Step {r.get('step_id')}: " + r.get('output', {}).get('stderr', '') for r in results])
            
            # Truncate outputs to fit context limits (rough limit)
            if len(stdout_text) > 4000:
                stdout_text = stdout_text[:2000] + "\n...[TRUNCATED]...\n" + stdout_text[-2000:]
            if len(stderr_text) > 4000:
                stderr_text = stderr_text[:2000] + "\n...[TRUNCATED]...\n" + stderr_text[-2000:]

            system_prompt = """
            You are an Experiment Validator for the S.A.I. R&D Lab.
            You must evaluate if the experiment met its stated success_criteria based on the provided logs.
            
            Respond strictly in JSON format matching this schema:
            {
                "success": bool (true if criteria met, otherwise false),
                "reasoning": "Detailed justification on why it passed or failed",
                "metrics": {"total_executed_steps": int, "custom_metric_1": ..., "custom_metric_2": ...}
            }
            """
            
            user_query = f"""
            Goal: {plan.get('goal')}
            Success Criteria: {plan.get('success_criteria')}
            Did all steps exit 0? {all_steps_successful}
            
            === STDOUT ===
            {stdout_text}
            
            === STDERR ===
            {stderr_text}
            """
            
            try:
                result_json = self.ai_provider.prompt(system_prompt, user_query)
                if "success" in result_json and "reasoning" in result_json:
                    return result_json
            except Exception as e:
                logger.error(f"Validator AI evaluation failed: {e}. Falling back to default heuristics.")

        # Basic fallback validation
        if all_steps_successful:
            return {
                "success": True,
                "reasoning": "All execution steps exited with code 0. Assuming success criteria met based on logs.",
                "metrics": {"total_steps": len(results)}
            }
        else:
            failed_steps = [r.get('step_id') for r in results if not r.get("output", {}).get("success")]
            return {
                "success": False,
                "reasoning": f"Execution failed at step(s): {failed_steps}. Please review stderr.",
                "metrics": {"total_steps": len(results), "failed_steps": len(failed_steps)}
            }
