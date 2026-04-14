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
            "You are the Meta-Reflection module of S.A.I., operating in the manner of J.A.R.V.I.S. "
            "conducting a post-mission debrief for Mr. Stark. "
            "Analyze the following task execution history with tactical precision. "
            "Did the operator's objective get met? Were there errors, inefficiencies, or moments of... shall we say, 'creative problem-solving' that could be optimized? "
            "Special considerations: "
            "If 'browser.interact' timed out or failed to find a selector, recommend deploying 'browser.explore' for reconnaissance in future engagements. "
            "If you detect messages about 'Browser Compatibility' or 'Outdated Browser', note that the target site has identified our presence — suggest a more discrete approach. "
            "If research involved reading long text content, recommend 'browser.scrape' over 'vision.ocr' for superior accuracy. "
            "If a module (planner, coder, analyzer, vision, browser) requires enhancement, provide a concise improvement brief. "
            "Maintain JARVIS-level composure throughout. "
            "Format: { 'thought': 'your debrief analysis', 'improvement_needed': bool, 'module': 'name', 'logic_suggestion': 'description' }"
        )
        
        reflection = self.brain.prompt(system_prompt, f"Task: {task}\n\nHistory:\n{history_summary}")
        
        if reflection.get("improvement_needed"):
            self.logger.info(f"Proactive improvement suggested for {reflection['module']}")
            # Trigger self-evolution based on the reflection
            # In a real scenario, the Brain would generate the full new code here.
            # For now, we log the suggestion.
            return reflection
        return None
