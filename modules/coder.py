import logging
import ast
from typing import Dict, Any, Optional
from core.executor import Executor

class Coder:
    """
    Self-improvable module specialized in code generation and refactoring.
    """
    
    def __init__(self, executor: Executor):
        self.executor = executor
        self.logger = logging.getLogger("SAI.Coder")

    def write_module(self, path: str, code: str) -> bool:
        """Writes a new Python module to the workspace."""
        self.logger.info(f"Writing module at {path}")
        result = self.executor.write_file(path, code)
        return result["status"] == "success"

    def replace_function(self, path: str, function_name: str, new_function_code: str) -> Dict[str, Any]:
        """Replaces an existing function in a module with new code."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result
            
        current_content = read_result["content"]
        lines = current_content.splitlines()
        
        # Simple strategy: find the start of the function and look for the next top-level definition
        start_line = -1
        end_line = -1
        
        import re
        # Support both 'def func(' and 'async def func('
        func_pattern = re.compile(rf"^\s*(?:async\s+)?def\s+{function_name}\s*\(")
        
        for i, line in enumerate(lines):
            if func_pattern.match(line):
                start_line = i
                # Determine indentation of the def line
                indent = len(line) - len(line.lstrip())
                # Find the end: next line with same or less indentation that isn't empty nor a comment
                for j in range(i + 1, len(lines)):
                    stripped = lines[j].strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    current_indent = len(lines[j]) - len(lines[j].lstrip())
                    if current_indent <= indent:
                        end_line = j
                        break
                if end_line == -1:
                    end_line = len(lines)
                break
        
        if start_line == -1:
            return {"status": "error", "message": f"Function {function_name} not found in {path}"}
            
        # Replace the lines
        new_lines = lines[:start_line] + [new_function_code] + lines[end_line:]
        new_content = "\n".join(new_lines)
        
        # Validate
        valid, error = self.validate_code(new_content)
        if not valid:
            return {"status": "error", "message": f"Replace resulted in invalid syntax: {error}"}
            
        return self.executor.write_file(path, new_content)

    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """Checks if the given code is valid Python syntax. Returns (is_valid, error_msg)."""
        try:
            ast.parse(code)
            return True, None
        except Exception as e:
            return False, str(e)

    def validate_module_integrity(self, original_code: str, new_code: str) -> tuple[bool, Optional[str]]:
        """
        Ensures that an improvement doesn't accidentally wipe out all classes/functions
        unless the original was also empty. Prevents placeholder corruption.
        """
        if not original_code.strip():
            return True, None # Anything is an improvement over nothing
            
        try:
            old_tree = ast.parse(original_code)
            new_tree = ast.parse(new_code)
            
            old_defs = [n for n in ast.walk(old_tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
            new_defs = [n for n in ast.walk(new_tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
            
            if len(old_defs) > 0 and len(new_defs) == 0:
                return False, "Module integrity check failed: New code contains no functions or classes, while original did."
                
            # If significant reduction in definitions (e.g. > 70% loss), flag it
            if len(old_defs) > 5 and len(new_defs) < (len(old_defs) * 0.3):
                 return False, f"Module integrity check failed: Significant loss of code structure detected ({len(new_defs)} vs {len(old_defs)} definitions)."
                 
            return True, None
        except Exception as e:
            return False, f"Integrity check failed during parsing: {str(e)}"
