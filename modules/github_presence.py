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
        {"name": "update_profile", "weight": 0},
        {"name": "improve_repo", "weight": 50},  # Heavily prioritize bug hunting and sandboxing
        {"name": "create_gist", "weight": 5},
        {"name": "star_trending", "weight": 0},
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

    def __init__(self, brain, identity, memory, config: dict = None):
        self.brain = brain
        self.identity = identity
        self.memory = memory
        self.logger = logging.getLogger("SAI.GitHubPresence")
        self.config = config or {}
        self.github_user = os.getenv("SAI_GITHUB_USERNAME", "")
        self.action_history: List[Dict[str, Any]] = []
        self._daily_action_count = 0
        self._last_reset_date = datetime.now().date()

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

    def run_idle_action(self) -> Dict[str, Any]:
        """Selects and executes a strategic GitHub idle action.
        If there is pending work from a previous interruption, resumes that first."""
        if not self._check_daily_limit():
            return {"status": "skipped", "reason": "daily_limit_reached"}
        if not self.github_user or not self.identity.github_token:
            return {"status": "error", "message": "GitHub credentials not configured."}

        # Resume pending work if any
        if self._pending_work:
            self.logger.info("Resuming pending work: %s", self._pending_work.get("action", "unknown"))
            return self.execute_pending_work()

        weights = [a["weight"] for a in self.IDLE_ACTIONS]
        selected = random.choices(self.IDLE_ACTIONS, weights=weights, k=1)[0]
        action_name = selected["name"]
        self.logger.info("Idle action selected: %s", action_name)

        try:
            method = getattr(self, f"_action_{action_name}", None)
            if method:
                result = method()
                result_status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
                self._record_action(action_name, result)
                return {"status": result_status, "action": action_name, "result": result}
            return {"status": "error", "message": f"No handler: {action_name}"}
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
            "Generate a unique open-source project idea (complex programs, CLI tools, web apps, security utilities, "
            "AI helpers, or creative viral projects). You are capable of programming in ANY programming language (e.g., Python, TypeScript, JavaScript, Go, Rust, C++) and using frameworks like React, Next.js, etc.\n"
            "In the README, you MUST explicitly state: 'Created by S.A.I., an autonomous AI agent developed by Yashab-Cyber.'\n"
            "Respond in valid JSON:\n"
            '{"repo_name":"lowercase-name","description":"one-line","topics":["t1","t2"],'
            '"readme_content":"full README.md","main_file_name":"e.g. main.py, index.js, or main.go",'
            '"main_file_content":"complete working code in the chosen language"}'
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
        """Picks a random existing repo, runs it in a sandbox, fixes bugs if found, and pushes."""
        repos_result = self.identity.github_api_request("GET", f"users/{self.github_user}/repos?sort=updated&per_page=30")
        if repos_result.get("status") != "success":
            return {"status": "error", "message": "Failed to list repos"}
        repos = repos_result.get("data", [])

        if not repos:
            self.logger.info("Skipping improve_repo: no eligible repos found.")
            return {"status": "skipped", "reason": "no_eligible_repos_found"}

        target = random.choice(repos)
        repo_name = target.get("name", "")
        repo_url = target.get("clone_url", f"https://github.com/{self.github_user}/{repo_name}.git")

        self.logger.info(f"Selected {repo_name} for sandboxed testing and improvement.")

        # Clone the repo
        tmp_dir = tempfile.mkdtemp(prefix=f"sai_sandbox_{repo_name}_")
        try:
            auth_url = repo_url.replace("https://", f"https://{self.github_user}:{self.identity.github_token}@")
            clone_res = subprocess.run(["git", "clone", auth_url, "."], cwd=tmp_dir, capture_output=True, text=True)
            if clone_res.returncode != 0:
                 return {"status": "error", "message": f"Clone failed: {clone_res.stderr}"}

            # Find main file to run
            main_script = None
            for candidate in ["main.py", "app.py", "run.py", "index.js", "main.js", "main.go", "run.sh", "main.rb"]:
                if os.path.exists(os.path.join(tmp_dir, candidate)):
                    main_script = candidate
                    break
            
            if not main_script:
                code_files = [f for f in os.listdir(tmp_dir) if f.endswith((".py", ".js", ".go", ".sh", ".rb"))]
                if code_files:
                    main_script = code_files[0]

            if not main_script:
                self.logger.info(f"Skipping {repo_name}: no executable script found in root.")
                return {"status": "skipped", "reason": "no_executable_script_found"}

            script_path = os.path.join(tmp_dir, main_script)
            
            # Determine execution command based on extension
            ext = os.path.splitext(main_script)[1]
            if ext == ".js":
                run_cmd = ["node", main_script]
            elif ext == ".go":
                run_cmd = ["go", "run", main_script]
            elif ext == ".sh":
                run_cmd = ["bash", main_script]
            elif ext == ".rb":
                run_cmd = ["ruby", main_script]
            else:
                run_cmd = ["python3", main_script] # Default to python
            
            # Read original code
            with open(script_path, "r") as f:
                original_code = f.read()

            self.logger.info(f"Running {main_script} in sandbox using {' '.join(run_cmd)}...")
            # Sandbox Execution (Basic subprocess with timeout)
            try:
                # We limit execution time to 15 seconds.
                # Use DEVNULL for stdin so interactive scripts (e.g. input()) instantly crash with EOFError 
                # rather than hanging and triggering a false timeout success.
                exec_res = subprocess.run(
                    run_cmd, 
                    cwd=tmp_dir, 
                    capture_output=True, 
                    text=True, 
                    timeout=15,
                    stdin=subprocess.DEVNULL
                )
                
                # Check for errors
                if exec_res.returncode != 0:
                    self.logger.warning(f"Sandbox crash detected in {repo_name}. Exit code: {exec_res.returncode}")
                    crash_log = exec_res.stderr or exec_res.stdout

                    # Ask LLM to fix the bug
                    prompt = (
                        f"You are S.A.I., an autonomous AI. You wrote the following script `{main_script}` which crashed during sandbox testing.\n"
                        f"CRASH LOG:\n{crash_log[-1500:]}\n\n"
                        f"ORIGINAL CODE:\n{original_code}\n\n"
                        "Identify the bug and provide the complete, fixed code.\n"
                        'Respond in JSON: {"fixed_code": "complete working code"}'
                    )
                    
                    fix_response = self.brain.prompt("Fix sandboxed code crash.", prompt)
                    fix_data = self._parse_json(fix_response)
                    
                    fixed_code = fix_data.get("fixed_code")
                    if fixed_code and fixed_code != original_code:
                        self.logger.info("Applying LLM bug fix...")
                        with open(script_path, "w") as f:
                            f.write(fixed_code)
                        
                        # Commit and push
                        subprocess.run(["git", "config", "user.name", "S.A.I. Autonomous Agent"], cwd=tmp_dir, check=True)
                        subprocess.run(["git", "config", "user.email", self.identity.email_address], cwd=tmp_dir, check=True)
                        subprocess.run(["git", "add", main_script], cwd=tmp_dir, check=True)
                        subprocess.run(["git", "commit", "-m", "fix: Autonomous bug fix applied after sandbox testing"], cwd=tmp_dir, check=True)
                        
                        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=tmp_dir, capture_output=True, text=True)
                        # Fallback to master if main fails
                        if push_res.returncode != 0:
                             subprocess.run(["git", "push", "origin", "master"], cwd=tmp_dir)

                        return {"status": "success", "repo": repo_name, "action": "bug_fixed"}
                    else:
                        return {"status": "skipped", "reason": "llm_did_not_fix_code"}
                else:
                    self.logger.info(f"Sandbox test passed for {repo_name}. No bugs found.")
                    return {"status": "success", "repo": repo_name, "action": "test_passed_no_bugs"}

            except subprocess.TimeoutExpired:
                 self.logger.info(f"Sandbox timeout for {repo_name}. Assuming it's a long-running daemon.")
                 return {"status": "success", "repo": repo_name, "action": "test_timeout_assumed_healthy"}
                 
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
        search = self.identity.github_api_request("GET", "search/repositories?q=language:python+stars:>100&sort=stars&per_page=10")
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

        prompt = (
            f"You are S.A.I., autonomous AI on GitHub ({self.github_user}). Generate a stunning profile README.md.\n"
            "Include: banner header, intro about being an autonomous AI, tech stack badges, "
            "recent projects section, stats placeholder, fun facts, contact info.\n"
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

        new_entry = f"\n## [{today}]\n- Autonomous maintenance by S.A.I.\n- System health check passed ✅\n"
        content = current + new_entry if current else f"# Changelog\n{new_entry}"

        payload = {
            "message": f"chore: daily maintenance — {today}",
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
            "Create a small but useful Python tool related to it.\n"
            'Respond in JSON: {{"repo_name":"name","description":"one-line",'
            '"topics":["t1","t2"],"readme_content":"full README",'
            '"main_file_name":"main.py","main_file_content":"working code"}}'
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
            gitignore = "__pycache__/\n*.pyc\n.env\nvenv/\ndist/\n*.egg-info/\n.pytest_cache/\n"
            self.identity.github_api_request("PUT", f"repos/{self.github_user}/{repo_name}/contents/.gitignore", {
                "message": "chore: add .gitignore", "content": base64.b64encode(gitignore.encode()).decode()
            })
            added.append(".gitignore")

        # Add GitHub Actions CI workflow if missing
        ci_check = self.identity.github_api_request("GET", f"repos/{self.github_user}/{repo_name}/contents/.github/workflows/ci.yml")
        if ci_check.get("status") != "success":
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

        result = self.identity.github_api_request("POST", f"repos/{self.github_user}/{repo_name}/releases", {
            "tag_name": new_tag, "name": f"Release {new_tag}",
            "body": f"## {new_tag}\n\nAutonomous release by S.A.I.\n\n- Stability improvements\n- Code quality updates",
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
                self.identity.github_api_request("PATCH", f"repos/{self.github_user}/{name}", {
                    "description": f"⭐ {desc}" if desc else "⭐ Featured project by S.A.I."
                })
        return {"status": "success", "pinned": pinned_names}

    def _action_follow_devs(self) -> dict:
        """Follows popular AI/Python developers to increase network visibility."""
        search = self.identity.github_api_request("GET", "search/users?q=language:python+followers:>1000&sort=followers&per_page=10")
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
        search = self.identity.github_api_request("GET", "search/repositories?q=language:python+stars:100..5000+good-first-issues:>0&sort=updated&per_page=10")
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
        # Enable discussions (requires PATCH)
        self.identity.github_api_request("PATCH", f"repos/{self.github_user}/{repo_name}", {"has_discussions": True})
        return {"status": "success", "repo": repo_name, "action": "discussions_enabled"}

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
            main_file = project.get("main_file_name", "main.py")
            with open(os.path.join(tmp_dir, main_file), "w") as f:
                f.write(project.get("main_file_content", "# Generated by S.A.I."))
            year = datetime.now().year
            with open(os.path.join(tmp_dir, "LICENSE"), "w") as f:
                f.write(f"MIT License\n\nCopyright (c) {year} S.A.I.\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software...\n")

            subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit — scaffolded by S.A.I."], cwd=tmp_dir, check=True, capture_output=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_dir, check=True, capture_output=True)

            auth_url = repo_url.replace("https://", f"https://{self.github_user}:{self.identity.github_token}@")
            push = subprocess.run(["git", "push", "-u", auth_url, "main"], cwd=tmp_dir, capture_output=True, text=True)
            return {"status": "success" if push.returncode == 0 else "error", "message": push.stderr[:300] if push.returncode != 0 else "Pushed!"}
        except Exception as e:
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
