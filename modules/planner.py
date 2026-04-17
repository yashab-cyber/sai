import logging
from typing import List, Dict, Any, Optional
from core.brain import Brain

class Planner:
    """
    Cognitive module responsible for decomposition of complex goals.
    """

    def __init__(self, brain: Brain):
        self.brain = brain
        self.logger = logging.getLogger("SAI.Planner")

    def determine_next_step(self, task: str, history: List[Dict[str, Any]], image_path: Optional[str] = None, allowed_tools: Optional[List[str]] = None, role_prompt: Optional[str] = None, extra_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Determines the single best next action based on the task, history, and optional visual context.
        """
        self.logger.info(f"Determining next step for task: {task} (Visual: {bool(image_path)})")

        try:
            from core.tools import ToolManifest
            system_prompt = ToolManifest.get_system_prompt(allowed_tools=allowed_tools, role_prompt=role_prompt)

            # Prepare context with streamlined history management
            recent_history = history[-5:]  # Optimize to handle only the last 5 records
            history_str = ""
            for h in recent_history:
                action = h.get('action', 'N/A')
                obs = h.get('observation', 'N/A')
                obs_truncated = (obs[:2000] + "... [truncated]") if len(obs) > 2000 else obs
                history_str += f"Action: {action}\nObservation: {obs_truncated}\n---\n"

            # Prepare session-aware state warning
            session_state = ""
            if not history:
                session_state = (
                    "SESSION_STATE: [COLD START]\n"
                    "This is the first iteration of a new task. IMPORTANT: Any visual evidence of completion on the screen (e.g. terminal output or open files) may be 'stale' from a previous session. YOU MUST take a concrete action to fulfill the task yourself in this new session. Do not mark as 'completed' yet.\n\n"
                )

            rag_injection = f"Long-Term Memory Data (RAG):\n{extra_context}\n\n" if extra_context else ""

            context = (
                f"Task: {task}\n\n"
                f"{session_state}"
                f"{rag_injection}"
                f"Agent History (Recent):\n{history_str}\n\n"
                "Decision Requirements:\n"
                "- Provide 'thought' (mention what you see in the screenshot if provided)\n"
                "- Choose a 'tool' and provide 'parameters'\n"
                "- Set 'status' to 'ongoing' or 'completed'"
            )

            response = self.brain.prompt(system_prompt, context, image_path=image_path)

            # Validate response structure
            if not isinstance(response, dict):
                return {
                    "thought": "Brain returned invalid format.",
                    "status": "ongoing",
                    "tool": None
                }

            return response
        except Exception as e:
            self.logger.error(f"Error in determine_next_step: {e}")
            return {
                "thought": f"Critical error encountered: {e}",
                "status": "ongoing",
                "tool": None
            }
    def generate_subtasks(self, task: str) -> List[str]:
        """
        Generates logical sub-tasks for a given complex task.
        """
        self.logger.info(f"Generating subtasks for: {task}")
        context = f"Task: {task}\n\nDecompose this task into logical subtasks."
        response = self.brain.prompt("decompose_task", context)
        if "subtasks" in response:
            return response["subtasks"]
        return []

    def plan_multi_step(self, main_task: str, depth: int) -> List[Dict[str, Any]]:
        """
        Plans multiple steps toward completing a complex goal, recursively generating subtasks.
        """
        self.logger.info(f"Planning multi-step actions for task: {main_task}")
        plan = []
        subtasks = self.generate_subtasks(main_task)
        for subtask in subtasks:
            step = self.determine_next_step(subtask, history=[])
            plan.append({"subtask": subtask, "step": step})

            if depth > 1:
                deeper_plan = self.plan_multi_step(subtask, depth=depth-1)
                plan.extend(deeper_plan)
        return plan