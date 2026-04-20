import logging
import json
import os
import threading
from typing import Dict, Any
import datetime

logger = logging.getLogger(__name__)

class MemoryStore:
    """
    Save learnings in a structured format:
    experiment, result, insight, timestamp
    """

    def __init__(self, storage_file: str = "workspace/rnd_memory.json"):
        self.storage_file = os.path.abspath(os.path.join(os.getcwd(), storage_file))
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        self._lock = threading.Lock()
        self.memory = self._load_memory()

    def _load_memory(self):
        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_memory(self):
        with open(self.storage_file, 'w') as f:
            json.dump(self.memory, f, indent=4)

    def save_learning(self, plan: Dict[str, Any], validation: Dict[str, Any]):
        learning = {
            "experiment": plan.get("goal"),
            "success": validation.get("success"),
            "result": validation.get("reasoning"),
            "insight": f"Experiment completed. Metrics: {validation.get('metrics')}",
            "timestamp": datetime.datetime.now().isoformat()
        }
        with self._lock:
            self.memory.append(learning)
            self._save_memory()
        logger.info(f"Saved learning for: {plan.get('goal')}")

    def save_memory(self):
        self._save_memory()
