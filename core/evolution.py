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

    def propose_improvement(self, module_name: str, new_code: str, allow_core: bool = False) -> Dict[str, Any]:
        """
        Validates and applies an improvement to a module.
        Includes a rollback mechanism.
        Improves logging for better traceability.
        """
        # Safety Valve: Prevent empty code writes
        if not new_code or not str(new_code).strip():
            msg = f"Evolution rejected: Improvement code for {module_name} is empty."
            self.logger.error(msg)
            return {"status": "error", "message": msg}

        # Handle full path if provided, or assume modules/ if just a name
        if "/" in module_name:
            module_path = module_name
            module_base = os.path.basename(module_name).replace(".py", "")
        else:
            module_path = f"modules/{module_name}.py"
            module_base = module_name

        backup_path = f"{module_path}.bak"

        self.logger.info(f"[Start] Proposing improvement for {module_base}...")

        # 1. Validation
        is_valid, error_msg = self.coder.validate_code(new_code)
        if not is_valid:
            msg = f"[Fail] Improvement rejected due to invalid syntax: {error_msg}"
            self.logger.error(msg)
            return {"status": "error", "message": msg}

        # 2. Backup current version (optional if creating new)
        try:
            read_result = self.executor.read_file(module_path)
            original_code = ""
            if read_result["status"] == "success":
                original_code = read_result.get("content", "")
                
                # 2.5 Module Integrity Check
                is_intact, integrity_msg = self.coder.validate_module_integrity(original_code, new_code)
                if not is_intact:
                    msg = f"[Fail] Improvement rejected due to loss of structural integrity: {integrity_msg}"
                    self.logger.error(msg)
                    return {"status": "error", "message": msg}

                with open(backup_path, "w") as f:
                    f.write(original_code)
                    self.logger.info(f"[Backup] Created backup for {module_base}.")
            else:
                self.logger.info(f"[New] Module {module_base} does not exist yet. Creating as new.")

            # 3. Apply update
            write_result = self.executor.write_file(module_path, new_code, allow_core=allow_core)
            if write_result["status"] == "success":
                # 4. Log to memory
                self.memory.save_memory("improvements", {
                    "module_name": module_base,
                    "original_version": original_code[:100] + "...",
                    "improved_version": new_code[:100] + "...",
                    "metrics": "syntax_validated",
                    "core_evolution": allow_core
                })
                self.logger.info(f"[Success] Improvement applied to {module_base}.")
                return {"status": "success", "message": f"Improvement applied to {module_base}"}
            else:
                msg = f"[Fail] Could not write improvement to {module_base}: {write_result.get('message')}"
                self.logger.error(msg)
                self.rollback(module_name)
                return {"status": "error", "message": msg}
        
        except Exception as e:
            msg = f"[Critical] Modification failed due to exception: {str(e)}"
            self.logger.error(msg)
            self.rollback(module_name)
            return {"status": "error", "message": msg}

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