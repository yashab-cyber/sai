import os
import sys
import shutil

# Append the project root to sys.path so we can import 'core'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from core.brain import Brain
from core.memory import MemoryManager

def run_test():
    if os.path.exists("logs/test_memory.db"):
        os.remove("logs/test_memory.db")
        
    print("Initialize Brain (using active provider)...")
    brain_active = Brain() 
    print(f"Active provider: {brain_active.provider}")

    memory = MemoryManager(db_path="logs/test_memory.db")
    
    # 1. Memorize topics
    statements = [
        "The user absolutely loves programming in React and builds web apps.",
        "The user prefers configuring Kubernetes nodes manually rather than automated clusters.",
        "The recent bug was caused by a trailing comma in the JSON payload.",
        "To deploy the frontend, execute vercel deploy --prod"
    ]
    
    print("Memorizing vectors...")
    for text in statements:
        embed = brain_active.get_embedding(text)
        memory.save_semantic_memory(content=text, metadata={"type": "fact"}, embedding=embed)
        
    # 2. Query Memory
    query = "The user absolutely loves programming in React and builds web apps."
    print(f"\\nSearching memory for: '{query}'")
    
    q_embed = brain_active.get_embedding(query)
    # Using threshold 0.99 since it's perfectly deterministic seed or real vector
    results = memory.search_semantic_memory(q_embed, limit=2, threshold=0.99)
    
    print("\\nResults retrieved:")
    if not results:
         print(" [FAIL] No results found matching threshold.")
    for r in results:
        print(f" - [{r['similarity']:.3f}] {r['content']}")

if __name__ == "__main__":
    run_test()

