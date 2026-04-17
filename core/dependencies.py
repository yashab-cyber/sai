import ast
import os
import re
import logging
import subprocess
from typing import Set, List, Dict, Any

class DependencyManager:
    """
    Phase 5: Automated Dependency Management.
    Keeps SAI self-reliant by tracking, resolving, and installing 
    dependencies dynamically for both host and Docker sandbox execution.
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
        "base64", "hashlib", "argparse", "copy", "itertools", "collections", "uuid", "asyncio"
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
            try:
                # Quick test if it exists
                subprocess.check_output([sys.executable, "-c", f"import {pkg}"])
            except:
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
