import subprocess
import os
import shutil
import logging
from typing import Dict, Any, Optional
from core.safety import SafetyManager
from core.dependencies import DependencyManager

class Executor:
    """
    The Tool Execution Layer. 
    Orchestrates all system interactions through safety filters.
    Includes Universal Docker Sandboxing for untrusted operations.
    """
    
    def __init__(self, safety: SafetyManager):
        self.safety = safety
        self.logger = logging.getLogger("SAI.Executor")
        self.workspace_dir = os.path.abspath(os.path.join(os.getcwd(), "workspace"))
        os.makedirs(self.workspace_dir, exist_ok=True)
        self.deps = DependencyManager(self.workspace_dir)

    def execute_sandboxed(self, command: str, image: str = "python:3.10-slim", timeout: int = 60, auto_install: bool = True) -> Dict[str, Any]:
        """
        Executes a shell command inside an ephemeral Docker sandbox to securely isolate untrusted code.
        """
        # If it's a python file execution, let's scan for dependencies first
        if auto_install and command.startswith("python "):
            parts = command.split()
            if len(parts) >= 2 and parts[1].endswith(".py"):
                filepath = parts[1]
                if not filepath.startswith("/"):
                    filepath = os.path.join(self.workspace_dir, filepath)
                if os.path.exists(filepath):
                    with open(filepath, "r") as f:
                        code = f.read()
                        imports = self.deps.scan_code_for_imports(code)
                        pip_pkgs = self.deps.resolve_pip_names(imports)
                        if pip_pkgs:
                            pkg_str = " ".join(pip_pkgs)
                            self.logger.info(f"Auto-resolving Sandbox dependencies: {pkg_str}")
                            # Prepend pip install to the command
                            command = f"pip install {pkg_str} > /dev/null && {command}"

        docker_cmd = [
            "docker", "run", "--rm",
            "--memory=512m",
            "--cpuset-cpus=0",
            "-v", f"{self.workspace_dir}:/workspace",
            "-w", "/workspace",
            image,
            "sh", "-c", command
        ]
        
        self.logger.info(f"Executing in SANDBOX: {command}")
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            res = {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode,
                "sandboxed": True
            }
            
            # Phase 5: Self-healing missing modules
            output_content = result.stderr + "\n" + result.stdout
            if result.returncode != 0 and "ModuleNotFoundError" in output_content and auto_install:
                missing = self.deps.extract_missing_module_from_error(output_content)
                if missing:
                    self.logger.info(f"Sandbox detected missing module '{missing}'. Auto-healing...")
                    pip_name = list(self.deps.resolve_pip_names({missing}))[0]
                    # Retry with explicitly installed package
                    retry_cmd = f"pip install {pip_name} > /dev/null && {command}"
                    return self.execute_sandboxed(retry_cmd, image, timeout, auto_install=False)
                    
            return res
            
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Sandbox execution timed out.", "sandboxed": True}
        except Exception as e:
            return {"status": "error", "message": f"Sandbox error: {str(e)}", "sandboxed": True}

    def execute_shell(self, command: str, force_sandbox: bool = False, auto_install: bool = True) -> Dict[str, Any]:
        """Runs a shell command after safety validation, routing unsafe/unrecognized commands to the Docker sandbox."""
        if force_sandbox or not self.safety.is_command_safe(command):
            self.logger.warning(f"Command not host-whitelisted or sandbox forced, routing to Docker Sandbox: '{command}'")
            return self.execute_sandboxed(command, auto_install=auto_install)
        
        # Self-healing host injection: if python execution, pre-scan and install host dependencies
        if auto_install and command.startswith("python "):
            parts = command.split()
            if len(parts) >= 2 and parts[1].endswith(".py"):
                filepath = parts[1]
                if not filepath.startswith("/"):
                    filepath = os.path.join(self.workspace_dir, filepath)
                if os.path.exists(filepath):
                    with open(filepath, "r") as f:
                        imports = self.deps.scan_code_for_imports(f.read())
                        pip_pkgs = self.deps.resolve_pip_names(imports)
                        if pip_pkgs:
                            self.logger.info(f"Host script scan found dependencies: {pip_pkgs}. Ensuring they exist...")
                            self.deps.ensure_host_dependencies(pip_pkgs)

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
            
            res = {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode
            }
            
            # Auto-healing post-execution: Catch ModuleNotFoundError gracefully
            output_content = result.stderr + "\n" + result.stdout
            if result.returncode != 0 and "ModuleNotFoundError" in output_content and auto_install:
                missing = self.deps.extract_missing_module_from_error(output_content)
                if missing:
                    self.logger.info(f"Host detected missing module '{missing}'. Auto-healing...")
                    pip_name = list(self.deps.resolve_pip_names({missing}))[0]
                    self.deps.ensure_host_dependencies({pip_name})
                    self.logger.info(f"Retrying host command: {command}")
                    return self.execute_shell(command, force_sandbox, auto_install=False)
                    
            return res
            
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
