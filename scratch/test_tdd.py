import asyncio
import os
import sys

# Add parent dir to path so we can import sai
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sai import SAI

async def main():
    sai_instance = SAI()
    print("Initiating TDD Loop validation...")
    
    result = await sai_instance.execute_tool('coder.tdd', {
        'objective': 'Create a robust mathematical module containing divide, multiply, and factorial functions, and guarantee it handles zero and negative bounds flawlessly.',
        'path': 'modules/math_module.py'
    })
    
    print("\n--- Final Output ---")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
