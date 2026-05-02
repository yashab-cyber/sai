"""
SAI Language Registry — Polyglot Intelligence Layer.

Maps file extensions to language-specific tooling (linters, formatters,
test runners, structure extractors) so the Coder module can operate
on any supported language without hardcoded Python assumptions.
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger("SAI.LanguageRegistry")


@dataclass
class LanguageConfig:
    """Configuration for a single programming language."""
    name: str
    extensions: List[str]
    linter: Optional[str] = None
    formatter: Optional[str] = None
    test_cmd: Optional[str] = None
    build_cmd: Optional[str] = None
    dev_cmd: Optional[str] = None
    comment_style: str = "//"
    block_comment: tuple = ("/*", "*/")
    function_pattern: Optional[str] = None
    class_pattern: Optional[str] = None
    import_pattern: Optional[str] = None


class LanguageRegistry:
    """
    Central registry mapping file extensions to language tooling configurations.
    """

    _LANGUAGES: Dict[str, LanguageConfig] = {}

    @classmethod
    def _init_registry(cls):
        if cls._LANGUAGES:
            return

        configs = [
            LanguageConfig(
                name="python", extensions=[".py", ".pyw", ".pyi"],
                linter="flake8 {file}", formatter="black {file}",
                test_cmd="pytest {file} -v --tb=short",
                comment_style="#", block_comment=('"""', '"""'),
                function_pattern=r'(?:async\s+)?def\s+(\w+)\s*\(',
                class_pattern=r'class\s+(\w+)\s*[\(:]',
                import_pattern=r'(?:from\s+(\S+)\s+)?import\s+(.+)',
            ),
            LanguageConfig(
                name="javascript", extensions=[".js", ".jsx", ".mjs", ".cjs"],
                linter="npx eslint {file}", formatter="npx prettier --write {file}",
                test_cmd="npx jest {file}", build_cmd="npm run build", dev_cmd="npm run dev",
                function_pattern=r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?.*?\)?\s*=>',
                class_pattern=r'(?:export\s+)?class\s+(\w+)',
                import_pattern=r'import\s+.*?\s+from\s+[\'"](.+?)[\'"]|require\s*\(\s*[\'"](.+?)[\'"]\s*\)',
            ),
            LanguageConfig(
                name="typescript", extensions=[".ts", ".tsx"],
                linter="npx eslint {file}", formatter="npx prettier --write {file}",
                test_cmd="npx jest {file}", build_cmd="npx tsc", dev_cmd="npm run dev",
                function_pattern=r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*[\(<]|(?:const|let|var)\s+(\w+)\s*(?::\s*\w+)?\s*=\s*(?:async\s+)?\(?.*?\)?\s*=>',
                class_pattern=r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)',
                import_pattern=r'import\s+.*?\s+from\s+[\'"](.+?)[\'"]',
            ),
            LanguageConfig(
                name="rust", extensions=[".rs"],
                linter="cargo clippy", formatter="cargo fmt",
                test_cmd="cargo test", build_cmd="cargo build --release", dev_cmd="cargo run",
                function_pattern=r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)',
                class_pattern=r'(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)',
                import_pattern=r'use\s+(.+?);',
            ),
            LanguageConfig(
                name="go", extensions=[".go"],
                linter="golangci-lint run {file}", formatter="gofmt -w {file}",
                test_cmd="go test ./...", build_cmd="go build ./...", dev_cmd="go run .",
                function_pattern=r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(',
                class_pattern=r'type\s+(\w+)\s+struct',
                import_pattern=r'import\s+(?:\(\s*([^)]+)\s*\)|"(.+?)")',
            ),
            LanguageConfig(
                name="html", extensions=[".html", ".htm"],
                formatter="npx prettier --write {file}",
                comment_style="<!--", block_comment=("<!--", "-->"),
                import_pattern=r'<(?:script|link)\s+.*?(?:src|href)=[\'"](.+?)[\'"]',
            ),
            LanguageConfig(
                name="css", extensions=[".css", ".scss", ".sass", ".less"],
                linter="npx stylelint {file}", formatter="npx prettier --write {file}",
                function_pattern=r'@mixin\s+(\w+)',
                class_pattern=r'\.(\w[\w-]*)\s*\{',
                import_pattern=r'@import\s+[\'"](.+?)[\'"]|@use\s+[\'"](.+?)[\'"]',
            ),
            LanguageConfig(
                name="java", extensions=[".java"],
                formatter="google-java-format -i {file}",
                test_cmd="mvn test", build_cmd="mvn package",
                function_pattern=r'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(',
                class_pattern=r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)',
                import_pattern=r'import\s+(.+?);',
            ),
            LanguageConfig(
                name="kotlin", extensions=[".kt", ".kts"],
                formatter="ktlint -F {file}",
                test_cmd="gradle test", build_cmd="gradle build",
                function_pattern=r'(?:suspend\s+)?fun\s+(\w+)',
                class_pattern=r'(?:data\s+|sealed\s+|abstract\s+)?class\s+(\w+)',
                import_pattern=r'import\s+(.+)',
            ),
            LanguageConfig(
                name="c_cpp", extensions=[".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"],
                formatter="clang-format -i {file}", build_cmd="make",
                function_pattern=r'(?:\w[\w*&\s]+)\s+(\w+)\s*\([^;]*\)\s*\{',
                class_pattern=r'(?:class|struct)\s+(\w+)',
                import_pattern=r'#include\s+[<"](.+?)[>"]',
            ),
            LanguageConfig(
                name="shell", extensions=[".sh", ".bash", ".zsh"],
                linter="shellcheck {file}", comment_style="#",
                function_pattern=r'(?:function\s+)?(\w+)\s*\(\s*\)',
                import_pattern=r'(?:source|\.)\s+(.+)',
            ),
            LanguageConfig(
                name="ruby", extensions=[".rb", ".rake"],
                linter="rubocop {file}", formatter="rubocop -a {file}",
                test_cmd="rspec", dev_cmd="rails server", comment_style="#",
                function_pattern=r'def\s+(\w+)',
                class_pattern=r'class\s+(\w+)',
                import_pattern=r'require\s+[\'"](.+?)[\'"]',
            ),
            LanguageConfig(
                name="dart", extensions=[".dart"],
                linter="dart analyze {file}", formatter="dart format {file}",
                test_cmd="flutter test", build_cmd="flutter build", dev_cmd="flutter run",
                function_pattern=r'(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*(?:async\s*)?\{',
                class_pattern=r'(?:abstract\s+)?class\s+(\w+)',
                import_pattern=r'import\s+[\'"](.+?)[\'"]',
            ),
            LanguageConfig(
                name="swift", extensions=[".swift"],
                formatter="swiftformat {file}",
                test_cmd="swift test", build_cmd="swift build",
                function_pattern=r'func\s+(\w+)',
                class_pattern=r'(?:class|struct|protocol|enum)\s+(\w+)',
                import_pattern=r'import\s+(\w+)',
            ),
            LanguageConfig(
                name="sql", extensions=[".sql"],
                formatter="sqlfluff fix {file}", comment_style="--",
                function_pattern=r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+(\w+)',
                class_pattern=r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)',
            ),
            LanguageConfig(name="yaml", extensions=[".yaml", ".yml"], linter="yamllint {file}", comment_style="#"),
            LanguageConfig(name="json", extensions=[".json", ".jsonc"], formatter="npx prettier --write {file}"),
            LanguageConfig(name="markdown", extensions=[".md", ".mdx"], formatter="npx prettier --write {file}"),
            LanguageConfig(name="toml", extensions=[".toml"], comment_style="#"),
            LanguageConfig(name="dockerfile", extensions=[], linter="hadolint {file}", comment_style="#"),
        ]

        for cfg in configs:
            cls._LANGUAGES[cfg.name] = cfg

    @classmethod
    def detect_language(cls, filepath: str) -> Optional[LanguageConfig]:
        """Detects the programming language from a file path."""
        cls._init_registry()
        basename = os.path.basename(filepath).lower()

        if basename in ("dockerfile", "containerfile"):
            return cls._LANGUAGES.get("dockerfile")
        if basename in ("makefile", "gnumakefile"):
            return cls._LANGUAGES.get("shell")

        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        if not ext:
            return None

        for lang_config in cls._LANGUAGES.values():
            if ext in lang_config.extensions:
                return lang_config
        return None

    @classmethod
    def get_language(cls, name: str) -> Optional[LanguageConfig]:
        cls._init_registry()
        return cls._LANGUAGES.get(name)

    @classmethod
    def supported_extensions(cls) -> List[str]:
        cls._init_registry()
        exts = []
        for cfg in cls._LANGUAGES.values():
            exts.extend(cfg.extensions)
        return exts

    @classmethod
    def extract_structure(cls, filepath: str, code: str) -> Dict[str, Any]:
        """
        Extracts structural elements (functions, classes, imports) from source
        code using regex patterns defined in the language config.
        """
        lang = cls.detect_language(filepath)
        if not lang:
            return {"language": "unknown", "functions": [], "classes": [], "imports": []}

        functions, classes, imports = [], [], []

        if lang.function_pattern:
            for match in re.finditer(lang.function_pattern, code, re.MULTILINE):
                name = next((g for g in match.groups() if g is not None), None)
                if name and not name.startswith("_"):
                    line_num = code[:match.start()].count('\n') + 1
                    functions.append({"name": name, "line": line_num})

        if lang.class_pattern:
            for match in re.finditer(lang.class_pattern, code, re.MULTILINE):
                name = next((g for g in match.groups() if g is not None), None)
                if name:
                    line_num = code[:match.start()].count('\n') + 1
                    classes.append({"name": name, "line": line_num})

        if lang.import_pattern:
            for match in re.finditer(lang.import_pattern, code, re.MULTILINE):
                imp = next((g for g in match.groups() if g is not None), None)
                if imp:
                    imports.append(imp.strip())

        return {"language": lang.name, "functions": functions, "classes": classes, "imports": imports}

    @classmethod
    def get_linter_command(cls, filepath: str) -> Optional[str]:
        lang = cls.detect_language(filepath)
        if lang and lang.linter:
            return lang.linter.replace("{file}", filepath)
        return None

    @classmethod
    def get_formatter_command(cls, filepath: str) -> Optional[str]:
        lang = cls.detect_language(filepath)
        if lang and lang.formatter:
            return lang.formatter.replace("{file}", filepath)
        return None

    @classmethod
    def get_test_command(cls, filepath: str) -> Optional[str]:
        lang = cls.detect_language(filepath)
        if lang and lang.test_cmd:
            return lang.test_cmd.replace("{file}", filepath)
        return None

    @classmethod
    def is_python(cls, filepath: str) -> bool:
        lang = cls.detect_language(filepath)
        return lang is not None and lang.name == "python"
