import logging
import ast
import subprocess
from typing import Dict, Any, Optional, List
from core.executor import Executor

class FunctionReplacer(ast.NodeTransformer):
    """Safely locates and replaces an AST function or method node."""
    def __init__(self, target_name: str, new_node: ast.AST):
        self.target_name = target_name
        self.new_node = new_node
        self.found = False

    def visit_FunctionDef(self, node):
        if node.name == self.target_name:
            self.found = True
            return self.new_node
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        if node.name == self.target_name:
            self.found = True
            return self.new_node
        self.generic_visit(node)
        return node


class Coder:
    """
    Advanced AST-powered module specialized in code generation, refactoring, 
    blueprint analysis, and structural formatting.
    """
    
    def __init__(self, executor: Executor):
        self.executor = executor
        self.logger = logging.getLogger("SAI.Coder")

    def write_module(self, path: str, code: str) -> Dict[str, Any]:
        """Writes a new module to the workspace and runs formatter."""
        self.logger.info(f"Writing module at {path}")
        result = self.executor.write_file(path, code)
        if result["status"] == "success" and path.endswith(".py"):
            self.format_code(path)
        return result

    def replace_string(self, path: str, old_string: str, new_string: str) -> Dict[str, Any]:
        """Precise exact string replacement."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result

        content = read_result["content"]
        if old_string not in content:
            return {"status": "error", "message": f"Exact target string not found in {path}."}
        
        if content.count(old_string) > 1:
            return {"status": "error", "message": f"Target string appears multiple times in {path}."}

        new_content = content.replace(old_string, new_string)
        
        if path.endswith(".py"):
            valid, err = self.validate_code(new_content)
            if not valid:
                return {"status": "error", "message": f"Replacement caused Python syntax error: {err}"}

        result = self.executor.write_file(path, new_content)
        if result["status"] == "success" and path.endswith(".py"):
            self.format_code(path)
        return result

    def replace_function(self, path: str, function_name: str, new_function_code: str) -> Dict[str, Any]:
        """Structurally replaces a function/method using AST parsing (Python 3.9+)."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result
            
        original_code = read_result["content"]
        
        try:
            # Parse the new function
            new_tree = ast.parse(new_function_code)
            new_node = None
            for node in new_tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    new_node = node
                    break
            
            if not new_node:
                return {"status": "error", "message": "The provided code does not contain a valid function definition."}

            if new_node.name != function_name:
                self.logger.warning(f"New function name '{new_node.name}' does not match target '{function_name}'. Enforcing original name.")
                new_node.name = function_name

            # Parse the original file
            original_tree = ast.parse(original_code)
            
            # Transformer injection
            replacer = FunctionReplacer(function_name, new_node)
            modified_tree = replacer.visit(original_tree)
            ast.fix_missing_locations(modified_tree)

            if not replacer.found:
                return {"status": "error", "message": f"Function '{function_name}' not found in {path}."}

            # Unparse and validate
            unparsed_code = ast.unparse(modified_tree)
            
            valid, int_err = self.validate_module_integrity(original_code, unparsed_code)
            if not valid:
                return {"status": "error", "message": int_err}

            result = self.executor.write_file(path, unparsed_code)
            if result["status"] == "success":
                self.format_code(path)
            return result

        except SyntaxError as e:
            return {"status": "error", "message": f"Syntax Error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"AST manipulation failed: {str(e)}"}

    def insert_function(self, path: str, new_function_code: str, target_class: Optional[str] = None) -> Dict[str, Any]:
        """Injects a new function into a file, optionally inside a specific class."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result
            
        original_code = read_result["content"]
        
        try:
            new_tree = ast.parse(new_function_code)
            new_nodes = [n for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if not new_nodes:
                return {"status": "error", "message": "Code does not contain a function definition."}

            original_tree = ast.parse(original_code)
            
            if target_class:
                class_found = False
                for node in original_tree.body:
                    if isinstance(node, ast.ClassDef) and node.name == target_class:
                        node.body.extend(new_nodes)
                        class_found = True
                        break
                if not class_found:
                    return {"status": "error", "message": f"Class '{target_class}' not found."}
            else:
                original_tree.body.extend(new_nodes)
                
            ast.fix_missing_locations(original_tree)
            unparsed_code = ast.unparse(original_tree)
            
            result = self.executor.write_file(path, unparsed_code)
            if result["status"] == "success":
                self.format_code(path)
            return result
            
        except Exception as e:
            return {"status": "error", "message": f"AST injection failed: {str(e)}"}

    def analyze_structure(self, path: str) -> Dict[str, Any]:
        """Reads a python file and returns an organizational blueprint of its structure."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result
            
        code = read_result["content"]
        
        try:
            tree = ast.parse(code)
            structure = {"classes": [], "functions": [], "imports": []}
            
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        structure["imports"].extend(n.name for n in node.names)
                    else:
                        module = node.module or ""
                        structure["imports"].extend(f"{module}.{n.name}" for n in node.names)
                        
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    structure["functions"].append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "docstring": ast.get_docstring(node)
                    })
                    
                elif isinstance(node, ast.ClassDef):
                    cls_struct = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "methods": []
                    }
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            cls_struct["methods"].append({
                                "name": sub.name,
                                "args": [arg.arg for arg in sub.args.args]
                            })
                    structure["classes"].append(cls_struct)
                    
            return {"status": "success", "structure": structure, "file": path}
            
        except Exception as e:
            return {"status": "error", "message": f"AST parsing failed: {str(e)}"}

    def lint_code(self, path: str) -> Dict[str, Any]:
        """Runs flake8 on a given file."""
        return self.executor.execute_shell(f"flake8 {path}")

    def format_code(self, path: str) -> Dict[str, Any]:
        """Runs black auto-formatter silently to preserve code hygiene."""
        res = self.executor.execute_shell(f"black {path}")
        return res

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
        """Ensures AST-unparsed output hasn't structurally corrupted critical files."""
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
