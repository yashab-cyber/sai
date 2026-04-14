class ControlManager:
    def __init__(self, executor):
        self.executor = executor
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            self.pyautogui = pyautogui
        except:
            self.pyautogui = None
            
    def execute_command(self, command):
        if not self.pyautogui: return {"status": "ignored"}
        return {"status": "success"}
