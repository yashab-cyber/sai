import subprocess
import os
import shutil
import logging
from typing import Dict, Any, Optional
from core.safety import SafetyManager

class Executor:
    """
    The Tool Execution Layer. 
    Orchestrates all system interactions through safety filters.
    """
    
    def __init__(self, safety: SafetyManager):
        self.safety = safety
        self.logger = logging.getLogger("SAI.Executor")

    def execute_shell(self, command: str) -> Dict[str, Any]:
        """Runs a shell command after safety validation."""
        if not self.safety.is_command_safe(command):
            return {"status": "error", "message": f"Command '{command}' is not whitelisted."}
        
        try:
            # Handle backgrounding natively to prevent blocking
            if command.strip().endswith("&"):
                self.logger.info(f"Launching background process: {command}")
                subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return {"status": "success", "message": "Process launched in background."}

            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            return {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode
            }
        except Exception as e:
            self.logger.error(f"Execution failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def write_file(self, path: str, content: str, allow_core: bool = False) -> Dict[str, Any]:
        """Writes content to a file after path validation."""
        try:
            safe_path = self.safety.validate_path(path, is_write=True, allow_core=allow_core)
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, "w") as f:
                f.write(content)
            return {"status": "success", "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def read_file(self, path: str) -> Dict[str, Any]:
        """Reads content from a file after path validation."""
        try:
            safe_path = self.safety.validate_path(path)
            if not os.path.exists(safe_path):
                return {"status": "error", "message": "File not found"}
            with open(safe_path, "r") as f:
                return {"status": "success", "content": f.read()}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """Deletes a file, or clears all contents of a directory (preserving the directory itself)."""
        try:
            safe_path = self.safety.validate_path(path)
            if os.path.isdir(safe_path):
                # Clear contents but keep the directory — prevents "directory not found" loops
                deleted_count = 0
                for item in os.listdir(safe_path):
                    item_path = os.path.join(safe_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                    deleted_count += 1
                return {"status": "success", "message": f"Cleared {deleted_count} items from {path}. Directory preserved."}
            elif os.path.exists(safe_path):
                os.remove(safe_path)
                return {"status": "success", "message": f"Deleted file: {path}"}
            else:
                return {"status": "error", "message": f"Path not found: {path}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    def install_package(self, package: str) -> Dict[str, Any]:
        """Installs a whitelisted package."""
        if not self.safety.validate_package(package):
            return {"status": "error", "message": f"Package {package} is not whitelisted."}
        return self.execute_shell(f"pip install {package}")
