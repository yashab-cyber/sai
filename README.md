# S.A.I. — Self-Adaptive Intelligence

### JARVIS Protocol v2 · Neural Command Node

> A fully autonomous, visual-perceptive research and automation agent designed to orchestrate your local environment and connected devices with JARVIS-level sophistication.

![Status](https://img.shields.io/badge/Status-MARK_IV_ACTIVE-00F2FF?style=for-the-badge&logo=intelligence)
![Core](https://img.shields.io/badge/Core-Python%20%7C%20React%20%7C%20Kotlin-blue?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Android-green?style=for-the-badge)

---

## 🌌 Overview

SAI combines high-level reasoning (LLMs) with low-level system control, real-time visual perception, and a futuristic 3D cockpit interface. It doesn't just *chat* — it navigates the web, executes shell commands, manages files, controls Android devices remotely, and conducts multi-step research autonomously.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    S.A.I. COMMAND HUB                         │
│                  (Python · Flask · SocketIO)                  │
│                                                              │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Planner │  │  Brain  │  │  Vision  │  │   Browser    │   │
│  │ (LLM)   │  │ (GPT-4) │  │  (OCR)   │  │ (Playwright) │   │
│  └─────────┘  └─────────┘  └──────────┘  └──────────────┘   │
│                                                              │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │ Device Manager │  │  Evolution   │  │   Voice (TTS)  │    │
│  │ (Multi-Node)   │  │  Engine      │  │   "Hi SAI"     │    │
│  └───────┬────────┘  └──────────────┘  └────────────────┘    │
└──────────┼───────────────────────────────────────────────────┘
           │
    ┌──────▼──────┐
    │  HTTP / WS  │
    └──────┬──────┘
           │
    ┌──────▼──────────────────┐
    │  ANDROID COMPANION NODE │
    │  (React Native · Kotlin)│
    │                         │
    │  • Accessibility API    │
    │  • Screen Capture       │
    │  • Gesture Injection    │
    │  • App Launch (Intent)  │
    └─────────────────────────┘
```

---

## ✨ Key Features

### 🧠 Autonomous Intelligence
- **Strategic Planner** — LLM-powered task decomposition with iterative execution loops
- **Self-Evolution** — Analyzes and improves its own code modules autonomously
- **Reflection Engine** — Post-task analysis for continuous improvement
- **Memory System** — SQLite-backed persistent memory with learned pattern replay

### 👁️ Visual Perception
- **Vision Nexus** — Live screen capture with OCR text extraction
- **Desktop HUD** — Always-on-top native window for visual feedback
- **Browser Automation** — Playwright-based web navigation with screenshot reasoning

### 🎙️ Voice Interface
- **Wake-Word Detection** — Hands-free activation with "Hi SAI"
- **Text-to-Speech** — JARVIS-style composed, authoritative voice delivery
- **Inline Commands** — Speak commands directly after the wake-word

### 📱 Android Device Control
- **Native Companion App** — React Native + Kotlin app (no ROOT required)
- **Accessibility-Powered** — Screen reading, gesture injection, and text input via Android Accessibility API
- **Screenshot Capture** — Real-time device screen capture via Accessibility screenshot pipeline
- **App Launcher** — Open any installed app via Android Intent system
- **Direct HTTP API** — Robust REST API with token auth, rate limiting, and IP whitelisting
- **Hub Auto-Discovery** — mDNS-based automatic SAI Hub detection on local network
- **Connection Status** — Live hub connection indicator on the companion app

### 🌐 Multi-Device Distributed Network
- **Device Plugin Architecture** — Extensible base classes for adding new device types
- **mDNS Auto-Discovery** — Agents find the SAI Hub automatically on LAN
- **Task Execution Pipeline** — Offline queuing and retry logic for disconnected agents
- **Real-time Monitoring** — Live device dashboard in the web cockpit
- **LAN Security** — Token-based authentication with IP-subnet whitelisting

### 🖥️ JARVIS Cockpit
- **Web Dashboard** — React-based tactical interface at `http://localhost:5000`
- **Real-time Telemetry** — CPU, RAM, disk, network speed, and temperature
- **SocketIO Streaming** — Live state updates pushed to all connected clients
- **Command Input** — Issue directives directly from the browser

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Core runtime |
| Node.js | 22+ | Web UI & Android agent build |
| Chromium | Latest | Browser automation via Playwright |

### 1. Clone & Initialize

```bash
git clone https://github.com/yashab-cyber/sai.git
cd sai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

Copy the example and fill in your API keys:

```bash
cp .env.example .env
nano .env
```

**Required variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `SAI_PROVIDER` | LLM provider | `openai`, `gemini`, `ollama`, `anthropic` |
| `MODEL_NAME` | Model identifier | `gpt-4-turbo`, `gemini-1.5-pro` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `SAI_BROWSER_HEADLESS` | Run browser headless | `true` / `false` |

### 3. Launch SAI

```bash
# Start with GUI cockpit
python3 sai.py gui

# Start with a specific directive
python3 sai.py "research recent papers on agentic AI"

# Interactive chat mode
python3 sai.py --chat
```

Visit `http://localhost:5000` to access the JARVIS Cockpit.

---

## 📱 Android Companion Setup

The **SAI Companion Node** is a native Android app that gives SAI full control over your phone — no root, no Termux required.

> **Full build instructions →** [`sai-rn-agent/README.md`](sai-rn-agent/README.md)

### Quick Overview

1. Build the APK from `sai-rn-agent/` using React Native CLI
2. Install on your Android device via ADB or manual transfer
3. Enable the **SAI Accessibility Service** in Android settings
4. Tap **START** in the companion app to launch the API server
5. SAI auto-discovers the device and shows **HUB LINKED** on the companion

### Capabilities

| Action | Endpoint | Description |
|--------|----------|-------------|
| Open App | `POST /action/open_app` | Launch any app by package name |
| Tap | `POST /action/tap` | Inject touch at x,y coordinates |
| Type | `POST /action/type` | Input text into focused field |
| Screen Text | `GET /state/screen_text` | Extract all visible text via Accessibility |
| Screenshot | `GET /state/screenshot` | Capture screen as base64 JPEG |
| Health | `GET /health` | Device health + hub connection status |

---

## 🛠 Module Reference

| Module | Path | Purpose |
|--------|------|---------|
| **Planner** | `modules/planner.py` | Strategic task decomposition with visual context |
| **Vision** | `modules/vision.py` | Screen capture, OCR, and visual analysis |
| **Browser** | `modules/browser.py` | Playwright-based autonomous web interaction |
| **Voice** | `modules/voice.py` | TTS, STT, and "Hi SAI" wake-word detection |
| **Device Manager** | `modules/device_manager.py` | Multi-device registration, heartbeat, dispatch |
| **Coder** | `modules/coder.py` | Code writing, replacement, linting, and testing |
| **Evolution** | `modules/evolution.py` | Self-improvement proposals and module upgrades |
| **Brain** | `core/brain.py` | Multi-provider LLM abstraction layer |
| **Executor** | `core/executor.py` | Secure sandboxed shell execution |
| **Memory** | `core/memory.py` | SQLite persistent memory and pattern learning |
| **Safety** | `core/safety.py` | Command whitelist and path restrictions |
| **GUI Server** | `web/gui_server.py` | Flask + SocketIO cockpit server |
| **Android Client** | `modules/device_plugins/android_companion.py` | HTTP client for Android companion app |

---

## 🛡 Safety & Security

SAI operates through a **Safety Executor** enforcing strict guardrails:

- **Shell Whitelist** — Only pre-approved commands (`git`, `npm`, `python`, `firefox`, etc.)
- **Path Restrictions** — File operations locked to the designated workspace directory
- **Token Authentication** — All network communication secured with bearer tokens
- **IP Whitelisting** — Android companion API restricted to known LAN addresses
- **Rate Limiting** — Android API enforces 120 requests/minute per IP
- **Human-in-the-Loop** — `system.ask` tool for requesting user confirmation on sensitive operations

---

## 📂 Project Structure

```
sai/
├── sai.py                  # Main orchestrator
├── config.yaml             # System configuration
├── .env                    # API keys and secrets
├── requirements.txt        # Python dependencies
├── core/                   # Core systems (brain, executor, memory, safety)
├── modules/                # Feature modules (vision, voice, planner, browser)
│   └── device_plugins/     # Android companion client
├── web/                    # Flask GUI server + templates
├── web-ui/                 # React cockpit frontend
├── sai-rn-agent/           # Android companion app (React Native + Kotlin)
│   └── android/            # Native Android source
├── logs/                   # Runtime logs and HUD captures
└── tests/                  # Test suite
```

---

*Built with the AR_CORE Initiative · S.A.I. — Your will, executed.*
