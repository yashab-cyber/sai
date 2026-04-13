from core.brain import Brain
import logging
import os

logging.basicConfig(level=logging.INFO)

def test():
    # Force a provider for testing if .env isn't set
    os.environ["SAI_PROVIDER"] = "mock"
    brain = Brain()
    print(f"Detected Provider: {brain.provider}")
    
    print("\nTesting Mock prompt:")
    res = brain.prompt("system", "hello")
    print(res)

if __name__ == "__main__":
    test()
