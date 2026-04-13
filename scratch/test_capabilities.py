import sys
import os
sys.path.append(os.getcwd())

from modules.control import ControlManager
from modules.vision import VisionManager
from modules.voice import VoiceManager

def test_modules():
    print("Testing ControlManager...")
    try:
        control = ControlManager()
        # Test move (small safe movement)
        res = control.mouse_move(100, 100, duration=0.1)
        print(f"Control: {res}")
    except Exception as e:
        print(f"Control Failed: {e}")

    print("\nTesting VisionManager...")
    try:
        vision = VisionManager()
        res = vision.capture_screen("logs/test_screenshot.png")
        print(f"Vision: {res}")
        if os.path.exists("logs/test_screenshot.png"):
            print("Screenshot successful.")
    except Exception as e:
        print(f"Vision Failed: {e}")

    print("\nTesting VoiceManager...")
    try:
        voice = VoiceManager()
        if voice.engine:
            print("TTS Engine initialized.")
            # We won't call speak() as it might block or fail if no audio device
        else:
            print("Voice Engine not available (expected in some headless setups).")
    except Exception as e:
        print(f"Voice Failed: {e}")

if __name__ == "__main__":
    test_modules()
