import time
import socketio
import socket
import concurrent.futures
import logging
import threading
import subprocess
import re

from modules.device_plugins.android_companion import DeviceControl

HUB_URL = "auto"  # Set to "auto" to automatically find the SAI Hub, e.g. on 10.x.x.x hotspot networks
TOKEN = "jarvis_network_key"
DEVICE_ID = "android_phone"

logger = logging.getLogger("SAI.AndroidAgent")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

is_registered = False
VISION_STREAM_INTERVAL_SEC = 1.0

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


def _local_shell(cmd: str) -> bool:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=6,
        )
        return result.returncode == 0
    except Exception:
        return False


def _local_open_app(package_name: str) -> bool:
    return _local_shell(f"am start -n {package_name}/.MainActivity") or _local_shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")


def _local_tap(x: int, y: int) -> bool:
    return _local_shell(f"input tap {int(x)} {int(y)}")


def _local_type(text: str) -> bool:
    safe = re.sub(r"\s+", "%s", str(text or "").strip())
    if not safe:
        return False
    return _local_shell(f"input text '{safe}'")

@sio.event(namespace='/agent')
def connect():
    global is_registered
    logger.info("Connected to SAI Hub transport. Authenticating agent...")
    try:
        response = sio.call(
            'agent_connect',
            {
                "token": TOKEN,
                "device_id": DEVICE_ID,
                "device_type": "android"
            },
            namespace='/agent',
            timeout=10
        )

        if isinstance(response, dict) and response.get("status") == "success":
            is_registered = True
            logger.info("Authenticated as '%s'. Listening for commands.", DEVICE_ID)
        else:
            is_registered = False
            logger.error("Agent registration rejected by hub: %s", response)
            sio.disconnect()
    except Exception as exc:
        is_registered = False
        logger.error("Agent registration failed: %s", exc)
        sio.disconnect()

@sio.event(namespace='/agent')
def connect_error(data):
    logger.error("Connection error: %s", data)

@sio.event(namespace='/agent')
def disconnect():
    global is_registered
    is_registered = False
    logger.warning("Disconnected from SAI Hub.")

@sio.on('execute', namespace='/agent')
def on_execute(data):
    command_id = data.get("command_id")
    command = data.get("command")
    params = data.get("params", {})
    
    logger.info("Command received: %s %s", command, params)
    response = {}
    
    try:
        if command == "open_app":
            pkg = params.get("package", "com.whatsapp")
            success = control.open_app(pkg)
            transport = "companion_http"
            if not success:
                success = _local_open_app(pkg)
                transport = "local_shell" if success else "failed"
            response = {"status": "success" if success else "error", "transport": transport}
            
        elif command == "tap":
            x, y = params.get("x"), params.get("y")
            success = control.tap(x, y)
            transport = "companion_http"
            if not success and x is not None and y is not None:
                success = _local_tap(int(x), int(y))
                transport = "local_shell" if success else "failed"
            response = {"status": "success" if success else "error", "transport": transport}
            
        elif command == "type":
            text = params.get("text")
            success = control.type(text)
            transport = "companion_http"
            if not success:
                success = _local_type(text)
                transport = "local_shell" if success else "failed"
            response = {"status": "success" if success else "error", "transport": transport}
            
        elif command == "get_screen_text":
            text = control.get_screen_text()
            if text:
                response = {"status": "success", "data": text, "transport": "companion_http"}
            else:
                response = {"status": "error", "message": "No screen text available", "transport": "failed"}

        elif command == "send_message":
            app = params.get("app")
            contact = params.get("contact")
            msg = params.get("message")
            success = control.send_message(app, contact, msg)
            response = {"status": "success" if success else "error", "transport": "companion_http"}
            
        else:
            response = {"status": "error", "message": f"Command '{command}' not implemented in new Android Agent."}
            
    except Exception as e:
        response = {"status": "error", "message": str(e)}
        
    sio.emit('agent_response', {"command_id": command_id, "response": response}, namespace='/agent')


def _vision_stream_loop():
    """Continuously publishes live screenshot frames to the Hub for real-time vision."""
    while True:
        try:
            if sio.connected and is_registered:
                frame_b64 = control.get_screenshot_base64()
                if frame_b64:
                    sio.emit(
                        'vision_stream',
                        {"device_id": DEVICE_ID, "frame": frame_b64},
                        namespace='/agent'
                    )
        except Exception as exc:
            logger.debug("Vision stream publish skipped: %s", exc)
        time.sleep(VISION_STREAM_INTERVAL_SEC)


HEARTBEAT_INTERVAL_SEC = 10.0

def _heartbeat_loop():
    """Sends a lightweight heartbeat to the Hub so it knows we're alive."""
    while True:
        try:
            if sio.connected and is_registered:
                sio.emit(
                    'heartbeat',
                    {"device_id": DEVICE_ID, "ts": int(time.time())},
                    namespace='/agent'
                )
        except Exception as exc:
            logger.debug("Heartbeat skipped: %s", exc)
        time.sleep(HEARTBEAT_INTERVAL_SEC)


if __name__ == "__main__":
    threading.Thread(target=_vision_stream_loop, daemon=True).start()
    threading.Thread(target=_heartbeat_loop, daemon=True).start()
    while True:
        try:
            logger.info("Connecting to %s", ACTUAL_HUB_URL)
            sio.connect(ACTUAL_HUB_URL, namespaces=['/agent'])
            sio.wait()
        except socketio.exceptions.ConnectionError:
            logger.warning("Retrying connection in 5 seconds...")
            time.sleep(5)
