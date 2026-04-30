"""
S.A.I. Idle Behavior Engine.

Background daemon that activates when S.A.I. has no active user task.
Triggers autonomous GitHub presence actions at configurable intervals.

Supports pause/resume: when a user command arrives mid-idle-action,
the engine saves its state, yields to the user task, and resumes
its work after the user task completes.
"""

import time
import json
import random
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional


class IdleEngine:
    """
    Background daemon that monitors SAI's idle state and triggers
    autonomous GitHub presence actions when the system is not busy.

    Supports interruption: if a user task arrives, the engine pauses
    gracefully, saves what it was doing to memory, and resumes after
    the user task completes.
    """

    def __init__(self, sai_instance, config: dict = None):
        """
        Args:
            sai_instance: The main SAI orchestrator instance.
            config: Optional idle behavior settings from config.yaml.
        """
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.IdleEngine")
        self.config = config or {}

        self._thread: threading.Thread = None
        self._running = False
        self._enabled = self.config.get("enabled", True)

        # Cooldown between idle actions (in seconds)
        self._min_cooldown = int(self.config.get("min_cooldown_seconds", 30))
        self._max_cooldown = int(self.config.get("max_cooldown_seconds", 60))

        # Time to wait after startup before first idle action
        self._startup_delay = int(self.config.get("startup_delay_seconds", 30))

        self._last_action_time = 0
        self._actions_executed = 0

        # ── Pause / Resume State ──
        self._paused = False
        self._pause_event = threading.Event()  # Cleared = paused, Set = running
        self._pause_event.set()  # Start unpaused
        self._interrupted_state: Optional[Dict[str, Any]] = None
        self._action_in_progress = False  # True while an idle action is executing

        # Business vs GitHub weight — percentage of idle time allocated to business
        self._business_weight = int(self.config.get("business_weight", 0))
        # Override from business config if present
        if hasattr(self.sai, 'config'):
            biz_cfg = self.sai.config.get('business', {}) if hasattr(self.sai, 'config') else {}
            self._business_weight = int(biz_cfg.get('idle_business_weight', self._business_weight))

        # GUI callback for real-time idle log broadcasting
        self._gui_callback = None

        # Last plan produced — surfaced in get_status()
        self._last_plan: Optional[Dict[str, Any]] = None

    def set_gui_callback(self, callback):
        """Set a callback function to broadcast idle events to the GUI."""
        self._gui_callback = callback

    def _broadcast(self, event_type: str, data: dict = None):
        """Send an event to the GUI if a callback is set."""
        if self._gui_callback:
            try:
                entry = {"type": event_type, "timestamp": time.time(), **(data or {})}
                self._gui_callback(entry)
            except Exception:
                pass

    def start(self):
        """Starts the idle engine daemon thread."""
        if not self._enabled:
            self.logger.info("Idle engine is disabled in configuration. Skipping start.")
            return

        if self._thread and self._thread.is_alive():
            self.logger.warning("Idle engine is already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._idle_loop, daemon=True, name="SAI-IdleEngine")
        self._thread.start()
        self.logger.info(
            "Idle engine started. Cooldown: %d-%ds. Startup delay: %ds.",
            self._min_cooldown, self._max_cooldown, self._startup_delay
        )

    def stop(self):
        """Stops the idle engine."""
        self._running = False
        self._pause_event.set()  # Unblock if paused so thread can exit
        if self._thread:
            self.logger.info("Idle engine stopping...")
            self._thread = None

    def pause(self):
        """
        Pauses the idle engine when a user task arrives.
        Saves the current state so work can be resumed later.
        """
        if self._paused:
            return  # Already paused

        self._paused = True
        self._pause_event.clear()  # Block the idle loop

        # Save interrupted state
        state = {
            "paused_at": datetime.now().isoformat(),
            "action_was_in_progress": self._action_in_progress,
            "actions_executed_before_pause": self._actions_executed,
            "last_action_time": self._last_action_time,
        }

        # Ask GitHubPresence for its pending work if it has any
        if hasattr(self.sai, 'github_presence'):
            pending = self.sai.github_presence.get_pending_work()
            if pending:
                state["pending_work"] = pending

        self._interrupted_state = state
        self.logger.info(
            "Idle engine PAUSED — user task has priority. State saved: %s",
            json.dumps(state, default=str)[:300]
        )

        # Persist to semantic memory for cross-session recall
        self._save_state_to_memory(state)

    def resume(self):
        """
        Resumes the idle engine after a user task completes.
        Restores saved state and continues where it left off.
        """
        if not self._paused:
            return  # Not paused

        saved_state = self._interrupted_state
        self._paused = False
        self._interrupted_state = None
        self._pause_event.set()  # Unblock the idle loop

        if saved_state:
            self.logger.info(
                "Idle engine RESUMING — user task complete. Restoring state from %s",
                saved_state.get("paused_at", "unknown")
            )

            # Restore pending work to GitHubPresence
            pending_work = saved_state.get("pending_work")
            if pending_work and hasattr(self.sai, 'github_presence'):
                self.sai.github_presence.restore_pending_work(pending_work)
                self.logger.info(
                    "Restored pending GitHub work: %s",
                    pending_work.get("action", "unknown")
                )

            # Publish resume event
            if hasattr(self.sai, 'event_bus'):
                self.sai.event_bus.publish("idle_engine_resumed", {
                    "interrupted_state": saved_state,
                    "resumed_at": datetime.now().isoformat()
                })
        else:
            self.logger.info("Idle engine RESUMING — no interrupted state to restore.")

    def _idle_loop(self):
        """Main loop — runs in a background thread."""
        # Initial startup delay
        self.logger.info("Idle engine waiting %d seconds before first action...", self._startup_delay)
        self._sleep_interruptible(self._startup_delay)

        while self._running:
            try:
                # ── Wait if paused ──
                # Block here until resume() sets the event
                if self._paused:
                    self.logger.debug("Idle loop is paused. Waiting for resume signal...")
                    self._pause_event.wait()  # Blocks until set()
                    if not self._running:
                        break
                    # After resuming, execute pending work immediately (no cooldown)
                    if hasattr(self.sai, 'github_presence') and self.sai.github_presence.has_pending_work():
                        self.logger.info("Resuming interrupted work after user task...")
                        self._execute_pending_work()
                        continue

                # Check if SAI is idle (no active user task)
                if not self.sai.is_running:
                    self._execute_idle_action()

                    # Random cooldown between actions
                    cooldown = random.randint(self._min_cooldown, self._max_cooldown)
                    self.logger.info("Next idle action in %d seconds.", cooldown)
                    self._broadcast("next_cooldown", {"seconds": cooldown})
                    self._sleep_interruptible(cooldown)
                else:
                    # SAI is busy — check again in 60 seconds
                    self._sleep_interruptible(60)

            except Exception as e:
                self.logger.error("Idle engine error: %s", e)
                self._sleep_interruptible(120)  # Back off on error

    def _execute_idle_action(self):
        """Entry point: runs the full PLAN → EXECUTE → REVIEW cycle."""
        self._plan_then_execute()

    def _plan_then_execute(self):
        """
        3-Stage deliberate idle cycle:

        STAGE 1 — PLAN
            Ask the LLM (via BusinessEngine or GitHubPresence) what the single
            best action is given the current state. Reasoning is logged and
            broadcast to the GUI.

        STAGE 2 — EXECUTE
            Run the chosen action handler with the plan context.

        STAGE 3 — REVIEW
            Ask the LLM to evaluate the outcome. Store the reflection in
            semantic memory so future planning cycles can learn from it.
        """
        # Determine domain (business vs github) by weight
        use_business = (
            self._business_weight > 0
            and hasattr(self.sai, 'business_engine')
            and random.randint(1, 100) <= self._business_weight
        )
        domain = "business" if use_business else "github"

        # ── STAGE 1: PLAN ──────────────────────────────────────────────────
        self.logger.info("SAI is idle — [PLAN] choosing best %s action...", domain)
        self._broadcast("plan_start", {"domain": domain})

        plan = {}
        try:
            if use_business:
                plan = self.sai.business_engine.plan_action()
            elif hasattr(self.sai, 'github_presence'):
                plan = self.sai.github_presence.plan_action()
        except Exception as e:
            self.logger.warning("[PLAN] Planning call failed: %s", e)
            plan = {"action": "", "reasoning": f"planning_error: {e}"}

        self._last_plan = plan
        action_name = plan.get("action", "unknown")
        reasoning = plan.get("reasoning", "")

        self.logger.info(
            "[PLAN] %s action decided: '%s' — %s",
            domain.upper(), action_name, str(reasoning)[:150],
        )
        self._broadcast("plan_complete", {
            "domain": domain,
            "action": action_name,
            "reasoning": str(reasoning)[:200],
        })

        # ── STAGE 2: EXECUTE ───────────────────────────────────────────────
        self.logger.info("[EXECUTE] Running %s action: %s", domain, action_name)
        self._action_in_progress = True
        self._broadcast("action_start", {
            "message": f"Executing {domain} action: {action_name}",
            "planned": True,
        })

        result = {}
        try:
            if use_business:
                result = self.sai.business_engine.run_business_action(
                    planned_action=action_name
                )
            elif hasattr(self.sai, 'github_presence'):
                result = self.sai.github_presence.run_idle_action(plan=plan)
            else:
                result = {"status": "skipped", "reason": "no_module_available"}

            self._actions_executed += 1
            self._last_action_time = time.time()

            status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
            extra_msg = ""
            if status == "skipped" and isinstance(result, dict) and "reason" in result:
                extra_msg = f" (Reason: {result['reason']})"
            elif status == "error" and isinstance(result, dict) and "message" in result:
                extra_msg = f" (Error: {result['message']})"

            self.logger.info(
                "[EXECUTE] %s action '%s' completed [%s]%s (total: %d)",
                domain.upper(), action_name, status, extra_msg, self._actions_executed,
            )
            self._broadcast("action_complete", {
                "action": f"{domain}:{action_name}",
                "status": status,
                "detail": extra_msg,
                "total": self._actions_executed,
                "result_summary": str(result.get("result", result.get("reason", "")))[:200],
            })

            if hasattr(self.sai, 'event_bus'):
                self.sai.event_bus.publish(f"{domain}_action_executed", {
                    "action": action_name,
                    "status": status,
                    "result": result,
                    "total_actions": self._actions_executed,
                    "plan": plan,
                })

        except Exception as e:
            self.logger.error("[EXECUTE] %s action '%s' failed: %s", domain, action_name, e)
            result = {"status": "error", "message": str(e)}
            self._broadcast("action_error", {"error": str(e)})
        finally:
            self._action_in_progress = False

        # ── STAGE 3: REVIEW ────────────────────────────────────────────────
        self.logger.info("[REVIEW] Evaluating outcome of '%s'...", action_name)
        self._broadcast("review_start", {"action": action_name, "domain": domain})

        review = {}
        try:
            if use_business and hasattr(self.sai, 'business_engine'):
                review = self.sai.business_engine.review_action(action_name, result)
            elif hasattr(self.sai, 'github_presence'):
                review = self.sai.github_presence.review_action(action_name, result)
        except Exception as e:
            self.logger.debug("[REVIEW] Review call failed: %s", e)
            review = {"success": False, "lessons": str(e), "next_recommendation": ""}

        self.logger.info(
            "[REVIEW] '%s' — success=%s | next: %s",
            action_name,
            review.get("success"),
            str(review.get("next_recommendation", ""))[:80],
        )
        self._broadcast("review_complete", {
            "action": action_name,
            "success": review.get("success"),
            "lessons": str(review.get("lessons", ""))[:200],
            "next_recommendation": str(review.get("next_recommendation", ""))[:100],
        })

    def _execute_pending_work(self):
        """Resumes interrupted pending work from GitHubPresence."""
        if not hasattr(self.sai, 'github_presence'):
            return

        self.logger.info("Executing pending work from before interruption...")
        self._action_in_progress = True
        try:
            result = self.sai.github_presence.execute_pending_work()
            if result:
                self._actions_executed += 1
                self._last_action_time = time.time()
                self.logger.info("Pending work completed: %s", result.get("action", "unknown"))

                if hasattr(self.sai, 'event_bus'):
                    self.sai.event_bus.publish("idle_action_resumed", {
                        "action": result.get("action", "resumed_work"),
                        "status": result.get("status", "unknown"),
                        "result": result
                    })
        except Exception as e:
            self.logger.error("Failed to execute pending work: %s", e)
        finally:
            self._action_in_progress = False

    def _sleep_interruptible(self, seconds: int):
        """Sleeps in small increments so the thread can be stopped or paused quickly."""
        elapsed = 0
        while elapsed < seconds and self._running and not self._paused:
            sleep_time = min(5, seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time

    def _save_state_to_memory(self, state: dict):
        """Persists interrupted state to semantic memory for cross-session recall."""
        try:
            if hasattr(self.sai, 'memory') and hasattr(self.sai, 'brain'):
                content = (
                    f"Idle Engine Interrupted: Was working on GitHub presence. "
                    f"Paused at {state.get('paused_at')}. "
                    f"Pending: {json.dumps(state.get('pending_work', {}))[:300]}"
                )
                embedding = self.sai.brain.get_embedding(content)
                self.sai.memory.save_semantic_memory(
                    content, embedding,
                    {"type": "idle_engine_state", "event": "paused"}
                )
        except Exception as e:
            self.logger.debug("Failed to save state to memory: %s", e)

    def get_status(self) -> dict:
        """Returns idle engine diagnostics."""
        status = {
            "enabled": self._enabled,
            "running": self._running,
            "paused": self._paused,
            "action_in_progress": self._action_in_progress,
            "has_pending_work": (
                hasattr(self.sai, 'github_presence') and
                self.sai.github_presence.has_pending_work()
            ),
            "interrupted_state": self._interrupted_state,
            "actions_executed": self._actions_executed,
            "last_action_time": (
                datetime.fromtimestamp(self._last_action_time).isoformat()
                if self._last_action_time else None
            ),
            "cooldown_range": f"{self._min_cooldown}-{self._max_cooldown}s",
            "sai_is_idle": not self.sai.is_running,
            "business_weight_pct": self._business_weight,
            "github_weight_pct": 100 - self._business_weight,
            # Last plan produced by PLAN stage
            "last_plan": self._last_plan,
        }

        # Add business engine status if available
        if hasattr(self.sai, 'business_engine'):
            try:
                biz_status = self.sai.business_engine.get_status()
                status["business_actions"] = biz_status.get("actions_executed", 0)
            except Exception:
                pass

        return status
