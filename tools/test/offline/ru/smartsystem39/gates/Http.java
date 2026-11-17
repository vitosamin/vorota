package ru.smartsystem39.gates;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Тестовый транспорт: неизвестные запросы запрещены, сеть не используется. */
public final class Http {
    static final List<String> requests = new ArrayList<>();
    static final Map<String, Response> responses = new HashMap<>();

    public static final class Response {
        public int code;
        public String body = "";
        public String error;
        public boolean ok() { return error == null && code >= 200 && code < 300; }
    }

    static void reset() { requests.clear(); responses.clear(); }
    static void reply(String url, int code, String body, String error) {
        Response r = new Response();
        r.code = code;
        r.body = body;
        r.error = error;
        responses.put(url, r);
    }
    public static Response get(String url, String token, boolean insecure) {
        requests.add("GET " + url);
        Response r = responses.get(url);
        if (r == null) throw new AssertionError("Unexpected request: " + url);
        return r;
    }
    public static Response post(String url, String token, String json, boolean insecure) {
        requests.add("POST " + url);
        Response r = responses.get(url);
        if (r == null) throw new AssertionError("Unexpected request: " + url);
        return r;
    }
}
