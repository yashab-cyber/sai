import pyttsx3
import speech_recognition as sr
import logging
from typing import Dict, Any, Optional

class VoiceManager:
    """
    Module for text-to-speech and speech-to-text.
    """
    
    def __init__(self, sai=None):
        self.sai = sai
        self.logger = logging.getLogger("SAI.Voice")
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)
            self.engine.setProperty('volume', 1.0)
        except Exception as e:
            self.logger.warning(f"Failed to initialize TTS engine: {e}")
            self.engine = None

    def speak(self, text: str):
        """Converts text to speech."""
        if not self.engine:
            return {"status": "error", "message": "TTS engine not initialized."}
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

    def listen(self, timeout: int = 5):
        """Listens for audio input and converts to text."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self.logger.info("Listening for speech...")
                audio = recognizer.listen(source, timeout=timeout)
                text = recognizer.recognize_google(audio)
                self.logger.info(f"Heard: {text}")
                return {"status": "success", "text": text}
        except ImportError:
            return {"status": "error", "message": "Speech recognition library not installed."}
        except OSError as e:
            if "No Default Input Device" in str(e):
                return {"status": "error", "message": "No microphone detected. Please connect a microphone or check your sound settings."}
            return {"status": "error", "message": f"Audio hardware error: {e}"}
        except sr.WaitTimeoutError:
            return {"status": "error", "message": "Listening timed out. No speech detected."}
        except sr.UnknownValueError:
            return {"status": "error", "message": "Speech not understood."}
        except Exception as e:
            self.logger.error(f"Voice Recognition failed: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}
