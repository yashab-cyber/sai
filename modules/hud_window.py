import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import os
import logging

class HUDWindow:
    """
    A small, always-on-top desktop window that displays SAI's current vision state.
    """
    def __init__(self, image_path="logs/hud.png", refresh_ms=2000):
        self.image_path = image_path
        self.refresh_ms = refresh_ms
        self.root = None
        self.label = None
        self.thread = None
        self.running = False
        self.logger = logging.getLogger("SAI.HUD")

    def start(self):
        """Starts the HUD window in a separate thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.root = tk.Tk()
            self.root.title("SAI VISION HUD")
            # Set window size and position (Bottom Right)
            self.root.geometry("320x180-30-30") 
            self.root.attributes("-topmost", True)
            self.root.overrideredirect(False) # Keep borders for now
            
            self.label = tk.Label(self.root, bg="black")
            self.label.pack(expand=True, fill="both")
            
            self._update_image()
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"HUD Window error: {e}")
            self.running = False

    def _update_image(self):
        if not self.running or not self.root:
            return
            
        try:
            if os.path.exists(self.image_path):
                img = Image.open(self.image_path)
                # Aspect ratio friendly resize
                img.thumbnail((320, 180), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.label.config(image=photo)
                self.label.image = photo # Keep reference
        except Exception as e:
            pass # Ignore read errors during writes
            
        self.root.after(self.refresh_ms, self._update_image)

    def stop(self):
        self.running = False
        if self.root:
            self.root.destroy()
