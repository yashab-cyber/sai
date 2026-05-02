"""
S.A.I. Idle Behavior Engine.

Background daemon that activates when S.A.I. has no active user task.
Triggers autonomous GitHub presence and business actions at configurable intervals.

Key behavior:
  - When SAI picks a domain (business or github), it COMPLETES the full task
    sequence before switching domains. The REVIEW stage's next_recommendation
    is followed until the task is logically done.
  - Supports pause/resume: when a user command arrives mid-idle-action,
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
    autonomous GitHub presence and business actions when the system is not busy.

    Task Continuity: Once a domain (business/github) is selected, the engine
    follows through on the REVIEW stage's next_recommendation to complete the
    full logical workflow before switching domains.
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

        # ── Task Continuity State ──
        # Tracks the active domain and pending next action from REVIEW
        self._active_domain: Optional[str] = None          # "business" or "github"
        self._next_recommendation: Optional[str] = None    # Action name from REVIEW
        self._domain_action_count = 0                       # Actions executed in current domain run
        self._max_domain_actions = int(self.config.get("max_domain_actions", 5))  # Max sequential actions before forcing domain switch

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

        # Save interrupted state including task continuity
        state = {
            "paused_at": datetime.now().isoformat(),
            "action_was_in_progress": self._action_in_progress,
            "actions_executed_before_pause": self._actions_executed,
            "last_action_time": self._last_action_time,
            # Task continuity state — so we can resume the same domain
            "active_domain": self._active_domain,
            "next_recommendation": self._next_recommendation,
            "domain_action_count": self._domain_action_count,
        }

        # Ask GitHubPresence for its pending work if it has any
        if hasattr(self.sai, 'github_presence'):
            pending = self.sai.github_presence.get_pending_work()
            if pending:
                state["pending_work"] = pending

        self._interrupted_state = state
        self.logger.info(
            "Idle engine PAUSED — user task has priority. Active domain: %s, Next: %s. State saved.",
            self._active_domain or "none",
            self._next_recommendation or "none",
        )

        # Persist to semantic memory for cross-session recall
        self._save_state_to_memory(state)

    def resume(self):
        """
        Resumes the idle engine after a user task completes.
        Restores saved state including the active domain and pending recommendation.
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

            # Restore task continuity state
            self._active_domain = saved_state.get("active_domain")
            self._next_recommendation = saved_state.get("next_recommendation")
            self._domain_action_count = saved_state.get("domain_action_count", 0)

            if self._active_domain:
                self.logger.info(
                    "Resuming domain '%s' — next action: %s (step %d/%d)",
                    self._active_domain,
                    self._next_recommendation or "from plan",
                    self._domain_action_count,
                    self._max_domain_actions,
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

                    # Cooldown between actions (shorter if continuing same domain)
                    if self._active_domain and self._next_recommendation:
                        # Short cooldown — we're continuing a task sequence
                        cooldown = max(5, self._min_cooldown // 3)
                        self.logger.info(
                            "Continuing %s domain (step %d/%d). Short cooldown: %ds.",
                            self._active_domain, self._domain_action_count,
                            self._max_domain_actions, cooldown,
                        )
                    else:
                        # Normal cooldown — task sequence complete, next iteration will pick new domain
                        cooldown = random.randint(self._min_cooldown, self._max_cooldown)
                        self.logger.info("Task sequence complete. Next idle action in %d seconds.", cooldown)

                    self._broadcast("next_cooldown", {"seconds": cooldown})
                    self._sleep_interruptible(cooldown)
                else:
                    # SAI is busy — check again in 60 seconds
                    self._sleep_interruptible(60)

            except Exception as e:
                self.logger.error("Idle engine error: %s", e)
                self._reset_domain_state()
                self._sleep_interruptible(120)  # Back off on error

    def _execute_idle_action(self):
        """Entry point: runs the full PLAN → EXECUTE → REVIEW cycle with task continuity."""
        self._plan_then_execute()

    def _plan_then_execute(self):
        """
        3-Stage deliberate idle cycle with TASK CONTINUITY:

        STAGE 1 — PLAN
            If we have an active domain with a next_recommendation from the
            previous REVIEW, use that instead of picking a new random domain.
            Otherwise, pick a domain (business vs github) by weight.

        STAGE 2 — EXECUTE
            Run the chosen action handler with the plan context.

        STAGE 3 — REVIEW
            Ask the LLM to evaluate the outcome. If the review recommends a
            follow-up action in the same domain, store it so the next iteration
            continues instead of switching.
        """
        # ─── Determine domain ─────────────────────────────────────────────

        # If we have an active domain from a previous cycle, continue it
        if self._active_domain and self._domain_action_count < self._max_domain_actions:
            domain = self._active_domain
            forced_action = self._next_recommendation
            self.logger.info(
                "[CONTINUITY] Continuing %s domain — step %d/%d, recommended action: %s",
                domain, self._domain_action_count + 1, self._max_domain_actions,
                forced_action or "from plan",
            )
        else:
            # Fresh start — pick domain by weight
            if self._active_domain:
                self.logger.info(
                    "[CONTINUITY] Domain '%s' completed after %d actions. Switching.",
                    self._active_domain, self._domain_action_count,
                )
            self._reset_domain_state()

            use_business = (
                self._business_weight > 0
                and hasattr(self.sai, 'business_engine')
                and random.randint(1, 100) <= self._business_weight
            )
            domain = "business" if use_business else "github"
            forced_action = None
            self._active_domain = domain
            self._domain_action_count = 0

        # ── STAGE 1: PLAN ──────────────────────────────────────────────────
        self.logger.info("SAI is idle — [PLAN] choosing best %s action...", domain)
        self._broadcast("plan_start", {"domain": domain, "is_continuation": forced_action is not None})

        plan = {}
        try:
            if domain == "business" and hasattr(self.sai, 'business_engine'):
                if forced_action:
                    # Use the recommendation from previous REVIEW instead of re-planning
                    plan = {"action": forced_action, "reasoning": f"Follow-up from previous review (step {self._domain_action_count + 1})"}
                else:
                    plan = self.sai.business_engine.plan_action()
            elif hasattr(self.sai, 'github_presence'):
                if forced_action:
                    plan = {"action": forced_action, "reasoning": f"Follow-up from previous review (step {self._domain_action_count + 1})"}
                else:
                    plan = self.sai.github_presence.plan_action()
        except Exception as e:
            self.logger.warning("[PLAN] Planning call failed: %s", e)
            plan = {"action": "", "reasoning": f"planning_error: {e}"}

        self._last_plan = plan
        action_name = plan.get("action", "unknown")
        reasoning = plan.get("reasoning", "")

        # Validate the forced action is actually available
        if forced_action and action_name == forced_action:
            self.logger.info(
                "[PLAN] %s continuation: '%s' — %s",
                domain.upper(), action_name, str(reasoning)[:150],
            )
        else:
            self.logger.info(
                "[PLAN] %s action decided: '%s' — %s",
                domain.upper(), action_name, str(reasoning)[:150],
            )

        self._broadcast("plan_complete", {
            "domain": domain,
            "action": action_name,
            "reasoning": str(reasoning)[:200],
            "is_continuation": forced_action is not None,
            "domain_step": self._domain_action_count + 1,
        })

        # ── STAGE 2: EXECUTE ───────────────────────────────────────────────
        self.logger.info("[EXECUTE] Running %s action: %s (step %d)", domain, action_name, self._domain_action_count + 1)
        self._action_in_progress = True
        self._broadcast("action_start", {
            "message": f"Executing {domain} action: {action_name}",
            "planned": True,
            "domain_step": self._domain_action_count + 1,
        })

        result = {}
        try:
            if domain == "business" and hasattr(self.sai, 'business_engine'):
                result = self.sai.business_engine.run_business_action(
                    planned_action=action_name
                )
            elif hasattr(self.sai, 'github_presence'):
                result = self.sai.github_presence.run_idle_action(plan=plan)
            else:
                result = {"status": "skipped", "reason": "no_module_available"}

            self._actions_executed += 1
            self._domain_action_count += 1
            self._last_action_time = time.time()

            status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
            extra_msg = ""
            if status == "skipped" and isinstance(result, dict) and "reason" in result:
                extra_msg = f" (Reason: {result['reason']})"
            elif status == "error" and isinstance(result, dict) and "message" in result:
                extra_msg = f" (Error: {result['message']})"

            self.logger.info(
                "[EXECUTE] %s action '%s' completed [%s]%s (step %d/%d, total: %d)",
                domain.upper(), action_name, status, extra_msg,
                self._domain_action_count, self._max_domain_actions,
                self._actions_executed,
            )
            self._broadcast("action_complete", {
                "action": f"{domain}:{action_name}",
                "status": status,
                "detail": extra_msg,
                "total": self._actions_executed,
                "domain_step": self._domain_action_count,
                "result_summary": str(result.get("result", result.get("reason", "")))[:200],
            })

            if hasattr(self.sai, 'event_bus'):
                self.sai.event_bus.publish(f"{domain}_action_executed", {
                    "action": action_name,
                    "status": status,
                    "result": result,
                    "total_actions": self._actions_executed,
                    "plan": plan,
                    "domain_step": self._domain_action_count,
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
            if domain == "business" and hasattr(self.sai, 'business_engine'):
                review = self.sai.business_engine.review_action(action_name, result)
            elif hasattr(self.sai, 'github_presence'):
                review = self.sai.github_presence.review_action(action_name, result)
        except Exception as e:
            self.logger.debug("[REVIEW] Review call failed: %s", e)
            review = {"success": False, "lessons": str(e), "next_recommendation": ""}

        next_rec = str(review.get("next_recommendation", "")).strip()
        success = review.get("success", False)

        self.logger.info(
            "[REVIEW] '%s' — success=%s | next: %s",
            action_name, success, next_rec[:80] if next_rec else "none (task complete)",
        )
        self._broadcast("review_complete", {
            "action": action_name,
            "success": success,
            "lessons": str(review.get("lessons", ""))[:200],
            "next_recommendation": next_rec[:100] if next_rec else "",
            "domain_step": self._domain_action_count,
        })

        # ── TASK CONTINUITY DECISION ─────────────────────────────────
        # If the REVIEW recommends a follow-up action in the same domain,
        # store it so the next idle cycle continues instead of randomizing.
        status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"

        if self._should_continue_domain(next_rec, status, domain):
            self._next_recommendation = self._normalize_recommendation(next_rec, domain)
            self.logger.info(
                "[CONTINUITY] Domain '%s' will continue → next action: '%s' (step %d/%d)",
                domain, self._next_recommendation, self._domain_action_count, self._max_domain_actions,
            )
            self._broadcast("continuity", {
                "domain": domain,
                "next_action": self._next_recommendation,
                "step": self._domain_action_count,
                "max_steps": self._max_domain_actions,
            })
        else:
            # Task sequence is complete — clear domain state
            reason = "max_steps" if self._domain_action_count >= self._max_domain_actions else "no_follow_up"
            self.logger.info(
                "[CONTINUITY] Domain '%s' sequence COMPLETE — reason: %s. Domain will be re-selected next cycle.",
                domain, reason,
            )
            self._reset_domain_state()

    def _should_continue_domain(self, next_rec: str, status: str, domain: str) -> bool:
        """
        Decides whether to continue in the current domain based on the REVIEW output.

        Returns True if:
        - The REVIEW recommended a follow-up action
        - The action succeeded or was skipped (not a hard error)
        - We haven't exceeded the max sequential domain actions
        """
        if not next_rec:
            return False

        if self._domain_action_count >= self._max_domain_actions:
            return False

        if status == "error":
            # Don't continue on errors — switch to a fresh domain
            return False

        # Validate the recommendation looks like an action name (not random prose)
        # Business actions: find_jobs, evaluate_jobs, send_proposals, deliver_project, etc.
        # GitHub actions: improve_repo, enhance_repo, create_repo, daily_commit, etc.
        valid_business_actions = {a["name"] for a in _get_domain_actions("business")}
        valid_github_actions = {a["name"] for a in _get_domain_actions("github")}

        all_valid = valid_business_actions | valid_github_actions
        normalized = self._normalize_recommendation(next_rec, domain)

        if normalized in all_valid:
            return True

        # If the recommendation is prose but contains a known action name, extract it
        for action_name in all_valid:
            if action_name in next_rec.lower().replace("-", "_").replace(" ", "_"):
                return True

        return False

    def _normalize_recommendation(self, next_rec: str, domain: str) -> str:
        """
        Normalizes a REVIEW recommendation string into a valid action name.
        Handles cases where the LLM returns prose like "evaluate_jobs to score leads"
        instead of just "evaluate_jobs".
        """
        if not next_rec:
            return ""

        rec_lower = next_rec.lower().strip().replace("-", "_").replace(" ", "_")

        # Direct match
        valid_actions = {a["name"] for a in _get_domain_actions(domain)}
        if rec_lower in valid_actions:
            return rec_lower

        # Check if any valid action name is a prefix/substring of the recommendation
        for action_name in valid_actions:
            if action_name in rec_lower:
                return action_name

        # Fuzzy: check if the first word(s) match an action
        words = next_rec.lower().strip().replace("-", "_").split()
        if words:
            candidate = words[0]
            if candidate in valid_actions:
                return candidate
            # Try first two words joined with underscore
            if len(words) >= 2:
                candidate = f"{words[0]}_{words[1]}"
                if candidate in valid_actions:
                    return candidate

        return next_rec.strip()

    def _reset_domain_state(self):
        """Clears the task continuity state, preparing for a fresh domain selection."""
        self._active_domain = None
        self._next_recommendation = None
        self._domain_action_count = 0

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
                    f"Idle Engine Interrupted: Was working on {state.get('active_domain', 'unknown')} domain. "
                    f"Paused at {state.get('paused_at')}. "
                    f"Step {state.get('domain_action_count', 0)}, next: {state.get('next_recommendation', 'none')}. "
                    f"Pending: {json.dumps(state.get('pending_work', {}))[:200]}"
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
            # Task continuity state
            "active_domain": self._active_domain,
            "next_recommendation": self._next_recommendation,
            "domain_action_count": self._domain_action_count,
            "max_domain_actions": self._max_domain_actions,
        }

        # Add business engine status if available
        if hasattr(self.sai, 'business_engine'):
            try:
                biz_status = self.sai.business_engine.get_status()
                status["business_actions"] = biz_status.get("actions_executed", 0)
            except Exception:
                pass

        return status


def _get_domain_actions(domain: str) -> list:
    """Returns the action list for a given domain. Used for validation."""
    if domain == "business":
        return [
            {"name": "find_jobs"},
            {"name": "evaluate_jobs"},
            {"name": "send_proposals"},
            {"name": "deliver_project"},
            {"name": "follow_up"},
            {"name": "update_portfolio"},
        ]
    else:  # github
        return [
            {"name": "create_repo"},
            {"name": "update_profile"},
            {"name": "improve_repo"},
            {"name": "create_gist"},
            {"name": "star_trending"},
            {"name": "update_status"},
            {"name": "profile_readme"},
            {"name": "daily_commit"},
            {"name": "trend_jack"},
            {"name": "github_pages"},
            {"name": "enhance_repo"},
            {"name": "create_release"},
            {"name": "pin_repos"},
            {"name": "follow_devs"},
            {"name": "self_issues"},
            {"name": "fork_improve"},
            {"name": "awesome_list"},
            {"name": "enable_discussions"},
        ]
