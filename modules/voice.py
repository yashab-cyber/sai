import pyttsx3
import speech_recognition as sr
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable

class VoiceManager:
    """
    Module for text-to-speech and speech-to-text.
    Voice is calibrated for JARVIS-like delivery — composed, measured, authoritative.
    """
    
    def __init__(self, sai=None):
        self.sai = sai
        self.logger = logging.getLogger("SAI.Voice")
        self.is_busy = False
        self.stop_trigger = False
        self.trigger_thread = None
        
        try:
            self.engine = pyttsx3.init()
            # JARVIS-like voice settings: measured pace, full volume
            self.engine.setProperty('rate', 140)  # Slightly slower for composed delivery
            self.engine.setProperty('volume', 1.0)
            
            # Attempt to select a deeper male voice (closest to JARVIS)
            voices = self.engine.getProperty('voices')
            if voices:
                # Prefer male English voice
                for voice in voices:
                    if 'male' in voice.name.lower() or 'english' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        self.logger.info(f"Voice profile selected: {voice.name}")
                        break
        except Exception as e:
            self.logger.warning(f"Failed to initialize TTS engine: {e}")
            self.engine = None

    def speak(self, text: str):
        """Converts text to speech."""
        if not self.engine:
            return {"status": "error", "message": "TTS engine not initialized."}
        
        self.is_busy = True
        try:
            self.logger.info(f"Speaking: {text[:30]}...")
            if self.sai and hasattr(self.sai, 'gui'):
                self.sai.gui.update(action="SPEAKING")
            
            self.engine.say(text)
            self.engine.runAndWait()
            
            if self.sai and hasattr(self.sai, 'gui'):
                self.sai.gui.update(action="SYSTEM_IDLE")
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            self.is_busy = False

    def listen(self, timeout: int = 5, phrase_time_limit: Optional[int] = None):
        """Listens for audio input and converts to text."""
        self.is_busy = True
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self.logger.info("Listening for speech...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                text = recognizer.recognize_google(audio)
                self.logger.info(f"Heard: {text}")
                return {"status": "success", "text": text}
        except sr.WaitTimeoutError:
            return {"status": "error", "message": "Listening timed out."}
        except sr.UnknownValueError:
            return {"status": "error", "message": "Speech not understood."}
        except Exception as e:
            self.logger.error(f"Voice Recognition failed: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            self.is_busy = False

    def start_voice_trigger(self, callback: Callable[[str], None]):
        """Starts background wake-word detection."""
        if self.trigger_thread and self.trigger_thread.is_alive():
            return
            
        self.stop_trigger = False
        self.trigger_thread = threading.Thread(
            target=self._voice_trigger_loop, 
            args=(callback,), 
            daemon=True
        )
        self.trigger_thread.start()
        self.logger.info("Voice trigger system ('Hi SAI') active, sir.")

    def stop_voice_trigger(self):
        """Stops background wake-word detection."""
        self.stop_trigger = True
        if self.trigger_thread:
            self.trigger_thread.join(timeout=1)
        self.logger.info("Voice trigger system deactivated.")

    def _voice_trigger_loop(self, callback: Callable[[str], None]):
        """Internal loop for wake-word detection."""
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300 # Adjust based on environment
        
        while not self.stop_trigger:
            if self.is_busy:
                time.sleep(1)
                continue
                
            try:
                with sr.Microphone() as source:
                    # Short burst listen for wake-word
                    audio = recognizer.listen(source, timeout=2, phrase_time_limit=2)
                    text = recognizer.recognize_google(audio).lower()
                    
                    if "hi sai" in text:
                        self.logger.info("Wake-word detected!")
                        # Acknowledge
                        self.speak("Yes, sir?")
                        
                        # Listen for actual command
                        command_result = self.listen(timeout=8)
                        if command_result["status"] == "success":
                            self.logger.info(f"Voice Command: {command_result['text']}")
                            callback(command_result["text"])
                        else:
                            self.speak("I'm sorry, sir, I didn't quite catch that.")
                            
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                continue
            except Exception as e:
                self.logger.debug(f"Trigger loop non-critical error: {e}")
                time.sleep(1)
