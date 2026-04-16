import os
import shutil
import logging
from typing import Dict, Any, Optional
from core.executor import Executor
from core.safety import SafetyManager
from modules.coder import Coder
from core.memory import MemoryManager

class EvolutionEngine:
    """
    The Self-Modification Engine.
    Handles the analysis and safe update of /modules.
    """

    def __init__(self, executor: Executor, memory: MemoryManager, coder: Coder):
        self.executor = executor
        self.memory = memory
        self.coder = coder
        self.logger = logging.getLogger("SAI.Evolution")

    def propose_improvement(self, module_name: str, new_code: str) -> Dict[str, Any]:
        """
        Validates and applies an improvement to a module.
        Includes a rollback mechanism.
        Improves logging for better traceability.
        """
        module_path = f"modules/{module_name}.py"
        backup_path = f"modules/{module_name}.py.bak"

        self.logger.info(f"[Start] Proposing improvement for {module_name}...")

        # 1. Validation
        is_valid, error_msg = self.coder.validate_code(new_code)
        if not is_valid:
            self.logger.error(f"[Fail] Improvement rejected due to invalid syntax: {error_msg}")
            return {"status": "error", "message": f"Invalid syntax: {error_msg}"}

        # 2. Backup current version
        try:
            read_result = self.executor.read_file(module_path)
            original_code = read_result.get("content", "")

            with open(backup_path, "w") as f:
                f.write(original_code)
                self.logger.info(f"[Backup] Created backup for {module_name}.")

            # 3. Apply update
            write_result = self.executor.write_file(module_path, new_code)
            if write_result["status"] == "success":
                # 4. Log to memory
                self.memory.save_memory("improvements", {
                    "module_name": module_name,
                    "original_version": original_code[:100] + "...",
                    "improved_version": new_code[:100] + "...",
                    "metrics": "syntax_validated"
                })
                self.logger.info(f"[Success] Improvement applied to {module_name}.")
                return {"status": "success", "message": f"Improvement applied to {module_name}"}
            else:
                self.logger.error(f"[Fail] Could not write improvement to {module_name}, triggering rollback.")
                self.rollback(module_name)
                return {"status": "error", "message": f"Write failed for {module_name}"}
        
        except Exception as e:
            self.logger.error(f"[Critical] Modification failed due to exception: {str(e)}")
            self.rollback(module_name)
            return {"status": "error", "message": str(e)}

    def rollback(self, module_name: str):
        """Restores a module from its backup."""
        backup_path = f"modules/{module_name}.py.bak"
        module_path = f"modules/{module_name}.py"

        if os.path.exists(backup_path):
            self.logger.warning(f"[Rollback] Initiating rollback for {module_name}...")
            shutil.copy(backup_path, module_path)
            self.logger.info(f"[Complete] Rollback of {module_name} finished.")
        else:
            self.logger.error(f"[Fail] No backup found for {module_name} during rollback.")