from typing import Dict, Any, List
import os
from core.executor import Executor

class FileManager:
    """
    Self-improvable module for file system operations.
    Acts as a higher-level abstraction for the executor.
    """
    
    def __init__(self, executor: Executor):
        self.executor = executor
        self.safety = executor.safety

    def create_project_structure(self, base_path: str, folders: List[str]):
        """Creates a set of folders in the workspace."""
        for folder in folders:
            path = f"{base_path}/{folder}"
            self.executor.execute_shell(f"mkdir -p {path}")

    def list_files(self, path: str = ".") -> List[str]:
        """Lists files in a given directory safely."""
        try:
            valid_path = self.safety.validate_path(path, is_write=False)
            # Use whitelisted shell command with a validated absolute path
            cmd = f"ls -R {valid_path} -I venv -I .git -I __pycache__"
            result = self.executor.execute_shell(cmd)
            if result["status"] == "success":
                return result["stdout"].split("\n")
            return []
        except Exception:
            return []

    def safe_read(self, path: str) -> str:
        """Reads a file safely, validating the path first."""
        try:
            valid_path = self.safety.validate_path(path, is_write=False)
            with open(valid_path, "r") as f:
                return f.read()
        except PermissionError as e:
            return f"SAFETY LIMITATION: {str(e)}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def safe_write(self, path: str, content: str, allow_core: bool = False) -> Dict[str, Any]:
        """Writes to a file safely, validating the path first."""
        # Pass the request to the executor which handles the safety check
        return self.executor.write_file(path, content, allow_core=allow_core)

    def delete_file(self, path: str) -> Dict[str, Any]:
        """Deletes a file or directory safely."""
        return self.executor.delete_file(path)

    def safe_append(self, path: str, content: str) -> Dict[str, Any]:
        """Appends content to a file safely, validating the path first."""
        try:
            safe_path = self.safety.validate_path(path, is_write=True)
            with open(safe_path, "a") as f:
                f.write(content)
            return {"status": "success", "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}
