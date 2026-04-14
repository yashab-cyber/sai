import logging
import ast
import subprocess
from typing import Dict, Any, Optional
from core.executor import Executor

class Coder:
    """
    Upgraded self-improvable module specialized in code generation, refactoring, formatting and analysis.
    """
    
    def __init__(self, executor: Executor):
        self.executor = executor
        self.logger = logging.getLogger("SAI.Coder")

    def write_module(self, path: str, code: str) -> bool:
        """Writes a new module to the workspace."""
        self.logger.info(f"Writing module at {path}")
        result = self.executor.write_file(path, code)
        return result["status"] == "success"

    def replace_string(self, path: str, old_string: str, new_string: str) -> Dict[str, Any]:
        """Precise AST-independent string replacement for any file type."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result

        content = read_result["content"]
        if old_string not in content:
            return {"status": "error", "message": f"Exact target string not found in {path}."}
        
        if content.count(old_string) > 1:
            return {"status": "error", "message": f"Target string appears multiple times in {path}. Make it more specific."}

        new_content = content.replace(old_string, new_string)
        
        # If it's a python file, validate syntax softly
        if path.endswith(".py"):
            valid, err = self.validate_code(new_content)
            if not valid:
                return {"status": "error", "message": f"Replacement caused Python syntax error: {err}"}

        return self.executor.write_file(path, new_content)

    def replace_function(self, path: str, function_name: str, new_function_code: str) -> Dict[str, Any]:
        """Replaces an existing function in a module with new code."""
        # Using the original naive implementation, but encourage use of replace_string for precision
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result
            
        current_content = read_result["content"]
        lines = current_content.splitlines()
        
        start_line = -1
        end_line = -1
        
        import re
        func_pattern = re.compile(rf"^\s*(?:async\s+)?def\s+{function_name}\s*\(")
        
        for i, line in enumerate(lines):
            if func_pattern.match(line):
                start_line = i
                indent = len(line) - len(line.lstrip())
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
            
        new_lines = lines[:start_line] + [new_function_code] + lines[end_line:]
        new_content = "\n".join(new_lines)
        
        valid, error = self.validate_code(new_content)
        if not valid:
            return {"status": "error", "message": f"Replace resulted in invalid syntax: {error}"}
            
        return self.executor.write_file(path, new_content)

    def lint_code(self, path: str) -> Dict[str, Any]:
        """Runs flake8 on a given file."""
        return self.executor.execute_shell(f"flake8 {path}")

    def format_code(self, path: str) -> Dict[str, Any]:
        """Runs black on a given python file."""
        return self.executor.execute_shell(f"black {path}")

    def run_tests(self, path: str) -> Dict[str, Any]:
        """Runs pytest for a specific file or directory."""
        return self.executor.execute_shell(f"pytest {path} -v --tb=short")

    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """Checks if the given code is valid Python syntax."""
        try:
            ast.parse(code)
            return True, None
        except Exception as e:
            return False, str(e)

    def validate_module_integrity(self, original_code: str, new_code: str) -> tuple[bool, Optional[str]]:
        if not original_code.strip():
            return True, None
            
        try:
            old_tree = ast.parse(original_code)
            new_tree = ast.parse(new_code)
            
            old_defs = [n for n in ast.walk(old_tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
            new_defs = [n for n in ast.walk(new_tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
            
            if len(old_defs) > 0 and len(new_defs) == 0:
                return False, "Module integrity check failed: New code contains no functions/classes."
                
            if len(old_defs) > 5 and len(new_defs) < (len(old_defs) * 0.3):
                 return False, f"Module integrity check failed: Significant loss of code boundaries ({len(new_defs)} vs {len(old_defs)})."
                 
            return True, None
        except Exception as e:
            return False, f"Integrity check failed: {str(e)}"
