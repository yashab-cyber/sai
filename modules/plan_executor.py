import logging
import time
from typing import Any, Dict, List


class PlanExecutor:
    """Executes command-intelligence plans against connected devices with guardrails."""

    def __init__(self, sai_instance):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.PlanExecutor")

    def execute(self, device_id: str, plan: Dict[str, Any], retry_limit: int = 2, confidence_gate: float = 0.45) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = plan.get("steps", []) if isinstance(plan, dict) else []
        if not steps:
            return {"status": "failed", "message": "Plan has no executable steps.", "results": []}

        results = []
        for index, step in enumerate(steps, start=1):
            action = step.get("action")

            # Skip uncertain UI-targeted actions unless confidence is acceptable.
            step_score = float(step.get("match_score", 1.0))
            if step_score < confidence_gate:
                result = {
                    "status": "failed",
                    "action": action,
                    "message": f"Step confidence below gate ({step_score:.2f} < {confidence_gate:.2f}).",
                }
                results.append(result)
                self.logger.warning("Skipping low-confidence step %s/%s: %s", index, len(steps), step)
                continue

            final = None
            for attempt in range(retry_limit + 1):
                final = self._execute_step(device_id, step)
                if isinstance(final, dict) and final.get("status") in ("success", "queued"):
                    break
                self.logger.warning(
                    "Step %s/%s attempt %s failed: %s",
                    index,
                    len(steps),
                    attempt + 1,
                    final,
                )
                time.sleep(0.5)

            results.append({
                "step": index,
                "action": action,
                "input": step,
                "result": final,
            })

            # Hard stop if a critical step fails.
            if not isinstance(final, dict) or final.get("status") not in ("success", "queued"):
                return {
                    "status": "failed",
                    "message": f"Execution halted at step {index} ({action}).",
                    "results": results,
                }

        return {
            "status": "success",
            "message": "Plan executed successfully.",
            "results": results,
        }

    def _execute_step(self, device_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        action = step.get("action")

        if action == "open_app":
            package_name = step.get("target") or step.get("package")
            return self.sai.device_manager.route_command(
                device_id,
                "open_app",
                {"package": package_name},
            )

        if action == "tap":
            return self.sai.device_manager.route_command(
                device_id,
                "tap",
                {"x": int(step.get("x", 0)), "y": int(step.get("y", 0))},
            )

        if action == "type":
            return self.sai.device_manager.route_command(
                device_id,
                "type",
                {"text": step.get("text", "")},
            )

        if action == "get_screen_text":
            return self.sai.device_manager.route_command(device_id, "get_screen_text", {})

        if action == "send_message":
            return self.sai.device_manager.route_command(
                device_id,
                "send_message",
                {
                    "app": step.get("app", "com.whatsapp"),
                    "contact": step.get("contact", ""),
                    "message": step.get("message", ""),
                },
            )

        return {"status": "failed", "message": f"Unsupported action '{action}' in plan."}
