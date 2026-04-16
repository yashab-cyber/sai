# S.A.I. Android Companion Node

> Native Android companion agent for the S.A.I. command hub. Provides screen reading, gesture injection, screenshot capture, and app control — **no ROOT required**.

![Platform](https://img.shields.io/badge/Platform-Android%2024+-green?style=for-the-badge&logo=android)
![Framework](https://img.shields.io/badge/Framework-React%20Native%200.85-blue?style=for-the-badge&logo=react)
![Language](https://img.shields.io/badge/Native-Kotlin-purple?style=for-the-badge&logo=kotlin)

---

## 🌐 How It Works

The companion app runs a **local HTTP API server** on your Android phone (default port `8080`). The SAI Python brain on your computer sends commands to this server over your local network. The app uses Android's **Accessibility Service** to read screen content, inject taps, type text, and capture screenshots — all without root.

```
┌─────────────────────┐         HTTP          ┌──────────────────────┐
│   SAI Command Hub   │ ◀──────────────────▶  │  Android Companion   │
│   (Kali Linux)      │   Port 8080 / LAN     │  (Your Phone)        │
│                     │                       │                      │
│  • Sends commands   │                       │  • API Server        │
│  • Receives screen  │                       │  • Accessibility Svc │
│  • Vision analysis  │                       │  • Screenshot Engine │
└─────────────────────┘                       └──────────────────────┘
```

### Features

| Feature | Method | Description |
|---------|--------|-------------|
| **Open App** | `POST /action/open_app` | Launch any installed app by package name |
| **Tap Screen** | `POST /action/tap` | Inject touch gesture at (x, y) coordinates |
| **Type Text** | `POST /action/type` | Input text into currently focused field |
| **Read Screen** | `GET /state/screen_text` | Extract all visible UI text via Accessibility tree |
| **Screenshot** | `GET /state/screenshot` | Capture screen as base64 JPEG (Android 11+) |
| **Health Check** | `GET /health` | Device status, accessibility, hub connection |
| **Hub Status** | `GET /status/hub` | SAI Hub connection status and IP |
| **Send Message** | `POST /macro/send_message` | High-level message automation macro |

---

## 📋 Prerequisites

| Tool | Version | Installation |
|------|---------|-------------|
| **Node.js** | ≥ 22.11.0 | `nvm install 22` or [nodejs.org](https://nodejs.org) |
| **Java JDK** | 17 | `sudo apt install openjdk-17-jdk` |
| **Android SDK** | API 36 (Build Tools 36.0.0) | Via Android Studio or `sdkmanager` |
| **ADB** | Latest | `sudo apt install adb` |
| **USB Debugging** | Enabled | Android Settings → Developer Options |

### Environment Variables

Ensure these are set in your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/emulator
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
```

Reload your shell:

```bash
source ~/.bashrc
```

---

## 🔨 Build Instructions

### Step 1: Install Dependencies

```bash
cd sai-rn-agent
npm install
```

### Step 2: Connect Your Android Device

Connect your phone via USB and verify ADB sees it:

```bash
adb devices
```

You should see your device listed. If prompted on your phone, tap **"Allow USB Debugging"**.

### Step 3: Build the Debug APK

```bash
cd android
./gradlew assembleDebug
```

The APK will be generated at:
```
android/app/build/outputs/apk/debug/app-debug.apk
```

### Step 4: Install on Device

**Option A — Direct ADB Install:**
```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

**Option B — Run directly (builds + installs + launches):**
```bash
npx react-native run-android
```

**Option C — Manual Transfer:**
Copy `app-debug.apk` to your phone and tap it to install.

---

## 🧹 Clean Build Commands

When you encounter build issues, use these commands to reset the build environment:

### Clean Gradle Cache

```bash
cd android
./gradlew clean
```

### Full Cache Reset (Nuclear Option)

```bash
# Stop any running Metro bundler
npx react-native start --reset-cache &
kill $!

# Clean Gradle build artifacts
cd android && ./gradlew clean && cd ..

# Remove node_modules and reinstall
rm -rf node_modules
npm install

# Clear Gradle caches
rm -rf android/.gradle
rm -rf android/app/build

# Clear Metro bundler cache
rm -rf /tmp/metro-*
rm -rf /tmp/haste-map-*
```

### Rebuild After Cache Clear

```bash
# Reinstall dependencies
npm install

# Build fresh APK
cd android && ./gradlew assembleDebug
```

### Fix Common Build Errors

```bash
# Gradle wrapper permissions
chmod +x android/gradlew

# SDK license agreements
yes | sdkmanager --licenses

# Java version mismatch — ensure JDK 17
java -version   # Should show 17.x
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Sync Gradle if build.gradle changed
cd android && ./gradlew --refresh-dependencies
```

---

## ⚙️ App Setup on Android

After installing the APK on your phone:

### 1. Enable Accessibility Service

1. Open the **S.A.I. Companion** app
2. Tap the ⚠️ **"Accessibility Required"** warning card
3. In Android Settings, find **Installed Services → SAI Companion Agent Accessibility Router**
4. Toggle it **ON** and confirm the permission dialog

> **Why?** The Accessibility Service is how the app reads screen content, injects taps, types text, and captures screenshots — all without root.

### 2. Start the API Server

1. Return to the S.A.I. Companion app
2. Tap the **▶ START** button
3. The status orb should show **ONLINE** with **API Server · Port 8080**

### 3. Verify Hub Connection

When SAI is running on your computer (`python3 sai.py gui`), the companion app will display:

- **Header**: A green **HUB** badge appears next to **ONLINE**
- **Status Orb**: Shows **HUB LINKED** with the SAI hub IP address
- **Metrics**: The **🔗 SAI Hub** card shows ✓
- **Activity Log**: Logs `"SAI Hub connected from <IP>"`

---

## 🔌 Network Configuration

### Default Setup (Phone Hotspot)

When your computer is connected to your phone's mobile hotspot, SAI auto-detects the phone's IP via the default gateway. No configuration needed.

### Custom IP Setup

If your phone and computer are on the same Wi-Fi but auto-detection fails, set the phone's IP manually:

```bash
# In your .env file on the SAI command hub
SAI_ANDROID_HOST=192.168.1.100
```

### Security Settings

Configure these in the companion app's **Settings** tab:

| Setting | Default | Description |
|---------|---------|-------------|
| **Port** | `8080` | API server listen port |
| **Auth Token** | `jarvis_network_key` | Bearer token for all API requests |
| **IP Whitelist** | *(empty = allow all LAN)* | Comma-separated IPs to allow |

---

## 🧪 Testing the Connection

### From Python (on your computer)

```python
from modules.device_plugins.android_companion import AndroidCompanionClient

client = AndroidCompanionClient()

# Check health
print(client.is_healthy())        # True
print(client.get_health_details()) # {'status': 'ok', 'accessibility': True, ...}

# Read screen text
text = client.get_screen_text()
print(text)

# Open an app
client.open_app("com.whatsapp")
client.open_app("com.google.android.youtube")

# Tap at coordinates
client.tap(500, 1200)

# Type text into focused input
client.type_text("Hello from SAI!")

# Capture screenshot
b64 = client.get_screenshot_base64()
print(f"Screenshot: {len(b64)} chars")
```

### From cURL (direct API test)

```bash
# Health check
curl -H "Authorization: Bearer jarvis_network_key" \
     http://<PHONE_IP>:8080/health

# Read screen text
curl -H "Authorization: Bearer jarvis_network_key" \
     http://<PHONE_IP>:8080/state/screen_text

# Open WhatsApp
curl -X POST \
     -H "Authorization: Bearer jarvis_network_key" \
     -H "Content-Type: application/json" \
     -d '{"package": "com.whatsapp"}' \
     http://<PHONE_IP>:8080/action/open_app

# Tap at coordinates
curl -X POST \
     -H "Authorization: Bearer jarvis_network_key" \
     -H "Content-Type: application/json" \
     -d '{"x": 500, "y": 1200}' \
     http://<PHONE_IP>:8080/action/tap
```

---

## 📂 Project Structure

```
sai-rn-agent/
├── App.tsx                             # React Native UI (Control, Vision, Settings tabs)
├── package.json                        # Dependencies and scripts
├── tsconfig.json                       # TypeScript configuration
├── android/
│   ├── build.gradle                    # Root Gradle config (SDK 36, Build Tools 36.0.0)
│   ├── gradle/wrapper/
│   │   └── gradle-wrapper.properties   # Gradle 9.3.1
│   └── app/
│       ├── build.gradle                # App-level build config
│       └── src/main/
│           ├── AndroidManifest.xml      # Permissions and service declarations
│           └── java/com/saicompanion/
│               ├── MainActivity.kt              # React Native activity entry
│               ├── MainApplication.kt           # Application class
│               ├── SaiDeviceControlModule.kt     # React Native ↔ Kotlin bridge
│               ├── SaiDeviceControlPackage.kt    # Module registration
│               ├── SaiHttpServer.kt              # NanoHTTPD API server
│               └── SaiAccessibilityService.kt    # Accessibility service (core engine)
```

---

## 📊 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI** | React Native 0.85 | Cross-platform interface |
| **Native Bridge** | Kotlin + NativeModules | Server lifecycle & permissions |
| **HTTP Server** | NanoHTTPD | Lightweight embedded API server |
| **Accessibility** | Android Accessibility API | Screen reading & gesture injection |
| **Screenshot** | `takeScreenshot()` API (Android 11+) | Programmatic screen capture |
| **Build** | Gradle 9.3.1 + Android SDK 36 | Compilation and packaging |

---

*Part of the S.A.I. ecosystem · Your will, executed.*
