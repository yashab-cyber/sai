


import os
import sys
import yaml
import logging
import re
import time
import threading
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load .env at the very beginning
load_dotenv()

# Import Core
from core.safety import SafetyManager
from core.executor import Executor
from core.memory import MemoryManager
from core.brain import Brain
from modules.evolution import EvolutionEngine
from modules.control import ControlManager
from modules.vision import VisionManager
from modules.interaction import InteractionEngine
from modules.state_manager import StateManager
from modules.command_router import CommandRouter
from modules.feedback_loop import FeedbackLoop
from modules.voice import VoiceManager
from web.dashboard import DashboardManager
from modules.browser import BrowserManager
from web.gui_server import GUIManager
from core.tools import ToolManifest
from core.reflection import ReflectionEngine

# Import Modules
from modules.planner import Planner
from modules.coder import Coder
from modules.analyzer import Analyzer
from modules.file_manager import FileManager
from modules.hud_window import HUDWindow
from modules.system_manager import SystemManager
from modules.device_manager import DeviceManager

class SAI:
    """
    Main Orchestrator for Self-Adaptive Intelligence.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self._load_config(config_path)
        self._setup_logging()
        self.logger = logging.getLogger("SAI")
        
        # Initialize Core
        self.safety = SafetyManager(self.config['safety']['base_dir'])
        self.executor = Executor(self.safety)
        self.memory = MemoryManager(self.config['memory']['db_path'])
        self.brain = Brain()
        
        # Initialize Modules
        self.device_manager = DeviceManager()
        self.planner = Planner(self.brain)
        self.coder = Coder(self.executor)
        self.analyzer = Analyzer(self.memory, self.config['safety']['base_dir'])
        self.file_manager = FileManager(self.executor)
        
        # Initialize Evolution
        self.evolution = EvolutionEngine(self.executor, self.memory, self.coder)
        self.control = ControlManager(self.executor)
        self.vision = VisionManager(sai_instance=self)
        self.interaction = InteractionEngine(self)
        self.state_manager = StateManager()
        self.command_router = CommandRouter(self)
        self.feedback_loop = FeedbackLoop(self)


        self.voice = VoiceManager(self)
        self.dashboard = DashboardManager()
        browser_config = self.config.get('browser', {})
        self.browser = BrowserManager(
            headless=browser_config.get('headless', True),
            timeout=int(browser_config.get('timeout', 30000)),
            locale=browser_config.get('locale', "en-US"),
            timezone=browser_config.get('timezone', "UTC")
        )
        self.gui = GUIManager(self)
        self.system = SystemManager(self.executor)
        self.hud_window = HUDWindow()
        self.reflection = ReflectionEngine(self.brain, self.evolution)
        self.is_running = False
        
        logging.info("S.A.I. systems initialized. All modules operational, sir.")

    def _load_config(self, path: str):
        """Loads YAML config and interpolates ${VAR} or ${VAR:-default} placeholders."""
        with open(path, "r") as f:
            raw_yaml = f.read()
            
        # Pattern to find ${VAR_NAME} or ${VAR_NAME:-default}
        pattern = re.compile(r'\$\{(?P<var>[A-Z0-9_]+)(?::-(?P<default>[^}]*))?\}')

        def replace_match(match):
            var_name = match.group('var')
            default_val = match.group('default')
            return os.getenv(var_name, default_val if default_val is not None else match.group(0))

        interpolated_yaml = pattern.sub(replace_match, raw_yaml)
        self.config = yaml.safe_load(interpolated_yaml)

    def _setup_logging(self):
        logging.basicConfig(
            level=self.config['system']['log_level'],
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("logs/sai.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def run_task(self, task: str, max_iterations=25):
        """Standardizes autonomous execution loop with thread-safe perception and stuck-loop detection."""
        if self.is_running:
            self.logger.warning("Another process is currently running, sir.")
            return
            
        self.is_running = True
        print(f"\n[S.A.I.] Very good, sir. Initializing directive: {task}")
        history = []
        _consecutive_fails = 0
        _last_action_key = None
        
        try:
            for i in range(max_iterations):
                print(f"  [Processing] Tactical iteration {i+1}, sir...")
                
                # Sense: Update Vision HUD
                hud_shot = self.vision.capture_screen("logs/hud.png")
                screenshot_path = None
                if hud_shot.get("status") == "success":
                    screenshot_path = hud_shot["path"]
                    self.gui.update(screenshot=screenshot_path)
                
                # 1. Determine next best step
                response = self.planner.determine_next_step(task, history, image_path=screenshot_path)
                
                thought = response.get("thought", "Thinking...")
                tool_name = response.get("tool")
                params = response.get("parameters", {})
                
                # Update GUI Status (Thoughts and Operation)
                self.gui.update(thought=thought, action=f"{tool_name}({params})")
                
                status = response.get("status", "ongoing")
                
                print(f"  > Analysis: {thought}")
                
                if status == "completed":
                    print("🏁 Objective achieved, sir. Standing by for further directives.")
                    break
                    
                if not tool_name:
                    print("⚠️ No further action required at this time, sir.")
                    break

                # ── Stuck-Loop Detection ──
                action_key = f"{tool_name}:{sorted(params.items()) if isinstance(params, dict) else params}"
                if action_key == _last_action_key:
                    _consecutive_fails += 1
                else:
                    _consecutive_fails = 0
                _last_action_key = action_key
                
                if _consecutive_fails >= 3:
                    print("⚠️  Sir, I appear to be caught in a loop — repeating the same action without progress.")
                    print("    I'd recommend we reassess the approach. Breaking tactical loop.")
                    self.gui.update(
                        thought="I've detected a tactical loop, sir. The same action has failed 3 consecutive times. Awaiting new directive.",
                        action="LOOP_BREAK"
                    )
                    break

                # 2. Execute Action
                print(f"  > Executing: {tool_name}...")
                action_result = self.execute_tool(tool_name, params)
                
                # 3. Observe
                observation = str(action_result)
                
                # Prevent Token Overflow: Truncate large results
                if len(observation) > 10000:
                    self.logger.warning(f"Observation truncated from {len(observation)} to 10000 chars.")
                    observation = observation[:10000] + "\n...[TRUNCATED FOR SYSTEM STABILITY]..."
                
                print(f"  > Result: {observation[:100]}...")
                
                # 4. Record to history
                history.append({
                    "action": f"{tool_name}({params})",
                    "observation": observation
                })
                
                # 5. Store in persistent memory
                self.memory.save_memory("history", {
                    "task_id": str(hash(task)),
                    "query": task,
                    "action": f"{tool_name}",
                    "result": observation,
                    "status": status
                })
                
                # Settle time: help prevent rapid-fire interaction issues on slow sites
                time.sleep(1)

            # Final Reflection
            self.reflection.reflect_on_task(task, history)
            self.gui.update(status="online")
            print("✅ Mission complete, sir. All systems nominal.")
            self.is_running = False
        finally:
            self.logger.info("Cleaning up tactical logs...")
            self._cleanup_perception_logs()
            # Clean up the browser session for this specific thread
            self.browser.close()

    def handle_voice_command(self, text: str):
        """Callback for background voice trigger."""
        if self.is_running:
            self.logger.warning("Already executing a directive, sir. Ignoring voice command.")
            return

        self.logger.info(f"Voice directive received: {text}")
        # Run the task in a separate thread so we don't block the voice trigger system permanently 
        # (though VoiceManager will be 'busy' anyway)
        task_thread = threading.Thread(target=self.run_task, args=(text,), daemon=True)
        task_thread.start()

    def _cleanup_perception_logs(self):
        """Removes temporary visual logs created during the task."""
        import glob
        log_dir = "logs"
        if not os.path.exists(log_dir):
            return
            
        # Target HUD shots and other tool-generated screenshots
        patterns = ["hud*.png", "screenshot*.png", "browser_shot*.png"]
        for pattern in patterns:
            for file_path in glob.glob(os.path.join(log_dir, pattern)):
                try:
                    os.remove(file_path)
                    self.logger.info(f"Cleaned up temporary log: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete {file_path}: {e}")

    def start_chat(self):
        """Persistent Interactive Chat REPL — JARVIS Protocol."""
        print("\n" + "═"*50)
        print("  S.A.I. TACTICAL INTERFACE — ONLINE")
        print("═"*50)
        print("Good day, sir. All systems are operational.")
        print("How may I be of assistance?")
        
        while True:
            try:
                user_input = input("\n[USER] > ").strip()
                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("[S.A.I.] Very well, sir. Powering down all systems. It's been a pleasure.")
                    break
                
                if not user_input:
                    continue
                    
                self.run_task(user_input)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[S.A.I.] I'm afraid we have a situation, sir: {str(e)}")

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Dispatches to the appropriate module tool."""
        if not tool_name:
            return {"status": "info", "message": "No tool requested for this step."}

        self.logger.info(f"Executing tool: {tool_name} with params {params}")
        
        try:
            # File Operations
            if tool_name == "files.write":
                return self.file_manager.safe_write(params['path'], params['content'], allow_core=params.get('allow_core', False))
            elif tool_name == "files.read":
                return self.file_manager.safe_read(params['path'])
            elif tool_name == "files.list":
                return self.file_manager.list_files(params.get('path', '.'))
            elif tool_name == "files.delete":
                return self.file_manager.delete_file(params['path'])
            elif tool_name == "files.append":
                return self.file_manager.safe_append(params['path'], params['content'])
            
            # Browser Operations
            elif tool_name == "browser.search":
                return self.browser.search(params['query'])
            elif tool_name == "browser.navigate":
                return self.browser.navigate(params['url'])
            elif tool_name == "browser.interact":
                action = params['action']
                if action == "click":
                    return self.browser.click(params['selector'])
                elif action == "type":
                    return self.browser.type_text(params['selector'], params['text'])
                elif action == "screenshot":
                    return self.browser.capture_screenshot()
                elif action == "back":
                    return self.browser.navigate_back()
                elif action == "press":
                    return self.browser.press_key(params.get('selector'), params['key'])
            elif tool_name == "browser.wait":
                return self.browser.wait_for(params['selector'], params.get('state', 'visible'))
            elif tool_name == "browser.explore":
                return self.browser.get_interactive_elements()
            elif tool_name == "browser.scrape":
                return self.browser.scrape_page_text()
            
            # Coder Operations
            elif tool_name == "coder.write":
                return self.coder.write_module(params['path'], params['code'])
            elif tool_name == "coder.replace_string":
                return self.coder.replace_string(params['path'], params['old_string'], params['new_string'])
            elif tool_name == "coder.replace_function":
                return self.coder.replace_function(params['path'], params['function_name'], params['new_function_code'])
            elif tool_name == "coder.lint":
                return self.coder.lint_code(params['path'])
            elif tool_name == "coder.format":
                return self.coder.format_code(params['path'])
            elif tool_name == "coder.test":
                return self.coder.run_tests(params['path'])
            
            # Analyzer & Evolution
            elif tool_name == "analyzer.scan":
                return self.analyzer.scan_codebase()
            elif tool_name == "evolution.improve":
                return self.evolution.propose_improvement(
                    params['module_name'], 
                    params['new_code'], 
                    allow_core=params.get('allow_core', False)
                )
            
            # Shell
            elif tool_name == "executor.shell":
                return self.executor.execute_shell(params['command'])
            
            # Control Operations
            elif tool_name == "control.mouse":
                if params['action'] == "move":
                    return self.control.mouse_move(params['x'], params['y'])
                elif params['action'] == "click":
                    return self.control.mouse_click(params.get('x'), params.get('y'), params.get('button', 'left'))
            elif tool_name == "control.keyboard":
                if params['action'] == "type":
                    return self.control.keyboard_type(params['content'])
                elif params['action'] == "press":
                    return self.control.keyboard_press(params['content'])
            
            # Vision Operations
            elif tool_name == "vision.capture":
                if params['action'] == "capture":
                    return self.vision.capture_screen()
                elif params['action'] == "find":
                    return self.vision.find_image(params['target'])
            elif tool_name == "vision.ocr":
                return self.vision.ocr_image(params['target'])
            
            # Voice Operations
            elif tool_name == "voice.speak":
                return self.voice.speak(params['text'])
            elif tool_name == "voice.listen":
                return self.voice.listen()
                
            # Advanced Orchestration
            elif tool_name == "control.windows":
                if params['action'] == "list":
                    return self.control.windows.list_windows()
                elif params['action'] == "focus":
                    return self.control.windows.focus_window(params['title'])
                elif params['action'] == "active":
                    return self.control.windows.get_active_window()
                    
            elif tool_name == "system.dashboard":
                if params['action'] == "start":
                    return self.dashboard.start()
            
            elif tool_name == "system.gui":
                if params['action'] == "start":
                    return self.gui.start()
            
            elif tool_name == "network.list":
                return self.device_manager.list_devices()
            elif tool_name == "network.execute":
                return self.device_manager.route_command(params['device_id'], params['command'], params.get('params', {}))
            
            elif tool_name == "system.ask":
                print(f"\n[SAI PROMPT] {params['prompt']}")
                user_res = input("Your response: ").strip()
                return {"status": "success", "response": user_res}

            elif tool_name == "system.speak":
                return self.voice.speak(params['text'])

            elif tool_name == "system.telemetry":
                return self.system.get_telemetry()
            
            elif tool_name == "system.cleanup":
                return self.system.cleanup_workspace()

            elif tool_name == "system.window_layout":
                return self.control.windows.set_layout(params['mode'])

            elif tool_name == "system.open_mode":
                mode = params['mode'].lower()
                if mode == "research":
                    self.execute_tool("executor.shell", {"command": "chromium &"})
                    self.execute_tool("executor.shell", {"command": "mousepad &"})
                    return {"status": "success", "message": "Research mode activated (Browser + Editor)."}
                elif mode == "coding":
                    self.execute_tool("executor.shell", {"command": "gnome-terminal &"})
                    self.execute_tool("executor.shell", {"command": "code &"})
                    return {"status": "success", "message": "Coding mode activated (Terminal + VS Code)."}
                elif mode == "writing":
                    self.execute_tool("executor.shell", {"command": "chromium &"})
                    self.execute_tool("executor.shell", {"command": "mousepad &"})
                    return {"status": "success", "message": "Writing mode activated (Browser + Editor)."}
                return {"status": "error", "message": f"Unknown mode: {mode}"}
                
            else:
                return {"status": "error", "message": f"Tool {tool_name} not found."}
        except KeyError as e:
            return {"status": "error", "message": f"Missing parameter: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def self_improve(self):
        """Self-Modification Loop — JARVIS Evolution Protocol."""
        print("\n🧬 If I may, sir — initiating self-diagnostic and improvement protocol...")
        self.analyzer.scan_codebase()
        
        # Simulating a self-improvement proposal
        # In practice, the Brain would analyze metrics and propose this
        print("🔍 Analysis complete, sir. I've identified potential optimizations in the coder module...")
        
        proposal = self.brain.prompt(
            "Analyze modules/coder.py for improvements.",
            "Write an improved version of coder.py with more robust error handling."
        )
        
        # For demo purposes, we don't actually let the mock brain overwrite code 
        # unless requested by a real task, but the engine is ready.
        print("🛠️ Evolution engine standing by, sir. Ready to implement improvements on your command.")

if __name__ == "__main__":
    sai = SAI()
    if "--chat" in sys.argv:
        sai.start_chat()
    elif len(sys.argv) > 1:
        sai.run_task(" ".join(sys.argv[1:]))
        
        # Keep process alive if GUI or Dashboard was started
        if sai.gui.is_active or sai.dashboard.is_active:
            print("\n📡 S.A.I. PERSISTENCE MODE — All systems nominal, sir.")
            print("The tactical interface is operational. Press Ctrl+C when you wish to power down.")
            try:
                while sai.gui.is_active or sai.dashboard.is_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Understood, sir. Initiating graceful shutdown sequence...")
                sai.gui.update(status="offline")
                sys.exit(0)
    else:
        print("S.A.I. v1.1.0 — JARVIS Protocol Active")
        print("At your service, sir. Usage: python3 sai.py --chat  OR  python3 sai.py 'directive'")
