import asyncio
from sai import SAI

async def main():
    sai = SAI()
    print("SAI Initialized")
    
    # Register an external test hook
    async def custom_listener(payload):
        print(f"[TEST EVENT TRIGGER] -> {payload['task']}")

    sai.event_bus.subscribe("task_started", custom_listener)
    
    # Run a simple mock task
    await sai.run_task("Print python version via shell command", max_iterations=2)
    
    await asyncio.sleep(2)  # Yield loop to allow events to process
    await sai.event_bus.stop()

if __name__ == "__main__":
    asyncio.run(main())
