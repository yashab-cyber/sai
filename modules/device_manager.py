
import logging

try:
    from modules.device_plugins.windows_plugin import WindowsDevicePlugin
    from modules.device_plugins.android_plugin import AndroidDevicePlugin
except ImportError:
    pass

import threading
import time
import uuid
from typing import Dict, Any, Optional

class DeviceManager:
    """
    Registry for connected remote agents (Windows, Android, etc.) across the local network.
    Manages state and acts as a router for commands.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SAI.DeviceManager")
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.pending_commands: Dict[str, Dict[str, Any]] = {}
        self.command_queues: Dict[str, list] = {}  # Task execution pipeline queue
        self.lock = threading.Lock()
        self.on_command_dispatch = None

    def register_device(self, device_id: str, device_type: str, ip_address: str) -> bool:
        """Registers a device when it connects and processes any queued tasks."""
        with self.lock:
            self.devices[device_id] = {
                "type": device_type,
                "ip": ip_address,
                "status": "online",
                "last_seen": time.time()
            }
            if device_id not in self.command_queues:
                self.command_queues[device_id] = []
        self.logger.info(f"Device registered: {device_id} ({device_type}) at {ip_address}")
        
        # Process task queue on reconnection
        threading.Thread(target=self._process_queue, args=(device_id,), daemon=True).start()
        return True

    def _process_queue(self, device_id: str):
        with self.lock:
            queued_cmds = list(self.command_queues.get(device_id, []))
            self.command_queues[device_id] = []
            
        for cmd_item in queued_cmds:
            self.logger.info(f"Executing queued command '{cmd_item['command']}' for {device_id}")
            self.route_command(device_id, cmd_item['command'], cmd_item['params'], timeout=cmd_item['timeout'])

    def unregister_device(self, device_id: str):
        """Marks a device as offline when it disconnects."""
        with self.lock:
            if device_id in self.devices:
                self.devices[device_id]["status"] = "offline"
                self.logger.info(f"Device offline: {device_id}")

    def list_devices(self) -> Dict[str, Any]:
        """Provides the AI with a list of currently known devices on the network."""
        with self.lock:
            return {"status": "success", "devices": self.devices}

    def route_command(self, device_id: str, command: str, params: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
        """Routes a command. If the device is offline, it queues the command automatically."""
        with self.lock:
            if device_id not in self.devices or self.devices[device_id]["status"] != "online":
                if device_id not in self.command_queues:
                    self.command_queues[device_id] = []
                self.command_queues[device_id].append({
                    "command": command,
                    "params": params,
                    "timeout": timeout
                })
                self.logger.info(f"Device '{device_id}' offline. Queued command '{command}'.")
                return {"status": "queued", "message": f"Command '{command}' queued automatically."}
        
        command_id = str(uuid.uuid4())
        event = threading.Event()
        
        with self.lock:
            self.pending_commands[command_id] = {"event": event, "response": None}
            
        self.logger.info(f"Routing command '{command}' to {device_id}...")
        
        if self.on_command_dispatch:
            try:
                self.on_command_dispatch(device_id, command_id, command, params)
            except Exception as e:
                self.logger.error(f"Dispatch failed: {e}")
                return {"status": "error", "message": f"Failed to send to comm layer: {str(e)}"}
        else:
            return {"status": "error", "message": "Communication layer not initialized."}
            
        success = event.wait(timeout)
        
        with self.lock:
            pending = self.pending_commands.pop(command_id, None)
            
        if success and pending and pending["response"] is not None:
            return pending["response"]
        else:
            # Retry logic: Re-queue if timed out
            self.logger.warning(f"Command '{command}' to '{device_id}' timed out. Re-queuing.")
            with self.lock:
                self.command_queues[device_id].append({
                    "command": command,
                    "params": params,
                    "timeout": timeout
                })
            return {"status": "error", "message": f"Command timed out. Queued for retry."}

    def resolve_command(self, command_id: str, response: Dict[str, Any]):
        """Called by the WebSocket listener when a device replies to a command."""
        with self.lock:
            if command_id in self.pending_commands:
                self.pending_commands[command_id]["response"] = response
                self.pending_commands[command_id]["event"].set()
                self.logger.debug(f"Command {command_id} resolved successfully.")
