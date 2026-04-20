import os
import tempfile
import subprocess
import shutil

def run_in_sandbox(script_path, timeout=10):
    """Basic sandbox using subprocess with timeout."""
    try:
        # Run the script with python
        # In a real sandbox we might use docker or restrict permissions
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            # We would drop privileges here if we were running as root
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired as e:
        return {
            "status": "timeout",
            "exit_code": -1,
            "stdout": e.stdout.decode('utf-8') if e.stdout else "",
            "stderr": e.stderr.decode('utf-8') if e.stderr else f"Execution timed out after {timeout} seconds."
        }
    except Exception as e:
         return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e)
        }

print(run_in_sandbox("/bin/ls")) # Expecting fail since it's python running ls
