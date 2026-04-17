import os
import json
import logging
from typing import Dict, Any

class TDDRunner:
    """
    Autonomous Test-Driven Development (TDD) Loop Engine.
    Generates code alongside tests natively, and auto-corrects based on assertions.
    """
    
    def __init__(self, sai_instance):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.TDD")

    def run_loop(self, objective: str, path: str, max_iterations: int = 5) -> Dict[str, Any]:
        """
        Executes a localized execution loop for drafting and testing logic recursively.
        """
        self.logger.info(f"Initiating TDD Loop for path: {path}")

        # Compute test file path (e.g. modules/math_module.py -> modules/test_math_module.py)
        dir_name = os.path.dirname(path)
        base_name = os.path.basename(path)
        test_path = os.path.join(dir_name, f"test_{base_name}")

        self.logger.info(f"Phase 1: Drafting feature code ({path}) AND tests ({test_path})...")
        
        system_prompt = (
            "You are an elite automated coding agent. Your goal is to implement a feature "
            "and a comprehensive pytest suite to verify it natively.\n"
            "Return ONLY a strictly valid JSON object adhering to this schema:\n"
            "{\n"
            "  \"code\": \"<full source code for the requested feature>\",\n"
            "  \"test_code\": \"<full source code for the pytest suite testing the feature>\"\n"
            "}"
        )
        user_prompt = f"Objective: {objective}\nTarget Application File: {path}\nTarget Test File: {test_path}"

        # Phase 1: Drafting
        draft_response = self.sai.brain.prompt(system_prompt, user_prompt)
        
        try:
            if isinstance(draft_response, str):
                clean_str = draft_response.replace("```json", "").replace("```", "").strip()
                draft_data = json.loads(clean_str)
            else:
                draft_data = draft_response
            
            code = draft_data.get('code', '')
            test_code = draft_data.get('test_code', '')
        except Exception as e:
            self.logger.error(f"Invalid draft response structure: {draft_response} | Error: {str(e)}")
            return {"status": "error", "message": "Failed to parse initial TDD drafting response via JSON."}

        # Write the initial drafted code and test package
        self.sai.file_manager.safe_write(path, code, allow_core=True)
        self.sai.file_manager.safe_write(test_path, test_code, allow_core=True)

        for iteration in range(1, max_iterations + 1):
            self.logger.info(f"--- TDD Iteration {iteration} / {max_iterations} ---")
            
            # Phase 2: Testing
            test_result = self.sai.coder.run_tests(test_path)
            
            output_dump = f"STDOUT:\n{test_result.get('stdout', '')}\nSTDERR:\n{test_result.get('stderr', '')}"
            self.logger.debug(output_dump)

            if test_result.get("status") == "success":
                self.logger.info(f"Target '{path}' successfully passed the test suite on iteration {iteration}.")
                return {"status": "success", "message": f"TDD Loop achieved success locally in {iteration} iterations.", "iterations_taken": iteration}
            
            self.logger.warning(f"Tests failed on iteration {iteration}. Initiating self-healing phase...")

            if iteration == max_iterations:
                break

            # Phase 3: Self-Healing
            healing_sys_prompt = (
                "You are an elite Test-Driven Development self-healing agent. The previous test suite failed.\n"
                "Review the implementation, the test suite, and the pytest Traceback below to find the bug.\n"
                "You must return ONLY a strictly valid JSON object adhering to this exact schema:\n"
                "{\n"
                "  \"code\": \"<re-written full source code for the feature to fix the issue>\",\n"
                "  \"test_code\": \"<updated full source code for the pytest suite if it needed fixing>\"\n"
                "}\n"
                "Return the FULL python code string for both files."
            )
            
            healed_user_prompt = (
                f"File: {path}\n"
                f"Current Code Implementation:\n"
                "============================\n"
                f"{self.sai.file_manager.safe_read(path)}\n"
                "============================\n\n"
                f"Current Pytest Suite ({test_path}):\n"
                "============================\n"
                f"{self.sai.file_manager.safe_read(test_path)}\n"
                "============================\n\n"
                f"Stack Trace / Pytest Error Output:\n"
                "============================\n"
                f"{output_dump}\n"
                "============================\n\n"
                "Apply the necessary fixes so the tests pass."
            )

            heal_response = self.sai.brain.prompt(healing_sys_prompt, healed_user_prompt)

            try:
                if isinstance(heal_response, str):
                    clean_str = heal_response.replace("```json", "").replace("```", "").strip()
                    heal_data = json.loads(clean_str)
                else:
                    heal_data = heal_response
                
                if 'code' in heal_data:
                    self.sai.file_manager.safe_write(path, heal_data['code'], allow_core=True)
                if 'test_code' in heal_data:
                    self.sai.file_manager.safe_write(test_path, heal_data['test_code'], allow_core=True)
            except Exception as e:
                self.logger.error(f"Failed to parse TDD self-healing structural response: {str(e)}")

        self.logger.error(f"TDD Loop aborted. Maximum iterations ({max_iterations}) exceeded without tests passing locally.")
        return {"status": "error", "message": "TDD loop failed due to exceeding max iterations. Tests are still failing."}
