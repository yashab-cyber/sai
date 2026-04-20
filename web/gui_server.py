from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import logging
import threading
import os
import time

app = Flask(__name__)
CORS(app)

# Suppress werkzeug per-request INFO logs (GET /logs/hud.png spam)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
# Allow CORS and provide a secret key for session/socket security
app.config['SECRET_KEY'] = os.environ.get('SAI_SECRET_KEY', 'sai-ultra-secret')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Shared state for persistence and initial sync
state = {
    "thought": "Systems nominal, sir. All modules operational and standing by for your directive.",
    "action": "STANDBY",
    "status": "online",
    "screenshot": "logs/hud.png",
    "history": [],
    "neural_load": "12%",
    "cpu_load": "48%",
    "latency": "14ms"
}
voice_transcripts = []
idle_logs = []  # Circular buffer of idle engine events

# The SAI instance will be injected after initialization
sai_instance = None


def add_idle_log(entry: dict):
    """Add an idle engine event to the log buffer and broadcast via SocketIO."""
    entry.setdefault("timestamp", time.time())
    idle_logs.append(entry)
    if len(idle_logs) > 200:
        del idle_logs[:-200]
    socketio.emit('idle_log_update', entry, namespace='/')

    # Also push to the main event log stream
    event_type = entry.get("type", "")
    event_msgs = {
        "action_start": "⚡ Idle: Starting autonomous action...",
        "action_complete": f"✅ Idle: {entry.get('action', '?')} [{entry.get('status', '?')}] (#{entry.get('total', 0)})",
        "action_error": f"❌ Idle error: {str(entry.get('error', ''))[:80]}",
        "pipeline_start": f"🔧 Pipeline: {entry.get('action', '?')}",
        "pipeline_end": f"{'✅' if entry.get('status') == 'success' else '❌'} Pipeline done: {entry.get('action', '?')} [{entry.get('status', '?')}]",
        "pipeline_error": f"❌ Pipeline error: {str(entry.get('error', ''))[:80]}",
        "phase": f"   ▸ Phase: {(entry.get('phase', '')).upper()}",
        "phase_complete": f"   ✓ {(entry.get('phase', '')).upper()} complete",
        "phase_error": f"   ✗ {entry.get('phase', '')} failed",
        "quality_gate_failed": f"🚫 Quality gate failed ({entry.get('rounds', 0)} rounds)",
        "next_cooldown": f"⏱ Next action in {entry.get('seconds', 0)}s",
    }
    msg = event_msgs.get(event_type)
    if msg:
        push_event(msg)

# Changed to serve the React app directly
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web-ui', 'dist')
    if path and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    if os.path.exists(os.path.join(dist_dir, 'index.html')):
        return send_from_directory(dist_dir, 'index.html')
    else:
        return "<p>React build not found. Please run <code>npm run build</code> in <code>web-ui</code>.</p>", 404

@app.route('/logs/<path:filename>')
def serve_logs(filename):
    return send_from_directory('../logs', filename)

@app.route('/api/command', methods=['POST'])
def handle_command():
    data = request.json
    command = data.get("command")
    if command and sai_instance:
        push_event(f"📡 Command received: {command}")
        def _run_async_wrapper():
            import asyncio
            sai_instance._gui_task = True  # Flag so system.ask skips blocking input()
            try:
                asyncio.run(sai_instance.run_task(command))
            finally:
                sai_instance._gui_task = False

        # Start the task in a separate thread so the GUI doesn't block
        thread = threading.Thread(target=_run_async_wrapper, daemon=True)
        thread.start()
        return jsonify({"status": "success", "message": f"Task '{command}' initiated."})
    return jsonify({"status": "error", "message": "No command or SAI instance found."}), 400

@socketio.on('connect')
def handle_connect():
    # Send initial state + a startup event if history is empty
    if not state["history"]:
        state["history"].append({"action": "🟢 SAI Cockpit connected. Systems online."})
    emit('state_update', state)

def broadcast_state(new_state):
    """Update global state and broadcast to all connected clients."""
    state.update(new_state)
    socketio.emit('state_update', state)


def push_event(text: str):
    """Append an event to the history log and broadcast it."""
    state["history"].append({"action": text})
    # Keep history bounded
    if len(state["history"]) > 200:
        state["history"] = state["history"][-200:]
    socketio.emit('state_update', {"history": state["history"]})


