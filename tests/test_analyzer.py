import os
import pytest
from modules.analyzer import Analyzer
from core.memory import MemoryManager

@pytest.fixture
def setup_analyzer():
    memory = MemoryManager(':memory:')  # Use an in-memory database
    base_dir = os.getcwd()  # Current directory simulating the base directory
    return Analyzer(memory, base_dir)

def test_scan_codebase(setup_analyzer):
    analyzer = setup_analyzer

    # Test the scan_codebase method
    result = analyzer.scan_codebase()
    assert "Codebase scan complete." in result

def test_analyze_file(setup_analyzer):
    analyzer = setup_analyzer
    sample_file_path = os.path.join(os.getcwd(), "sample_test_file.py")

    # Create a temporary Python file for testing
    with open(sample_file_path, "w") as f:
        f.write("""class TestClass:\n    pass\ndef test_function():\n    pass\n""")

    analyzer._analyze_file(sample_file_path, "sample_test_file.py")

    # Validate memory contents
    codebase_map = analyzer.memory.recall_memory("codebase_map")
    assert len(codebase_map) == 2  # One class, one function
    assert codebase_map[0]["name"] == "TestClass"
    assert codebase_map[1]["name"] == "test_function"

    # Clean up
    os.remove(sample_file_path)

def test_skip_hidden_dirs(setup_analyzer):
    analyzer = setup_analyzer

    # Create a hidden folder with a sample file
    hidden_dir = os.path.join(os.getcwd(), ".hidden")
    os.makedirs(hidden_dir, exist_ok=True)
    hidden_file = os.path.join(hidden_dir, "hidden.py")
    with open(hidden_file, "w") as f:
        f.write("""def hidden_function():
                pass
             """)

    result = analyzer.scan_codebase()

    # Ensure hidden files are ignored
    codebase_map = analyzer.memory.recall_memory("codebase_map")
    assert len(codebase_map) == 0  # No entries should exist for hidden files

    # Clean up
    os.remove(hidden_file)
    os.rmdir(hidden_dir)