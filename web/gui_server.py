from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import logging
import threading
import os
import time

app = Flask(__name__)
CORS(app)
# Allow CORS and provide a secret key for session/socket security
app.config['SECRET_KEY'] = 'sai-ultra-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Shared state for persistence and initial sync
state = {
    "thought": "Neural Command Node Standby...",
    "action": "SYSTEM_IDLE",
    "status": "online",
    "screenshot": "logs/hud.png",
    "history": [],
    "neural_load": "12%",
    "cpu_load": "48%",
    "latency": "14ms"
}

# The SAI instance will be injected after initialization
sai_instance = None

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
        # Start the task in a separate thread so the GUI doesn't block
        thread = threading.Thread(target=sai_instance.run_task, args=(command,), daemon=True)
        thread.start()
        return jsonify({"status": "success", "message": f"Task '{command}' initiated."})
    return jsonify({"status": "error", "message": "No command or SAI instance found."}), 400

@socketio.on('connect')
def handle_connect():
    emit('state_update', state)

def broadcast_state(new_state):
    """Update global state and broadcast to all connected clients."""
    state.update(new_state)
    socketio.emit('state_update', state)

def run_gui(port=5000):
    import subprocess
    import time
    
    # Panic Port Recovery: Forcefully reclaim the port if it's stuck
    try:
        # Using fuser to kill the process on the port. Silent if no process found.
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
        time.sleep(1) # Tiny grace period for OS to release resources
    except Exception as e:
        pass
        
    socketio.run(app, host='0.0.0.0', port=port, log_output=False)

class GUIManager:
    """Manages the lifecycle and real-time communication of the SAI Cockpit GUI."""
    
    def __init__(self, sai, port=5000):
        global sai_instance
        self.sai = sai
        sai_instance = sai
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

        self.logger.info(f"SAI COCKPIT ONLINE at http://localhost:{self.port}")
        return {"status": "success", "url": f"http://localhost:{self.port}"}

    def _telemetry_loop(self):
        """Polls system metrics and broadcasts them to the cockpit."""
        while True:
            try:
                if self.is_active:
                    telemetry = self.system.get_telemetry()
                    if telemetry["status"] == "success":
                        stats = telemetry["metrics"]
                        self.update(
                            cpu_load=stats["cpu_load"],
                            neural_load=stats["ram_usage"],
                            latency=stats["disk_usage"],
                            net_speed=stats["net_speed"],
                            core_temp=stats["temp"]
                        )
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Telemetry loop error: {e}")
                time.sleep(10)

    def update(self, **kwargs):
        """External interface to update the GUI state."""
        broadcast_state(kwargs)

    @property
    def is_active(self):
        return self.thread and self.thread.is_alive()