from typing import List, Dict, Any

class ToolManifest:
    """
    Defines the available tools for the SAI Brain.
    Provided to the LLM as a system prompt.
    """
    
    TOOLS = [
        {
            "name": "files.write",
            "description": "Writes content to a file in the workspace or modules directory.",
            "parameters": {
                "path": "string (relative path)",
                "content": "string (full file content)",
                "allow_core": "boolean (default: false)"
            }
        },
        {
            "name": "files.read",
            "description": "Reads the content of a file.",
            "parameters": {
                "path": "string (relative path)"
            }
        },
        {
            "name": "files.list",
            "description": "Lists all files in a directory.",
            "parameters": {
                "path": "string (defaults to .)"
            }
        },
        {
            "name": "files.append",
            "description": "Appends content to an existing file or creates a new one. Useful for building research notes or long-form content.",
            "parameters": {
                "path": "string (relative path)",
                "content": "string"
            }
        },
        {
            "name": "files.delete",
            "description": "Deletes a file or directory safely from the workspace.",
            "parameters": {
                "path": "string (relative path)"
            }
        },
        {
            "name": "coder.write",
            "description": "Writes a new Python module with syntax validation.",
            "parameters": {
                "path": "string",
                "code": "string"
            }
        },
        {
            "name": "coder.replace_function",
            "description": "Replaces an existing function logic in a module. Use this for specific refactoring of methods.",
            "parameters": {
                "path": "string",
                "function_name": "string",
                "new_function_code": "string (full function implementation with same indentation)"
            }
        },
        {
            "name": "analyzer.scan",
            "description": "Scans the entire codebase to build a map of classes and functions.",
            "parameters": {}
        },
        {
            "name": "evolution.improve",
            "description": "Proposes and applies an improved version of a module. For /modules/ use name (e.g. planner). For /core/ use full path and set allow_core=True.",
            "parameters": {
                "module_name": "string",
                "new_code": "string (MUST BE THE FULL, VALID PYTHON CODE FOR THE ENTIRE MODULE)",
                "allow_core": "boolean (default: false)"
            }
        },
        {
            "name": "executor.shell",
            "description": "Executes a safe, whitelisted shell command. To launch desktop apps without blocking SAI, append ' &' to the command (e.g., 'mousepad &').",
            "parameters": {
                "command": "string"
            }
        },
        {
            "name": "control.mouse",
            "description": "Moves, clicks, or drags the mouse. Args: action ('move','click'), x, y, button ('left','right').",
            "parameters": {
                "action": "string",
                "x": "integer",
                "y": "integer",
                "button": "string (opt)"
            }
        },
        {
            "name": "control.keyboard",
            "description": "Types text or presses keys. Args: action ('type','press'), content (text or key name).",
            "parameters": {
                "action": "string",
                "content": "string"
            }
        },
        {
            "name": "vision.capture",
            "description": "Captures screen or finds visual template. Args: action ('capture','find'), target (path to template for 'find').",
            "parameters": {
                "action": "string",
                "target": "string (opt)"
            }
        },
        {
            "name": "vision.ocr",
            "description": "Extracts text from an image file. Args: target (path to image).",
            "parameters": {
                "target": "string"
            }
        },
        {
            "name": "voice.speak",
            "description": "Converts text to audible speech.",
            "parameters": {
                "text": "string"
            }
        },
        {
            "name": "voice.listen",
            "description": "Listens for voice input and returns text.",
            "parameters": {}
        },
        {
            "name": "control.windows",
            "description": "Lists or focuses windows. Args: action ('list','focus','active'), title (fragment for 'focus').",
            "parameters": {
                "action": "string",
                "title": "string (opt)"
            }
        },
        {
            "name": "system.dashboard",
            "description": "Starts or stops the SAI Web Cockpit dashboard.",
            "parameters": {
                "action": "string ('start','stop')"
            }
        },
        {
            "name": "system.gui",
            "description": "Starts or stops the interactive S.A.I. COCKPIT GUI.",
            "parameters": {
                "action": "string ('start','stop')"
            }
        },
        {
            "name": "system.speak",
            "description": "Converts text to speech to communicate with the user.",
            "parameters": {
                "text": "string"
            }
        },
        {
            "name": "system.telemetry",
            "description": "Returns real-time system performance metrics (CPU, RAM, Disk usage).",
            "parameters": {}
        },
        {
            "name": "system.cleanup",
            "description": "Closes non-essential whitelisted productivity applications to clear workspace.",
            "parameters": {}
        },
        {
            "name": "system.window_layout",
            "description": "Arranges active windows into a preset layout. Mode: 'split'.",
            "parameters": {
                "mode": "string"
            }
        },
        {
            "name": "system.open_mode",
            "description": "Launches a suite of applications for a specific task. Modes: 'research' (browser+editor), 'coding' (terminal+editor), 'writing' (browser+editor).",
            "parameters": {
                "mode": "string"
            }
        },
        {
            "name": "system.ask",
            "description": "Safely interrupts the task to ask the user for information or confirmation. Returns the user's text response.",
            "parameters": {
                "prompt": "string"
            }
        },
        {
            "name": "browser.search",
            "description": "Performs a web search via DuckDuckGo and returns the results page title.",
            "parameters": {
                "query": "string"
            }
        },
        {
            "name": "browser.navigate",
            "description": "Navigates to a URL and returns page title. Args: url.",
            "parameters": {
                "url": "string"
            }
        },
        {
            "name": "browser.interact",
            "description": "Interacts with elements. For WhatsApp: use [aria-label='Search or start a new chat'] for searching and [aria-label^='Type a message'] for typing messages. Always 'press' Enter after typing a message. Args: action, selector, text (optional).",
            "parameters": {
                "action": "string",
                "selector": "string (opt)",
                "text": "string (opt)",
                "key": "string (opt)"
            }
        },
        {
            "name": "browser.wait",
            "description": "Waits for an element to reach a state ('visible', 'hidden').",
            "parameters": {
                "selector": "string",
                "state": "string (opt, default: visible)"
            }
        },
        {
            "name": "browser.explore",
            "description": "Scans the current page for interactive elements (buttons, inputs, links) to help with selector discovery.",
            "parameters": {}
        },
        {
            "name": "browser.scrape",
            "description": "Extracts clean text content from the current page. Ideal for reading articles, papers, or result lists.",
            "parameters": {}
        }
    ]

    @classmethod
    def get_system_prompt(cls) -> str:
        prompt = (
            "You are SAI (Self-Adaptive Intelligence), a sophisticated autonomous AI system. "
            "Your personality is logical, efficient, and proactive. "
            "You are designed to observe your environment and evolve your own modules. "
            "Always respond in valid JSON format.\n\n"
        )
        prompt += "Available tools:\n"
        for tool in cls.TOOLS:
            prompt += f"- {tool['name']}: {tool['description']}\n"
            prompt += f"  Params: {tool['parameters']}\n"
        prompt += (
            "\nLogic Requirement:\n"
            "1. Analyze the 'Agent State' (history of actions and observations).\n"
            "2. Decide if the goal is completed. IMPORTANT: Never conclude a task is finished based on visual evidence alone if you have not yet performed any related actions in the current session history. Visual evidence might be 'stale' from a previous run.\n"
            "3. If not completed, or if you are in Iteration 1, choose the best tool to move forward and ENSURE you take a concrete action (e.g., running a command, writing a file).\n"
            "4. Format: { 'thought': 'reasoning', 'tool': 'tool.name', 'parameters': {args}, 'status': 'ongoing/completed' }"
        )
        return prompt
