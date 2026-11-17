package ru.smartsystem39.gates;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Клиент REST API Home Assistant. */
public final class HaClient {

    public static final class State {
        public final String id;
        public final String name;
        public final String state;

        public State(String id, String name, String state) {
            this.id = id;
            this.name = name;
            this.state = state;
        }
    }

    public static final class Result<T> {
        public final T value;
        public final String error;

        private Result(T value, String error) {
            this.value = value;
            this.error = error;
        }

        public static <T> Result<T> ok(T value) {
            return new Result<>(value, null);
        }

        public static <T> Result<T> err(String error) {
            return new Result<>(null, error);
        }
    }

    private final String base;
    private final String token;
    private final boolean insecure;

    public HaClient(String url, String token, boolean insecure) {
        this.base = normalizeBase(url);
        this.token = token == null ? "" : token.trim();
        this.insecure = insecure;
    }

    public static String normalizeBase(String url) {
        String b = url == null ? "" : url.trim();
        if (b.isEmpty()) return "";
        if (!b.startsWith("http://") && !b.startsWith("https://")) b = "http://" + b;
        while (b.endsWith("/")) b = b.substring(0, b.length() - 1);
        return b;
    }

    public Result<List<State>> states() {
        if (base.isEmpty()) return Result.err("Укажите адрес Home Assistant");
        if (token.isEmpty()) return Result.err("Укажите токен Home Assistant");
        Http.Response r = Http.get(base + "/api/states", token, insecure);
        if (!r.ok()) return Result.err(mapError(r));
        try {
            JSONArray arr = new JSONArray(r.body);
            List<State> out = new ArrayList<>();
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                String id = o.optString("entity_id", "");
                if (id.isEmpty()) continue;
                String state = o.optString("state", "");
                JSONObject attrs = o.optJSONObject("attributes");
                String name = attrs == null ? id : attrs.optString("friendly_name", id);
                out.add(new State(id, name, state));
            }
            return Result.ok(out);
        } catch (Exception e) {
            return Result.err("Некорректный ответ Home Assistant");
        }
    }

    public Result<String> callService(String domain, String service, String entityId) {
        if (base.isEmpty()) return Result.err("Укажите адрес Home Assistant");
        if (token.isEmpty()) return Result.err("Укажите токен Home Assistant");
        try {
            JSONObject body = new JSONObject();
            body.put("entity_id", entityId);
            Http.Response r = Http.post(base + "/api/services/" + domain + "/" + service,
                    token, body.toString(), insecure);
            if (!r.ok()) return Result.err(mapError(r));
            return Result.ok("ok");
        } catch (Exception e) {
            return Result.err(e.getMessage() == null ? "Ошибка запроса" : e.getMessage());
        }
    }

    private String mapError(Http.Response r) {
        if (r.code == 401) return "Токен не принят (401)";
        if (r.code == 404) return "Адрес не найден (404)";
        if (r.error != null) return r.error;
        return "Ошибка " + r.code;
    }
}
