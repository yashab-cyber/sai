package com.saicompanion;

import java.io.IOException;
import java.util.Map;
import nanohttpd.protocols.http.IHTTPSession;
import nanohttpd.protocols.http.response.Response;
import nanohttpd.protocols.http.response.Status;
import nanohttpd.protocols.http.NanoHTTPD;
import com.facebook.react.bridge.ReactApplicationContext;

public class SaiHttpServer extends NanoHTTPD {
    private final ReactApplicationContext context;

    public SaiHttpServer(int port, ReactApplicationContext context) {
        super(port);
        this.context = context;
    }

    @Override
    public Response serve(IHTTPSession session) {
        String uri = session.getUri();
        if (session.getMethod() == Method.POST) {
            if ("/action/tap".equals(uri)) {
                // Call Accessibility Service logic here
                return Response.newFixedLengthResponse(Status.OK, "application/json", "{\"status\":\"success\"}");
            }
        }
        return Response.newFixedLengthResponse(Status.NOT_FOUND, "application/json", "{\"status\":\"error\", \"message\":\"Not found\"}");
    }
}
