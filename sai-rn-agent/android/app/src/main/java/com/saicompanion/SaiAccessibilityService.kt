package com.saicompanion

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

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
}
