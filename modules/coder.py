import logging
import ast
import os
import shlex
import subprocess
from typing import Dict, Any, Optional, List
from core.executor import Executor
from modules.coding.language_registry import LanguageRegistry
from modules.coding.project_detector import ProjectDetector, ProjectProfile


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


# ── Scaffolding Templates ──

_SCAFFOLD_COMMANDS = {
    "react": "npx -y create-react-app {path}",
    "nextjs": "npx -y create-next-app@latest {path} --ts --eslint --tailwind --src-dir --app --no-import-alias",
    "vite": "npx -y create-vite@latest {path} --template react-ts",
    "vue": "npx -y create-vue@latest {path}",
    "angular": "npx -y @angular/cli new {name} --directory {path} --defaults",
    "svelte": "npx -y sv create {path}",
    "astro": "npx -y create-astro@latest {path} --template basics --no-install --no-git",
    "nuxt": "npx -y nuxi@latest init {path}",
    "rust": "cargo init {path}",
    "go": "go mod init {name}",
    "flutter": "flutter create {path}",
    "django": "django-admin startproject {name} {path}",
}

# Inline boilerplate for frameworks that don't have CLI scaffolders
_SCAFFOLD_TEMPLATES = {
    "express": {
        "package.json": '''{
  "name": "{name}",
  "version": "1.0.0",
  "main": "index.js",
  "scripts": {
    "start": "node index.js",
    "dev": "nodemon index.js"
  },
  "dependencies": {
    "express": "^4.18.0"
  },
  "devDependencies": {
    "nodemon": "^3.0.0"
  }
}''',
        "index.js": '''const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {
  res.json({ message: 'Hello from {name}!' });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
''',
    },
    "flask": {
        "requirements.txt": "flask>=3.0\ngunicorn\n",
        "app.py": '''from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify(message="Hello from {name}!")

if __name__ == "__main__":
    app.run(debug=True)
''',
    },
    "fastapi": {
        "requirements.txt": "fastapi>=0.110\nuvicorn[standard]\n",
        "main.py": '''from fastapi import FastAPI

app = FastAPI(title="{name}")

@app.get("/")
def root():
    return {{"message": "Hello from {name}!"}}
''',
    },
}


