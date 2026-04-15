# SAI React Native Agent

The SAI React Native Agent completely replaces the deprecated `Termux:API`. It runs natively on your Android phone and exposes a silent HTTP server in the background (on Port 8080) that allows the Python SAI Brain to natively tap, type, read the screen, and open apps without ROOT access.

---

## 🛠️ Step 1: Install the Android Application

You can install the compiled `.apk` onto your phone directly via your Kali Linux terminal.

**Option A: Direct Install via USB (ADB)**
1. Connect your Android phone to Kali Linux using a USB cable.
2. Ensure you have **USB Debugging** enabled in `Settings -> Developer Options` on your phone.
3. Install the app via Android Debug Bridge (ADB):

```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

**Option B: Manual Transfer**
Just copy the `app-debug.apk` file from your Kali Linux terminal `android/app/build/outputs/apk/debug/app-debug.apk` to your phone's download folder and tap it to install.

---

## ⚙️ Step 2: Configure the App Permissions

Once the **SAI Companion Agent** is installed on your phone:

1. Open the "SAI Companion Agent" app.
2. Tap the button reading: **Enable Accessibility Service**
3. This opens your phone's system settings. Scroll down to *Installed Apps -> SAI Companion Agent Accessibility Router* and toggle it **ON**.
   *(This gives the app permission to "see" UI elements and simulate screen taps programmatically).*
4. Go back to the SAI App, and verify the Accessibility Status says "Enabled".
5. Finally, tap the **Start API** button. 
   *(Your phone is now silently listening on port `8080` for SAI Python scripts to send it instructions).*

---

## 🔌 Step 3: Run the SAI Python Brain

On your computer (Kali/Ubuntu/Codespace), run the main S.A.I hub and python automation scripts safely.

Because you are likely connecting your laptop to your Android phone's Mobile Hotspot, the Agent handles network routing gracefully (such as automatically searching your `10.x.x.x` blocks).

Start the main Python script on your laptop as you normally would:

```bash
python3 sai.py
```

**(Optional) Test It Directly:**
You can manually trigger actions on your phone straight from Python:

```python
from modules.device_plugins.android_companion import DeviceControl

control = DeviceControl()

# Simulates a finger tapping at the x=500, y=500 pixel coordinate
control.tap(500, 500)

# Extracts all the words currently readable on the Android screen natively
screen_content = control.get_screen_text()
print(screen_content)

# Simulates typing text instantly into whichever input box is currently selected
control.type("Hello from SAI AI!")

# Opens YouTube immediately
control.open_app("com.google.android.youtube")
```