def add_voice_transcript(entry):
    voice_transcripts.append(entry)
    if len(voice_transcripts) > 100:
        del voice_transcripts[:-100]
    socketio.emit('voice_transcript_update', entry, namespace='/')


# --- AGENT COMMUNICATION LAYER ---
agent_sessions = {}  # device_id -> socket_sid

@socketio.on('agent_connect', namespace='/agent')
def handle_agent_connect(auth):
    if sai_instance and hasattr(sai_instance, 'safety'):
        if not sai_instance.safety.is_ip_allowed(request.remote_addr):
            return {"status": "error", "message": "IP network blocked by safety"}

    token = auth.get("token")
    if token != os.environ.get("SAI_NETWORK_TOKEN", "jarvis_network_key"):
        return {"status": "error", "message": "Unauthorized"}
    
    device_id = auth.get("device_id")
    device_type = auth.get("device_type", "unknown")
    if not device_id:
        return {"status": "error", "message": "Missing device_id"}
        
    ip_addr = request.remote_addr
    agent_sessions[device_id] = request.sid
    logging.getLogger("SAI.GUI").debug(f"AGENT_CONNECT: {device_id} mapped to SID={request.sid}")
    if sai_instance and hasattr(sai_instance, 'device_manager'):
        sai_instance.device_manager.register_device(device_id, device_type, ip_addr)
        
    return {"status": "success", "message": "Welcome to SAI Hub."}


@socketio.on('vision_stream', namespace='/agent')
def handle_vision_stream(data):
    device_id = data.get("device_id")
    frame_b64 = data.get("frame")
    if device_id and frame_b64:
        sai = app.config.get('SAI_INSTANCE')
        if hasattr(sai, 'device_manager'):
            sai.device_manager.latest_frames[device_id] = frame_b64
            # Update last_seen — vision frames count as heartbeat
            sai.device_manager.receive_heartbeat(device_id)
            # Forward the frame to the frontend for real-time monitoring
            socketio.emit('device_vision_update', {"device_id": device_id, "frame": frame_b64}, namespace='/')

        if hasattr(sai, 'vision_intelligence'):
            parsed = sai.vision_intelligence.parse_screenshot_base64(frame_b64)
            socketio.emit(
                'device_vision_parsed_update',
                {
                    "device_id": device_id,
                    "parsed": parsed
                },
                namespace='/'
            )


@socketio.on('heartbeat', namespace='/agent')
def handle_agent_heartbeat(data):
    """Lightweight heartbeat from agents — keeps device marked as online."""
    device_id = data.get("device_id") if isinstance(data, dict) else None
    if device_id and sai_instance and hasattr(sai_instance, 'device_manager'):
        sai_instance.device_manager.receive_heartbeat(device_id)



@app.route('/api/vision/latest', methods=['GET'])
def get_latest_vision():
    device_id = request.args.get("device_id", "android_phone")
    sai = app.config.get('SAI_INSTANCE')
    if not sai or not hasattr(sai, 'device_manager'):
        return jsonify({"status": "error", "message": "SAI instance unavailable"}), 500

    frame_b64 = sai.device_manager.latest_frames.get(device_id)
    if not frame_b64:
        return jsonify({"status": "error", "message": "No frame available", "device_id": device_id}), 404

    parsed = {}
    if hasattr(sai, 'vision_intelligence'):
        parsed = sai.vision_intelligence.parse_screenshot_base64(frame_b64)

    return jsonify({
        "status": "success",
        "device_id": device_id,
        "frame": frame_b64,
        "parsed": parsed
    })


@app.route('/api/voice/transcripts', methods=['GET'])
def get_voice_transcripts():
    try:
        limit = int(request.args.get("limit", 25))
    except (ValueError, TypeError):
        limit = 25
    limit = max(1, min(limit, 100))
    return jsonify({
        "status": "success",
        "items": voice_transcripts[-limit:]
    })


@app.route('/api/devices', methods=['GET'])
def get_devices():
    sai = app.config.get('SAI_INSTANCE')
    if not sai or not hasattr(sai, 'device_manager'):
        return jsonify({"status": "error", "devices": []}), 500

    devices_raw = sai.device_manager.list_devices().get('devices', {})
    items = []
    for device_id, meta in devices_raw.items():
        items.append({
            "device_id": device_id,
            "device_type": meta.get("type", "unknown"),
            "status": meta.get("status", "unknown")
        })
    return jsonify({"status": "success", "devices": items})


