from flask import Flask, render_template, send_from_directory, jsonify
import threading
import logging
import os

app = Flask(__name__)

# Global state for the dashboard
state = {
    "thought": "Initializing...",
    "action": "Waiting for tasks",
    "status": "online",
    "screenshot": "logs/screenshot.png"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    return jsonify(state)

@app.route('/logs/<path:filename>')
def custom_static(filename):
    return send_from_directory('../logs', filename)

def run_flask(port=5050):
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

class DashboardManager:
    """Manages the lifecycle of the SAI Web Dashboard."""
    
    def __init__(self, port=5050):
        self.port = port
        self.thread = None
        self.logger = logging.getLogger("SAI.Dashboard")

    def start(self):
        """Starts the dashboard in a background thread."""
        if self.thread and self.thread.is_alive():
            return {"status": "error", "message": "Dashboard already running."}
        
        self.thread = threading.Thread(target=run_flask, args=(self.port,), daemon=True)
        self.thread.start()
        self.logger.info(f"Dashboard started on port {self.port}")
        return {"status": "success", "url": f"http://localhost:{self.port}"}

    def update_state(self, thought=None, action=None, status=None):
        """Updates the state displayed on the dashboard."""
        if thought: state["thought"] = thought
        if action: state["action"] = action
        if status: state["status"] = status

    @property
    def is_active(self):
        return self.thread and self.thread.is_alive()
