import ast
import os
import re
import json
import logging
import subprocess
from typing import Set, List, Dict, Any

class DependencyManager:
    """
    Phase 5: Automated Dependency Management.
    Keeps SAI self-reliant by tracking, resolving, and installing 
    dependencies dynamically for both host and Docker sandbox execution.
    Supports Python (pip), Node.js (npm/yarn/pnpm), Rust (cargo), and Go.
    """
    
    # Common mappings where pip name != import name
    IMPORT_TO_PIP = {
        "cv2": "opencv-python",
        "bs4": "beautifulsoup4",
        "yaml": "pyyaml",
        "PIL": "Pillow",
        "dotenv": "python-dotenv",
        "playwright": "playwright"
    }

    # Standard lib modules to ignore
    STDLIB = {
        "os", "sys", "json", "time", "re", "math", "random", "logging", "typing",
        "ast", "shutil", "sqlite3", "subprocess", "threading", "datetime", "pathlib",
        "base64", "hashlib", "argparse", "copy", "itertools", "collections", "uuid", "asyncio",
        "imaplib", "smtplib", "email",
    }

    # Reverse mapping: pip package name -> import name (for dependency existence checks)
    PIP_TO_IMPORT = {
        "opencv-python": "cv2",
        "beautifulsoup4": "bs4",
        "pyyaml": "yaml",
        "Pillow": "PIL",
        "python-dotenv": "dotenv",
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.logger = logging.getLogger("SAI.DependencyManager")
        self.req_file = os.path.join(os.path.dirname(workspace_dir), "requirements.txt")
        
    def scan_code_for_imports(self, code: str) -> Set[str]:
        """Scans python code natively to find all imports."""
        imports = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except SyntaxError:
            self.logger.error("Syntax error while scanning code for imports.")
            pass
            
        # Filter out stdlib
        return {pkg for pkg in imports if pkg not in self.STDLIB}

    def resolve_pip_names(self, imports: Set[str]) -> Set[str]:
        """Converts raw import names to canonical pip package names."""
        pip_packages = set()
        for imp in imports:
            pip_packages.add(self.IMPORT_TO_PIP.get(imp, imp))
        return pip_packages

    def sync_requirements_txt(self, new_packages: Set[str]) -> None:
        """Adds any missing packages to requirements.txt."""
        if not new_packages:
            return
            
        existing = set()
        if os.path.exists(self.req_file):
            with open(self.req_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract base package name ignoring versions like ==1.0.0
                        base_name = re.split(r'[=<>~!]', line)[0].strip().lower()
                        existing.add(base_name)
                        
        added = False
        with open(self.req_file, "a") as f:
            for pkg in new_packages:
                if pkg.lower() not in existing:
                    f.write(f"\n{pkg}")
                    existing.add(pkg.lower())
                    added = True
                    self.logger.info(f"Added {pkg} to requirements.txt")
                    
        if added:
            self.logger.info("Synchronized requirements.txt with new dependencies.")

    def ensure_host_dependencies(self, packages: Set[str]) -> Dict[str, Any]:
        """Installs packages directly on the host (for core evolution)."""
        import sys
        missing = []
        for pkg in packages:
            # Use the import name (not pip name) to test if the package exists
            import_name = self.PIP_TO_IMPORT.get(pkg, pkg)
            try:
                # Quick test if it exists
                subprocess.check_output([sys.executable, "-c", f"import {import_name}"], stderr=subprocess.DEVNULL)
            except Exception:
                missing.append(pkg)
                
        if not missing:
            return {"status": "success", "message": "All dependencies met."}
            
        self.logger.info(f"Installing missing host dependencies: {missing}")
        try:
            result = subprocess.run(
                ["pip", "install", *missing],
                capture_output=True,
                text=True
            )
            self.sync_requirements_txt(set(missing))
            if result.returncode == 0:
                return {"status": "success", "message": f"Installed: {', '.join(missing)}"}
            else:
                return {"status": "error", "message": result.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def extract_missing_module_from_error(self, error_text: str) -> str:
        """Parses python tracebacks to extract the missing module name."""
        match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", error_text)
        if match:
            return match.group(1)
        return ""

    # ══════════════════════════════════════════════════════════════
    # MULTI-LANGUAGE DEPENDENCY MANAGEMENT (NEW)
    # ══════════════════════════════════════════════════════════════

    def detect_package_manager(self, project_dir: str) -> Dict[str, Any]:
        """Detects the package manager for a given project directory."""
        abs_dir = os.path.abspath(project_dir)
        files = set(os.listdir(abs_dir)) if os.path.isdir(abs_dir) else set()

        if "package.json" in files:
            if "pnpm-lock.yaml" in files:
                return {"manager": "pnpm", "install": "pnpm install", "language": "javascript"}
            elif "yarn.lock" in files:
                return {"manager": "yarn", "install": "yarn install", "language": "javascript"}
            elif "bun.lockb" in files:
                return {"manager": "bun", "install": "bun install", "language": "javascript"}
            else:
                return {"manager": "npm", "install": "npm install", "language": "javascript"}

        if "Cargo.toml" in files:
            return {"manager": "cargo", "install": "cargo build", "language": "rust"}

        if "go.mod" in files:
            return {"manager": "go", "install": "go mod tidy", "language": "go"}

        if "Gemfile" in files:
            return {"manager": "bundler", "install": "bundle install", "language": "ruby"}

        if "pubspec.yaml" in files:
            return {"manager": "pub", "install": "flutter pub get", "language": "dart"}

        if "pom.xml" in files:
            return {"manager": "maven", "install": "mvn install", "language": "java"}

        if "build.gradle" in files or "build.gradle.kts" in files:
            return {"manager": "gradle", "install": "gradle build", "language": "java"}

        if "requirements.txt" in files or "pyproject.toml" in files or "setup.py" in files:
            return {"manager": "pip", "install": "pip install -r requirements.txt", "language": "python"}

        return {"manager": "unknown", "install": None, "language": "unknown"}

    def scan_node_dependencies(self, project_dir: str) -> Dict[str, Any]:
        """Reads package.json and returns dependency info."""
        pkg_path = os.path.join(project_dir, "package.json")
        if not os.path.exists(pkg_path):
            return {"status": "error", "message": "No package.json found."}

        try:
            with open(pkg_path, "r") as f:
                pkg = json.load(f)

            return {
                "status": "success",
                "dependencies": pkg.get("dependencies", {}),
                "devDependencies": pkg.get("devDependencies", {}),
                "scripts": pkg.get("scripts", {}),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def install_project_deps(self, project_dir: str) -> Dict[str, Any]:
        """Auto-detects package manager and runs install for any project type."""
        info = self.detect_package_manager(project_dir)
        if not info.get("install"):
            return {"status": "error", "message": f"Could not detect package manager in {project_dir}"}

        cmd = info["install"]
        self.logger.info(f"Installing {info['language']} dependencies via {info['manager']}: {cmd}")

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=project_dir, timeout=300
            )
            return {
                "status": "success" if result.returncode == 0 else "error",
                "manager": info["manager"],
                "language": info["language"],
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Dependency installation timed out (5 min limit)."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def extract_missing_node_module(self, error_text: str) -> str:
        """Parses Node.js errors to extract missing module names."""
        # Cannot find module 'express'
        match = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", error_text)
        if match:
            return match.group(1)
        # Module not found: Error: Can't resolve 'react'
        match = re.search(r"Can't resolve ['\"]([^'\"]+)['\"]", error_text)
        if match:
            return match.group(1)
        return ""
