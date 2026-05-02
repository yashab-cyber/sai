import os
import ast
import logging
from typing import Dict, List, Any
from core.memory import MemoryManager
from modules.coding.language_registry import LanguageRegistry

class Analyzer:
    """
    Analyzes the SAI codebase to maintain self-awareness.
    Parses Python files via AST and all other supported languages
    via regex-based structural extraction from the LanguageRegistry.
    """

    def __init__(self, memory: MemoryManager, base_dir: str):
        self.memory = memory
        self.base_dir = os.path.abspath(base_dir)
        self.logger = logging.getLogger("SAI.Analyzer")

    def scan_codebase(self) -> str:
        """Recursively scans the codebase and updates memory with all source files."""
        self.logger.info("Starting polyglot codebase scan...")
        self.memory.clear_codebase_map()
        files_scanned = 0

        # Build the set of scannable extensions
        scannable_exts = set(LanguageRegistry.supported_extensions())
        # Always include Python
        scannable_exts.update({".py", ".pyw", ".pyi"})

        for root, dirs, files in os.walk(self.base_dir):
            # Optimization: Modify dirs in-place to skip unwanted branches
            dirs_to_skip = ["venv", ".git", "__pycache__", "workspace", "artifacts",
                            "node_modules", ".next", "dist", "build", "target",
                            ".venv", "env", ".tox", ".mypy_cache"]
            dirs[:] = [d for d in dirs if d not in dirs_to_skip and not d.startswith('.')]

            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() not in scannable_exts:
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.base_dir)
                self._analyze_file(full_path, rel_path)
                files_scanned += 1

        summary = f"Codebase scan complete. {files_scanned} source files analyzed and mapped to memory."
        self.logger.info(summary)
        return summary

    def _analyze_file(self, full_path: str, rel_path: str):
        """Analyzes a single file — AST for Python, regex for everything else."""
        try:
            with open(full_path, "r", errors="ignore") as f:
                code = f.read()
        except Exception as e:
            self.logger.error(f"Failed to read {rel_path}: {str(e)}")
            return

        if LanguageRegistry.is_python(full_path):
            self._analyze_python_ast(full_path, rel_path, code)
        else:
            self._analyze_with_registry(full_path, rel_path, code)

    def _analyze_python_ast(self, full_path: str, rel_path: str, code: str):
        """Uses AST to parse a single Python file."""
        try:
            tree = ast.parse(code, filename=full_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self.memory.save_memory("codebase_map", {
                        "file_path": rel_path,
                        "language": "python",
                        "type": "class",
                        "name": node.name,
                        "dependencies": self._get_imports(node)
                    })
                elif isinstance(node, ast.FunctionDef):
                    self.memory.save_memory("codebase_map", {
                        "file_path": rel_path,
                        "language": "python",
                        "type": "function",
                        "name": node.name,
                        "dependencies": self._get_imports(node)
                    })
        except Exception as e:
            self.logger.error(f"Failed to analyze {rel_path}: {str(e)}")

    def _analyze_with_registry(self, full_path: str, rel_path: str, code: str):
        """Uses LanguageRegistry regex patterns to extract structure from non-Python files."""
        try:
            structure = LanguageRegistry.extract_structure(full_path, code)
            language = structure.get("language", "unknown")

            for cls in structure.get("classes", []):
                self.memory.save_memory("codebase_map", {
                    "file_path": rel_path,
                    "language": language,
                    "type": "class",
                    "name": cls["name"],
                    "line": cls.get("line"),
                    "dependencies": ",".join(structure.get("imports", [])[:10])
                })

            for func in structure.get("functions", []):
                self.memory.save_memory("codebase_map", {
                    "file_path": rel_path,
                    "language": language,
                    "type": "function",
                    "name": func["name"],
                    "line": func.get("line"),
                    "dependencies": ""
                })

        except Exception as e:
            self.logger.error(f"Failed to analyze {rel_path} with registry: {str(e)}")

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