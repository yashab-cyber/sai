"""
SAI Project Detector — Framework & Stack Detection Engine.

Scans a directory tree to identify the tech stack, framework, package manager,
and available dev/build/test commands for any project.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List

logger = logging.getLogger("SAI.ProjectDetector")


@dataclass
class ProjectProfile:
    """Detected project profile with all operational metadata."""
    root: str
    primary_language: str = "unknown"
    framework: str = "none"
    package_manager: str = "none"
    entry_point: str = ""
    dev_command: str = ""
    build_command: str = ""
    test_command: str = ""
    install_command: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)
    dev_dependencies: Dict[str, str] = field(default_factory=dict)
    detected_markers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "primary_language": self.primary_language,
            "framework": self.framework,
            "package_manager": self.package_manager,
            "entry_point": self.entry_point,
            "dev_command": self.dev_command,
            "build_command": self.build_command,
            "test_command": self.test_command,
            "install_command": self.install_command,
            "dependency_count": len(self.dependencies),
            "dev_dependency_count": len(self.dev_dependencies),
            "detected_markers": self.detected_markers,
        }


# Framework detection rules keyed by dependency names in package.json
_NODE_FRAMEWORK_MAP = {
    "next": ("nextjs", "npx next dev", "npx next build"),
    "react-scripts": ("create-react-app", "npm start", "npm run build"),
    "react": ("react", "npm run dev", "npm run build"),
    "vue": ("vue", "npm run dev", "npm run build"),
    "@angular/core": ("angular", "ng serve", "ng build"),
    "svelte": ("svelte", "npm run dev", "npm run build"),
    "nuxt": ("nuxt", "npx nuxt dev", "npx nuxt build"),
    "express": ("express", "node index.js", None),
    "fastify": ("fastify", "node index.js", None),
    "gatsby": ("gatsby", "npx gatsby develop", "npx gatsby build"),
    "astro": ("astro", "npx astro dev", "npx astro build"),
    "vite": ("vite", "npx vite", "npx vite build"),
    "electron": ("electron", "npm start", "npm run build"),
}

# Python framework detection by package presence in requirements
_PYTHON_FRAMEWORK_MAP = {
    "django": ("django", "python manage.py runserver", None),
    "flask": ("flask", "flask run", None),
    "fastapi": ("fastapi", "uvicorn main:app --reload", None),
    "streamlit": ("streamlit", "streamlit run app.py", None),
    "tornado": ("tornado", "python app.py", None),
    "pyramid": ("pyramid", "pserve development.ini", None),
}


class ProjectDetector:
    """
    Scans a directory tree and identifies the tech stack, framework,
    package manager, and available dev/build/test commands.
    """

    def detect(self, path: str) -> ProjectProfile:
        """
        Scans the given directory and returns a ProjectProfile
        describing the detected tech stack and framework.
        """
        root = os.path.abspath(path)
        profile = ProjectProfile(root=root)

        if not os.path.isdir(root):
            logger.warning(f"Path is not a directory: {root}")
            return profile

        files = set()
        for item in os.listdir(root):
            files.add(item)

        # ── Node.js / JavaScript / TypeScript ──
        if "package.json" in files:
            profile.detected_markers.append("package.json")
            self._detect_node_project(root, profile)

        # ── Python (only as primary if no JS/TS detected from package.json) ──
        if "requirements.txt" in files or "pyproject.toml" in files or "setup.py" in files:
            marker = next(m for m in ["requirements.txt", "pyproject.toml", "setup.py"] if m in files)
            profile.detected_markers.append(marker)
            if profile.primary_language == "unknown":
                self._detect_python_project(root, profile, files)

        # ── Rust ──
        if "Cargo.toml" in files and profile.primary_language == "unknown":
            profile.detected_markers.append("Cargo.toml")
            profile.primary_language = "rust"
            profile.package_manager = "cargo"
            profile.build_command = "cargo build --release"
            profile.test_command = "cargo test"
            profile.dev_command = "cargo run"
            profile.install_command = "cargo build"

        # ── Go ──
        if "go.mod" in files and profile.primary_language == "unknown":
            profile.detected_markers.append("go.mod")
            profile.primary_language = "go"
            profile.package_manager = "go"
            profile.build_command = "go build ./..."
            profile.test_command = "go test ./..."
            profile.dev_command = "go run ."
            profile.install_command = "go mod tidy"

        # ── Dart / Flutter ──
        if "pubspec.yaml" in files and profile.primary_language == "unknown":
            profile.detected_markers.append("pubspec.yaml")
            profile.primary_language = "dart"
            profile.framework = "flutter" if "flutter" in open(os.path.join(root, "pubspec.yaml")).read() else "dart"
            profile.package_manager = "pub"
            profile.build_command = "flutter build" if profile.framework == "flutter" else "dart compile"
            profile.test_command = "flutter test" if profile.framework == "flutter" else "dart test"
            profile.dev_command = "flutter run" if profile.framework == "flutter" else "dart run"
            profile.install_command = "flutter pub get" if profile.framework == "flutter" else "dart pub get"

        # ── Ruby / Rails (only as primary if no JS/Python detected) ──
        if "Gemfile" in files:
            profile.detected_markers.append("Gemfile")
            if profile.primary_language == "unknown":
                profile.primary_language = "ruby"
                profile.package_manager = "bundler"
                profile.install_command = "bundle install"
                if "config.ru" in files or os.path.isdir(os.path.join(root, "app")):
                    profile.framework = "rails"
                    profile.dev_command = "rails server"
                    profile.test_command = "rails test"
                else:
                    profile.test_command = "rspec"

        # ── Java / Kotlin ──
        if "pom.xml" in files and profile.primary_language == "unknown":
            profile.detected_markers.append("pom.xml")
            profile.primary_language = "java"
            profile.package_manager = "maven"
            profile.build_command = "mvn package"
            profile.test_command = "mvn test"
            profile.install_command = "mvn install"
        elif ("build.gradle" in files or "build.gradle.kts" in files) and profile.primary_language == "unknown":
            marker = "build.gradle.kts" if "build.gradle.kts" in files else "build.gradle"
            profile.detected_markers.append(marker)
            profile.primary_language = "kotlin" if marker.endswith(".kts") else "java"
            profile.package_manager = "gradle"
            profile.build_command = "gradle build"
            profile.test_command = "gradle test"
            profile.install_command = "gradle dependencies"

        # ── C/C++ ──
        if "CMakeLists.txt" in files and profile.primary_language == "unknown":
            profile.detected_markers.append("CMakeLists.txt")
            profile.primary_language = "c_cpp"
            profile.build_command = "cmake --build build"
            profile.install_command = "cmake -B build && cmake --build build"
        elif "Makefile" in files and profile.primary_language == "unknown":
            profile.detected_markers.append("Makefile")
            profile.primary_language = "c_cpp"
            profile.build_command = "make"

        # ── Docker (supplementary, doesn't override primary language) ──
        if "docker-compose.yml" in files or "docker-compose.yaml" in files or "compose.yml" in files:
            dc = next(f for f in ["docker-compose.yml", "docker-compose.yaml", "compose.yml"] if f in files)
            profile.detected_markers.append(dc)
        if "Dockerfile" in files:
            profile.detected_markers.append("Dockerfile")

        # ── TypeScript marker (standalone, when no package.json) ──
        if "tsconfig.json" in files and "package.json" not in files:
            profile.detected_markers.append("tsconfig.json")
            if profile.primary_language == "unknown":
                profile.primary_language = "typescript"

        return profile

    def _detect_node_project(self, root: str, profile: ProjectProfile):
        """Parse package.json to determine Node.js framework and commands."""
        pkg_path = os.path.join(root, "package.json")
        try:
            with open(pkg_path, "r") as f:
                pkg = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to parse package.json: {e}")
            return

        profile.primary_language = "javascript"

        # Check for TypeScript
        if os.path.exists(os.path.join(root, "tsconfig.json")):
            profile.primary_language = "typescript"

        # Detect package manager
        if os.path.exists(os.path.join(root, "pnpm-lock.yaml")):
            profile.package_manager = "pnpm"
            profile.install_command = "pnpm install"
        elif os.path.exists(os.path.join(root, "yarn.lock")):
            profile.package_manager = "yarn"
            profile.install_command = "yarn install"
        elif os.path.exists(os.path.join(root, "bun.lockb")):
            profile.package_manager = "bun"
            profile.install_command = "bun install"
        else:
            profile.package_manager = "npm"
            profile.install_command = "npm install"

        # Collect dependencies
        all_deps = {}
        all_deps.update(pkg.get("dependencies", {}))
        all_dev_deps = pkg.get("devDependencies", {})
        all_deps.update(all_dev_deps)
        profile.dependencies = pkg.get("dependencies", {})
        profile.dev_dependencies = all_dev_deps

        # Detect framework from dependencies
        for dep_name, (fw, dev, build) in _NODE_FRAMEWORK_MAP.items():
            if dep_name in all_deps:
                profile.framework = fw
                profile.dev_command = dev
                if build:
                    profile.build_command = build
                break

        # Override with package.json scripts if available
        scripts = pkg.get("scripts", {})
        if "dev" in scripts and not profile.dev_command:
            profile.dev_command = f"{profile.package_manager} run dev"
        elif "start" in scripts and not profile.dev_command:
            profile.dev_command = f"{profile.package_manager} start"
        if "build" in scripts:
            profile.build_command = f"{profile.package_manager} run build"
        if "test" in scripts:
            profile.test_command = f"{profile.package_manager} test"
        else:
            profile.test_command = "npx jest"

        # Entry point
        profile.entry_point = pkg.get("main", "index.js")

    def _detect_python_project(self, root: str, profile: ProjectProfile, files: set):
        """Detect Python framework from requirements or pyproject.
        Only called when no higher-priority language has been detected."""
        if profile.primary_language == "unknown":
            profile.primary_language = "python"
        profile.package_manager = profile.package_manager if profile.package_manager != "none" else "pip"
        if not profile.install_command:
            profile.install_command = "pip install -r requirements.txt"
        if not profile.test_command:
            profile.test_command = "pytest -v"

        # Read requirements to detect framework
        req_content = ""
        req_path = os.path.join(root, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r") as f:
                    req_content = f.read().lower()
            except Exception:
                pass

        # Check pyproject.toml too
        pyproject_path = os.path.join(root, "pyproject.toml")
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, "r") as f:
                    req_content += "\n" + f.read().lower()
            except Exception:
                pass
            profile.install_command = "pip install -e ."

        # Detect framework
        for pkg_name, (fw, dev, build) in _PYTHON_FRAMEWORK_MAP.items():
            if pkg_name in req_content:
                profile.framework = fw
                profile.dev_command = dev
                if build:
                    profile.build_command = build
                break

        # Entry point detection
        if "manage.py" in files:
            profile.entry_point = "manage.py"
            profile.framework = "django"
            profile.dev_command = "python manage.py runserver"
        elif "app.py" in files:
            profile.entry_point = "app.py"
        elif "main.py" in files:
            profile.entry_point = "main.py"
