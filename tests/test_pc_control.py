import pytest
import os
from sai import SAI

def test_file_deletion():
    sai = SAI()
    test_file = "workspace/test_delete.txt"
    
    # Target file
    os.makedirs("workspace", exist_ok=True)
    with open(test_file, "w") as f:
        f.write("test content")
    
    assert os.path.exists(test_file)
    
    # Execute tool
    res = sai.execute_tool("files.delete", {"path": "workspace/test_delete.txt"})
    assert res["status"] == "success"
    assert not os.path.exists(test_file)

def test_safety_whitelist_extension():
    sai = SAI()
    # Check if mousepad is allowed
    res = sai.execute_tool("executor.shell", {"command": "mousepad --version"})
    # It might fail if mousepad is not installed, but it should NOT be "not whitelisted"
    assert "not whitelisted" not in str(res.get("message", ""))

def test_backgrounding_syntax():
    sai = SAI()
    # Check if 'mousepad &' is allowed by the safety manager directly
    assert sai.safety.is_command_safe("mousepad &")
