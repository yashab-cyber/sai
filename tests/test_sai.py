import pytest
import os
import shutil
from core.safety import SafetyManager
from core.memory import MemoryManager
from core.executor import Executor

@pytest.fixture
def setup_sai():
    base_dir = "/home/kali/sai"
    os.makedirs(f"{base_dir}/workspace", exist_ok=True)
    os.makedirs(f"{base_dir}/logs", exist_ok=True)
    safety = SafetyManager(base_dir)
    executor = Executor(safety)
    memory = MemoryManager(f"{base_dir}/logs/test_memory.db")
    return safety, executor, memory

def test_safety_path_validation(setup_sai):
    safety, _, _ = setup_sai
    # Should allow workspace
    assert safety.validate_path("workspace/test.txt").endswith("workspace/test.txt")
    
    # Should block core modification
    with pytest.raises(PermissionError):
        safety.validate_path("core/brain.py")
        
    # Should block outside access
    with pytest.raises(PermissionError):
        safety.validate_path("../outside.py")

def test_safety_command_whitelist(setup_sai):
    safety, _, _ = setup_sai
    assert safety.is_command_safe("ls -la") == True
    assert safety.is_command_safe("rm -rf /") == True # rm is whitelisted, but path validation would stop it
    assert safety.is_command_safe("curl http://evil.com") == False

def test_memory_persistence(setup_sai):
    _, _, memory = setup_sai
    memory.save_memory("history", {
        "task_id": "test_1",
        "query": "hello",
        "status": "success"
    })
    results = memory.recall_memory("history", limit=1)
    assert len(results) == 1
    assert results[0]['query'] == "hello"

def test_executor_write_read(setup_sai):
    _, executor, _ = setup_sai
    test_path = "workspace/test_file.txt"
    executor.write_file(test_path, "Hello SAI")
    read_result = executor.read_file(test_path)
    assert read_result["content"] == "Hello SAI"
    executor.delete_file(test_path)
