import logging
import time

class StateManager:
    """
    Step 2/7: State Management.
    System Tracker for multi-step network execution.
    Maintains context on which device S.A.I. is looking at, what app is open,
    and tracks physical task progression to prevent getting lost in multi-step goals.
    """
    def __init__(self):
        self.logger = logging.getLogger("SAI.StateManager")
        self.current_device = None
        self.active_app = None
        self.task_progress = {}
        self.history = []

    def set_focus(self, device_id: str, app_name: str = None):
        """Locks S.A.I.'s cognitive focus to a specific networked device."""
        self.current_device = device_id
        if app_name:
            self.active_app = app_name
        self.logger.info(f"[State] Focus shifted to {device_id} | App: {self.active_app}")

    def update_task(self, task_id: str, status: str, result: dict = None):
        """Records progression of a multi-step execution."""
        self.task_progress[task_id] = {
            "status": status,
            "last_updated": time.time(),
            "result": result or {}
        }
        self.history.append({"task_id": task_id, "status": status, "result": result})

    def get_context(self) -> dict:
        """Returns current operational state for the LLM."""
        return {
            "focused_device": self.current_device,
            "active_app": self.active_app,
            "recent_tasks": self.history[-5:] if self.history else []
        }

    def clear_focus(self):
        self.current_device = None
        self.active_app = None

    def get_task(self, task_id: str):
        return self.task_progress.get(task_id)