@app.route('/api/idle/status', methods=['GET'])
def get_idle_status():
    """Returns the current state of the idle engine."""
    sai = app.config.get('SAI_INSTANCE')
    if not sai or not hasattr(sai, 'idle_engine'):
        return jsonify({"status": "error", "message": "Idle engine not available"}), 500

    ie = sai.idle_engine
    return jsonify({
        "status": "success",
        "enabled": ie._enabled,
        "running": ie._running,
        "paused": ie._paused,
        "actions_executed": ie._actions_executed,
        "min_cooldown": ie._min_cooldown,
        "max_cooldown": ie._max_cooldown,
        "last_action_time": ie._last_action_time,
        "action_in_progress": ie._action_in_progress,
    })


@app.route('/api/idle/logs', methods=['GET'])
def get_idle_logs():
    """Returns recent idle engine log entries."""
    try:
        limit = int(request.args.get("limit", 50))
    except (ValueError, TypeError):
        limit = 50
    limit = max(1, min(limit, 200))
    return jsonify({
        "status": "success",
        "items": idle_logs[-limit:]
    })


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Returns current SAI settings."""
    sai = app.config.get('SAI_INSTANCE')
    if not sai:
        return jsonify({"status": "error"}), 500

    settings = {
        "idle_enabled": getattr(sai.idle_engine, '_enabled', False) if hasattr(sai, 'idle_engine') else False,
        "idle_min_cooldown": getattr(sai.idle_engine, '_min_cooldown', 120) if hasattr(sai, 'idle_engine') else 120,
        "idle_max_cooldown": getattr(sai.idle_engine, '_max_cooldown', 300) if hasattr(sai, 'idle_engine') else 300,
        "email_enabled": hasattr(sai, 'email_manager') and sai.email_manager is not None,
        "voice_enabled": hasattr(sai, 'voice') and sai.voice is not None,
        "brain_provider": getattr(sai.brain, 'provider', 'unknown') if hasattr(sai, 'brain') else 'unknown',
        "brain_model": getattr(sai.brain, 'model_name', 'unknown') if hasattr(sai, 'brain') else 'unknown',
        "safety_level": getattr(sai.safety, 'level', 'STRICT') if hasattr(sai, 'safety') else 'STRICT',
    }
    return jsonify({"status": "success", "settings": settings})


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Updates SAI settings at runtime."""
    sai = app.config.get('SAI_INSTANCE')
    if not sai:
        return jsonify({"status": "error"}), 500

    data = request.json or {}
    updated = []

    if hasattr(sai, 'idle_engine'):
        ie = sai.idle_engine
        if "idle_enabled" in data:
            ie._enabled = bool(data["idle_enabled"])
            updated.append("idle_enabled")
        if "idle_min_cooldown" in data:
            ie._min_cooldown = max(30, int(data["idle_min_cooldown"]))
            updated.append("idle_min_cooldown")
        if "idle_max_cooldown" in data:
            ie._max_cooldown = max(ie._min_cooldown + 10, int(data["idle_max_cooldown"]))
            updated.append("idle_max_cooldown")

    return jsonify({"status": "success", "updated": updated})

@socketio.on('agent_response', namespace='/agent')

def handle_agent_response(data):
    if sai_instance and hasattr(sai_instance, 'device_manager'):
        sai_instance.device_manager.resolve_command(data.get("command_id"), data.get("response"))

@socketio.on('disconnect', namespace='/agent')
def handle_agent_disconnect():
    for dev_id, sid in list(agent_sessions.items()):
        if sid == request.sid:
            del agent_sessions[dev_id]
            if sai_instance and hasattr(sai_instance, 'device_manager'):
                sai_instance.device_manager.unregister_device(dev_id)
            break

def run_gui(port=5000):
    import subprocess
    import time
    
    # Panic Port Recovery: Forcefully reclaim the port if it's stuck
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
        time.sleep(1)
    except Exception:
        pass
    
    # Advertise via mDNS so agents can auto-discover the Hub
    try:
        from zeroconf import Zeroconf, ServiceInfo
        import socket
        local_ip = get_local_ip()
        info = ServiceInfo(
            "_sai._tcp.local.",
            "SAI Hub._sai._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={"version": "1.1.0"},
        )
        zc = Zeroconf()
        zc.register_service(info)
        logging.getLogger("SAI.GUI").info(f"mDNS service registered: _sai._tcp.local. at {local_ip}:{port}")
    except Exception as e:
        logging.getLogger("SAI.GUI").debug(f"mDNS registration skipped: {e}")
        
    socketio.run(app, host='0.0.0.0', port=port, log_output=False)

