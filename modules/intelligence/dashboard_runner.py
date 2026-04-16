"""
Dashboard Runner — Manages Streamlit process lifecycle.

Launches, monitors, and stops Streamlit dashboard processes.
"""

import os
import signal
import logging
import subprocess
import time
import requests
from typing import Optional

logger = logging.getLogger("SAI.Intelligence.DashboardRunner")


class DashboardRunner:
    """Manages Streamlit dashboard subprocess."""

    def __init__(self, port: int = 8501):
        self.port = port
        self._process: Optional[subprocess.Popen] = None
        self._script_path: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Check if the dashboard process is alive."""
        return self._process is not None and self._process.poll() is None

    @property
    def url(self) -> str:
        """Returns the dashboard URL."""
        return f"http://localhost:{self.port}"

    def launch(self, script_path: str, timeout: int = 15) -> dict:
        """Launches a Streamlit dashboard.

        Args:
            script_path: Path to the .py dashboard script
            timeout: Seconds to wait for the server to start

        Returns:
            Dict with status, url, pid
        """
        if not os.path.exists(script_path):
            return {"status": "failed", "error": f"Script not found: {script_path}"}

        # Stop any existing dashboard first
        if self.is_running:
            self.stop()

        try:
            cmd = [
                "streamlit", "run", script_path,
                "--server.port", str(self.port),
                "--server.headless", "true",
                "--server.address", "0.0.0.0",
                "--browser.gatherUsageStats", "false",
                "--theme.base", "dark",
            ]

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,  # Create new process group for clean cleanup
            )
            self._script_path = script_path

            # Wait for the server to be ready
            start = time.time()
            while time.time() - start < timeout:
                if self._process.poll() is not None:
                    stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                    return {"status": "failed", "error": f"Streamlit exited: {stderr[:300]}"}

                if self._health_check():
                    logger.info("Dashboard running at %s (PID: %d)", self.url, self._process.pid)
                    return {
                        "status": "success",
                        "url": self.url,
                        "pid": self._process.pid,
                        "script": os.path.basename(script_path),
                    }
                time.sleep(1)

            # Timeout — kill and report
            self.stop()
            return {"status": "failed", "error": f"Streamlit failed to start within {timeout}s"}

        except FileNotFoundError:
            return {"status": "failed", "error": "streamlit not installed (pip install streamlit)"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def stop(self) -> dict:
        """Stops the running dashboard."""
        if not self._process:
            return {"status": "success", "message": "No dashboard running"}

        try:
            # Kill the entire process group
            os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            self._process.wait(timeout=5)
        except (ProcessLookupError, OSError):
            pass
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass

        pid = self._process.pid if self._process else None
        self._process = None
        self._script_path = None

        logger.info("Dashboard stopped (PID: %s)", pid)
        return {"status": "success", "message": f"Dashboard stopped (PID: {pid})"}

    def _health_check(self) -> bool:
        """Check if Streamlit is responding."""
        try:
            resp = requests.get(f"http://localhost:{self.port}/_stcore/health", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def status(self) -> dict:
        """Returns current dashboard status."""
        return {
            "running": self.is_running,
            "url": self.url if self.is_running else None,
            "pid": self._process.pid if self.is_running else None,
            "script": os.path.basename(self._script_path) if self._script_path else None,
        }
