package com.saicompanion;

import com.facebook.react.bridge.ReactApplicationContext;
import com.facebook.react.bridge.ReactContextBaseJavaModule;
import com.facebook.react.bridge.ReactMethod;
import com.facebook.react.bridge.Promise;
import android.content.Intent;
import android.provider.Settings;

public class SaiDeviceControlModule extends ReactContextBaseJavaModule {
    private final ReactApplicationContext reactContext;
    private SaiHttpServer server;

    public SaiDeviceControlModule(ReactApplicationContext reactContext) {
        super(reactContext);
        this.reactContext = reactContext;
    }

    @Override
    public String getName() {
        return "SaiDeviceControl";
    }

    @ReactMethod
    public void startLocalServer(int port, Promise promise) {
        try {
            if (server == null) {
                server = new SaiHttpServer(port, reactContext);
                server.start();
            }
            promise.resolve("Server started on port " + port);
        } catch (Exception e) {
            promise.reject("SERVER_ERROR", e.getMessage());
        }
    }

    @ReactMethod
    public void stopLocalServer(Promise promise) {
        if (server != null) {
            server.stop();
            server = null;
        }
        promise.resolve("Server stopped");
    }

    @ReactMethod
    public void checkAccessibilityPermission(Promise promise) {
        // Logic to check if Accessibility is enabled
        promise.resolve(true); // Simplified for example
    }

    @ReactMethod
    public void openAccessibilitySettings() {
        Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        reactContext.startActivity(intent);
    }
}
