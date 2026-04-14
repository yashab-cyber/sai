import os
import sys
import time
import json
import socketio
import subprocess

HUB_URL = "auto"  # Set to "auto" to detect S.A.I. Hub automatically
TOKEN = "jarvis_network_key"
DEVICE_ID = "android_phone"


def discover_hub():
    if HUB_URL != "auto":
        return HUB_URL
        
    print("[*] Searching for S.A.I. Hub (mDNS) on local network...")
    try:
        from zeroconf import Zeroconf, ServiceBrowser
        import threading
        import socket
        import time
    except ImportError:
        print("[-] zeroconf missing. Run: pip install zeroconf")
        return "http://localhost:5000"

    found_url = []
    
    class MyListener:
        def remove_service(self, zeroconf, type, name): pass
        def add_service(self, zeroconf, type, name):
            info = zeroconf.get_service_info(type, name)
            if info:
                ip = socket.inet_ntoa(info.addresses[0])
                found_url.append(f"http://{ip}:{info.port}")

    zc = Zeroconf()
    browser = ServiceBrowser(zc, "_sai._tcp.local.", MyListener())
    
    timeout = 10
    while not found_url and timeout > 0:
        time.sleep(0.5)
        timeout -= 0.5
        
    zc.close()
    if found_url:
        print(f"[+] Found S.A.I. Hub at: {found_url[0]}")
        return found_url[0]
        
    print("[-] Auto-discovery timed out.")
    return "http://localhost:5000"

ACTUAL_HUB_URL = discover_hub()

sio = socketio.Client()

def run_termux_cmd(parts):
    # Relies on the termux-api package being installed 
    # e.g., pkg install termux-api
    try:
        res = subprocess.run(parts, capture_output=True, text=True)
        return {"status": "success", "stdout": res.stdout}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@sio.event(namespace='/agent')
def connect():
    print("[+] Connected. Authenticating...")
    sio.emit('agent_connect', {
        "token": TOKEN,
        "device_id": DEVICE_ID,
        "device_type": "android"
    }, namespace='/agent')

@sio.on('execute', namespace='/agent')
def on_execute(data):
    command_id = data.get("command_id")
    command = data.get("command")
    params = data.get("params", {})
    
    print(f"[>] {command}: {params}")
    response = {}
    
    if command == "open_app":
        # Open WhatsApp or Spotify using intents
        pkg = params.get("package", "com.whatsapp")
        response = run_termux_cmd(["am", "start", "-n", f"{pkg}/.Main"])
        
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
        response = {"status": "error", "message": "Unknown command"}
        
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
