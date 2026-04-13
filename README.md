# S.A.I. — Self-Adaptive Intelligence
### JARVIS Protocol v2 | Neural Command Node

SAI is a fully autonomous, visual-perceptive research and automation agent designed to control your local PC environment with JARVIS-style sophistication.

![JARVIS Cockpit](https://img.shields.io/badge/Status-MARK_IV_ACTIVE-00F2FF?style=for-the-badge&logo=intelligence)
![Tech](https://img.shields.io/badge/Core-React%20%7C%20Three.js%20%7C%20Python-blue?style=for-the-badge)

## 🌌 Overview
SAI combines high-level reasoning (LLMs) with low-level PC control, real-time vision, and a futuristic 3D interface. It doesn't just "chat"—it navigates the web, executes shell commands, manages files, and conducts research autonomously.

### Key Features
*   **Vision Nexus**: Live visual perception with an "always-on-top" desktop HUD window.
*   **JARVIS Cockpit**: A futuristic 3D web dashboard using React, Tailwind, and Three.js.
*   **Autonomous Research**: Multi-step web navigation, content scraping, and incremental reporting.
*   **Self-Evolution**: Capability to analyze and improve its own code modules.
*   **PC Orchestration**: Control terminal, applications (Firefox, VS Code, Mousepad), and file systems through a secure whitelist.

## 🚀 Quick Start
1.  **Initialize Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
    ```
2.  **Configure API Keys**:
    Create a `.env` file with your `OPENAI_API_KEY`.
3.  **Launch the Cockpit**:
    ```bash
    python3 sai.py "start gui"
    ```
    Visit `http://localhost:5000` to enter the JARVIS Command Node.

## 🛠 Modules
*   **`Planner`**: Strategic task decomposition.
*   **`Vision`**: Real-time screen analysis and OCR.
*   **`Browser`**: Playwright-based autonomous web interaction.
*   **`HUD`**: Native desktop window for visual feedback.
*   **`Core`**: Secure shell execution and path validation.

## 🛡 Safety
SAI operates through a **Safety Executor** that enforces:
*   Whitelisted shell commands (e.g., `git`, `npm`, `firefox`).
*   Path-restricted file operations (restricted to the workspace).
*   Human-in-the-loop interruption via `system.ask`.

---
*Created with the AR_CORE Initiative.*
