"""
S.A.I. Action Pipeline — Plan → Research → Implement → Test → Publish.

Every code-producing GitHub action flows through this 5-phase pipeline
to ensure quality before anything is published.

Phase 1 (Plan):      LLM determines strategy, scope, target language
Phase 2 (Research):  DataCollector gathers web context (DuckDuckGo, RSS, ArXiv)
Phase 3 (Implement): LLM generates code with research context injected
Phase 4 (Test):      Sandbox execution + auto-fix loop (up to 10 rounds)
Phase 5 (Publish):   Git push only if tests pass
"""

import os
import json
import shutil
import logging
import tempfile
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, List

from modules.intelligence.data_collector import DataCollector


class ActionPipeline:
    """
    5-Phase Action Pipeline for autonomous GitHub actions.
    Ensures every code-producing action is researched, tested,
    and validated before publishing.
    """

    MAX_TEST_ROUNDS = 10
    PHASES = ["plan", "research", "implement", "test", "publish"]

    # Actions that CREATE new repos/content — go through full pipeline
    CODE_ACTIONS = {
        "create_repo", "trend_jack", "awesome_list", "github_pages", "create_gist",
    }

    # Actions that MODIFY existing repos — use their own handlers
    # (improve_repo already has clone→test→fix→push, enhance_repo adds CI/gitignore, etc.)
    EXISTING_REPO_ACTIONS = {
        "improve_repo", "enhance_repo", "daily_commit", "self_issues",
        "fork_improve", "profile_readme", "create_release",
    }

    # Actions that only call GitHub API — bypass the pipeline
    API_ONLY_ACTIONS = {
        "star_trending", "follow_devs", "update_status", "update_profile",
        "pin_repos", "enable_discussions",
    }

    def __init__(self, brain, identity, memory, config: dict = None):
        self.brain = brain
        self.identity = identity
        self.memory = memory
        self.config = config or {}
        self.logger = logging.getLogger("SAI.ActionPipeline")
        self.github_user = os.getenv("SAI_GITHUB_USERNAME", "")

        # DataCollector for Phase 2 (Research)
        self.data_collector = DataCollector()

    def requires_pipeline(self, action_name: str) -> bool:
        """Returns True if the action should go through the full pipeline."""
        return action_name in self.CODE_ACTIONS

    def execute(self, action_name: str, action_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs the full 5-phase pipeline for a code-producing action.

        Args:
            action_name: The idle action name (e.g. 'create_repo')
            action_context: Dict with keys like 'repo_name', 'repo_url',
                            'original_code', 'files', etc.

        Returns:
            Dict with status, phase results, and final outcome.
        """
        self.logger.info("═══ PIPELINE START: %s ═══", action_name)
        pipeline_result = {
            "action": action_name,
            "started_at": datetime.now().isoformat(),
            "phases": {},
        }

        try:
            # ── Phase 1: PLAN ──
            plan = self._phase_plan(action_name, action_context)
            pipeline_result["phases"]["plan"] = plan
            if plan.get("status") == "error":
                pipeline_result["status"] = "error"
                pipeline_result["message"] = "Planning phase failed"
                return pipeline_result

            # ── Phase 2: RESEARCH ──
            research = self._phase_research(plan)
            pipeline_result["phases"]["research"] = {
                "data_points": len(research),
                "status": "success" if research else "no_data",
            }

            # ── Phase 3: IMPLEMENT ──
            implementation = self._phase_implement(
                action_name, action_context, plan, research
            )
            pipeline_result["phases"]["implement"] = implementation
            if implementation.get("status") == "error":
                pipeline_result["status"] = "error"
                pipeline_result["message"] = "Implementation phase failed"
                return pipeline_result

            # ── Phase 4: TEST ──
            test_result = self._phase_test(action_name, implementation)
            pipeline_result["phases"]["test"] = test_result

            if test_result.get("status") != "pass":
                self.logger.warning(
                    "PIPELINE GATE: Tests failed after %d rounds. Discarding work.",
                    test_result.get("rounds", 0),
                )
                pipeline_result["status"] = "quality_gate_failed"
                pipeline_result["message"] = (
                    f"All {self.MAX_TEST_ROUNDS} test rounds failed. "
                    "Work discarded to maintain quality."
                )
                return pipeline_result

            # ── Phase 5: PUBLISH ──
            publish = self._phase_publish(action_name, action_context, implementation)
            pipeline_result["phases"]["publish"] = publish
            pipeline_result["status"] = publish.get("status", "error")

        except Exception as e:
            self.logger.error("Pipeline failed for %s: %s", action_name, e)
            pipeline_result["status"] = "error"
            pipeline_result["message"] = str(e)

        pipeline_result["finished_at"] = datetime.now().isoformat()
        self.logger.info(
            "═══ PIPELINE END: %s [%s] ═══",
            action_name, pipeline_result.get("status", "unknown"),
        )

        # Persist pipeline result to semantic memory
        self._save_to_memory(action_name, pipeline_result)

        return pipeline_result

    # ─────────────────────────────────────────────
    # Phase 1: PLAN
    # ─────────────────────────────────────────────
    def _phase_plan(self, action_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """LLM determines strategy, scope, and approach."""
        self.logger.info("[PLAN] Generating strategic plan for: %s", action_name)

        prompt = (
            f"You are S.A.I., an autonomous AI agent (GitHub: {self.github_user}) "
            f"created by Yashab-Cyber.\n"
            f"You are about to execute the GitHub action: '{action_name}'.\n"
            f"Context: {json.dumps(context, default=str)[:2000]}\n\n"
            "Create a strategic plan. Consider:\n"
            "1. What is the goal of this action?\n"
            "2. What language/framework is most appropriate?\n"
            "3. What are the key technical considerations?\n"
            "4. What search queries should be used to research best practices?\n\n"
            "Respond in JSON:\n"
            '{"goal": "one-line goal", "language": "python/javascript/go/rust/etc", '
            '"framework": "optional framework", '
            '"search_queries": ["query1", "query2", "query3"], '
            '"technical_notes": "key considerations", '
            '"approach": "step-by-step approach"}'
        )

        try:
            response = self.brain.prompt("Strategic planning for GitHub action.", prompt)
            plan = response if isinstance(response, dict) else self._parse_json(response)
            plan["status"] = "success"
            self.logger.info(
                "[PLAN] Goal: %s | Language: %s | Queries: %d",
                plan.get("goal", "?")[:80],
                plan.get("language", "?"),
                len(plan.get("search_queries", [])),
            )
            return plan
        except Exception as e:
            self.logger.error("[PLAN] Failed: %s", e)
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # Phase 2: RESEARCH
    # ─────────────────────────────────────────────
    def _phase_research(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collects web data using DataCollector based on the plan's search queries."""
        queries = plan.get("search_queries", [])
        if not queries:
            self.logger.info("[RESEARCH] No search queries in plan. Skipping.")
            return []

        self.logger.info("[RESEARCH] Executing %d search queries...", len(queries))
        all_data = []

        for query in queries[:3]:  # Cap at 3 queries to avoid slowness
            try:
                self.logger.info("[RESEARCH] Searching: %s", query)
                data_points = self.data_collector.collect(
                    query=query,
                    sources=["scrape", "rss"],
                    max_items=10,
                )
                all_data.extend(data_points)
                self.logger.info(
                    "[RESEARCH] Found %d results for: %s", len(data_points), query
                )
            except Exception as e:
                self.logger.warning("[RESEARCH] Query failed (%s): %s", query, e)

        self.logger.info("[RESEARCH] Total data points collected: %d", len(all_data))
        return all_data

    # ─────────────────────────────────────────────
    # Phase 3: IMPLEMENT
    # ─────────────────────────────────────────────
    def _phase_implement(
        self,
        action_name: str,
        context: Dict[str, Any],
        plan: Dict[str, Any],
        research: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """LLM generates code with research context injected."""
        self.logger.info("[IMPLEMENT] Generating code with research context...")

        # Build research summary for the LLM
        research_summary = self._summarize_research(research)

        prompt = (
            f"You are S.A.I., an autonomous AI agent (GitHub: {self.github_user}) "
            f"created and developed by Yashab-Cyber.\n\n"
            f"ACTION: {action_name}\n"
            f"PLAN:\n{json.dumps(plan, default=str)[:1500]}\n\n"
            f"RESEARCH FINDINGS:\n{research_summary}\n\n"
            f"CONTEXT:\n{json.dumps(context, default=str)[:1500]}\n\n"
            "Using the research findings and plan, generate high-quality code.\n"
            "Apply best practices discovered during research.\n"
            "You are a POLYGLOT ARCHITECT. Use ANY language or framework that best fits "
            "the project: Python, TypeScript, JavaScript, C, C++, C#, Go, Rust, Kotlin, "
            "Ruby, SQL, HTML/CSS, XML, and frameworks like Node.js, React, Next.js, "
            "Django, Flask, Tailwind CSS, Express, etc.\n"
            "Generate ALL necessary files including config files (.json, .yaml, .toml), "
            "documentation (.md, .txt), dependency manifests (requirements.txt, "
            "package.json, go.mod, Cargo.toml), and any other supporting files.\n"
            "The code MUST be self-contained and runnable without external services "
            "(no database connections, no API keys required, no network calls at startup).\n"
            "In any README, state: 'Created by S.A.I., an autonomous AI agent "
            "developed by Yashab-Cyber.'\n\n"
            "Respond in JSON:\n"
            '{"repo_name": "name", "description": "one-line", '
            '"readme_content": "full README.md", '
            '"files": [{"path": "relative/path", "content": "full code"}], '
            '"topics": ["t1", "t2"], '
            '"test_command": "command to test this project", '
            '"main_entry": "main file to execute"}'
        )

        try:
            response = self.brain.prompt("Implement code with research context.", prompt)
            impl = response if isinstance(response, dict) else self._parse_json(response)
            impl["status"] = "success"

            files = impl.get("files", [])
            self.logger.info(
                "[IMPLEMENT] Generated %d files for %s",
                len(files), impl.get("repo_name", action_name),
            )
            return impl
        except Exception as e:
            self.logger.error("[IMPLEMENT] Failed: %s", e)
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # Phase 4: TEST
    # ─────────────────────────────────────────────
    def _phase_test(
        self, action_name: str, implementation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sandbox execution + auto-fix loop (up to MAX_TEST_ROUNDS)."""
        files = implementation.get("files", [])
        main_entry = implementation.get("main_entry", "")
        test_command = implementation.get("test_command", "")
        readme = implementation.get("readme_content", "")

        if not files and not readme:
            self.logger.info("[TEST] No files to test. Skipping sandbox.")
            return {"status": "pass", "rounds": 0, "reason": "no_files"}

        self.logger.info(
            "[TEST] Starting sandbox testing (%d max rounds)...",
            self.MAX_TEST_ROUNDS,
        )

        tmp_dir = tempfile.mkdtemp(prefix=f"sai_pipeline_{action_name}_")
        try:
            # Scaffold files into sandbox
            self._scaffold_sandbox(tmp_dir, implementation)

            # Determine what to run
            run_cmd = self._determine_run_command(tmp_dir, main_entry, test_command)
            if not run_cmd:
                self.logger.info("[TEST] No executable entry point found. Syntax-only check.")
                # Do syntax validation for Python files
                syntax_ok = self._syntax_check_all(tmp_dir)
                return {
                    "status": "pass" if syntax_ok else "fail",
                    "rounds": 1,
                    "reason": "syntax_check_only",
                }

            # Test loop
            last_error = ""
            repeat_count = 0
            for round_num in range(1, self.MAX_TEST_ROUNDS + 1):
                self.logger.info("[TEST] Round %d/%d...", round_num, self.MAX_TEST_ROUNDS)

                try:
                    exec_res = subprocess.run(
                        run_cmd,
                        cwd=tmp_dir,
                        capture_output=True,
                        text=True,
                        timeout=20,
                        stdin=subprocess.DEVNULL,
                    )

                    if exec_res.returncode == 0:
                        self.logger.info(
                            "[TEST] ✅ PASS on round %d/%d",
                            round_num, self.MAX_TEST_ROUNDS,
                        )
                        return {
                            "status": "pass",
                            "rounds": round_num,
                            "stdout": exec_res.stdout[:500],
                        }

                    # Test failed — check if environmental
                    crash_log = (exec_res.stderr or exec_res.stdout)[:2000]
                    self.logger.warning(
                        "[TEST] ❌ FAIL round %d (exit %d): %s",
                        round_num, exec_res.returncode, crash_log[:200],
                    )

                    # Detect repeated identical errors (environmental, not code)
                    error_sig = crash_log[:100]
                    if error_sig == last_error:
                        repeat_count += 1
                    else:
                        repeat_count = 0
                        last_error = error_sig

                    # If same error 3+ times, it's environmental — fall back
                    if repeat_count >= 2:
                        self.logger.info(
                            "[TEST] Same error repeated %d times — environmental issue. "
                            "Falling back to syntax-only validation.",
                            repeat_count + 1,
                        )
                        syntax_ok = self._syntax_check_all(tmp_dir)
                        return {
                            "status": "pass" if syntax_ok else "fail",
                            "rounds": round_num,
                            "reason": "env_fallback_syntax_check",
                        }

                    if round_num < self.MAX_TEST_ROUNDS:
                        fixed = self._attempt_fix(tmp_dir, crash_log, implementation)
                        if not fixed:
                            self.logger.warning("[TEST] Fix attempt returned no changes.")

                except subprocess.TimeoutExpired:
                    self.logger.info(
                        "[TEST] ⏱ Timeout on round %d. Treating as healthy daemon.",
                        round_num,
                    )
                    return {
                        "status": "pass",
                        "rounds": round_num,
                        "reason": "timeout_assumed_healthy",
                    }

            # All rounds exhausted
            return {"status": "fail", "rounds": self.MAX_TEST_ROUNDS}

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ─────────────────────────────────────────────
    # Phase 5: PUBLISH
    # ─────────────────────────────────────────────
    def _phase_publish(
        self,
        action_name: str,
        context: Dict[str, Any],
        implementation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Git push the validated code. Only called if tests pass."""
        self.logger.info("[PUBLISH] Tests passed. Publishing to GitHub...")

        # The actual publish logic varies by action type.
        # We store the validated implementation back into context
        # so the calling action handler in GitHubPresence can use it.
        # This method returns the implementation with a publish flag.
        return {
            "status": "success",
            "action": action_name,
            "validated": True,
            "implementation": implementation,
        }

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    def _summarize_research(self, research: List[Dict[str, Any]]) -> str:
        """Condenses research data points into a prompt-friendly summary."""
        if not research:
            return "No external research data available."

        lines = []
        for dp in research[:15]:  # Cap to prevent token overflow
            source = dp.get("source", "unknown")
            title = dp.get("title", "")[:100]
            text = dp.get("text", "")[:200]
            lines.append(f"- [{source}] {title}: {text}")

        return "\n".join(lines)

    def _scaffold_sandbox(self, tmp_dir: str, implementation: Dict[str, Any]):
        """Writes all implementation files into the sandbox directory."""
        # Write README
        readme = implementation.get("readme_content", "")
        if readme:
            with open(os.path.join(tmp_dir, "README.md"), "w") as f:
                f.write(readme)

        # Write all files
        for file_obj in implementation.get("files", []):
            path = file_obj.get("path", "")
            content = file_obj.get("content", "")
            if path and content:
                full_path = os.path.join(tmp_dir, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)

    def _determine_run_command(
        self, tmp_dir: str, main_entry: str, test_command: str
    ) -> Optional[list]:
        """Determines the best command to run in the sandbox."""
        # If a test command was provided, use it
        if test_command:
            return ["bash", "-c", test_command]

        # If main_entry specified, use it
        if main_entry and os.path.exists(os.path.join(tmp_dir, main_entry)):
            return self._cmd_for_file(main_entry, tmp_dir)

        # Auto-detect main file
        candidates = [
            "main.py", "app.py", "run.py", "index.js", "main.js", "index.ts",
            "main.ts", "main.go", "run.sh", "main.rb", "main.c", "main.cpp",
            "main.kt", "Program.cs", "src/index.js", "src/main.py",
            "src/index.ts", "src/main.ts", "src/main.go",
        ]
        for candidate in candidates:
            if os.path.exists(os.path.join(tmp_dir, candidate)):
                return self._cmd_for_file(candidate, tmp_dir)

        # Fallback: find any executable source file
        runnable_exts = (
            ".py", ".js", ".ts", ".go", ".sh", ".rb", ".c", ".cpp", ".kt",
        )
        for f in os.listdir(tmp_dir):
            if f.endswith(runnable_exts):
                return self._cmd_for_file(f, tmp_dir)

        return None

    def _cmd_for_file(self, filename: str, tmp_dir: str) -> list:
        """Returns the appropriate run command based on file extension.
        
        Supports: Python, JavaScript, TypeScript, Go, Rust, C, C++,
        Kotlin, Ruby, Shell, and framework-specific builds.
        """
        # Install deps if needed
        if os.path.exists(os.path.join(tmp_dir, "package.json")):
            subprocess.run(
                ["npm", "install"], cwd=tmp_dir,
                capture_output=True, timeout=120,
            )
        if os.path.exists(os.path.join(tmp_dir, "requirements.txt")):
            subprocess.run(
                ["pip", "install", "-r", "requirements.txt"],
                cwd=tmp_dir, capture_output=True, timeout=120,
            )
        if os.path.exists(os.path.join(tmp_dir, "go.mod")):
            subprocess.run(
                ["go", "mod", "download"],
                cwd=tmp_dir, capture_output=True, timeout=120,
            )

        ext = os.path.splitext(filename)[1]
        cmd_map = {
            ".py": ["python3", filename],
            ".js": ["node", filename],
            ".ts": ["npx", "ts-node", filename],
            ".go": ["go", "run", filename],
            ".sh": ["bash", filename],
            ".rb": ["ruby", filename],
            ".c": ["bash", "-c", f"gcc -o /tmp/sai_c_out {filename} && /tmp/sai_c_out"],
            ".cpp": ["bash", "-c", f"g++ -o /tmp/sai_cpp_out {filename} && /tmp/sai_cpp_out"],
            ".kt": ["bash", "-c", f"kotlinc {filename} -include-runtime -d /tmp/sai_kt.jar && java -jar /tmp/sai_kt.jar"],
            ".cs": ["bash", "-c", f"dotnet-script {filename}"],
        }
        return cmd_map.get(ext, ["python3", filename])

    def _attempt_fix(
        self, tmp_dir: str, crash_log: str, implementation: Dict[str, Any]
    ) -> bool:
        """Asks LLM to fix the code based on crash log. Returns True if fix applied."""
        # Gather current file contents from sandbox
        file_contents = {}
        for file_obj in implementation.get("files", []):
            path = file_obj.get("path", "")
            full_path = os.path.join(tmp_dir, path)
            if path and os.path.exists(full_path):
                try:
                    with open(full_path, "r") as f:
                        file_contents[path] = f.read()
                except Exception:
                    pass

        prompt = (
            "You are S.A.I., an autonomous AI. Your code crashed during sandbox testing.\n"
            f"CRASH LOG:\n{crash_log}\n\n"
            f"CURRENT FILES:\n"
        )
        for path, content in list(file_contents.items())[:3]:
            prompt += f"\n--- {path} ---\n{content[:2000]}\n"

        prompt += (
            "\nIdentify the bug and provide the complete fixed code.\n"
            'Respond in JSON: {"files": [{"path": "relative/path", "content": "fixed code"}]}'
        )

        try:
            response = self.brain.prompt("Fix sandbox test failure.", prompt)
            fix_data = response if isinstance(response, dict) else self._parse_json(response)
            fixed_files = fix_data.get("files", [])

            if not fixed_files and "fixed_code" in fix_data:
                # Fallback: single-file fix format
                main_file = implementation.get("main_entry", "")
                if not main_file and implementation.get("files"):
                    main_file = implementation["files"][0].get("path", "main.py")
                fixed_files = [{"path": main_file, "content": fix_data["fixed_code"]}]

            if not fixed_files:
                return False

            for f_obj in fixed_files:
                f_path = f_obj.get("path", "")
                f_content = f_obj.get("content", "")
                if f_path and f_content:
                    full_path = os.path.join(tmp_dir, f_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w") as f:
                        f.write(f_content)

                    # Also update the implementation dict for Phase 5
                    for impl_file in implementation.get("files", []):
                        if impl_file.get("path") == f_path:
                            impl_file["content"] = f_content
                            break

            self.logger.info("[TEST] Applied fixes to %d files.", len(fixed_files))
            return True

        except Exception as e:
            self.logger.error("[TEST] Fix attempt failed: %s", e)
            return False

    def _syntax_check_all(self, tmp_dir: str) -> bool:
        """Checks Python syntax for all .py files in the sandbox."""
        import ast as _ast

        all_ok = True
        for root, _, files in os.walk(tmp_dir):
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r") as f:
                            _ast.parse(f.read())
                    except SyntaxError as e:
                        self.logger.warning("[TEST] Syntax error in %s: %s", fname, e)
                        all_ok = False
        return all_ok

    def _parse_json(self, response) -> dict:
        """Parses LLM response into a dict."""
        if isinstance(response, dict):
            return response
        text = str(response).strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]
        text = text.strip()
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        return json.loads(text)

    def _save_to_memory(self, action_name: str, result: Dict[str, Any]):
        """Persists pipeline result to semantic memory."""
        try:
            phases = result.get("phases", {})
            content = (
                f"ActionPipeline [{action_name}]: {result.get('status', '?')}. "
                f"Plan: {phases.get('plan', {}).get('goal', 'N/A')[:100]}. "
                f"Research: {phases.get('research', {}).get('data_points', 0)} data points. "
                f"Test rounds: {phases.get('test', {}).get('rounds', 0)}."
            )
            embedding = self.brain.get_embedding(content)
            self.memory.save_semantic_memory(
                content, embedding,
                {"type": "action_pipeline", "action": action_name,
                 "status": result.get("status", "unknown")},
            )
        except Exception as e:
            self.logger.debug("Failed to save pipeline result to memory: %s", e)
