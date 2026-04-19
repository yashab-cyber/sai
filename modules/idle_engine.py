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
                    self._sleep_interruptible(cooldown)
                else:
                    # SAI is busy — check again in 60 seconds
                    self._sleep_interruptible(60)

            except Exception as e:
                self.logger.error("Idle engine error: %s", e)
                self._sleep_interruptible(120)  # Back off on error

    def _execute_idle_action(self):
        """Triggers a GitHub presence action."""
        if not hasattr(self.sai, 'github_presence'):
            self.logger.warning("GitHubPresence module not initialized. Skipping.")
            return

        self.logger.info("SAI is idle — executing autonomous GitHub action...")
        self._action_in_progress = True
        try:
            result = self.sai.github_presence.run_idle_action()
            self._actions_executed += 1
            self._last_action_time = time.time()

            action = result.get("action", "unknown")
            status = result.get("status", "unknown")
            self.logger.info(
                "Idle action completed: %s [%s] (total: %d)",
                action, status, self._actions_executed
            )

            # Publish event
            if hasattr(self.sai, 'event_bus'):
                self.sai.event_bus.publish("idle_action_executed", {
                    "action": action,
                    "status": status,
                    "result": result,
                    "total_actions": self._actions_executed
                })

        except Exception as e:
            self.logger.error("Failed to execute idle action: %s", e)
        finally:
            self._action_in_progress = False

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
            time.sleep(min(5, seconds - elapsed))
            elapsed += 5

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
        return {
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
            "sai_is_idle": not self.sai.is_running
        }
