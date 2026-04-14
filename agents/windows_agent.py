import os
import sys
import time
import getpass
import socketio
import subprocess
import traceback

try:
    import pyautogui
except ImportError:
    print("[-] warning: pyautogui not installed. Mouse/Keyboard commands will fail.")
    print("    Run: pip install pyautogui")
    pyautogui = None

HUB_URL = "http://localhost:5000"  # Change to the Hub's IP
TOKEN = "jarvis_network_key"
DEVICE_ID = f"windows_{getpass.getuser()}"

print(f"[*] Starting S.A.I. Windows Agent as '{DEVICE_ID}'")

# Initialize SocketIO Client
sio = socketio.Client()

@sio.event(namespace='/agent')
def connect():
    print("[+] Connected to S.A.I. Hub. Authenticating...")
    sio.emit('agent_connect', {
        "token": TOKEN,
        "device_id": DEVICE_ID,
        "device_type": "windows"
    }, namespace='/agent')

@sio.event(namespace='/agent')
def disconnect():
    print("[-] Disconnected from S.A.I. Hub.")

@sio.on('execute', namespace='/agent')
def on_execute(data):
    command_id = data.get("command_id")
    command = data.get("command")
    params = data.get("params", {})
    
    print(f"\n[>] Received Command: {command}")
    print(f"    Params: {params}")
    
    response = {"status": "error", "message": "Unknown command"}
    
    try:
        if command == "shell":
            cmd = params.get("cmd")
            # WARNING: Highly dangerous depending on network. Be careful.
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            response = {"status": "success", "stdout": result.stdout, "stderr": result.stderr}
            
        elif command == "open_app":
            app_name = params.get("app_name")
            subprocess.Popen(["start", "", app_name], shell=True)
            response = {"status": "success", "message": f"Opened {app_name}"}
        
        elif command == "mouse_move":
            if not pyautogui: raise Exception("pyautogui missing")
            x, y = params.get("x", 0), params.get("y", 0)
            pyautogui.moveTo(x, y, duration=0.25)
            response = {"status": "success", "message": f"Moved mouse to {x}, {y}"}

        elif command == "mouse_click":
            if not pyautogui: raise Exception("pyautogui missing")
            button = params.get("button", "left")
            pyautogui.click(button=button)
            response = {"status": "success", "message": f"Clicked {button} mouse button"}

        elif command == "type_text":
            if not pyautogui: raise Exception("pyautogui missing")
            text = params.get("text", "")
            pyautogui.write(text, interval=0.05)
            response = {"status": "success", "message": "Typed text successfully"}

        elif command == "press_key":
            if not pyautogui: raise Exception("pyautogui missing")
            key = params.get("key", "enter")
            pyautogui.press(key)
            response = {"status": "success", "message": f"Pressed key: {key}"}
            
    except Exception as e:
        response = {
            "status": "error", 
            "message": str(e), 
            "traceback": traceback.format_exc()
        }
    
    print(f"[<] Sending Response: {response['status']}")
    sio.emit('agent_response', {"command_id": command_id, "response": response}, namespace='/agent')

if __name__ == "__main__":
    while True:
        try:
            print(f"[*] Attempting to connect to {HUB_URL}...")
            sio.connect(HUB_URL, namespaces=['/agent'])
            sio.wait()
        except socketio.exceptions.ConnectionError:
            print("[-] Connection failed. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("[*] Shutting down agent.")
            break
