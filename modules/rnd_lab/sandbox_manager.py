import subprocess
import os
import json
import logging
import time

logger = logging.getLogger(__name__)

class SandboxManager:
    """
    Responsible for creating Docker containers, enforcing isolation,
    mounting /workspace, executing commands inside the container,
    and capturing logs.
    """

    def __init__(self, image: str = "python:3.10-slim", memory_limit: str = "512m", cpuset_cpus: str = "0"):
        self.image = image
        self.memory_limit = memory_limit
        self.cpuset_cpus = cpuset_cpus
        self.workspace_dir = os.path.abspath(os.path.join(os.getcwd(), "workspace"))
        os.makedirs(self.workspace_dir, exist_ok=True)

    def run_command(self, cmd: str, timeout: int = 60) -> dict:
        """
        Runs a command inside an isolated Docker container.
        """
        docker_cmd = [
            "docker", "run", "--rm",
            f"--memory={self.memory_limit}",
            f"--cpuset-cpus={self.cpuset_cpus}",
            "-v", f"{self.workspace_dir}:/workspace",
            "-w", "/workspace",
            self.image,
            "sh", "-c", cmd
        ]

        logger.info(f"Running in sandbox: {cmd}")
        
        start_time = time.time()
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            execution_time = time.time() - start_time
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "execution_time": execution_time
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "exit_code": -1,
                "execution_time": timeout
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error running docker: {str(e)}",
                "exit_code": -2,
                "execution_time": time.time() - start_time
            }
