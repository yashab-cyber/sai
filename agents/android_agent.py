import os
import sys
import time
import json
import socketio
import base64
import threading
import socket
import concurrent.futures

from modules.device_plugins.android_companion import DeviceControl

HUB_URL = "auto"  # Set to "auto" to automatically find the SAI Hub, e.g. on 10.x.x.x hotspot networks
TOKEN = "jarvis_network_key"
DEVICE_ID = "android_phone"

def _scan_subnet_for_hub(port=5000, timeout=0.3):
    """Scan local subnet for SAI Hub. Handles 192.168.x.x and 10.x.x.x networks automatically."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connects to an external IP to determine the local IP routing source
        s.connect(('8.8.8.8', 80))
        my_ip = s.getsockname()[0]
        s.close()
    except Exception:
        my_ip = "127.0.0.1"
        return None
    
    subnet = '.'.join(my_ip.split('.')[:3])
    print(f"[*] Scanning subnet {subnet}.0/24 (from {my_ip}) for SAI Hub on port {port}...")
    
    def check_host(ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            result = s.connect_ex((ip, port))
            s.close()
            # If the port is open and we found a hub
            if result == 0:
                return ip
        except Exception:
            pass
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        # Range 1 to 255 handles standard subnets for hotspots and home routers
        futures = {executor.submit(check_host, f"{subnet}.{i}"): i for i in range(1, 255)}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                return f"http://{result}:{port}"
    return None

def discover_hub():
    if HUB_URL != "auto":
        return HUB_URL
        
    print("[*] Searching for S.A.I. Hub on local network...")
    
    # Phase 1: Try subnet scan (Works flawlessly on Android Hotspots like 10.x.x.x)
    hub = _scan_subnet_for_hub()
    if hub:
        print(f"[+] Found S.A.I. Hub via scan: {hub}")
        return hub
    
    print("[-] No SAI Hub found on network. Falling back to localhost.")
    return "http://localhost:5000"

ACTUAL_HUB_URL = discover_hub()

sio = socketio.Client()
control = DeviceControl()

@sio.event(namespace='/agent')
def connect():
    print("[+] Connected to SAI Hub. Authenticating...")
    sio.emit('agent_connect', {
        "token": TOKEN,
        "device_id": DEVICE_ID,
        "device_type": "android"
    }, namespace='/agent')
    print(f"[+] Authenticated as '{DEVICE_ID}'. Listening for commands...")

@sio.event(namespace='/agent')
def connect_error(data):
    print(f"[-] Connection error: {data}")

@sio.event(namespace='/agent')
def disconnect():
    print("[-] Disconnected from SAI Hub.")

@sio.on('execute', namespace='/agent')
def on_execute(data):
    command_id = data.get("command_id")
    command = data.get("command")
    params = data.get("params", {})
    
    print(f"[>] {command}: {params}")
    response = {}
    
    try:
        if command == "open_app":
            pkg = params.get("package", "com.whatsapp")
            success = control.open_app(pkg)
            response = {"status": "success" if success else "error"}
            
        elif command == "tap":
            x, y = params.get("x"), params.get("y")
            success = control.tap(x, y)
            response = {"status": "success" if success else "error"}
            
        elif command == "type":
            text = params.get("text")
            success = control.type(text)
            response = {"status": "success" if success else "error"}
            
        elif command == "get_screen_text":
            text = control.get_screen_text()
            response = {"status": "success", "data": text}

        elif command == "send_message":
            app = params.get("app")
            contact = params.get("contact")
            msg = params.get("message")
            success = control.send_message(app, contact, msg)
            response = {"status": "success" if success else "error"}
            
        else:
            response = {"status": "error", "message": f"Command '{command}' not implemented in new Android Agent."}
            
    except Exception as e:
        response = {"status": "error", "message": str(e)}
        
    sio.emit('agent_response', {"command_id": command_id, "response": response}, namespace='/agent')

if __name__ == "__main__":
    while True:
        try:
            print(f"[*] Connecting to {ACTUAL_HUB_URL}")
            sio.connect(ACTUAL_HUB_URL, namespaces=['/agent'])
            sio.wait()
        except socketio.exceptions.ConnectionError:
            print("Retrying connection in 5 seconds...")
            time.sleep(5)
