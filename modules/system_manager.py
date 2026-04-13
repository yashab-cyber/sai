import logging
import re
from typing import Dict, Any

class SystemManager:
    """
    Handles high-level system monitoring and process orchestration.
    """
    def __init__(self, executor):
        self.executor = executor
        self.logger = logging.getLogger("SAI.System")
        self.last_net_bytes = 0
        self.last_net_time = 0

    def get_telemetry(self) -> Dict[str, Any]:
        """Gathers real-time performance metrics including network and thermal."""
        import time
        telemetry = {
            "cpu_load": "0%",
            "ram_usage": "0%",
            "disk_usage": "0%",
            "net_speed": "0 KB/s",
            "temp": "N/A"
        }
        
        try:
            # 1. CPU Load & Temp via uptime/sensors
            uptime_res = self.executor.execute_shell("uptime")
            if uptime_res["status"] == "success":
                match = re.search(r"load average:\s+([\d.]+)", uptime_res["stdout"])
                if match:
                    load = float(match.group(1))
                    telemetry["cpu_load"] = f"{min(int(load * 100 / 4), 100)}%"

            sensor_res = self.executor.execute_shell("sensors")
            if sensor_res["status"] == "success":
                # Find line with temp1: +65.5°C
                match = re.search(r"temp1:\s+\+([\d.]+)", sensor_res["stdout"])
                if match:
                    telemetry["temp"] = f"{match.group(1)}°C"

            # 2. RAM Usage via free
            ram_res = self.executor.execute_shell("free -m")
            if ram_res["status"] == "success":
                lines = ram_res["stdout"].split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    total, used = int(parts[1]), int(parts[2])
                    telemetry["ram_usage"] = f"{int((used / total) * 100)}%"

            # 3. Disk Usage via df
            disk_res = self.executor.execute_shell("df -h /")
            if disk_res["status"] == "success":
                lines = disk_res["stdout"].split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    for part in parts:
                        if "%" in part:
                            telemetry["disk_usage"] = part
                            break
                            
            # 4. Network Speed via /proc/net/dev
            net_res = self.executor.execute_shell("cat /proc/net/dev")
            if net_res["status"] == "success":
                # Sum bytes from all interfaces except lo
                lines = net_res["stdout"].split("\n")
                current_bytes = 0
                for line in lines:
                    if ":" in line and "lo:" not in line:
                        parts = line.split(":")[1].split()
                        current_bytes += int(parts[0]) # Receive bytes
                
                now = time.time()
                if self.last_net_time > 0:
                    dt = now - self.last_net_time
                    speed = (current_bytes - self.last_net_bytes) / dt / 1024 # KB/s
                    telemetry["net_speed"] = f"{int(speed)} KB/s"
                
                self.last_net_bytes = current_bytes
                self.last_net_time = now

            return {"status": "success", "metrics": telemetry}
        except Exception as e:
            self.logger.error(f"Telemetry error: {e}")
            return {"status": "error", "message": str(e)}

    def cleanup_workspace(self, confirm=True) -> Dict[str, Any]:
        """Closes all non-essential whitelisted productivity apps."""
        apps_to_kill = ["mousepad", "chromium", "firefox", "vlc"]
        results = []
        
        for app in apps_to_kill:
            res = self.executor.execute_shell(f"pkill {app}")
            results.append({"app": app, "status": res["status"]})
            
        self.logger.info("Workspace cleanup completed.")
        return {"status": "success", "actions": results}
