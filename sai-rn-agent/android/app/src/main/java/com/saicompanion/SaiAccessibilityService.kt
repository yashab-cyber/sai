package com.saicompanion

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.accessibilityservice.AccessibilityService.TakeScreenshotCallback
import android.accessibilityservice.AccessibilityService.ScreenshotResult
import android.graphics.Bitmap
import android.graphics.Rect
import android.graphics.Path
import android.os.Bundle
import android.os.Build
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.graphics.ColorSpace
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class SaiAccessibilityService : AccessibilityService() {

    companion object {
        var instance: SaiAccessibilityService? = null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Track state, record screen content for the API client, etc.
    }

    override fun onInterrupt() {}

    override fun onDestroy() {
        super.onDestroy()
        instance = null
    }

    // --- Actions called by Local API Server ---

    fun performTap(x: Float, y: Float): Boolean {
        val path = Path().apply { moveTo(x, y) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    fun typeText(text: String): Boolean {
        val node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
        val arguments = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)
    }

    fun getScreenText(node: AccessibilityNodeInfo? = rootInActiveWindow): String {
        if (node == null) return ""
        val sb = StringBuilder()
        if (node.text != null) sb.append(node.text).append("\n")
        if (node.contentDescription != null) sb.append(node.contentDescription).append("\n")
        
        for (i in 0 until node.childCount) {
            sb.append(getScreenText(node.getChild(i)))
        }
        return sb.toString()
    }

    fun getCurrentPackage(): String {
        return rootInActiveWindow?.packageName?.toString() ?: "unknown"
    }

    fun getCurrentActivity(): String {
        return rootInActiveWindow?.className?.toString() ?: "unknown"
    }

    fun getScreenElements(limit: Int = 200): JSONArray {
        val result = JSONArray()

        fun walk(node: AccessibilityNodeInfo?) {
            if (node == null || result.length() >= limit) return

            val text = node.text?.toString()
            val desc = node.contentDescription?.toString()
            if (!text.isNullOrBlank() || !desc.isNullOrBlank()) {
                val bounds = Rect()
                node.getBoundsInScreen(bounds)
                val element = JSONObject().apply {
                    put("text", text ?: desc ?: "")
                    put("type", when {
                        node.className?.toString()?.contains("Button", ignoreCase = true) == true -> "button"
                        node.className?.toString()?.contains("EditText", ignoreCase = true) == true -> "input"
                        else -> "unknown"
                    })
                    put("bounds", JSONArray().apply {
                        put(bounds.left)
                        put(bounds.top)
                        put(bounds.right)
                        put(bounds.bottom)
                    })
                }
                result.put(element)
            }

            for (i in 0 until node.childCount) {
                walk(node.getChild(i))
                if (result.length() >= limit) break
            }
        }

        walk(rootInActiveWindow)
        return result
    }

    fun captureScreenshotBase64(timeoutMs: Long = 2000): String? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            return null
        }

        val latch = CountDownLatch(1)
        var encoded: String? = null

        takeScreenshot(
            Display.DEFAULT_DISPLAY,
            mainExecutor,
            object : TakeScreenshotCallback {
                override fun onSuccess(screenshot: ScreenshotResult) {
                    try {
                        val hardwareBuffer = screenshot.hardwareBuffer
                        val colorSpace = screenshot.colorSpace ?: ColorSpace.get(ColorSpace.Named.SRGB)
                        val bitmap = Bitmap.wrapHardwareBuffer(hardwareBuffer, colorSpace)

                        if (bitmap != null) {
                            val stream = ByteArrayOutputStream()
                            bitmap.compress(Bitmap.CompressFormat.JPEG, 70, stream)
                            encoded = android.util.Base64.encodeToString(stream.toByteArray(), android.util.Base64.NO_WRAP)
                            stream.close()
                            bitmap.recycle()
                        }

                        hardwareBuffer.close()
                    } catch (_: Exception) {
                        encoded = null
                    } finally {
                        latch.countDown()
                    }
                }

                override fun onFailure(errorCode: Int) {
                    encoded = null
                    latch.countDown()
                }
            }
        )

        latch.await(timeoutMs, TimeUnit.MILLISECONDS)
        return encoded
    }
}
