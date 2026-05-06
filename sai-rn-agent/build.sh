#!/bin/bash

echo "🚀 Starting a clean build of the S.A.I. Android Companion App..."

echo "🧹 Step 1: Terminating any lingering Node/Metro bundler processes..."
killall node 2>/dev/null || true

echo "🧹 Step 2: Cleaning Android Gradle cache..."
cd android
./gradlew clean
cd ..

echo "🧹 Step 3: Clearing Watchman cache (if applicable)..."
watchman watch-del-all 2>/dev/null || true

echo "📦 Step 4: Starting Metro Bundler with a cleared cache in the background..."
npm run start:clean &

# Give Metro a few seconds to initialize
sleep 5

echo "📱 Step 5: Building and launching the Android App..."
npm run android

echo "✅ Build process initiated! You can monitor the Metro bundler logs above."
