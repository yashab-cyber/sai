import logging
from typing import Dict, Any, Optional

class SelfAdaptationEngine:
    """
    Self-Adaptation Engine (MAPE-K Framework).
    Monitors tactical execution, analyzes anomalies (loops, persistent failures),
    and plans/executes adaptation strategies dynamically.
    """

    def __init__(self, sai_instance):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.SelfAdaptation")
        
        # State tracking
        self._consecutive_same = 0
        self._cumulative_fails = 0
        self._device_failures = 0
        self._last_action_key = None

    def reset_state(self):
        """Resets the tactical tracking state for a new objective."""
        self._consecutive_same = 0
        self._cumulative_fails = 0
        self._device_failures = 0
        self._last_action_key = None

    def monitor_action(self, tool_name: str, params: Any, action_result: Any) -> Dict[str, Any]:
        """
        Monitors an executed action and determines if adaptation is required.
        
        Args:
            tool_name: The tool that was executed.
            params: Parameters passed to the tool.
            action_result: The result returned by the tool.
            
        Returns:
            Dict containing an 'adaptation_strategy' and associated details.
            If no adaptation is needed, strategy is 'CONTINUE'.
        """
        # 1. Check for Stuck Tactical Loop (identical consecutive + cumulative failure tracking)
        action_key = f"{tool_name}:{sorted(params.items()) if isinstance(params, dict) else params}"
        
        # Track identical consecutive actions
        if action_key == self._last_action_key:
            self._consecutive_same += 1
        else:
            self._consecutive_same = 0
        self._last_action_key = action_key

        # Track cumulative failures regardless of action identity
        is_action_failed = False
        if isinstance(action_result, dict):
            status = action_result.get("status", "")
            if status in ("error", "failed", "queued"):
                is_action_failed = True
        
        if is_action_failed:
            self._cumulative_fails += 1
        else:
            # Successful action resets cumulative counter
            self._cumulative_fails = 0

        # Tools that are legitimately called many times in a row for the same task
        REPETITION_EXEMPT = {
            "github.presence", "email.send", "email.read", "email.read_unread",
            "browser.navigate", "browser.search", "browser.scrape",
        }

        # Break on 4 identical consecutive (raised from 2) — but exempt multi-call tools
        # unless they are also failing (stuck + failing = real loop)
        loop_threshold = 4
        if tool_name in REPETITION_EXEMPT:
            # Only flag a loop if the tool is ALSO producing errors repeatedly
            if self._consecutive_same >= loop_threshold and is_action_failed:
                self.logger.warning(
                    "Detected a failing loop on exempt tool '%s' (%d consecutive failures).",
                    tool_name, self._consecutive_same,
                )
                return {
                    "strategy": "LOOP_BREAK",
                    "message": (
                        f"Sir, '{tool_name}' has failed {self._consecutive_same} times in a row. "
                        "I'd recommend we reassess the approach."
                    ),
                    "thought": "Repeated failures on the same tool detected, sir. Awaiting new directive.",
                }
        elif self._consecutive_same >= loop_threshold:
            self.logger.warning("Detected a tactical loop. Identical consecutive actions: %d", self._consecutive_same)
            return {
                "strategy": "LOOP_BREAK",
                "message": (
                    "Sir, I appear to be caught in a loop — repeating the same action without progress. "
                    "I'd recommend we reassess the approach."
                ),
                "thought": "I've detected a tactical loop, sir. The same action has been repeated without progress. Awaiting new directive.",
            }

        if self._cumulative_fails >= 4:
            self.logger.warning("Cumulative failure threshold reached: %d consecutive failed actions.", self._cumulative_fails)
            return {
                "strategy": "LOOP_BREAK",
                "message": (
                    "Sir, I've encountered %d consecutive failures across different approaches. "
                    "The current strategy doesn't appear to be working." % self._cumulative_fails
                ),
                "thought": "Multiple different approaches have all failed, sir. Recommending we reassess the objective."
            }

        # 2. Check for Device Failures (Android companion unreachable)
        is_device_failure = False
        if isinstance(action_result, dict):
            status = action_result.get("status", "")
            error = action_result.get("error", "")
            msg = action_result.get("message", "")

            # Queued = device offline
            if status == "queued":
                is_device_failure = True
            # Explicit device errors
            elif status in ("failed", "error") and error in (
                "DEVICE_UNREACHABLE", "DEVICE_UNHEALTHY",
                "COMMAND_TIMEOUT", "NO_COMM_LAYER", "DISPATCH_ERROR"
            ):
                is_device_failure = True
            # Vision check failures
            elif status == "failed" and any(kw in msg.lower() for kw in (
                "no screenshot", "no screen text", "device", "companion", "direct http"
            )):
                is_device_failure = True

        if is_device_failure:
            self._device_failures += 1
            fail_reason = (action_result.get("error") if isinstance(action_result, dict) else None) or "unknown"
            self.logger.warning("Device failure %d/2 detected (tool=%s, reason=%s)", self._device_failures, tool_name, fail_reason)
            
            if self._device_failures >= 2:
                return {
                    "strategy": "DEVICE_OFFLINE",
                    "message": (
                        "Sir, the target device appears to be unreachable. "
                        "Please verify the companion app is running and connected to the same network."
                    ),
                    "thought": "The target device is unreachable, sir. Two consecutive attempts have failed. Please check the companion app."
                }
        else:
            # Reset device failure tracker upon a successful non-device-failing result
            self._device_failures = 0

        # No anomaly detected
        return {"strategy": "CONTINUE"}
