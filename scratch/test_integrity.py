import sys
import os
sys.path.append(os.getcwd())

from modules.coder import Coder
from unittest.mock import MagicMock

def test_integrity():
    coder = Coder(MagicMock())
    original = "class X:\n    def y(self): pass"
    placeholder = "PLACEHOLDER_FOR_CODE"
    
    valid, msg = coder.validate_module_integrity(original, placeholder)
    print(f"Original: {original[:20]}...")
    print(f"New: {placeholder}")
    print(f"Valid: {valid}")
    print(f"Message: {msg}")
    
    assert not valid
    assert "no functions or classes" in msg
    print("Test passed: Integrity check blocked placeholder.")

if __name__ == "__main__":
    test_integrity()
