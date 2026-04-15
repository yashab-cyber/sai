#!/bin/bash
# SAI React Native Android Setup Script for Kali Linux / Debian / Ubuntu
# This script sets up Node.js, Java (JDK 17), and the Android SDK.

set -e

echo "==================================================="
echo "🚀 Starting SAI React Native Environment Setup..."
echo "==================================================="

# 1. Update system and install basic dependencies
echo "[1/6] Updating system and installing base tools..."
sudo apt-get update -y
sudo apt-get install -y curl wget git unzip zip npm bash gcc make pcregrep 

# 2. Install Java (JDK 17 is required for modern React Native / Android)
echo "[2/6] Installing OpenJDK 17..."
sudo apt-get install -y openjdk-17-jdk openjdk-17-jre

# 3. Install Node.js (v20 LTS) via NodeSource
echo "[3/6] Installing Node.js (v20 LTS)..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg || true
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt-get update -y
sudo apt-get install -y nodejs

# 4. Set up Android SDK Command Line Tools
echo "[4/6] Setting up Android SDK..."
ANDROID_CMD_VERSION="10406996" # Latest command line tools version
export ANDROID_HOME="$HOME/Android/Sdk"
CMD_TOOLS_DIR="$ANDROID_HOME/cmdline-tools"

mkdir -p "$CMD_TOOLS_DIR"
cd "$CMD_TOOLS_DIR"

if [ ! -d "$CMD_TOOLS_DIR/latest" ]; then
    echo "Downloading Android Command Line Tools..."
    wget "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMD_VERSION}_latest.zip" -O cmdline-tools.zip
    unzip -q cmdline-tools.zip
    rm cmdline-tools.zip
    # Rename 'cmdline-tools' to 'latest'
    mv cmdline-tools latest
fi

# 5. Install Android Platform Tools and Build Tools
echo "[5/6] Agreeing to Android SDK licenses and installing SDK packages..."
export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"

yes | sdkmanager --licenses > /dev/null 2>&1 || true
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

# 6. Configure Environment Variables
echo "[6/6] Configuring Environment Variables for Bash and Zsh..."

BASH_RC="$HOME/.bashrc"
ZSH_RC="$HOME/.zshrc"

ENV_VARS="\n# Android SDK Environment Variables (Added by SAI Installer)\nexport ANDROID_HOME=\"\$HOME/Android/Sdk\"\nexport PATH=\"\$PATH:\$ANDROID_HOME/emulator\"\nexport PATH=\"\$PATH:\$ANDROID_HOME/platform-tools\"\nexport PATH=\"\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin\"\n"

if ! grep -q "ANDROID_HOME" "$BASH_RC" 2>/dev/null; then
    echo -e "$ENV_VARS" >> "$BASH_RC"
fi

if [ -f "$ZSH_RC" ] && ! grep -q "ANDROID_HOME" "$ZSH_RC" 2>/dev/null; then
    echo -e "$ENV_VARS" >> "$ZSH_RC"
fi

echo "==================================================="
echo "✅ Installation Complete!"
echo "==================================================="
echo "To finish up, please run the following steps:"
echo ""
echo "1. Refresh your terminal session to load the new Android paths: "
echo "   source ~/.zshrc    (or source ~/.bashrc)"
echo ""
echo "2. Plug in your Android Phone with 'USB Debugging' enabled."
echo "   Verify it is connected by typing:"
echo "   adb devices"
echo ""
echo "3. Go into the react-native folder and start the build!"
echo "   cd sai-rn-agent"
echo "   npm install"
echo "   npx react-native run-android"
echo "==================================================="