import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class GUIManager:
    """Manages the lifecycle and real-time communication of the SAI Cockpit GUI."""
    
    def __init__(self, sai, port=5000):
        global sai_instance
        self.sai = sai
        sai_instance = sai
        app.config['SAI_INSTANCE'] = sai
        self.port = port
        self.thread = None
        self.logger = logging.getLogger("SAI.GUI")

    def start(self):
        """Starts the GUI server and the telemetry poller in background threads."""
        if self.thread and self.thread.is_alive():
            return {"status": "error", "message": "GUI already running."}
        
        # Injected system manager for live stats
        from modules.system_manager import SystemManager
        self.system = SystemManager(self.sai.executor)

        self.thread = threading.Thread(target=run_gui, args=(self.port,), daemon=True)
        self.thread.start()

        # Telemetry Background Task
        self.telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.telemetry_thread.start()

        # Voice Trigger Background Task (New)
        if hasattr(self.sai, 'voice'):
            self.sai.voice.set_transcript_callback(add_voice_transcript)
            self.sai.voice.start_voice_trigger(self.sai.handle_voice_command)

        # Hook DeviceManager dispatch to SocketIO
        if hasattr(self.sai, 'device_manager'):
            def _dispatch(device_id, command_id, command, params):
                sid = agent_sessions.get(device_id)
                self.logger.debug(f"DISPATCH: device={device_id}, sid={sid}, cmd={command}, all_sessions={agent_sessions}")
                if sid:
                    socketio.emit("execute", {
                        "command_id": command_id,
                        "command": command,
                        "params": params
                    }, to=sid, namespace='/agent')
                    time.sleep(0)  # Yield thread so the packet flushes
                    self.logger.debug(f"DISPATCH: emit sent for {command_id}")
                else:
                    raise Exception(f"No active socket session for {device_id}")
            self.sai.device_manager.on_command_dispatch = _dispatch

            # Start the device heartbeat monitor
            self.sai.device_manager.start_heartbeat()

        self.logger.info(f"SAI COCKPIT ONLINE at http://localhost:{self.port} and http://{get_local_ip()}:{self.port}")

        # Hook Idle Engine to broadcast events to GUI
        if hasattr(self.sai, 'idle_engine'):
            self.sai.idle_engine.set_gui_callback(add_idle_log)

        # Hook Action Pipeline to broadcast phase updates to GUI
        if hasattr(self.sai, 'action_pipeline'):
            self.sai.action_pipeline.set_gui_callback(add_idle_log)

        return {"status": "success", "url": f"http://{get_local_ip()}:{self.port}"}

    def _telemetry_loop(self):
        """Polls system metrics and broadcasts them to the cockpit."""
        while True:
            try:
                if self.is_active:
                    telemetry = self.system.get_telemetry()
                    if telemetry["status"] == "success":
                        stats = telemetry["metrics"]
                        devs = {}
                        if hasattr(self.sai, 'device_manager'):
                            devs = self.sai.device_manager.list_devices().get('devices', {})
                        
                        self.update(
                            cpu_load=stats["cpu_load"],
                            neural_load=stats["ram_usage"],
                            latency=stats["disk_usage"],
                            net_speed=stats["net_speed"],
                            core_temp=stats["temp"],
                            devices=devs
                        )
                else:
                    break # Stop looping if inactive
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Telemetry loop error: {e}")
                time.sleep(10)

    def stop(self):
        """Stops the GUI server and associated background tasks."""
        if hasattr(self.sai, 'voice'):
            self.sai.voice.stop_voice_trigger()
        
        # Flask-SocketIO in daemon thread won't stop easily, but we signal pollers to stop
        self.logger.info("GUI systems powering down...")
        return {"status": "success", "message": "GUI systems powering down."}

    def update(self, **kwargs):
        """External interface to update the GUI state."""
        broadcast_state(kwargs)

    @property
    def is_active(self):
        return self.thread and self.thread.is_alive()