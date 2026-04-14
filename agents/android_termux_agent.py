import os
import sys
import time
import json
import socketio
import subprocess

HUB_URL = "http://192.168.1.10:5000"  # Replace with actual Pi/Hub IP
TOKEN = "jarvis_network_key"
DEVICE_ID = "android_phone"

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

if __name__ == "__main__":
    while True:
        try:
            print(f"[*] Connecting to {HUB_URL}")
            sio.connect(HUB_URL, namespaces=['/agent'])
            sio.wait()
        except socketio.exceptions.ConnectionError:
            time.sleep(5)
