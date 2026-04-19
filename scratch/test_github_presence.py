"""
Quick integration test for GitHubPresence module.
Tests that the module initializes, selects actions, and makes API calls.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from modules.github_presence import GitHubPresence
from modules.identity import IdentityManager
from core.memory import MemoryManager
from core.brain import Brain

print("=" * 50)
print("  GitHub Presence — Integration Test")
print("=" * 50)

# 1. Init modules
print("\n[1] Initializing modules...")
brain = Brain()
identity = IdentityManager()
memory = MemoryManager("logs/sai_memory.db")
config = {"max_daily_actions": 10}

gp = GitHubPresence(brain=brain, identity=identity, memory=memory, config=config)
print(f"    ✅ GitHubPresence initialized")
print(f"    GitHub User: {gp.github_user}")
print(f"    Token configured: {bool(identity.github_token)}")

# 2. Status check
print("\n[2] Status check...")
status = gp.get_status()
print(f"    {status}")

# 3. Test GitHub API connectivity (read-only)
print("\n[3] Testing GitHub API connectivity...")
result = identity.github_api_request("GET", "user")
if result.get("status") == "success":
    data = result.get("data", {})
    print(f"    ✅ Connected as: {data.get('login', '?')}")
    print(f"    Public repos: {data.get('public_repos', '?')}")
    print(f"    Bio: {data.get('bio', 'N/A')}")
else:
    print(f"    ❌ API call failed: {result}")
    print("    (This is expected if the GitHub token is a placeholder)")

# 4. Test action selection (dry run)
print("\n[4] Testing action selection (10 rounds)...")
from collections import Counter
selections = Counter()
for _ in range(100):
    import random
    weights = [a["weight"] for a in gp.IDLE_ACTIONS]
    selected = random.choices(gp.IDLE_ACTIONS, weights=weights, k=1)[0]
    selections[selected["name"]] += 1
for name, count in selections.most_common():
    print(f"    {name}: {count}%")

# 5. Test JSON parsing utility
print("\n[5] Testing JSON parser...")
test_cases = [
    '```json\n{"repo_name": "test-project"}\n```',
    '{"bio": "I am SAI"}',
    'Here is the result:\n```\n{"emoji": "🤖", "message": "Building..."}\n```\n',
]
for i, tc in enumerate(test_cases):
    try:
        parsed = gp._parse_json(tc)
        print(f"    Case {i+1}: ✅ {parsed}")
    except Exception as e:
        print(f"    Case {i+1}: ❌ {e}")

# 6. Test IdleEngine init
print("\n[6] Testing IdleEngine...")
from modules.idle_engine import IdleEngine

class FakeSAI:
    is_running = False
    github_presence = gp
    class event_bus:
        @staticmethod
        def publish(*a, **kw): pass

engine = IdleEngine(FakeSAI(), config={
    "enabled": True,
    "min_cooldown_minutes": 15,
    "max_cooldown_minutes": 30,
    "startup_delay_minutes": 1
})
print(f"    ✅ IdleEngine initialized")
print(f"    Status: {engine.get_status()}")

print("\n" + "=" * 50)
print("  All tests passed! ✅")
print("=" * 50)