class Coder:
    """
    Polyglot AST-powered module specialized in code generation, refactoring,
    blueprint analysis, and structural formatting across all major languages.
    """

    def __init__(self, executor: Executor):
        self.executor = executor
        self.logger = logging.getLogger("SAI.Coder")
        self.project_detector = ProjectDetector()

    # ══════════════════════════════════════════════════════════════
    # FILE WRITING & EDITING
    # ══════════════════════════════════════════════════════════════

    def write_module(self, path: str, code: str) -> Dict[str, Any]:
        """Writes a new source file with language-appropriate validation and formatting."""
        self.logger.info(f"Writing module at {path}")

        # Python-specific: validate syntax before writing
        if LanguageRegistry.is_python(path):
            valid, err = self.validate_code(code)
            if not valid:
                return {"status": "error", "message": f"Python syntax error: {err}"}

        result = self.executor.write_file(path, code)
        if result["status"] == "success":
            self.format_code(path)
        return result

    def replace_string(self, path: str, old_string: str, new_string: str) -> Dict[str, Any]:
        """Precise exact string replacement — works on any file type."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result

        content = read_result["content"]
        if old_string not in content:
            return {"status": "error", "message": f"Exact target string not found in {path}."}

        if content.count(old_string) > 1:
            return {"status": "error", "message": f"Target string appears multiple times in {path}."}

        new_content = content.replace(old_string, new_string)

        # Python-specific: validate syntax after replacement
        if LanguageRegistry.is_python(path):
            valid, err = self.validate_code(new_content)
            if not valid:
                return {"status": "error", "message": f"Replacement caused Python syntax error: {err}"}

        result = self.executor.write_file(path, new_content)
        if result["status"] == "success":
            self.format_code(path)
        return result

    def replace_function(self, path: str, function_name: str, new_function_code: str) -> Dict[str, Any]:
        """
        Replaces a function/method.
        - Python: Uses AST-based structural replacement (precise, safe).
        - Other languages: Uses intelligent text-block replacement via signature detection.
        """
        if LanguageRegistry.is_python(path):
            return self._replace_function_ast(path, function_name, new_function_code)
        else:
            return self._replace_function_text(path, function_name, new_function_code)

    def _replace_function_ast(self, path: str, function_name: str, new_function_code: str) -> Dict[str, Any]:
        """AST-based function replacement for Python files (unchanged from original logic)."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result

        original_code = read_result["content"]

        try:
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

            original_tree = ast.parse(original_code)
            replacer = FunctionReplacer(function_name, new_node)
            modified_tree = replacer.visit(original_tree)
            ast.fix_missing_locations(modified_tree)

            if not replacer.found:
                return {"status": "error", "message": f"Function '{function_name}' not found in {path}."}

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

    def _replace_function_text(self, path: str, function_name: str, new_function_code: str) -> Dict[str, Any]:
        """
        Text-based function replacement for non-Python languages.
        Finds the function by signature and replaces the entire block
        using brace-counting for block boundaries.
        """
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result

        content = read_result["content"]
        lang = LanguageRegistry.detect_language(path)

        if not lang or not lang.function_pattern:
            return {"status": "error", "message": f"No function pattern defined for {path}. Use replace_string instead."}

        import re
        # Find the function declaration line
        pattern = lang.function_pattern.replace(r'(\w+)', rf'({re.escape(function_name)})')
        match = re.search(pattern, content, re.MULTILINE)

        if not match:
            return {"status": "error", "message": f"Function '{function_name}' not found in {path}."}

        # Find the opening brace and count to find the closing brace
        start_pos = match.start()
        brace_pos = content.find('{', start_pos)

        if brace_pos == -1:
            # No braces (e.g., arrow function without braces) — use line-based replacement
            line_end = content.find('\n', start_pos)
            if line_end == -1:
                line_end = len(content)
            new_content = content[:start_pos] + new_function_code + content[line_end:]
        else:
            # Count braces to find the end of the function block
            depth = 0
            end_pos = brace_pos
            for i in range(brace_pos, len(content)):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end_pos = i + 1
                        break

            new_content = content[:start_pos] + new_function_code + content[end_pos:]

        result = self.executor.write_file(path, new_content)
        if result["status"] == "success":
            self.format_code(path)
        return result

    def insert_function(self, path: str, new_function_code: str, target_class: Optional[str] = None) -> Dict[str, Any]:
        """Injects a new function into a file, optionally inside a specific class."""
        if LanguageRegistry.is_python(path):
            return self._insert_function_ast(path, new_function_code, target_class)
        else:
            return self._insert_function_text(path, new_function_code, target_class)

    def _insert_function_ast(self, path: str, new_function_code: str, target_class: Optional[str] = None) -> Dict[str, Any]:
        """AST-based function insertion for Python files."""
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

    def _insert_function_text(self, path: str, new_function_code: str, target_class: Optional[str] = None) -> Dict[str, Any]:
        """Text-based function insertion for non-Python files."""
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result

        content = read_result["content"]

        if target_class:
            import re
            lang = LanguageRegistry.detect_language(path)
            if lang and lang.class_pattern:
                pattern = lang.class_pattern.replace(r'(\w+)', rf'({re.escape(target_class)})')
                match = re.search(pattern, content)
                if match:
                    # Find the last closing brace of the class
                    brace_pos = content.find('{', match.start())
                    if brace_pos != -1:
                        depth = 0
                        for i in range(brace_pos, len(content)):
                            if content[i] == '{':
                                depth += 1
                            elif content[i] == '}':
                                depth -= 1
                                if depth == 0:
                                    # Insert before the closing brace
                                    new_content = content[:i] + "\n" + new_function_code + "\n" + content[i:]
                                    result = self.executor.write_file(path, new_content)
                                    if result["status"] == "success":
                                        self.format_code(path)
                                    return result
                return {"status": "error", "message": f"Class '{target_class}' not found."}
        else:
            # Append to end of file
            new_content = content.rstrip() + "\n\n" + new_function_code + "\n"
            result = self.executor.write_file(path, new_content)
            if result["status"] == "success":
                self.format_code(path)
            return result

    # ══════════════════════════════════════════════════════════════
    # ANALYSIS
    # ══════════════════════════════════════════════════════════════

    def analyze_structure(self, path: str) -> Dict[str, Any]:
        """
        Returns a structural blueprint of a source file.
        - Python: Full AST-based analysis (precise).
        - Other languages: Regex-based extraction via LanguageRegistry.
        """
        read_result = self.executor.read_file(path)
        if read_result["status"] != "success":
            return read_result

        code = read_result["content"]

        if LanguageRegistry.is_python(path):
            return self._analyze_python_ast(path, code)
        else:
            structure = LanguageRegistry.extract_structure(path, code)
            structure["file"] = path
            structure["status"] = "success"
            return structure

    def _analyze_python_ast(self, path: str, code: str) -> Dict[str, Any]:
        """Full AST-based structure analysis for Python files."""
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

            return {"status": "success", "language": "python", "structure": structure, "file": path}

        except Exception as e:
            return {"status": "error", "message": f"AST parsing failed: {str(e)}"}

    # ══════════════════════════════════════════════════════════════
    # LINTING, FORMATTING, TESTING (POLYGLOT)
    # ══════════════════════════════════════════════════════════════

    def lint_code(self, path: str) -> Dict[str, Any]:
        """Runs the appropriate linter for any supported language."""
        cmd = LanguageRegistry.get_linter_command(path)
        if not cmd:
            lang = LanguageRegistry.detect_language(path)
            lang_name = lang.name if lang else "unknown"
            return {"status": "info", "message": f"No linter configured for {lang_name} files."}
        return self.executor.execute_shell(cmd)

    def format_code(self, path: str) -> Dict[str, Any]:
        """Auto-formats a source file using the language-specific formatter."""
        cmd = LanguageRegistry.get_formatter_command(path)
        if not cmd:
            return {"status": "info", "message": "No formatter configured for this file type."}
        res = self.executor.execute_shell(cmd)
        return res

    def run_tests(self, path: str) -> Dict[str, Any]:
        """Runs the appropriate test suite for the detected project/file type."""
        # First try project-level test command
        dir_path = os.path.dirname(path) if os.path.isfile(path) else path
        profile = self.project_detector.detect(dir_path)
        if profile.test_command:
            return self.executor.execute_shell(profile.test_command)

        # Fall back to language-specific test command
        cmd = LanguageRegistry.get_test_command(path)
        if cmd:
            return self.executor.execute_shell(cmd)

        return {"status": "info", "message": "No test runner detected for this file or project."}

    # ══════════════════════════════════════════════════════════════
    # PROJECT OPERATIONS (NEW)
    # ══════════════════════════════════════════════════════════════

    def detect_project(self, path: str = ".") -> Dict[str, Any]:
        """Scans a directory and returns the detected tech stack and framework."""
        abs_path = os.path.abspath(path)
        profile = self.project_detector.detect(abs_path)
        return {"status": "success", "project": profile.to_dict()}

    def scaffold_project(self, framework: str, name: str = "app", path: str = ".") -> Dict[str, Any]:
        """Scaffolds a new project for a given framework."""
        framework = framework.lower().replace(" ", "").replace("-", "")
        self.logger.info(f"Scaffolding {framework} project: {name} at {path}")

        abs_path = os.path.abspath(os.path.join(path, name))

        # Check for CLI-based scaffolding
        if framework in _SCAFFOLD_COMMANDS:
            cmd = _SCAFFOLD_COMMANDS[framework].replace("{path}", abs_path).replace("{name}", name)
            result = self.executor.execute_shell(cmd)
            if result.get("status") == "success":
                return {"status": "success", "message": f"Scaffolded {framework} project at {abs_path}", "path": abs_path}
            return result

        # Check for template-based scaffolding
        if framework in _SCAFFOLD_TEMPLATES:
            os.makedirs(abs_path, exist_ok=True)
            templates = _SCAFFOLD_TEMPLATES[framework]
            for filename, content in templates.items():
                file_content = content.replace("{name}", name)
                filepath = os.path.join(abs_path, filename)
                self.executor.write_file(filepath, file_content)

            return {"status": "success", "message": f"Scaffolded {framework} project at {abs_path}", "path": abs_path, "files": list(templates.keys())}

        available = sorted(list(_SCAFFOLD_COMMANDS.keys()) + list(_SCAFFOLD_TEMPLATES.keys()))
        return {"status": "error", "message": f"Unknown framework: '{framework}'. Available: {', '.join(available)}"}

    def install_deps(self, path: str = ".") -> Dict[str, Any]:
        """Auto-detects the package manager and installs project dependencies."""
        abs_path = os.path.abspath(path)
        profile = self.project_detector.detect(abs_path)

        if not profile.install_command:
            return {"status": "error", "message": f"No install command detected for {abs_path}. Could not identify package manager."}

        self.logger.info(f"Installing dependencies: {profile.install_command}")
        return self.executor.execute_shell(f"cd {shlex.quote(abs_path)} && {profile.install_command}")

    def dev_server(self, path: str = ".") -> Dict[str, Any]:
        """Starts the dev server for the detected framework."""
        abs_path = os.path.abspath(path)
        profile = self.project_detector.detect(abs_path)

        if not profile.dev_command:
            return {"status": "error", "message": f"No dev command detected for {abs_path}."}

        self.logger.info(f"Starting dev server: {profile.dev_command}")
        # Launch in background so SAI doesn't block
        return self.executor.execute_shell(f"cd {shlex.quote(abs_path)} && {profile.dev_command} &")

    def build_project(self, path: str = ".") -> Dict[str, Any]:
        """Runs the build command for the detected framework."""
        abs_path = os.path.abspath(path)
        profile = self.project_detector.detect(abs_path)

        if not profile.build_command:
            return {"status": "error", "message": f"No build command detected for {abs_path}."}

        self.logger.info(f"Building project: {profile.build_command}")
        return self.executor.execute_shell(f"cd {shlex.quote(abs_path)} && {profile.build_command}")

    def run_file(self, path: str, args: str = "") -> Dict[str, Any]:
        """
        Executes a source file in the correct runtime.
        - Python: python3 <file>
        - JavaScript: node <file>
        - TypeScript: npx tsx <file>
        - Rust: cargo run (from project dir)
        - Go: go run <file>
        - Shell: bash <file>
        - Ruby: ruby <file>
        - Dart: dart run <file>
        """
        abs_path = os.path.abspath(path)
        lang = LanguageRegistry.detect_language(abs_path)

        if not lang:
            return {"status": "error", "message": f"Unknown file type: {path}. Cannot determine runtime."}

        runtime_map = {
            "python": f"python3 {shlex.quote(abs_path)} {args}",
            "javascript": f"node {shlex.quote(abs_path)} {args}",
            "typescript": f"npx tsx {shlex.quote(abs_path)} {args}",
            "rust": f"cd {shlex.quote(os.path.dirname(abs_path))} && cargo run {args}",
            "go": f"go run {shlex.quote(abs_path)} {args}",
            "shell": f"bash {shlex.quote(abs_path)} {args}",
            "ruby": f"ruby {shlex.quote(abs_path)} {args}",
            "dart": f"dart run {shlex.quote(abs_path)} {args}",
            "kotlin": f"kotlin {shlex.quote(abs_path)} {args}",
            "swift": f"swift {shlex.quote(abs_path)} {args}",
            "java": f"java {shlex.quote(abs_path)} {args}",
        }

        cmd = runtime_map.get(lang.name)
        if not cmd:
            return {"status": "error", "message": f"No runtime configured for {lang.name} files. Use executor.shell to run manually."}

        self.logger.info(f"Running {lang.name} file: {cmd}")
        return self.executor.execute_shell(cmd.strip())

    def get_project_summary(self, path: str = ".") -> Dict[str, Any]:
        """Returns a concise human-readable summary of a project's tech stack."""
        abs_path = os.path.abspath(path)
        profile = self.project_detector.detect(abs_path)
        p = profile

        summary_parts = []
        if p.primary_language != "unknown":
            summary_parts.append(f"Language: {p.primary_language.title()}")
        if p.framework != "none":
            summary_parts.append(f"Framework: {p.framework.title()}")
        if p.package_manager != "none":
            summary_parts.append(f"Package Manager: {p.package_manager}")
        if p.entry_point:
            summary_parts.append(f"Entry Point: {p.entry_point}")

        commands = {}
        if p.dev_command:
            commands["dev"] = p.dev_command
        if p.build_command:
            commands["build"] = p.build_command
        if p.test_command:
            commands["test"] = p.test_command
        if p.install_command:
            commands["install"] = p.install_command

        return {
            "status": "success",
            "summary": " | ".join(summary_parts) if summary_parts else "No project detected",
            "commands": commands,
            "project": profile.to_dict(),
        }

    # ══════════════════════════════════════════════════════════════
    # VALIDATION (Python-specific, kept intact)
    # ══════════════════════════════════════════════════════════════

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
