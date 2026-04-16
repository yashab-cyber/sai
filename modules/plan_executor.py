import logging
import time
from typing import Any, Dict, List


class PlanExecutor:
    """Executes command-intelligence plans against connected devices with guardrails.

    Resilience guarantees:
    - ``"queued"`` is treated as FAILURE (command was NOT executed)
    - Device health is verified before execution begins
    - Per-step exponential back-off between retries
    - Granular failure reasons are returned in results
    """

    def __init__(self, sai_instance):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.PlanExecutor")

    def execute(self, device_id: str, plan: Dict[str, Any], retry_limit: int = 2, confidence_gate: float = 0.45) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = plan.get("steps", []) if isinstance(plan, dict) else []
        if not steps:
            return {"status": "failed", "message": "Plan has no executable steps.", "results": []}

        # ---- Pre-flight device health check ----
        dm = self.sai.device_manager
        if not dm.is_device_healthy(device_id):
            device_status = dm.get_device_status(device_id)
            self.logger.warning(
                "Device '%s' is not healthy (status=%s). Aborting plan execution.",
                device_id, device_status
            )
            return {
                "status": "failed",
                "error": "DEVICE_UNHEALTHY",
                "message": f"Device '{device_id}' is {device_status}. Cannot execute plan.",
                "device_status": device_status,
                "results": [],
            }

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

                # ---- CRITICAL FIX: Only "success" counts as success ----
                # "queued" means the command was NOT executed (device offline)
                if isinstance(final, dict) and final.get("status") == "success":
                    break

                self.logger.warning(
                    "Step %s/%s attempt %s failed (status=%s): %s",
                    index,
                    len(steps),
                    attempt + 1,
                    final.get("status") if isinstance(final, dict) else "unknown",
                    final.get("message", "") if isinstance(final, dict) else str(final),
                )

                # Exponential back-off: 0.5s → 1s → 2s
                if attempt < retry_limit:
                    backoff = 0.5 * (2 ** attempt)
                    time.sleep(backoff)

            results.append({
                "step": index,
                "action": action,
                "input": step,
                "result": final,
            })

            # Hard stop if a critical step fails.
            if not isinstance(final, dict) or final.get("status") != "success":
                error_detail = ""
                if isinstance(final, dict):
                    error_detail = final.get("error", final.get("message", ""))
                return {
                    "status": "failed",
                    "error": error_detail or "STEP_FAILED",
                    "message": f"Execution halted at step {index}/{len(steps)} ({action}): {error_detail}",
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
