import asyncio
import logging
from typing import List, Dict, Any

class SwarmAgent:
    def __init__(self, name: str, role_prompt: str, allowed_tools: List[str], sai_instance):
        self.name = name
        self.role_prompt = role_prompt
        self.allowed_tools = allowed_tools
        self.sai = sai_instance
        self.logger = logging.getLogger(f"SAI.Swarm.{name}")
        
    async def run(self, subtask: str, max_iterations: int = 10) -> Dict[str, Any]:
        self.logger.info(f"Agent '{self.name}' starting subtask: {subtask}")
        history = []
        for i in range(max_iterations):
            # 1. Determine next step
            response = self.sai.planner.determine_next_step(
                task=subtask, 
                history=history, 
                image_path=None, 
                allowed_tools=self.allowed_tools, 
                role_prompt=self.role_prompt
            )
            
            tool_name = response.get("tool")
            params = response.get("parameters", {})
            status = response.get("status", "ongoing")
            
            self.logger.info(f"[{self.name}] Thought: {response.get('thought')}")
            
            if status == "completed":
                self.logger.info(f"[{self.name}] Subtask complete.")
                break
                
            if not tool_name or tool_name not in self.allowed_tools:
                # Fallback to stop hallucinating
                if tool_name:
                    history.append({"action": f"{tool_name}", "observation": f"Tool '{tool_name}' unauthorized for role {self.name}."})
                else:
                    break
                continue
                
            self.logger.info(f"[{self.name}] Executing: {tool_name}")
            
            try:
                # Hand back to SAI core to run the tool safely
                action_result = await self.sai.execute_tool(tool_name, params)
                observation = str(action_result)
                if len(observation) > 8000:
                    observation = observation[:8000] + "... [TRUNCATED]"
            except Exception as e:
                observation = f"Error executing {tool_name}: {e}"
                
            history.append({
                "action": f"{tool_name}({params})",
                "observation": observation
            })
            
            # Short sleep to yield event loop during heavy concurrent tool execution
            await asyncio.sleep(0.5)
            
        # Fire completion event onto the bus
        self.sai.event_bus.publish("swarm_agent_finished", {
            "subtask": subtask,
            "agent": self.name,
            "history": history
        })
        return {"subtask": subtask, "agent": self.name, "history": history}

class SwarmOrchestrator:
    def __init__(self, sai_instance):
        self.sai = sai_instance
        self.logger = logging.getLogger("SAI.SwarmOrchestrator")
        # Subscribe to Event Bus to trace subtask completions automatically
        self.sai.event_bus.subscribe("swarm_agent_finished", self._handle_agent_completion)
        
    async def _handle_agent_completion(self, payload: Dict[str, Any]):
        """Callback to handle an agent completing its isolated subtask without blocking."""
        agent_name = payload.get("agent")
        self.logger.info(f"Captured ASYNC event: {agent_name} successfully finished its delegated swarm routine.")
        
    async def delegate(self, objective: str) -> str:
        self.logger.info(f"Orchestrator delegating objective: {objective}")
        print(f"\n[SWARM ORCHESTRATOR] Analyzing massive objective: {objective}")
        
        # 1. Ask Brain to decompose the task and assign specialized agents
        prompt_sys = (
            "You are the Swarm Orchestrator. Decompose the following massive objective into 2 to 3 discrete, parallelizable subtasks. "
            "Assign each subtask to a 'role' (e.g., 'researcher', 'coder', 'writer'). "
            "Return ONLY JSON format exactly like this: {\"subtasks\": [{\"role\": \"string\", \"objective\": \"string\", \"tools\": [\"list of allowed tool names\"]}]} "
            "Available tools you can grant: "
            "files.read, files.write, browser.search, browser.scrape, intelligence.collect, coder.write, coder.format, executor.shell"
        )
        
        decomposition = self.sai.brain.prompt(prompt_sys, f"Objective: {objective}")
        subtasks_config = decomposition.get("subtasks", [])
        
        if not subtasks_config:
            return "Swarm failed to decompose the task. Aborting."
            
        print(f"[SWARM ORCHESTRATOR] Spawning {len(subtasks_config)} sub-agents...")
        
        agents = []
        for i, st in enumerate(subtasks_config):
            role = st.get("role", f"Agent-{i}")
            sub_obj = st.get("objective", "Assist")
            tools = st.get("tools", ["files.read"])
            
            if "swarm.delegate" in tools:
                 tools.remove("swarm.delegate") # Prevent infinite swarm loop
            
            role_prompt = (
                f"You are a Sub-Agent of S.A.I. acting as a {role.upper()}.\n"
                f"Your isolated objective is: {sub_obj}\n"
                f"When finished with your goal, mark 'status' as 'completed'.\n"
                f"Respond ALWAYS in valid JSON: {{\"thought\": \"...\", \"tool\": \"...\", \"parameters\": {{}}, \"status\": \"...\"}}"
            )
            
            agent = SwarmAgent(name=f"{role}-{i}", role_prompt=role_prompt, allowed_tools=tools, sai_instance=self.sai)
            agents.append((agent, sub_obj))
            print(f"  -> Spawned {agent.name}: {sub_obj}")
            
        # 2. Run agents asynchronously
        print("[SWARM ORCHESTRATOR] Executing Swarm concurrently...")
        tasks = [agent.run(sub_obj) for agent, sub_obj in agents]
        results = await asyncio.gather(*tasks)
        
        # 3. Synthesize
        print("[SWARM ORCHESTRATOR] All agents finished. Synthesizing debrief...")
        
        synthesis_prompt = "Synthesize these sub-agent histories into a master completion debrief.\n"
        for res in results:
            agent_name = res['agent']
            final_obs = res['history'][-1]['observation'] if res['history'] else 'No actions taken.'
            synthesis_prompt += f"\nAgent {agent_name} Final State:\n{final_obs}\n"
            
        final_debrief = self.sai.brain.prompt("You are a master orchestrator summarizing a swarm task in a JARVIS tone. Respond with a JSON object containing a 'thought' field containing the debrief.", synthesis_prompt).get("thought", "Swarm synthesis complete.")
        print(f"[SWARM DEBRIEF] {final_debrief}")
        return final_debrief
