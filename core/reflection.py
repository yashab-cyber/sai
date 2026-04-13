import logging
from typing import List, Dict, Any
from core.brain import Brain
from core.evolution import EvolutionEngine

class ReflectionEngine:
    """
    The Meta-Analysis Layer.
    Reviews SAI's performance and triggers proactive self-evolution.
    """
    
    def __init__(self, brain: Brain, evolution: EvolutionEngine):
        self.brain = brain
        self.evolution = evolution
        self.logger = logging.getLogger("SAI.Reflection")

    def reflect_on_task(self, task: str, history: List[Dict[str, Any]]):
        """
        Analyzes the completed task and determines if self-improvement is needed.
        """
        self.logger.info("Reflecting on task performance...")
        
        history_summary = "\n".join([f"Step: {h['action']} -> Result: {h['observation']}" for h in history])
        
        system_prompt = (
            "You are the Meta-Reflection module of SAI. "
            "Analyze the following task history. "
            "Did the user's objective get met? Were there errors or inefficiencies? "
            "Special: If 'browser.interact' timed out or failed to find a selector, suggest using 'browser.explore' next time. "
            "If you see messages about 'Browser Compatibility' or 'Outdated Browser', recognize that the website is blocking SAI's identity and suggest a stealthier approach. "
            "If you are looking for long lists of text (like research papers or articles), use 'browser.scrape' instead of 'vision.ocr' for 100% accuracy. "
            "If a module (planner, coder, analyzer, vision, browser) needs improvement, suggest it. "
            "Format: { 'thought': 'reasoning', 'improvement_needed': bool, 'module': 'name', 'logic_suggestion': 'description' }"
        )
        
        reflection = self.brain.prompt(system_prompt, f"Task: {task}\n\nHistory:\n{history_summary}")
        
        if reflection.get("improvement_needed"):
            self.logger.info(f"Proactive improvement suggested for {reflection['module']}")
            # Trigger self-evolution based on the reflection
            # In a real scenario, the Brain would generate the full new code here.
            # For now, we log the suggestion.
            return reflection
        return None
