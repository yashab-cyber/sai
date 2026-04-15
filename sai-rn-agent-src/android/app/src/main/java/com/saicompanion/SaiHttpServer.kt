package com.saicompanion

import com.facebook.react.bridge.ReactApplicationContext
import fi.iki.elonen.NanoHTTPD
import org.json.JSONObject
import org.json.JSONException

class SaiHttpServer(port: Int, private val reactContext: ReactApplicationContext) : NanoHTTPD(port) {

    override fun serve(session: IHTTPSession): Response {
        val uri = session.uri
        val method = session.method

        try {
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
                        "{\"status\":\"${if (success) "success" else "error"}\"}"
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
                        "{\"status\":\"${if (success) "success" else "error"}\"}"
                    )
                }
            }

            if (method == Method.GET && uri == "/state/screen_text") {
                val text = SaiAccessibilityService.instance?.getScreenText() ?: ""
                val responseJson = JSONObject().apply {
                    put("status", "success")
                    put("data", text)
                }
                return newFixedLengthResponse(Response.Status.OK, "application/json", responseJson.toString())
            }

        } catch (e: Exception) {
            e.printStackTrace()
            return newFixedLengthResponse(Response.Status.INTERNAL_ERROR, "application/json", "{\"status\":\"error\", \"message\":\"${e.message}\"}")
        }

        return newFixedLengthResponse(Response.Status.NOT_FOUND, "application/json", "{\"status\":\"error\", \"message\":\"endpoint not found\"}")
    }
}
