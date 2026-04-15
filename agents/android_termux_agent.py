import os
import sys
import time
import json
import socketio
import subprocess

HUB_URL = "auto"  # Set to "auto" to detect S.A.I. Hub automatically
TOKEN = "jarvis_network_key"
DEVICE_ID = "android_phone"


def _scan_subnet_for_hub(port=5000, timeout=0.3):
    """Scan local subnet for SAI Hub when mDNS fails."""
    import socket
    import concurrent.futures
    
    # Get our own IP to determine subnet
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        my_ip = s.getsockname()[0]
        s.close()
    except Exception:
        return None
    
    subnet = '.'.join(my_ip.split('.')[:3])
    print(f"[*] Scanning subnet {subnet}.0/24 for SAI Hub on port {port}...")
    
    def check_host(ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            result = s.connect_ex((ip, port))
            s.close()
            if result == 0 and ip != my_ip:
                return ip
        except Exception:
            pass
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_host, f"{subnet}.{i}"): i for i in range(1, 255)}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                return f"http://{result}:{port}"
    return None

def discover_hub():
    if HUB_URL != "auto":
        return HUB_URL
        
    # Phase 1: Try mDNS
    print("[*] Searching for S.A.I. Hub (mDNS) on local network...")
    try:
        from zeroconf import Zeroconf, ServiceBrowser
        import threading
        import socket
        import time

        found_url = []
        
        class MyListener:
            def remove_service(self, zeroconf, type, name): pass
            def update_service(self, zeroconf, type, name): pass
            def add_service(self, zeroconf, type, name):
                info = zeroconf.get_service_info(type, name)
                if info:
                    ip = socket.inet_ntoa(info.addresses[0])
                    found_url.append(f"http://{ip}:{info.port}")

        zc = Zeroconf()
        browser = ServiceBrowser(zc, "_sai._tcp.local.", MyListener())
        
        timeout = 5
        while not found_url and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
            
        zc.close()
        if found_url:
            print(f"[+] Found S.A.I. Hub via mDNS: {found_url[0]}")
            return found_url[0]
            
        print("[-] mDNS discovery timed out. Trying subnet scan...")
    except ImportError:
        print("[-] zeroconf not available. Trying subnet scan...")
    
    # Phase 2: Subnet scan fallback
    hub = _scan_subnet_for_hub()
    if hub:
        print(f"[+] Found S.A.I. Hub via scan: {hub}")
        return hub
    
    print("[-] No SAI Hub found on network. Falling back to localhost.")
    return "http://localhost:5000"

ACTUAL_HUB_URL = discover_hub()

sio = socketio.Client()

def run_termux_cmd(parts):
    # Relies on the termux-api package being installed 
    # e.g., pkg install termux-api
    try:
        # Use shell=True for single string commands, or list for parts
        is_shell = isinstance(parts, str)
        res = subprocess.run(parts, capture_output=True, text=True, shell=is_shell, timeout=15)
        
        status = "success" if res.returncode == 0 else "error"
        return {
            "status": status, 
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "code": res.returncode
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
    
    if command == "open_app":
        # Open any app by package name.
        # Monkey is the most reliable "universal launcher" by package name
        pkg = params.get("package", "com.whatsapp")
        print(f"[*] Attempting to launch package: {pkg}")
        response = run_termux_cmd(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        
        # Fallback to direct 'am' if monkey is missing
        if response.get("status") != "success":
            response = run_termux_cmd(["am", "start", "--user", "0", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", pkg])
        
    elif command == "shell":
        # Execute raw shell command
        cmd = params.get("cmd") or params.get("command")
        if cmd:
            print(f"[*] Running shell: {cmd}")
            response = run_termux_cmd(cmd)
        else:
            response = {"status": "error", "message": "Missing 'cmd' parameter"}

    elif command == "am_intent":
        # Send raw Android intent
        intent = params.get("intent")
        extras = params.get("extras", "")
        if intent:
            response = run_termux_cmd(f"am start -a {intent} {extras}")
        else:
            response = {"status": "error", "message": "Missing 'intent' parameter"}
            
    elif command == "battery":
        response = run_termux_cmd(["termux-battery-status"])
        
    elif command == "send_sms":
        num = params.get("number")
        text = params.get("text")
        response = run_termux_cmd(["termux-sms-send", "-n", num, text])
        
    elif command == "tts":
        text = params.get("text")
        response = run_termux_cmd(["termux-tts-speak", text])
        
    else:
        response = {"status": "error", "message": f"Command '{command}' not implemented in agent side."}
        
    sio.emit('agent_response', {"command_id": command_id, "response": response}, namespace='/agent')


import base64
import threading

def vision_loop():
    print("[*] Vision stream started...")
    tmp_path = "/data/data/com.termux/files/usr/tmp/screencap.png"
    while True:
        if sio.connected:
            try:
                # Try getting screencap. Often requires rooted Termux.
                res = subprocess.run(["su", "-c", f"screencap -p {tmp_path}"], capture_output=True)
                if res.returncode != 0: # fallback
                    res = subprocess.run(["screencap", "-p", tmp_path], capture_output=True)
                
                if os.path.exists(tmp_path):
                    with open(tmp_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    sio.emit('vision_stream', {"device_id": DEVICE_ID, "frame": b64}, namespace='/agent')
            except Exception as e:
                pass
        time.sleep(3)  # Mobile network optimization

threading.Thread(target=vision_loop, daemon=True).start()

if __name__ == "__main__":

    while True:
        try:
            print(f"[*] Connecting to {ACTUAL_HUB_URL}")
            sio.connect(ACTUAL_HUB_URL, namespaces=['/agent'])
            sio.wait()
        except socketio.exceptions.ConnectionError:
            time.sleep(5)
