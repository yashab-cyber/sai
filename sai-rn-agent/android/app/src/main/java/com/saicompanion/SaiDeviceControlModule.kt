package com.saicompanion

import android.content.Intent
import android.provider.Settings
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod

class SaiDeviceControlModule(private val reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    private var server: SaiHttpServer? = null

    override fun getName(): String {
        return "SaiDeviceControl"
    }

    @ReactMethod
    fun startLocalServer(port: Int, promise: Promise) {
        try {
            if (server == null) {
                server = SaiHttpServer(port, reactContext)
                server?.start()
            }
            promise.resolve("Server started on port $port")
        } catch (e: Exception) {
            promise.reject("SERVER_ERROR", e.message)
        }
    }

    @ReactMethod
    fun stopLocalServer(promise: Promise) {
        if (server != null) {
            server?.stop()
            server = null
        }
        promise.resolve("Server stopped")
    }

    @ReactMethod
    fun checkAccessibilityPermission(promise: Promise) {
        // Here you would optimally add logic checking Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        val isEnabled = SaiAccessibilityService.instance != null
        promise.resolve(isEnabled)
    }

    @ReactMethod
    fun openAccessibilitySettings() {
        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        reactContext.startActivity(intent)
    }
}
