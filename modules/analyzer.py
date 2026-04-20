import os
import ast
import logging
from typing import Dict, List, Any
from core.memory import MemoryManager

class Analyzer:
    """
    Analyzes the SAI codebase to maintain self-awareness.
    Parses Python files to map functions, classes, and imports.
    """

    def __init__(self, memory: MemoryManager, base_dir: str):
        self.memory = memory
        self.base_dir = os.path.abspath(base_dir)
        self.logger = logging.getLogger("SAI.Analyzer")

    def scan_codebase(self) -> str:
        """Recursively scans the codebase and updates memory."""
        self.logger.info("Starting codebase scan...")
        self.memory.clear_codebase_map()
        files_scanned = 0

        for root, dirs, files in os.walk(self.base_dir):
            # Optimization: Modify dirs in-place to skip unwanted branches
            dirs_to_skip = ["venv", ".git", "__pycache__", "workspace", "artifacts"]
            dirs[:] = [d for d in dirs if d not in dirs_to_skip and not d.startswith('.')]

            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.base_dir)
                    self._analyze_file(full_path, rel_path)
                    files_scanned += 1

        summary = f"Codebase scan complete. {files_scanned} Python files analyzed and mapped to memory."
        self.logger.info(summary)
        return summary

    def _analyze_file(self, full_path: str, rel_path: str):
        """Uses AST to parse a single Python file."""
        try:
            with open(full_path, "r") as f:
                tree = ast.parse(f.read(), filename=full_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self.memory.save_memory("codebase_map", {
                        "file_path": rel_path,
                        "type": "class",
                        "name": node.name,
                        "dependencies": self._get_imports(node)
                    })
                elif isinstance(node, ast.FunctionDef):
                    self.memory.save_memory("codebase_map", {
                        "file_path": rel_path,
                        "type": "function",
                        "name": node.name,
                        "dependencies": self._get_imports(node)
                    })
        except Exception as e:
            self.logger.error(f"Failed to analyze {rel_path}: {str(e)}")

    def _get_imports(self, node: ast.AST) -> str:
        """Extracts imports relevant to a specific AST node."""
        imports = []
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for n in child.names:
                    imports.append(n.name)
            elif isinstance(child, ast.ImportFrom):
                module = child.module or ""
                for n in child.names:
                    imports.append(f"{module}.{n.name}" if module else n.name)
        return ",".join(imports)