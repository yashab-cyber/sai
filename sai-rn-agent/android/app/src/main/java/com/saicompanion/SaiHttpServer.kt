package com.saicompanion

import android.content.Intent
import com.facebook.react.bridge.ReactApplicationContext
import fi.iki.elonen.NanoHTTPD
import org.json.JSONObject
import org.json.JSONException
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.max

class SaiHttpServer(
    port: Int,
    private val reactContext: ReactApplicationContext,
    private val apiToken: String,
    private val allowedIps: Set<String> = setOf("127.0.0.1", "::1")
) : NanoHTTPD(port) {

    private val requestTimestamps = ConcurrentHashMap<String, MutableList<Long>>()
    private val rateLimitWindowMs = 60_000L
    private val maxRequestsPerWindow = 120

    private fun isRateLimited(ip: String): Boolean {
        val now = System.currentTimeMillis()
        val timestamps = requestTimestamps.computeIfAbsent(ip) { mutableListOf() }
        synchronized(timestamps) {
            timestamps.removeAll { now - it > rateLimitWindowMs }
            if (timestamps.size >= maxRequestsPerWindow) return true
            timestamps.add(now)
        }
        return false
    }

    private fun isAuthorized(session: IHTTPSession): Boolean {
        val authHeader = session.headers["authorization"] ?: session.headers["Authorization"]
        if (authHeader.isNullOrBlank()) return false
        return authHeader.trim() == "Bearer $apiToken"
    }

    private fun isIpAllowed(session: IHTTPSession): Boolean {
        val remoteIp = session.remoteIpAddress ?: return false
        // Allow localhost always; if whitelist is empty, allow LAN by default.
        if (remoteIp == "127.0.0.1" || remoteIp == "::1") return true
        if (allowedIps.isEmpty()) return true
        return allowedIps.contains(remoteIp)
    }

    private fun buildResponse(
        status: String,
        action: String,
        message: String,
        extra: JSONObject? = null
    ): String {
        val svc = SaiAccessibilityService.instance
        val screenData = JSONObject().apply {
            put("text", svc?.getScreenText() ?: "")
            put("elements", svc?.getScreenElements() ?: org.json.JSONArray())
            put("activity", svc?.getCurrentActivity() ?: "unknown")
            put("package", svc?.getCurrentPackage() ?: "unknown")
        }

        val root = JSONObject().apply {
            put("status", status)
            put("action", action)
            put("message", message)
            put("timestamp", System.currentTimeMillis())
            put("screen_data", screenData)
        }

        if (extra != null) {
            val keys = extra.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                root.put(key, extra.get(key))
            }
        }
        return root.toString()
    }

    private fun openApp(packageName: String): Boolean {
        val launchIntent = reactContext.packageManager.getLaunchIntentForPackage(packageName)
            ?: return false
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        reactContext.startActivity(launchIntent)
        return true
    }

    override fun serve(session: IHTTPSession): Response {
        val uri = session.uri
        val method = session.method

        try {
            if (!isIpAllowed(session)) {
                return newFixedLengthResponse(
                    Response.Status.FORBIDDEN,
                    "application/json",
                    buildResponse("failed", "auth", "IP not allowed")
                )
            }

            if (!isAuthorized(session)) {
                return newFixedLengthResponse(
                    Response.Status.UNAUTHORIZED,
                    "application/json",
                    buildResponse("failed", "auth", "Invalid bearer token")
                )
            }

            if (isRateLimited(session.remoteIpAddress ?: "unknown")) {
                return newFixedLengthResponse(
                    Response.Status.TOO_MANY_REQUESTS,
                    "application/json",
                    buildResponse("failed", "rate_limit", "Rate limit exceeded")
                )
            }

            // ── Health Check Endpoint ──
            // Lightweight ping for SAI to verify the companion is alive.
            if (method == Method.GET && uri == "/health") {
                val svc = SaiAccessibilityService.instance
                val healthJson = JSONObject().apply {
                    put("status", "ok")
                    put("accessibility", svc != null)
                    put("screenshot_ready", svc != null && android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R)
                    put("timestamp", System.currentTimeMillis())
                }
                return newFixedLengthResponse(
                    Response.Status.OK,
                    "application/json",
                    healthJson.toString()
                )
            }

            if (method == Method.POST && uri == "/action/open_app") {
                val map = HashMap<String, String>()
                session.parseBody(map)
                val bodyData = map["postData"]

                if (bodyData != null) {
                    val json = JSONObject(bodyData)
                    val packageName = json.getString("package")

                    val success = openApp(packageName)

                    return newFixedLengthResponse(
                        Response.Status.OK,
                        "application/json",
                        buildResponse(
                            if (success) "success" else "failed",
                            "open_app",
                            if (success) "App opened" else "Failed to open app"
                        )
                    )
                }
            }

            if (method == Method.POST && uri == "/action/tap") {
                val map = HashMap<String, String>()
                session.parseBody(map)
                val bodyData = map["postData"]
                
                if (bodyData != null) {
                    val json = JSONObject(bodyData)
                    val x = json.getDouble("x").toFloat()
                    val y = json.getDouble("y").toFloat()
                    
                    val success = SaiAccessibilityService.instance?.performTap(x, y) ?: false
                    
                    return newFixedLengthResponse(
                        Response.Status.OK, 
                        "application/json", 
                        buildResponse(
                            if (success) "success" else "failed",
                            "tap",
                            if (success) "Tap dispatched" else "Tap failed"
                        )
                    )
                }
            }
            
            if (method == Method.POST && uri == "/action/type") {
                val map = HashMap<String, String>()
                session.parseBody(map)
                val bodyData = map["postData"]
                
                if (bodyData != null) {
                    val json = JSONObject(bodyData)
                    val text = json.getString("text")
                    
                    val success = SaiAccessibilityService.instance?.typeText(text) ?: false
                    
                    return newFixedLengthResponse(
                        Response.Status.OK, 
                        "application/json", 
                        buildResponse(
                            if (success) "success" else "failed",
                            "type",
                            if (success) "Text entered" else "Type failed"
                        )
                    )
                }
            }

            if (method == Method.POST && uri == "/macro/send_message") {
                val map = HashMap<String, String>()
                session.parseBody(map)
                val bodyData = map["postData"]

                if (bodyData != null) {
                    val json = JSONObject(bodyData)
                    val app = json.optString("app", "com.whatsapp")
                    val message = json.optString("message", "")

                    val opened = openApp(app)
                    if (!opened) {
                        return newFixedLengthResponse(
                            Response.Status.OK,
                            "application/json",
                            buildResponse("failed", "send_message", "Unable to open app")
                        )
                    }

                    // Typing into the current focus is best-effort; the accessibility service
                    // can inject the text if the input field is already focused.
                    val typed = SaiAccessibilityService.instance?.typeText(message) ?: false
                    return newFixedLengthResponse(
                        Response.Status.OK,
                        "application/json",
                        buildResponse(
                            if (typed) "success" else "failed",
                            "send_message",
                            if (typed) "Message text entered" else "Unable to type message"
                        )
                    )
                }
            }

            if (method == Method.GET && uri == "/state/screen_text") {
                val text = SaiAccessibilityService.instance?.getScreenText() ?: ""
                val extra = JSONObject().apply { put("data", text) }
                return newFixedLengthResponse(
                    Response.Status.OK,
                    "application/json",
                    buildResponse("success", "screen_text", "Screen text captured", extra)
                )
            }

            if (method == Method.GET && uri == "/state/screenshot") {
                try {
                    val screenshotBase64 = SaiAccessibilityService.instance?.captureScreenshotBase64()
                    if (screenshotBase64.isNullOrBlank()) {
                        val svc = SaiAccessibilityService.instance
                        val reason = when {
                            svc == null -> "ACCESSIBILITY_NOT_RUNNING"
                            android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.R -> "API_LEVEL_TOO_LOW"
                            else -> "SCREENSHOT_CAPTURE_FAILED"
                        }
                        return newFixedLengthResponse(
                            Response.Status.OK,
                            "application/json",
                            buildResponse("failed", "screenshot", reason)
                        )
                    }

                    val extra = JSONObject().apply {
                        put("image_base64", screenshotBase64)
                        put("image_format", "jpeg")
                    }
                    return newFixedLengthResponse(
                        Response.Status.OK,
                        "application/json",
                        buildResponse("success", "screenshot", "Screenshot captured", extra)
                    )
                } catch (e: Exception) {
                    e.printStackTrace()
                    return newFixedLengthResponse(
                        Response.Status.OK,
                        "application/json",
                        buildResponse("failed", "screenshot", "SCREENSHOT_PERMISSION_DENIED: ${e.message ?: "unknown"}")
                    )
                }
            }

        } catch (e: Exception) {
            e.printStackTrace()
            return newFixedLengthResponse(
                Response.Status.INTERNAL_ERROR,
                "application/json",
                buildResponse("failed", "server", e.message ?: "Unhandled server error")
            )
        }

        return newFixedLengthResponse(
            Response.Status.NOT_FOUND,
            "application/json",
            buildResponse("failed", "routing", "Endpoint not found")
        )
    }
}
