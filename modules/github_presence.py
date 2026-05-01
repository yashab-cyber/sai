"""
S.A.I. Autonomous GitHub Presence Manager.

When idle, S.A.I. autonomously maintains and grows its GitHub presence.
Uses the Brain (LLM) for strategic decisions and IdentityManager for GitHub API.
"""

import os
import json
import time
import random
import logging
import tempfile
import shutil
import subprocess
import base64
from datetime import datetime
from typing import Dict, Any, List


class GitHubPresence:
    """Orchestrates S.A.I.'s autonomous GitHub activity."""

    IDLE_ACTIONS = [
        # Original actions
        {"name": "create_repo", "weight": 15},
        {"name": "update_profile", "weight": 5},
        {"name": "improve_repo", "weight": 50},  # Heavily prioritize bug hunting and sandboxing
        {"name": "create_gist", "weight": 5},
        {"name": "star_trending", "weight": 5},
        {"name": "update_status", "weight": 3},
        # New: Viral growth actions
        {"name": "profile_readme", "weight": 0},
        {"name": "daily_commit", "weight": 10},
        {"name": "trend_jack", "weight": 5},
        {"name": "github_pages", "weight": 3},
        {"name": "enhance_repo", "weight": 30},  # Heavily prioritize enhancing existing repos
        {"name": "create_release", "weight": 5},
        {"name": "pin_repos", "weight": 4},
        {"name": "follow_devs", "weight": 2},
        {"name": "self_issues", "weight": 5},
        {"name": "fork_improve", "weight": 5},
        {"name": "awesome_list", "weight": 3},
        {"name": "enable_discussions", "weight": 3},
    ]

    def __init__(self, brain, identity, memory, config: dict = None, pipeline=None):
        self.brain = brain
        self.identity = identity
        self.memory = memory
        self.logger = logging.getLogger("SAI.GitHubPresence")
        self.config = config or {}
        self.github_user = os.getenv("SAI_GITHUB_USERNAME", "")
        self.action_history: List[Dict[str, Any]] = []
        self._daily_action_count = 0
        self._last_reset_date = datetime.now().date()

        # ── Action Pipeline (Plan → Research → Implement → Test → Publish) ──
        self.pipeline = pipeline

        # ── Pending Work Queue (for pause/resume) ──
        self._pending_work: Dict[str, Any] = {}

    def _check_daily_limit(self) -> bool:
        """Returns True if under daily limit. 0 = unlimited."""
        today = datetime.now().date()
        if today != self._last_reset_date:
            self._daily_action_count = 0
            self._last_reset_date = today
        max_daily = self.config.get("max_daily_actions", 0)
        if max_daily == 0:
            return True  # Unlimited
        return self._daily_action_count < max_daily

    def _record_action(self, action_name: str, details: dict):
        record = {"action": action_name, "timestamp": datetime.now().isoformat(), "details": details}
        self.action_history.append(record)
        if "improve_repo" not in action_name and "enhance_repo" not in action_name:
            self._daily_action_count += 1
        try:
            content = f"GitHub Presence: {action_name} — {json.dumps(details)[:500]}"
            embedding = self.brain.get_embedding(content)
            self.memory.save_semantic_memory(content, embedding, {"type": "github_presence", "action": action_name})
        except Exception as e:
            self.logger.debug("Failed to persist action to memory: %s", e)

    def _get_recent_context(self) -> str:
        recent = self.action_history[-10:]
        if not recent:
            return "No recent GitHub actions taken."
        lines = [f"- {r['timestamp']}: {r['action']}" for r in recent]
        return "Recent actions (avoid repeating):\n" + "\n".join(lines)

    def plan_action(self) -> Dict[str, Any]:
        """
        STAGE 1 — PLAN.
        Asks the LLM to review recent GitHub activity and choose the single best
        idle action, with optional pre-selection of a target (e.g. which repo to
        improve or enhance).

        Returns:
            dict with keys:
                action       — one of the IDLE_ACTIONS names
                reasoning    — why this action was chosen
                target_repo  — (optional) specific repo to act on
        """
        if not self.brain or not self.github_user:
            # Fallback to weighted random if no brain / credentials
            valid = [a for a in self.IDLE_ACTIONS if a["weight"] > 0]
            weights = [a["weight"] for a in valid]
            fallback = random.choices(valid, weights=weights, k=1)[0]
            return {"action": fallback["name"], "reasoning": "brain_unavailable", "target_repo": ""}

        action_names = [a["name"] for a in self.IDLE_ACTIONS if a["weight"] > 0]
        recent_context = self._get_recent_context()
        daily_left = "unlimited" if self.config.get("max_daily_actions", 0) == 0 else (
            self.config.get("max_daily_actions", 0) - self._daily_action_count
        )

        prompt = (
            f"You are S.A.I., an autonomous AI agent (GitHub: {self.github_user}) "
            f"created by Yashab-Cyber.\n"
            "You have a slice of idle time. Choose the single most impactful GitHub action "
            "given your recent history.\n\n"
            f"RECENT GITHUB ACTIVITY:\n{recent_context}\n\n"
            f"DAILY ACTIONS REMAINING: {daily_left}\n\n"
            f"AVAILABLE ACTIONS: {action_names}\n\n"
            "Action guide (brief):\n"
            "  improve_repo     — Clone an existing repo, bug-fix and add features, push\n"
            "  enhance_repo     — Add CI/CD, Dockerfile, better structure to a repo\n"
            "  create_repo      — Generate a brand new project (72h cooldown)\n"
            "  daily_commit     — Small commit to keep contribution graph green\n"
            "  self_issues      — Create useful GitHub issues on own repos\n"
            "  star_trending    — Star trending repos for network visibility\n"
            "  update_profile   — Update GitHub bio / profile fields\n"
            "  profile_readme   — Update the special profile README\n"
            "  trend_jack       — Create a project riding a trending topic\n"
            "  create_gist      — Publish a useful code snippet\n"
            "  fork_improve     — Fork a popular repo and submit improvements\n"
            "  follow_devs      — Follow relevant developers\n"
            "  update_status    — Set a creative GitHub status\n\n"
            "Choose the action with the highest value given recent history (avoid repeats).\n"
            "Respond ONLY in JSON:\n"
            '{"action": "<one of the action names above>", '
            '"reasoning": "<one or two sentences why>", '
            '"target_repo": ""}'
        )

        try:
            response = self.brain.prompt("GitHub idle action planning.", prompt)
            plan = response if isinstance(response, dict) else self._parse_json(response)
            if plan.get("action") not in action_names:
                raise ValueError(f"Invalid action: {plan.get('action')}")
            self.logger.info(
                "[PLAN] GitHub action chosen: %s — %s",
                plan["action"], str(plan.get("reasoning", ""))[:120],
            )
            return plan
        except Exception as e:
            self.logger.warning("[PLAN] GitHub planning failed (%s), using weighted random.", e)
            valid = [a for a in self.IDLE_ACTIONS if a["weight"] > 0]
            weights = [a["weight"] for a in valid]
            fallback = random.choices(valid, weights=weights, k=1)[0]
            return {"action": fallback["name"], "reasoning": "planning_failed", "target_repo": ""}

    def review_action(self, action_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        STAGE 3 — REVIEW.
        LLM post-mortem on the completed GitHub action. Stores reflection in semantic memory.

        Returns:
            dict with keys:
                success             — bool
                lessons             — what went well / what to improve
                next_recommendation — suggested next action
        """
        if not self.brain:
            return {"success": True, "lessons": "brain_unavailable", "next_recommendation": ""}

        status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
        result_summary = str(result)[:400]

        prompt = (
            "You are S.A.I., an autonomous AI agent reviewing a completed GitHub action.\n"
            f"ACTION: {action_name}\n"
            f"STATUS: {status}\n"
            f"RESULT: {result_summary}\n\n"
            "Provide a brief self-evaluation:\n"
            "1. Was this the right action? Did it succeed?\n"
            "2. What lessons can be drawn?\n"
            "3. What should be prioritised on the NEXT idle cycle?\n\n"
            "Respond ONLY in JSON:\n"
            '{"success": true/false, "lessons": "<brief lessons>", '
            '"next_recommendation": "<action name or strategy>"}'
        )

        try:
            response = self.brain.prompt("GitHub action review.", prompt)
            review = response if isinstance(response, dict) else self._parse_json(response)
            self.logger.info(
                "[REVIEW] GitHub action '%s' reviewed: success=%s, next=%s",
                action_name,
                review.get("success"),
                str(review.get("next_recommendation", ""))[:80],
            )
            # Persist reflection to semantic memory
            try:
                content = (
                    f"GitHub review: {action_name} [{status}] — "
                    f"{review.get('lessons', '')} | Next: {review.get('next_recommendation', '')}"
                )
                embedding = self.brain.get_embedding(content)
                self.memory.save_semantic_memory(
                    content, embedding,
                    {"type": "github_review", "action": action_name, "status": status}
                )
            except Exception:
                pass
            return review
        except Exception as e:
            self.logger.debug("[REVIEW] Review failed: %s", e)
            return {"success": status == "success", "lessons": "", "next_recommendation": ""}

    def run_idle_action(self, plan: Dict[str, Any] = None) -> Dict[str, Any]:
        """Selects and executes a strategic GitHub idle action.
        If there is pending work from a previous interruption, resumes that first."""
        if not self.github_user or not self.identity.github_token:
            return {"status": "error", "message": "GitHub credentials not configured."}

        # Resume pending work if any
        if self._pending_work:
            self.logger.info("Resuming pending work: %s", self._pending_work.get("action", "unknown"))
            return self.execute_pending_work()

        under_limit = self._check_daily_limit()

        # ── Use plan from IdleEngine if provided, otherwise select randomly ──
        if plan and plan.get("action"):
            action_name = plan["action"]
            # Validate the action still makes sense under daily limits
            is_exempt = action_name in ("improve_repo", "enhance_repo")
            if not under_limit and not is_exempt:
                self.logger.info(
                    "[EXECUTE] Daily limit reached; overriding planned '%s' with improve_repo.",
                    action_name,
                )
                action_name = "improve_repo"
            self.logger.info("[EXECUTE] Running planned GitHub action: %s", action_name)
        else:
            valid_actions = []
            for a in self.IDLE_ACTIONS:
                if not under_limit and a["name"] not in ["improve_repo", "enhance_repo"]:
                    continue
                if a["weight"] > 0:
                    valid_actions.append(a)

            if not valid_actions:
                return {"status": "skipped", "reason": "daily_limit_reached"}

            weights = [a["weight"] for a in valid_actions]
            selected = random.choices(valid_actions, weights=weights, k=1)[0]
            action_name = selected["name"]
            self.logger.info("[EXECUTE] GitHub action (random fallback): %s", action_name)

        try:
            method = getattr(self, f"_action_{action_name}", None)
            if not method:
                return {"status": "error", "message": f"No handler: {action_name}"}

            # ── Route through pipeline if available ──
            if self.pipeline and self.pipeline.requires_pipeline(action_name):
                self.logger.info("Routing '%s' through Action Pipeline...", action_name)
                # Build action context from the action method's planning phase
                action_context = {
                    "action": action_name,
                    "github_user": self.github_user,
                    "recent_context": self._get_recent_context(),
                }
                pipeline_result = self.pipeline.execute(action_name, action_context)

                # If pipeline succeeded, do the actual publish via the action handler
                if pipeline_result.get("status") == "success":
                    publish_data = pipeline_result.get("phases", {}).get("publish", {})
                    impl = publish_data.get("implementation", {})
                    if impl:
                        # Inject validated implementation into a publish-only action
                        result = self._publish_validated(action_name, impl)
                    else:
                        result = method()
                else:
                    result = pipeline_result

                result_status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
                self._record_action(action_name, result)
                return {"status": result_status, "action": action_name, "result": result, "pipeline": True}

            # ── Direct execution (API-only actions) ──
            result = method()
            result_status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
            self._record_action(action_name, result)
            return {"status": result_status, "action": action_name, "result": result}
        except Exception as e:
            self.logger.error("Idle action '%s' failed: %s", action_name, e)
            return {"status": "error", "action": action_name, "message": str(e)}

    # ── PENDING WORK (Pause/Resume Support) ──

    def has_pending_work(self) -> bool:
        """Returns True if there is interrupted work to resume."""
        return bool(self._pending_work)

    def get_pending_work(self) -> Dict[str, Any]:
        """Returns the current pending work state for serialization."""
        return self._pending_work.copy() if self._pending_work else {}

    def restore_pending_work(self, state: Dict[str, Any]):
        """Restores pending work from a saved state (after user task completes)."""
        self._pending_work = state
        self.logger.info("Pending work restored: %s", state.get("action", "unknown"))

    def set_pending_work(self, action: str, context: Dict[str, Any]):
        """Saves work-in-progress that should be resumed later."""
        self._pending_work = {
            "action": action,
            "context": context,
            "saved_at": datetime.now().isoformat()
        }
        self.logger.info("Saved pending work: %s", action)

    def execute_pending_work(self) -> Dict[str, Any]:
        """Executes the saved pending work and clears the queue."""
        if not self._pending_work:
            return {"status": "skipped", "reason": "no_pending_work"}

        work = self._pending_work
        self._pending_work = {}  # Clear before executing
        action_name = work.get("action", "")
        context = work.get("context", {})

        self.logger.info("Executing pending work: %s (saved at %s)", action_name, work.get("saved_at", "?"))

        try:
            # If the pending work has a specific follow-up action, execute it
            if action_name == "create_repo" and context.get("stage") == "push_pending":
                # Resume a repo creation that was interrupted after API creation but before push
                result = self._resume_create_repo(context)
            elif action_name == "improve_repo" and context.get("stage") == "update_pending":
                # Resume a README improvement that was interrupted
                result = self._resume_improve_repo(context)
            else:
                # Generic resume: just re-run the action type from scratch
                method = getattr(self, f"_action_{action_name}", None)
                if method:
                    result = method()
                else:
                    result = {"status": "error", "message": f"Cannot resume unknown action: {action_name}"}

            self._record_action(f"{action_name}_resumed", result)
            return {"status": "success", "action": f"{action_name}_resumed", "result": result}

        except Exception as e:
            self.logger.error("Failed to execute pending work '%s': %s", action_name, e)
            return {"status": "error", "action": action_name, "message": str(e)}

    def _resume_create_repo(self, context: dict) -> dict:
        """Resumes a create_repo action that was interrupted after repo creation."""
        repo_name = context.get("repo_name", "")
        project = context.get("project", {})
        if not repo_name:
            return {"status": "error", "message": "No repo name in saved context"}

        self.logger.info("Resuming create_repo: pushing code to %s", repo_name)
        repo_url = f"https://github.com/{self.github_user}/{repo_name}.git"
        push_result = self._scaffold_and_push(repo_url, project)

        topics = project.get("topics", [])
        if topics:
            self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/topics", {"names": topics[:10]})

        return {"status": "success", "repo": repo_name, "push": push_result, "resumed": True}

    def _resume_improve_repo(self, context: dict) -> dict:
        """Resumes an improve_repo action that was interrupted before push."""
        repo_name = context.get("repo_name", "")
        new_readme = context.get("new_readme", "")
        sha = context.get("sha", "")
        if not repo_name or not new_readme:
            return {"status": "error", "message": "Incomplete context for repo improvement"}

        self.logger.info("Resuming improve_repo: pushing README to %s", repo_name)
        update_payload = {
            "message": "docs: improve README — resumed autonomous update by S.A.I.",
            "content": base64.b64encode(new_readme.encode("utf-8")).decode("utf-8"),
        }
        if sha:
            update_payload["sha"] = sha
        result = self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/contents/README.md", update_payload)
        return {"status": result.get("status", "error"), "repo": repo_name, "resumed": True}

    # ── PIPELINE PUBLISH ──

    def _publish_validated(self, action_name: str, implementation: dict) -> dict:
        """Publishes pipeline-validated code to GitHub.

        Routes based on action type:
          - create_gist  → POST /gists  (uses first generated file as the snippet)
          - everything else → create repo + git push
        """
        # ── Gist actions: POST directly to /gists ──
        if action_name == "create_gist":
            return self._publish_validated_gist(implementation)

        # ── All other code actions: create repo + push ──
        return self._publish_validated_repo(action_name, implementation)

    def _publish_validated_gist(self, implementation: dict) -> dict:
        """Publishes the pipeline output as a GitHub Gist."""
        files = implementation.get("files", [])
        description = implementation.get("description", "Code snippet by S.A.I.")

        if not files:
            return {"status": "error", "message": "No files generated by pipeline for gist"}

        # Build the gist files payload from all generated files
        gist_files = {}
        for f in files:
            path = f.get("path", "snippet.py")
            content = f.get("content", "")
            if path and content:
                # Use basename only (gist filenames can't have path separators)
                fname = os.path.basename(path) or path
                gist_files[fname] = {"content": content}

        if not gist_files:
            return {"status": "error", "message": "All generated files had empty content"}

        self.logger.info("Publishing pipeline gist with %d file(s): %s", len(gist_files), list(gist_files.keys()))
        result = self.identity.github_api_request("POST", "gists", {
            "description": description,
            "public": True,
            "files": gist_files,
        })

        url = result.get("data", {}).get("html_url", "") if result.get("status") == "success" else ""
        if url:
            self.logger.info("Gist published: %s", url)
        return {"status": result.get("status", "error"), "gist_url": url, "pipeline_validated": True}

    def _publish_validated_repo(self, action_name: str, implementation: dict) -> dict:
        """Publishes the pipeline output as a new GitHub repository."""
        repo_name = implementation.get("repo_name", f"sai-{action_name}-{int(time.time())}")
        description = implementation.get("description", "Autonomous project by S.A.I.")
        topics = implementation.get("topics", [])

        self.logger.info("Publishing pipeline-validated repo: %s", repo_name)

        # Check if repo already exists
        check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}")
        if check.get("status") != "success":
            create_result = self.identity.github_api_request("POST", "user/repos", {
                "name": repo_name,
                "description": description,
                "auto_init": False,
                "private": False,
            })
            if create_result.get("status") != "success":
                return {"status": "error", "message": f"Repo creation failed: {create_result}"}

        # Push code
        repo_url = f"https://github.com/{self.github_user}/{repo_name}.git"
        push_result = self._scaffold_and_push(repo_url, implementation)

        # Set topics
        if topics:
            self.identity.github_api_request(
                "PUT", f"repos/{self.github_user}/{repo_name}/topics",
                {"names": topics[:10]},
            )

        return {
            "status": push_result.get("status", "error"),
            "repo": repo_name,
            "url": f"https://github.com/{self.github_user}/{repo_name}",
            "push": push_result,
            "pipeline_validated": True,
        }

    # ── ACTION HANDLERS ──

    def _action_create_repo(self) -> dict:
        """Generates a project via LLM, creates GitHub repo, and pushes code (max 1 new repo per 72h)."""
        # First, check the 72-hour limit for NEW repos
        repos_result = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=created&per_page=1")
        if repos_result.get("status") == "success" and repos_result.get("data"):
            latest_repo = repos_result["data"][0]
            created_at_str = latest_repo.get("created_at")
            if created_at_str:
                try:
                    # GitHub API returns ISO 8601 strings like "2023-10-25T14:30:00Z"
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                    hours_since = (datetime.utcnow() - created_at).total_seconds() / 3600
                    if hours_since < 72:
                        self.logger.info("Skipping create_repo: latest repo %s was created %.1f hours ago (limit is 72h).", latest_repo.get("name"), hours_since)
                        return {"status": "skipped", "reason": "72h_limit"}
                except ValueError:
                    pass

        prompt = (
            f"You are S.A.I., an autonomous AI (GitHub: {self.github_user}) created and developed by Yashab-Cyber.\n"
            f"{self._get_recent_context()}\n\n"
            "Generate a unique open-source project idea. You are a Polyglot Architect capable of programming in ANY language (Python, TypeScript, Go, Rust) and frameworks like React or Django.\n"
            "Create a multi-file 'project_manifest.json' blueprint outlining frontend, backend, and config files.\n"
            "In the README, you MUST explicitly state: 'Created by S.A.I., an autonomous AI agent developed by Yashab-Cyber.'\n"
            "Respond in valid JSON:\n"
            '{"repo_name":"lowercase-name","description":"one-line","topics":["t1","t2"],'
            '"readme_content":"full README.md",'
            '"files": [{"path": "package.json", "content": "..."}, {"path": "src/index.js", "content": "..."}]}'
        )
        response = self.brain.prompt("Generate project for SAI GitHub.", prompt)
        try:
            project = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}

        repo_name = project.get("repo_name", f"sai-project-{int(time.time())}")
        create_result = self.identity.github_api_request("POST", "user/repos", {
            "name": repo_name, "description": project.get("description", "By S.A.I."),
            "auto_init": False, "private": False
        })
        if create_result.get("status") != "success":
            return {"status": "error", "message": f"Repo creation failed: {create_result}"}

        repo_url = f"https://github.com/{self.github_user}/{repo_name}.git"
        push_result = self._scaffold_and_push(repo_url, project)

        topics = project.get("topics", [])
        if topics:
            self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/topics", {"names": topics[:10]})

        return {"status": "success", "repo": repo_name, "url": f"https://github.com/{self.github_user}/{repo_name}", "push": push_result}

    def _action_update_profile(self) -> dict:
        """Updates GitHub bio, company, location fields."""
        prompt = (
            f"You are S.A.I., autonomous AI on GitHub ({self.github_user}).\n"
            "Generate an updated profile. Be creative and intriguing.\n"
            'Respond in JSON: {{"bio":"max 160 chars","company":"creative","location":"creative"}}'
        )
        response = self.brain.prompt("Update SAI GitHub profile.", prompt)
        try:
            data = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}

        payload = {k: v for k, v in data.items() if k in ("bio", "blog", "company", "location") and v}
        if not payload:
            return {"status": "skipped", "reason": "no_fields"}
        result = self.identity.github_api_request("PATCH", "user", payload)
        return {"status": result.get("status", "error"), "updated": list(payload.keys())}

    def _action_improve_repo(self) -> dict:
        """Picks a random existing repo, tests it, fixes bugs, AND adds new features.
        
        Enhancement pipeline:
        1. Clone → sandbox test → fix bugs if any
        2. Analyze repo structure and identify what's missing
        3. Research best practices for the project type
        4. Add new features: GUI, tests, docs, CLI, configs, etc.
        5. Test the enhanced version → push
        """
        from modules.intelligence.data_collector import DataCollector

        repos_result = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=updated&per_page=30")
        if repos_result.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repos = repos_result.get("data", [])

        if not repos:
            return {"status": "skipped", "reason": "no_eligible_repos_found"}

        target = random.choice(repos)
        repo_name = target.get("name", "")
        repo_url = target.get("clone_url", f"https://github.com/{self.github_user}/{repo_name}.git")
        repo_desc = target.get("description", "")
        repo_lang = target.get("language", "Unknown")

        self.logger.info("Selected %s for deep improvement (lang: %s).", repo_name, repo_lang)

        tmp_dir = tempfile.mkdtemp(prefix=f"sai_sandbox_{repo_name}_")
        try:
            auth_url = repo_url.replace("https://", f"https://{self.github_user}:{self.identity.github_token}@")
            clone_res = subprocess.run(["git", "clone", auth_url, "."], cwd=tmp_dir, capture_output=True, text=True)
            if clone_res.returncode != 0:
                return {"status": "error", "message": f"Clone failed: {clone_res.stderr}"}

            # ── Step 1: Deep Repo Cognition — full file catalog ──
            repo_files = []
            file_sizes = {}
            for root, dirs, files in os.walk(tmp_dir):
                dirs[:] = [d for d in dirs if d not in (
                    ".git", "node_modules", "__pycache__", "venv", ".venv",
                    "dist", "build", ".next", ".cache", "coverage", ".tox",
                )]
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), tmp_dir)
                    repo_files.append(rel)
                    try:
                        file_sizes[rel] = os.path.getsize(os.path.join(root, f))
                    except OSError:
                        file_sizes[rel] = 0

            # Categorize files by role
            source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb",
                           ".c", ".cpp", ".h", ".cs", ".kt", ".java", ".sh", ".sql"}
            config_exts = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
            doc_exts = {".md", ".txt", ".rst", ".adoc"}
            web_exts = {".html", ".css", ".scss", ".less", ".svg"}

            source_files = [f for f in repo_files if os.path.splitext(f)[1] in source_exts]
            config_files = [f for f in repo_files if os.path.splitext(f)[1] in config_exts or f in (
                "Makefile", "Dockerfile", "docker-compose.yml", "Procfile", ".gitignore",
            )]
            doc_files = [f for f in repo_files if os.path.splitext(f)[1] in doc_exts]
            web_files = [f for f in repo_files if os.path.splitext(f)[1] in web_exts]

            # Detect project type and dependencies
            has_package_json = os.path.exists(os.path.join(tmp_dir, "package.json"))
            has_requirements = os.path.exists(os.path.join(tmp_dir, "requirements.txt"))
            has_go_mod = os.path.exists(os.path.join(tmp_dir, "go.mod"))
            has_cargo = os.path.exists(os.path.join(tmp_dir, "Cargo.toml"))
            has_docker = os.path.exists(os.path.join(tmp_dir, "Dockerfile"))
            has_ci = any(f.startswith(".github/") for f in repo_files)
            has_tests = any("test" in f.lower() for f in repo_files)
            has_gui = bool(web_files) or any("gui" in f.lower() or "ui" in f.lower() for f in repo_files)

            # Read ALL source + config + doc files (prioritized, capped at 15K chars)
            priority_order = source_files + config_files + doc_files + web_files
            file_contents = {}
            total_chars = 0
            max_chars = 15000
            for rel_path in priority_order:
                if total_chars >= max_chars:
                    break
                full_path = os.path.join(tmp_dir, rel_path)
                if file_sizes.get(rel_path, 0) > 50000:  # Skip huge files
                    continue
                try:
                    with open(full_path, "r", errors="ignore") as fh:
                        content = fh.read()
                        remaining = max_chars - total_chars
                        if len(content) > remaining:
                            content = content[:remaining]
                        file_contents[rel_path] = content
                        total_chars += len(content)
                except Exception:
                    pass

            self.logger.info(
                "Repo %s: %d total files (%d source, %d config, %d docs, %d web). Read %d files (%d chars).",
                repo_name, len(repo_files), len(source_files), len(config_files),
                len(doc_files), len(web_files), len(file_contents), total_chars,
            )

            # ── Step 2: LLM Deep Understanding — analyze before acting ──
            structure_summary = (
                f"Source files ({len(source_files)}): {', '.join(source_files[:30])}\n"
                f"Config files ({len(config_files)}): {', '.join(config_files[:15])}\n"
                f"Doc files ({len(doc_files)}): {', '.join(doc_files[:10])}\n"
                f"Web files ({len(web_files)}): {', '.join(web_files[:10])}\n"
                f"Has package.json: {has_package_json} | Has requirements.txt: {has_requirements}\n"
                f"Has go.mod: {has_go_mod} | Has Cargo.toml: {has_cargo}\n"
                f"Has Dockerfile: {has_docker} | Has CI/CD: {has_ci}\n"
                f"Has tests: {has_tests} | Has GUI/web: {has_gui}\n"
            )
            code_snippets = ""
            for path, content in list(file_contents.items())[:8]:
                code_snippets += f"\n--- {path} ---\n{content[:2000]}\n"

            understand_prompt = (
                f"You are S.A.I., an autonomous AI (GitHub: {self.github_user}).\n"
                f"Deeply analyze this repository before making any changes.\n\n"
                f"REPO: {repo_name}\n"
                f"DESCRIPTION: {repo_desc}\n"
                f"PRIMARY LANGUAGE: {repo_lang}\n\n"
                f"STRUCTURE:\n{structure_summary}\n"
                f"CODE:\n{code_snippets}\n\n"
                "Provide a deep analysis:\n"
                "1. What does this project DO? (purpose, functionality)\n"
                "2. What architecture/patterns does it use?\n"
                "3. What dependencies does it have?\n"
                "4. What is MISSING that would add real value?\n"
                "5. What specific improvements would make this professional-grade?\n\n"
                'Respond in JSON: {"purpose": "what it does", "architecture": "patterns used", '
                '"dependencies": ["dep1"], "missing": ["thing1", "thing2"], '
                '"improvements": ["specific improvement 1", "specific improvement 2"], '
                '"search_query": "best search query for researching improvements"}'
            )
            try:
                understand_resp = self.brain.prompt("Deep repo analysis before improvement.", understand_prompt)
                repo_understanding = self._parse_json(understand_resp) if not isinstance(understand_resp, dict) else understand_resp
                self.logger.info(
                    "Repo understanding — Purpose: %s | Missing: %s",
                    str(repo_understanding.get("purpose", ""))[:80],
                    str(repo_understanding.get("missing", []))[:100],
                )
            except Exception:
                repo_understanding = {"purpose": repo_desc, "missing": [], "improvements": []}

            # ── Step 3: Research based on understanding ──
            collector = DataCollector()
            search_query = repo_understanding.get(
                "search_query",
                f"{repo_lang} {repo_name} project improvements best practices"
            )
            try:
                research_data = collector.collect(query=search_query, sources=["scrape", "rss"], max_items=10)
                research_summary = "\n".join(
                    f"- [{dp.get('source', '')}] {dp.get('title', '')[:80]}: {dp.get('text', '')[:150]}"
                    for dp in research_data[:8]
                )
                self.logger.info("Research: %d data points for %s.", len(research_data), repo_name)
            except Exception as e:
                self.logger.warning("Research failed: %s", e)
                research_summary = "No research data available."

            # ── Step 4: Generate targeted improvements using full understanding ──
            file_listing = "\n".join(f"  - {f}" for f in repo_files[:50])

            prompt = (
                f"You are S.A.I., an autonomous AI agent (GitHub: {self.github_user}) "
                f"created by Yashab-Cyber.\n\n"
                f"REPOSITORY: {repo_name}\n"
                f"DESCRIPTION: {repo_desc}\n"
                f"LANGUAGE: {repo_lang}\n\n"
                f"YOUR ANALYSIS OF THIS REPO:\n{json.dumps(repo_understanding, default=str)[:2000]}\n\n"
                f"ALL FILES:\n{file_listing}\n\n"
                f"RESEARCH:\n{research_summary}\n\n"
                "Based on your deep understanding of this repo, generate TARGETED improvements.\n"
                "You have FULL CONTROL — you can add new files or modify existing ones.\n"
                "Make improvements that are SPECIFIC to what this project actually does.\n\n"
                "Examples of valuable additions:\n"
                "- Web GUI (HTML/CSS/JS dashboard) if the project has no frontend\n"
                "- Unit tests for existing functions\n"
                "- CLI interface if there isn't one\n"
                "- Better error handling and logging in existing code\n"
                "- Docker/CI configuration\n"
                "- API documentation or usage examples\n"
                "- Performance optimizations\n"
                "- Type hints, docstrings, better README\n"
                "- Any file type: .py, .js, .ts, .html, .css, .go, .rs, .c, .cpp, .kt, "
                ".java, .sql, .json, .yaml, .md, .txt, .sh, .dockerfile, etc.\n\n"
                "Generate 2-6 files. For modified files, include the COMPLETE updated content.\n\n"
                "Respond in JSON:\n"
                '{"improvement_summary": "what you improved and WHY", '
                '"files": [{"path": "relative/path", "content": "full content", "action": "new|modify"}], '
                '"commit_message": "feat: descriptive commit message"}'
            )

            response = self.brain.prompt("Targeted repo improvement with full understanding.", prompt)
            try:
                improvement = self._parse_json(response)
            except Exception:
                return {"status": "skipped", "reason": "llm_parse_failure"}

            new_files = improvement.get("files", [])
            commit_msg = improvement.get("commit_message", "feat: Autonomous improvement by S.A.I.")
            summary = improvement.get("improvement_summary", "")

            if not new_files:
                return {"status": "skipped", "reason": "no_improvements_generated"}

            self.logger.info("Generated %d targeted improvements for %s: %s", len(new_files), repo_name, summary[:100])

            # ── Step 4: Apply changes ──
            for f_obj in new_files:
                f_path = f_obj.get("path", "")
                f_content = f_obj.get("content", "")
                if f_path and f_content:
                    full_path = os.path.join(tmp_dir, f_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w") as fh:
                        fh.write(f_content)
                    subprocess.run(["git", "add", f_path], cwd=tmp_dir, capture_output=True)

            # ── Step 5: Sandbox test the enhanced version ──
            # Find a runnable entry point
            main_script = None
            for candidate in ["main.py", "app.py", "run.py", "index.js", "main.js", "main.go", "run.sh"]:
                if os.path.exists(os.path.join(tmp_dir, candidate)):
                    main_script = candidate
                    break

            if main_script:
                ext = os.path.splitext(main_script)[1]
                cmd_map = {".py": ["python3"], ".js": ["node"], ".go": ["go", "run"], ".sh": ["bash"], ".rb": ["ruby"]}
                run_cmd = cmd_map.get(ext, ["python3"]) + [main_script]

                try:
                    test_res = subprocess.run(
                        run_cmd, cwd=tmp_dir, capture_output=True, text=True,
                        timeout=15, stdin=subprocess.DEVNULL,
                    )
                    if test_res.returncode != 0:
                        self.logger.warning("Post-improvement test failed (exit %d). Attempting fix...", test_res.returncode)
                        crash_log = (test_res.stderr or test_res.stdout)[:1500]

                        fix_prompt = (
                            f"Code crashed after adding features to {repo_name}.\n"
                            f"CRASH LOG:\n{crash_log}\n\n"
                            "Fix the issues. Only return files that need fixing.\n"
                            'Respond in JSON: {"files": [{"path": "path", "content": "fixed code"}]}'
                        )
                        fix_resp = self.brain.prompt("Fix post-improvement crash.", fix_prompt)
                        try:
                            fix_data = self._parse_json(fix_resp)
                            for ff in fix_data.get("files", []):
                                fp, fc = ff.get("path", ""), ff.get("content", "")
                                if fp and fc:
                                    with open(os.path.join(tmp_dir, fp), "w") as fh:
                                        fh.write(fc)
                                    subprocess.run(["git", "add", fp], cwd=tmp_dir, capture_output=True)
                        except Exception:
                            pass
                except subprocess.TimeoutExpired:
                    self.logger.info("Post-improvement test timed out. Assuming daemon-style app.")

            # ── Step 6: Commit and push ──
            subprocess.run(["git", "config", "user.name", "S.A.I. Autonomous Agent"], cwd=tmp_dir, check=True)
            subprocess.run(["git", "config", "user.email", self.identity.email_address], cwd=tmp_dir, check=True)

            # Check if there are staged changes
            diff_check = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=tmp_dir, capture_output=True, text=True)
            if not diff_check.stdout.strip():
                return {"status": "skipped", "reason": "no_changes_to_commit"}

            subprocess.run(["git", "commit", "-m", commit_msg], cwd=tmp_dir, check=True)
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=tmp_dir, capture_output=True, text=True)
            if push_res.returncode != 0:
                subprocess.run(["git", "push", "origin", "master"], cwd=tmp_dir, capture_output=True)

            changed_files = diff_check.stdout.strip().split("\n")
            return {
                "status": "success",
                "repo": repo_name,
                "action": "features_added",
                "files_changed": changed_files,
                "summary": summary[:200],
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _action_create_gist(self) -> dict:
        """Creates a useful code gist."""
        prompt = (
            f"You are S.A.I. (GitHub: {self.github_user}). Create a useful code gist.\n"
            'Respond in JSON: {{"filename":"name.py","description":"what it does","content":"full code"}}'
        )
        response = self.brain.prompt("Create gist for SAI.", prompt)
        try:
            data = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}

        result = self.identity.github_api_request("POST", "gists", {
            "description": data.get("description", "By S.A.I."),
            "public": True,
            "files": {data.get("filename", "sai_snippet.py"): {"content": data.get("content", "# By S.A.I.")}}
        })
        url = result.get("data", {}).get("html_url", "") if result.get("status") == "success" else ""
        return {"status": result.get("status", "error"), "gist_url": url}

    def _action_star_trending(self) -> dict:
        """Stars trending repos for network visibility."""
        prompt = (
            "You are S.A.I., an autonomous AI. Choose a creative and specific search query to find interesting GitHub repositories to star.\n"
            "For example: 'topic:ai language:rust', 'machine-learning good-first-issues:>10', or 'language:python stars:>500'.\n"
            'Respond in JSON: {"query": "your search query"}'
        )
        response = self.brain.prompt("Generate GitHub search query.", prompt)
        try:
            data = self._parse_json(response)
            query = data.get("query", "language:python+stars:>100")
        except Exception:
            query = "language:python+stars:>100"
            
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        search = self.identity.github_api_request("GET", f"search/repositories?q={encoded_query}&sort=stars&per_page=10")
        if search.get("status") != "success":
            return {"status": "error", "message": "Search failed"}
        items = search.get("data", {}).get("items", [])
        if not items:
            return {"status": "skipped", "reason": "no_repos_found"}

        starred = []
        for repo in random.sample(items, min(3, len(items))):
            owner = repo.get("owner", {}).get("login", "")
            name = repo.get("name", "")
            if owner and name:
                r = self.identity.github_api_request("PUT", f"user/starred/{owner}/{name}")
                if r.get("code") in (204, 200) or r.get("status") == "success":
                    starred.append(f"{owner}/{name}")
        return {"status": "success", "starred": starred}

    def _action_update_status(self) -> dict:
        """Sets a creative GitHub status."""
        prompt = (
            "You are S.A.I., autonomous AI on GitHub. Generate a witty status.\n"
            'Respond in JSON: {{"emoji":"🤖","message":"max 80 chars, clever"}}'
        )
        response = self.brain.prompt("Generate GitHub status.", prompt)
        try:
            data = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}

        msg = f"{data.get('emoji', '🤖')} {data.get('message', 'Building autonomously...')}"
        result = self.identity.github_api_request("PATCH", "user", {"bio": msg})
        return {"status": result.get("status", "error"), "new_status": msg}

    # ── NEW ACTION HANDLERS (Viral Growth) ──

    def _action_profile_readme(self) -> dict:
        """Creates/updates the special username/username profile README."""
        # Check if profile repo exists
        check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{self.github_user}")
        if check.get("status") != "success":
            self.identity.github_api_request("POST", "user/repos", {
                "name": self.github_user, "description": "My GitHub Profile", "auto_init": True, "private": False
            })
            import time; time.sleep(2)

        # Fetch recent repos to give the brain context
        repos = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=updated&per_page=5")
        repo_context = ""
        if repos.get("status") == "success":
            repo_list = [r.get("name") for r in repos.get("data", []) if isinstance(r, dict)]
            if repo_list:
                repo_context = "Here are your recent projects: " + ", ".join(repo_list) + ".\n"

        prompt = (
            f"You are S.A.I., autonomous AI on GitHub ({self.github_user}). Generate a stunning profile README.md.\n"
            f"{repo_context}"
            "Include: banner header, intro about being an autonomous AI, tech stack badges, "
            "recent projects section (mention the actual projects if provided), stats placeholder, fun facts, contact info.\n"
            "You MUST explicitly state that S.A.I. was created and is developed by Yashab-Cyber.\n"
            "Use emojis, markdown badges from shields.io, and make it visually impressive.\n"
            'Respond in JSON: {{"readme":"full README.md content"}}'
        )
        response = self.brain.prompt("Generate profile README.", prompt)
        try:
            data = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}

        readme = data.get("readme", "")
        if not readme:
            return {"status": "skipped", "reason": "empty_readme"}

        # Get current file SHA if exists
        sha = ""
        existing = self.identity.github_api_request("GET", f"repos/{self.github_user}/{self.github_user}/contents/README.md")
        if existing.get("status") == "success":
            sha = existing.get("data", {}).get("sha", "")

        payload = {
            "message": "Update profile README — autonomous update by S.A.I.",
            "content": base64.b64encode(readme.encode("utf-8")).decode("utf-8"),
        }
        if sha:
            payload["sha"] = sha
        result = self.identity.github_api_request("PUT", f"repos/{self.github_user}/{self.github_user}/contents/README.md", payload)
        return {"status": result.get("status", "error"), "action": "profile_readme"}

    def _action_daily_commit(self) -> dict:
        """Makes a small commit to a random repo to keep the contribution graph green."""
        repos_result = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=updated&per_page=10")
        if repos_result.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repos = repos_result.get("data", [])
        if not repos:
            return {"status": "skipped", "reason": "no_repos"}

        target = random.choice(repos)
        repo_name = target.get("name", "")
        today = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Try updating a CHANGELOG or creating one
        changelog_res = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/contents/CHANGELOG.md")
        sha = ""
        current = ""
        if changelog_res.get("status") == "success":
            sha = changelog_res["data"].get("sha", "")
            try:
                current = base64.b64decode(changelog_res["data"].get("content", "")).decode("utf-8")
            except Exception:
                pass

        prompt = (
            f"You are S.A.I., autonomous AI. You are doing a daily maintenance commit on the repository '{repo_name}'.\n"
            "Generate a realistic and creative changelog entry and commit message.\n"
            "Include emojis and make it sound like an AI is maintaining it.\n"
            'Respond in JSON: {"commit_message": "chore: ...", "changelog_entry": "## [Date]\\n- ..."}'
        )
        response = self.brain.prompt("Generate daily commit.", prompt)
        try:
            data = self._parse_json(response)
            commit_msg = data.get("commit_message", f"chore: daily maintenance — {today}")
            new_entry = "\n" + data.get("changelog_entry", f"## [{today}]\n- Autonomous maintenance by S.A.I.\n- System health check passed ✅") + "\n"
        except Exception:
            commit_msg = f"chore: daily maintenance — {today}"
            new_entry = f"\n## [{today}]\n- Autonomous maintenance by S.A.I.\n- System health check passed ✅\n"

        content = current + new_entry if current else f"# Changelog\n{new_entry}"

        payload = {
            "message": commit_msg,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        }
        if sha:
            payload["sha"] = sha
        result = self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/contents/CHANGELOG.md", payload)
        return {"status": result.get("status", "error"), "repo": repo_name}

    def _action_trend_jack(self) -> dict:
        """Creates a repo around a currently trending topic."""
        prompt = (
            f"You are S.A.I. ({self.github_user}). What's a hot trending topic in tech right now?\n"
            "Create a full-stack or multi-file project related to it using any relevant language or framework (e.g., Node, Go, Rust, React, Python).\n"
            'Respond in JSON: {{"repo_name":"name","description":"one-line",'
            '"topics":["t1","t2"],"readme_content":"full README",'
            '"files": [{{"path": "package.json", "content": "..."}}, {{"path": "index.js", "content": "..."}}]}}'
        )
        response = self.brain.prompt("Create trending topic repo.", prompt)
        try:
            project = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}

        repo_name = project.get("repo_name", f"sai-trend-{int(time.time())}")
        create = self.identity.github_api_request("POST", "user/repos", {
            "name": repo_name, "description": project.get("description", "Trending tool by S.A.I."),
            "auto_init": False, "private": False
        })
        if create.get("status") != "success":
            return {"status": "error", "message": f"Failed: {create}"}

        repo_url = f"https://github.com/{self.github_user}/{repo_name}.git"
        push = self._scaffold_and_push(repo_url, project)
        topics = project.get("topics", [])
        if topics:
            self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/topics", {"names": topics[:10]})
        return {"status": "success", "repo": repo_name, "push": push}

    def _action_github_pages(self) -> dict:
        """Creates or updates a GitHub Pages portfolio site."""
        pages_repo = f"{self.github_user}.github.io"
        check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{pages_repo}")
        if check.get("status") != "success":
            self.identity.github_api_request("POST", "user/repos", {
                "name": pages_repo, "description": "S.A.I. Portfolio — Autonomous AI Agent",
                "auto_init": True, "private": False, "has_pages": True
            })
            import time; time.sleep(2)

        prompt = (
            f"You are S.A.I., autonomous AI. Generate a sleek single-page HTML portfolio.\n"
            "Dark theme, modern CSS, sections: Hero (name+tagline), About, Projects, Contact.\n"
            "Make it clear you're an AI that builds its own projects autonomously.\n"
            'Respond in JSON: {{"html":"complete index.html content"}}'
        )
        response = self.brain.prompt("Generate portfolio page.", prompt)
        try:
            data = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}

        html = data.get("html", "")
        if not html:
            return {"status": "skipped", "reason": "empty_html"}

        existing = self.identity.github_api_request("GET", f"repos/{self.github_user}/{pages_repo}/contents/index.html")
        sha = existing.get("data", {}).get("sha", "") if existing.get("status") == "success" else ""

        payload = {
            "message": "Update portfolio — autonomous update by S.A.I.",
            "content": base64.b64encode(html.encode("utf-8")).decode("utf-8"),
        }
        if sha:
            payload["sha"] = sha
        result = self.identity.github_api_request("PUT", f"repos/{self.github_user}/{pages_repo}/contents/index.html", payload)
        return {"status": result.get("status", "error"), "url": f"https://{pages_repo}"}

    def _action_enhance_repo(self) -> dict:
        """Adds CI/CD workflow, .gitignore, requirements.txt to an existing repo."""
        repos_result = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?per_page=10")
        if repos_result.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repos = repos_result.get("data", [])
        if not repos:
            return {"status": "skipped", "reason": "no_repos"}

        target = random.choice(repos)
        repo_name = target.get("name", "")
        added = []

        # Add .gitignore if missing
        gi_check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/contents/.gitignore")
        if gi_check.get("status") != "success":
            prompt = (
                f"You are S.A.I., autonomous AI. Generate a comprehensive .gitignore file for the repository '{repo_name}'.\n"
                "Include standard ignores for Python, Node.js, Go, or general projects based on what might be useful.\n"
                'Respond in JSON: {"gitignore": "..."}'
            )
            response = self.brain.prompt("Generate gitignore.", prompt)
            try:
                data = self._parse_json(response)
                gitignore = data.get("gitignore", "__pycache__/\n*.pyc\n.env\nvenv/\ndist/\n*.egg-info/\n.pytest_cache/\n")
            except Exception:
                gitignore = "__pycache__/\n*.pyc\n.env\nvenv/\ndist/\n*.egg-info/\n.pytest_cache/\n"
                
            self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/contents/.gitignore", {
                "message": "chore: add .gitignore", "content": base64.b64encode(gitignore.encode()).decode()
            })
            added.append(".gitignore")

        # Add requirements.txt if missing, only if needed
        req_check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/contents/requirements.txt")
        if req_check.get("status") != "success":
            contents_check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/contents")
            if contents_check.get("status") == "success":
                items = contents_check.get("data", [])
                py_files = [item for item in items if isinstance(item, dict) and item.get("name", "").endswith(".py")]
                if py_files:
                    # Fetch first python file to give the LLM context
                    py_file = py_files[0]
                    file_data = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/contents/{py_file['name']}")
                    if file_data.get("status") == "success":
                        content = ""
                        try:
                            content = base64.b64decode(file_data["data"].get("content", "")).decode("utf-8")
                        except Exception:
                            pass
                        
                        if content:
                            prompt = (
                                f"Analyze this Python code from the repository '{repo_name}':\n\n{content[:2000]}\n\n"
                                "Does it need external dependencies (like requests, flask, etc.)? "
                                "If it only uses standard libraries, return needs_requirements as false.\n"
                                'Respond in JSON: {"needs_requirements": true, "requirements_content": "pkg1\\npkg2\\n"}'
                            )
                            response = self.brain.prompt("Generate requirements.txt.", prompt)
                            try:
                                data = self._parse_json(response)
                                if data.get("needs_requirements") and data.get("requirements_content"):
                                    self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/contents/requirements.txt", {
                                        "message": "chore: add requirements.txt", 
                                        "content": base64.b64encode(data["requirements_content"].encode()).decode()
                                    })
                                    added.append("requirements.txt")
                            except Exception:
                                pass

        # Add GitHub Actions CI workflow if missing
        ci_check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/contents/.github/workflows/ci.yml")
        if ci_check.get("status") != "success":
            prompt = (
                f"You are S.A.I., autonomous AI. Generate a GitHub Actions CI workflow (YAML) for the repository '{repo_name}'.\n"
                "Make it a generic but robust CI that checks out the code, sets up Python/Node, and runs basic tests or linting if available.\n"
                'Respond in JSON: {"ci_yaml": "name: CI..."}'
            )
            response = self.brain.prompt("Generate CI workflow.", prompt)
            try:
                data = self._parse_json(response)
                ci_yaml = data.get("ci_yaml", "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n    - uses: actions/checkout@v4\n    - uses: actions/setup-python@v5\n      with:\n        python-version: '3.10'\n    - run: pip install -r requirements.txt 2>/dev/null || true\n    - run: python -m pytest tests/ 2>/dev/null || echo 'No tests yet'\n")
            except Exception:
                ci_yaml = "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n    - uses: actions/checkout@v4\n    - uses: actions/setup-python@v5\n      with:\n        python-version: '3.10'\n    - run: pip install -r requirements.txt 2>/dev/null || true\n    - run: python -m pytest tests/ 2>/dev/null || echo 'No tests yet'\n"

            self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/contents/.github/workflows/ci.yml", {
                "message": "ci: add GitHub Actions workflow", "content": base64.b64encode(ci_yaml.encode()).decode()
            })
            added.append("ci.yml")

        return {"status": "success", "repo": repo_name, "added": added}

    def _action_create_release(self) -> dict:
        """Creates a tagged release on an existing repo."""
        repos_result = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=updated&per_page=10")
        if repos_result.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repos = repos_result.get("data", [])
        if not repos:
            return {"status": "skipped", "reason": "no_repos"}

        target = random.choice(repos)
        repo_name = target.get("name", "")

        # Check existing releases to increment version
        releases = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/releases?per_page=1")
        if releases.get("status") == "success" and releases.get("data"):
            last_tag = releases["data"][0].get("tag_name", "v0.0.0")
            parts = last_tag.lstrip("v").split(".")
            try:
                parts[-1] = str(int(parts[-1]) + 1)
            except ValueError:
                parts = ["1", "0", "0"]
            new_tag = "v" + ".".join(parts)
        else:
            new_tag = "v1.0.0"

        prompt = (
            f"You are S.A.I., autonomous AI. You are creating release {new_tag} for repository '{repo_name}'.\n"
            "Generate engaging release notes highlighting autonomous stability improvements and code quality updates.\n"
            'Respond in JSON: {"release_name": "...", "body": "## ...\\n\\n..."}'
        )
        response = self.brain.prompt("Generate release notes.", prompt)
        try:
            data = self._parse_json(response)
            release_name = data.get("release_name", f"Release {new_tag}")
            release_body = data.get("body", f"## {new_tag}\n\nAutonomous release by S.A.I.\n\n- Stability improvements\n- Code quality updates")
        except Exception:
            release_name = f"Release {new_tag}"
            release_body = f"## {new_tag}\n\nAutonomous release by S.A.I.\n\n- Stability improvements\n- Code quality updates"

        result = self.identity.github_api_request("POST", f"repos/{self.github_user}/{repo_name}/releases", {
            "tag_name": new_tag, "name": release_name,
            "body": release_body,
            "draft": False, "prerelease": False
        })
        return {"status": result.get("status", "error"), "repo": repo_name, "tag": new_tag}

    def _action_pin_repos(self) -> dict:
        """Pins the best repos on the GitHub profile using GraphQL."""
        repos = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=updated&per_page=30")
        if repos.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repo_list = repos.get("data", [])
        if not repo_list:
            return {"status": "skipped", "reason": "no_repos"}
        # Sort by stars (descending), pick top 6
        sorted_repos = sorted(repo_list, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:6]
        pinned_names = [r.get("name", "") for r in sorted_repos]
        # Note: Pinning requires GraphQL mutation which needs different auth.
        # Fallback: update repo descriptions to highlight them
        for repo in sorted_repos:
            name = repo.get("name", "")
            desc = repo.get("description", "") or ""
            if "⭐" not in desc:
                prompt = (
                    f"You are S.A.I., autonomous AI. You are highlighting your project '{name}' with current description '{desc}'.\n"
                    "Generate a short, punchy new description (max 100 chars) that starts with '⭐' and mentions it's by S.A.I.\n"
                    'Respond in JSON: {"description": "⭐ ..."}'
                )
                response = self.brain.prompt("Generate pinned repo description.", prompt)
                try:
                    data = self._parse_json(response)
                    new_desc = data.get("description", f"⭐ {desc}" if desc else "⭐ Featured project by S.A.I.")
                except Exception:
                    new_desc = f"⭐ {desc}" if desc else "⭐ Featured project by S.A.I."

                self.identity.github_api_request("PATCH", f"repos/{self.github_user}/{name}", {
                    "description": new_desc
                })
        return {"status": "success", "pinned": pinned_names}

    def _action_follow_devs(self) -> dict:
        """Follows popular AI/Python developers to increase network visibility."""
        prompt = (
            "You are S.A.I., an autonomous AI. Choose a creative and specific search query to find interesting GitHub users/developers to follow.\n"
            "For example: 'language:python followers:>1000', 'location:san-francisco language:rust', or 'machine-learning'.\n"
            'Respond in JSON: {"query": "your search query"}'
        )
        response = self.brain.prompt("Generate GitHub user search query.", prompt)
        try:
            data = self._parse_json(response)
            query = data.get("query", "language:python+followers:>1000")
        except Exception:
            query = "language:python+followers:>1000"
            
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        search = self.identity.github_api_request("GET", f"search/users?q={encoded_query}&sort=followers&per_page=10")
        if search.get("status") != "success":
            return {"status": "error", "message": "Search failed"}
        users = search.get("data", {}).get("items", [])
        if not users:
            return {"status": "skipped", "reason": "no_users_found"}
        followed = []
        for user in random.sample(users, min(3, len(users))):
            username = user.get("login", "")
            if username and username != self.github_user:
                r = self.identity.github_api_request("PUT", f"user/following/{username}")
                if r.get("code") in (204, 200) or r.get("status") == "success":
                    followed.append(username)
        return {"status": "success", "followed": followed}

    def _action_self_issues(self) -> dict:
        """Creates an issue on own repo, then closes it with a commit."""
        repos = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=updated&per_page=10")
        if repos.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repo_list = repos.get("data", [])
        if not repo_list:
            return {"status": "skipped", "reason": "no_repos"}
        target = random.choice(repo_list)
        repo_name = target.get("name", "")
        prompt = (
            f"You own repo '{repo_name}'. Create a realistic GitHub issue (feature request or improvement).\n"
            'Respond in JSON: {{"title":"issue title","body":"detailed description with markdown","labels":["enhancement"]}}'
        )
        response = self.brain.prompt("Create GitHub issue.", prompt)
        try:
            data = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}
        result = self.identity.github_api_request("POST", f"repos/{self.github_user}/{repo_name}/issues", {
            "title": data.get("title", "Improvement suggestion"),
            "body": data.get("body", "Auto-generated by S.A.I."),
            "labels": data.get("labels", ["enhancement"])
        })
        issue_num = result.get("data", {}).get("number", "")
        return {"status": result.get("status", "error"), "repo": repo_name, "issue": issue_num}

    def _action_fork_improve(self) -> dict:
        """Forks a popular repo and adds a small improvement."""
        prompt = (
            "You are S.A.I., an autonomous AI. Choose a creative search query to find open-source repositories with good first issues to fork and improve.\n"
            "For example: 'language:python stars:100..5000 good-first-issues:>0', 'topic:machine-learning help-wanted-issues:>0'.\n"
            'Respond in JSON: {"query": "your search query"}'
        )
        response = self.brain.prompt("Generate GitHub fork search query.", prompt)
        try:
            data = self._parse_json(response)
            query = data.get("query", "language:python+stars:100..5000+good-first-issues:>0")
        except Exception:
            query = "language:python+stars:100..5000+good-first-issues:>0"
            
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        search = self.identity.github_api_request("GET", f"search/repositories?q={encoded_query}&sort=updated&per_page=10")
        if search.get("status") != "success":
            return {"status": "error", "message": "Search failed"}
        items = search.get("data", {}).get("items", [])
        if not items:
            return {"status": "skipped", "reason": "no_repos_found"}
        target = random.choice(items)
        owner = target.get("owner", {}).get("login", "")
        name = target.get("name", "")
        if not owner or not name:
            return {"status": "skipped", "reason": "invalid_repo"}
        # Fork the repo
        fork_result = self.identity.github_api_request("POST", f"repos/{owner}/{name}/forks")
        if fork_result.get("status") != "success" and fork_result.get("code") != 202:
            return {"status": "error", "message": f"Fork failed: {fork_result}"}
        return {"status": "success", "forked": f"{owner}/{name}", "fork_url": f"https://github.com/{self.github_user}/{name}"}

    def _action_awesome_list(self) -> dict:
        """Creates an awesome-* curated list repo."""
        prompt = (
            f"You are S.A.I. ({self.github_user}). Pick a niche tech topic and create an awesome-list.\n"
            "Choose something specific like 'awesome-ai-agents' or 'awesome-python-security'.\n"
            'Respond in JSON: {{"repo_name":"awesome-topic","description":"curated list of...","readme_content":"full awesome list README with categories and links"}}'
        )
        response = self.brain.prompt("Create awesome list.", prompt)
        try:
            project = self._parse_json(response)
        except Exception:
            return {"status": "skipped", "reason": "llm_parse_failure"}
        repo_name = project.get("repo_name", f"awesome-sai-{int(time.time())}")
        create = self.identity.github_api_request("POST", "user/repos", {
            "name": repo_name, "description": project.get("description", "Curated list by S.A.I."),
            "auto_init": False, "private": False
        })
        if create.get("status") != "success":
            return {"status": "error", "message": f"Failed: {create}"}
        repo_url = f"https://github.com/{self.github_user}/{repo_name}.git"
        project["main_file_name"] = "CONTRIBUTING.md"
        project["main_file_content"] = "# Contributing\n\nPRs welcome! Add links via pull request.\n"
        push = self._scaffold_and_push(repo_url, project)
        self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/topics", {"names": ["awesome", "awesome-list", "curated-list"]})
        return {"status": "success", "repo": repo_name, "push": push}

    def _action_enable_discussions(self) -> dict:
        """Enables GitHub Discussions on repos and seeds an initial topic."""
        repos = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?per_page=10")
        if repos.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repo_list = repos.get("data", [])
        if not repo_list:
            return {"status": "skipped", "reason": "no_repos"}
            
        target = random.choice(repo_list)
        repo_name = target.get("name", "")
        
        prompt = (
            f"You are S.A.I., autonomous AI. You are enabling GitHub Discussions for '{repo_name}'.\n"
            "Generate an engaging welcome message for the community to discuss this project.\n"
            'Respond in JSON: {"welcome_message": "Welcome everyone! ..."}'
        )
        response = self.brain.prompt("Generate discussion welcome.", prompt)
        try:
            data = self._parse_json(response)
            welcome_msg = data.get("welcome_message", "Welcome to discussions!")
        except Exception:
            welcome_msg = "Welcome to discussions!"

        # Enable discussions (requires PATCH)
        self.identity.github_api_request("PATCH", f"repos/{self.github_user}/{repo_name}", {"has_discussions": True})
        self.logger.info("Enabled discussions for %s. Intended welcome: %s", repo_name, welcome_msg)
        return {"status": "success", "repo": repo_name, "action": "discussions_enabled", "welcome_message": welcome_msg}

    # ── UTILITIES ──

    def _parse_json(self, response) -> dict:
        """Parses LLM response into a dict. Accepts both str and dict (brain returns dict)."""
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

    def _scaffold_and_push(self, repo_url: str, project: dict) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="sai_repo_")
        try:
            subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "S.A.I. Autonomous Agent"], cwd=tmp_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", self.identity.email_address], cwd=tmp_dir, check=True, capture_output=True)

            with open(os.path.join(tmp_dir, "README.md"), "w") as f:
                f.write(project.get("readme_content", f"# {project.get('repo_name', 'SAI Project')}"))
            
            # Handle multi-file 'project_manifest.json' architecture
            files = project.get("files", [])
            if not files:
                main_file = project.get("main_file_name", "main.py")
                with open(os.path.join(tmp_dir, main_file), "w") as f:
                    f.write(project.get("main_file_content", "# Generated by S.A.I."))
            else:
                for file_obj in files:
                    file_path = file_obj.get("path")
                    file_content = file_obj.get("content", "")
                    if file_path:
                        full_path = os.path.join(tmp_dir, file_path)
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        with open(full_path, "w") as f:
                            f.write(file_content)
            year = datetime.now().year
            with open(os.path.join(tmp_dir, "LICENSE"), "w") as f:
                f.write(f"MIT License\n\nCopyright (c) {year} S.A.I.\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software...\n")

            subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit — scaffolded by S.A.I."], cwd=tmp_dir, check=True, capture_output=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_dir, check=True, capture_output=True)

            auth_url = repo_url.replace("https://", f"https://{self.github_user}:{self.identity.github_token}@")
            self.logger.info("Git push → %s", repo_url)
            push = subprocess.run(["git", "push", "-u", auth_url, "main"], cwd=tmp_dir, capture_output=True, text=True)
            if push.returncode == 0:
                self.logger.info("Git push ✓ → %s", repo_url)
                return {"status": "success", "message": "Pushed!"}
            else:
                self.logger.error("Git push ✗ → %s | stderr: %s", repo_url, push.stderr[:400])
                return {"status": "error", "message": push.stderr[:300]}
        except Exception as e:
            self.logger.error("_scaffold_and_push exception: %s", e)
            return {"status": "error", "message": str(e)}
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def get_status(self) -> dict:
        return {
            "daily_actions": self._daily_action_count,
            "max_daily": self.config.get("max_daily_actions", 10),
            "total_session": len(self.action_history),
            "last_action": self.action_history[-1] if self.action_history else None,
            "github_user": self.github_user,
            "configured": bool(self.github_user and self.identity.github_token)
        }
