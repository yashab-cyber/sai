import os
import sys
import asyncio

# Append the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from sai import SAI

async def main():
    print("Initializing Core S.A.I...")
    sai = SAI()
    
    # Check if Swarm is initialized
    if not hasattr(sai, "swarm"):
        print("[FAIL] Swarm not found on SAI")
        return
        
    print("Swarm orchestrator initialized.")
    objective = "Identify the top 2 programming trends, while simultaneously writing a python script."
    
    print(f"\\nDispatching massive objective to Swarm: {objective}")
    
    # We directly hit the swarm.delegate tool which we registered!
    print("\\n----- SWARM DELEGATION START -----")
    debrief = await sai.execute_tool("swarm.delegate", {"task": objective})
    print("----- SWARM DELEGATION END -----")
    
    print("\\nFinal Synthesis from Swarm Orchestrator:")
    print(debrief)

if __name__ == "__main__":
    asyncio.run(main())

