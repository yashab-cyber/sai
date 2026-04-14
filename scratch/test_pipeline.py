import sys; from unittest.mock import MagicMock; sys.modules["pyautogui"] = MagicMock(); sys.modules["pynput"] = MagicMock(); sys.modules["pynput.keyboard"] = MagicMock()
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logging
from sai import SAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def main():
    print("--- Initialize S.A.I Unified Pipeline ---")
    bot = SAI()
    
    # Mocking a connected device so selection passes
    bot.device_manager.register_device("mock_android_01", "android", "192.168.1.99")
    
    intent = {
        "action": "send_message",
        "app": "whatsapp",
        "target": "Dad",
        "message": "Hello from the new Vision-capable SAI Pipeline!"
    }
    
    print("\n--- 1. Planner / Router Layer ---")
    res = bot.command_router.route_task(intent)
    if res.get("status") == "error":
        print("Failed to route task")
        return
    plan = res["plan"]
    
    if plan.get("status") == "error":
        print(f"Failed to route task: {plan}")
        return
        
    print(f"\nCreated Execution Plan for Device: {plan['device_id']}")
    for i, step in enumerate(plan['steps']):
        print(f"  Step {i+1}: [{step['type'].upper()}] - {step}")
        
    print("\n--- 2. Feedback Loop & Vision Execution (Steps 5 & 6) ---")
    result = bot.feedback_loop.execute_plan(plan)
    
    print("\n--- 3. Final State Manager Validation (Step 7 Example) ---")
    if result["status"] == "success":
        print("[SUCCESS] Pipeline Complete. The orchestration successfully bridged Commands and Vision interactions.")
    else:
        print(f"[FAILED] Pipeline Failed: {result.get('message')}")
        
    task_state = bot.state_manager.get_task("pipeline_rt")
    print(f"Task Tracked Status: {task_state['status'] if task_state else 'Unknown'}")

if __name__ == "__main__":
    main()
