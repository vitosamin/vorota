package ru.smartsystem39.gates;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Locale;

/**
 * Прямое управление контроллером по HTTP: Tasmota, Shelly Gen1/Gen2,
 * ESPHome web_server и произвольные URL.
 */
public final class DirectClient {

    public static final class Result {
        public final boolean ok;
        public final String error;

        private Result(boolean ok, String error) {
            this.ok = ok;
            this.error = error;
        }

        public static Result ok() {
            return new Result(true, null);
        }

        public static Result err(String error) {
            return new Result(false, error);
        }
    }

    private DirectClient() {}

    public static String base(String address) {
        String b = address == null ? "" : address.trim();
        if (b.isEmpty()) return "";
        if (!b.startsWith("http://") && !b.startsWith("https://")) b = "http://" + b;
        while (b.endsWith("/")) b = b.substring(0, b.length() - 1);
        return b;
    }

    private static int channel(Device d) {
        return Math.max(0, d.channel);
    }

    public static Status status(Device d, boolean insecure) {
        String base = base(d.address);
        if (base.isEmpty()) return new Status(Status.OFFLINE, "Не настроено");
        try {
            switch (d.protocol) {
                case Device.P_TASMOTA: {
                    String cmd = powerCmd(d);
                    Http.Response r = Http.get(base + "/cm?cmnd=" + cmd, null, insecure);
                    if (!r.ok()) return offline(r);
                    JSONObject o = new JSONObject(r.body);
                    String v = o.optString(cmd, "");
                    if ("ON".equalsIgnoreCase(v)) return new Status(Status.ON, "Включено");
                    if ("OFF".equalsIgnoreCase(v)) return new Status(Status.OFF, "Выключено");
                    return new Status(Status.UNKNOWN, "Нет данных");
                }
                case Device.P_SHELLY1: {
                    Http.Response r = Http.get(base + "/status", null, insecure);
                    if (!r.ok()) return offline(r);
                    JSONArray relays = new JSONObject(r.body).optJSONArray("relays");
                    if (relays == null || relays.length() <= channel(d)) return new Status(Status.UNKNOWN, "Нет данных");
                    boolean on = relays.getJSONObject(channel(d)).optBoolean("ison", false);
                    return new Status(on ? Status.ON : Status.OFF, on ? "Включено" : "Выключено");
                }
                case Device.P_SHELLY2: {
                    Http.Response r = Http.get(base + "/rpc/Shelly.GetStatus", null, insecure);
                    if (!r.ok()) return offline(r);
                    JSONObject sw = new JSONObject(r.body).optJSONObject("switch:" + channel(d));
                    if (sw == null) return new Status(Status.UNKNOWN, "Нет данных");
                    boolean on = sw.optBoolean("output", false);
                    return new Status(on ? Status.ON : Status.OFF, on ? "Включено" : "Выключено");
                }
                case Device.P_ESPHOME:
                    return new Status(Status.READY, "Готов");
                case Device.P_CUSTOM:
                    return customStatus(d, base, insecure);
                default:
                    return new Status(Status.UNKNOWN, "Нет данных");
            }
        } catch (Exception e) {
            return new Status(Status.OFFLINE, "Нет связи");
        }
    }

    public static Result toggle(Device d, boolean insecure) {
        String base = base(d.address);
        if (base.isEmpty()) return Result.err("Не настроено");
        try {
            switch (d.protocol) {
                case Device.P_TASMOTA: {
                    String cmd = powerCmd(d);
                    if (d.pulse) {
                        Result on = hit(base + "/cm?cmnd=" + cmd + "%20ON", insecure);
                        if (!on.ok) return on;
                        sleep(900);
                        return hit(base + "/cm?cmnd=" + cmd + "%20OFF", insecure);
                    }
                    return hit(base + "/cm?cmnd=" + cmd + "%20TOGGLE", insecure);
                }
                case Device.P_SHELLY1: {
                    int ch = channel(d);
                    if (d.pulse) return hit(base + "/relay/" + ch + "?turn=on&timer=1", insecure);
                    return hit(base + "/relay/" + ch + "?turn=toggle", insecure);
                }
                case Device.P_SHELLY2: {
                    int ch = channel(d);
                    if (d.pulse) return hit(base + "/rpc/Switch.Set?id=" + ch + "&on=true&toggle_after=1", insecure);
                    return hit(base + "/rpc/Switch.Toggle?id=" + ch, insecure);
                }
                case Device.P_ESPHOME: {
                    String id = d.objectId == null ? "" : d.objectId.trim();
                    if (id.isEmpty()) return Result.err("Не указан ID ESPHome");
                    if (d.pulse) {
                        Result on = post(base + "/switch/" + id + "/turn_on", insecure);
                        if (!on.ok) return on;
                        sleep(900);
                        return post(base + "/switch/" + id + "/turn_off", insecure);
                    }
                    return post(base + "/switch/" + id + "/toggle", insecure);
                }
                case Device.P_CUSTOM:
                    return customToggle(d, base, insecure);
                default:
                    return Result.err("Неизвестный протокол");
            }
        } catch (Exception e) {
            return Result.err(message(e));
        }
    }

    private static Result customToggle(Device d, String base, boolean insecure) {
        Status st = customStatus(d, base, insecure);
        String url;
        if (st.kind == Status.ON && !d.closeUrl.isEmpty()) {
            url = urlJoin(base, d.closeUrl);
        } else {
            url = urlJoin(base, d.openUrl);
        }
        if (url.isEmpty()) return Result.err("Не указан URL команды");
        return hit(url, insecure);
    }

    private static Status customStatus(Device d, String base, boolean insecure) {
        String statusUrl = urlJoin(base, d.statusUrl);
        if (statusUrl.isEmpty()) return new Status(Status.READY, "Готов");
        Http.Response r = Http.get(statusUrl, null, insecure);
        if (!r.ok()) return offline(r);
        if (d.statusField == null || d.statusField.trim().isEmpty()) {
            return new Status(Status.READY, "Готов");
        }
        String value = jsonPath(r.body, d.statusField.trim());
        if (value == null) return new Status(Status.UNKNOWN, "Нет данных");
        String on = d.onValue == null || d.onValue.trim().isEmpty() ? "ON" : d.onValue.trim();
        if (value.trim().equalsIgnoreCase(on)) return new Status(Status.ON, "Включено");
        return new Status(Status.OFF, "Выключено");
    }

    private static String urlJoin(String base, String path) {
        String p = path == null ? "" : path.trim();
        if (p.isEmpty()) return "";
        if (p.startsWith("http://") || p.startsWith("https://")) return p;
        return base + (p.startsWith("/") ? "" : "/") + p;
    }

    private static String powerCmd(Device d) {
        return d.channel <= 0 ? "Power" : "Power" + (d.channel + 1);
    }

    private static Result hit(String url, boolean insecure) {
        Http.Response r = Http.get(url, null, insecure);
        if (!r.ok()) return Result.err(errorText(r));
        return Result.ok();
    }

    private static Result post(String url, boolean insecure) {
        Http.Response r = Http.post(url, null, "", insecure);
        if (!r.ok()) return Result.err(errorText(r));
        return Result.ok();
    }

    private static Status offline(Http.Response r) {
        return new Status(Status.OFFLINE, r.code == 0 ? "Нет связи" : "HTTP " + r.code);
    }

    private static String errorText(Http.Response r) {
        if (r.error != null) return r.error;
        return "HTTP " + r.code;
    }

    private static String message(Exception e) {
        String m = e.getMessage();
        return m == null || m.trim().isEmpty() ? e.getClass().getSimpleName() : m;
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    /** Достаёт значение из JSON по пути вида "relays.0.ison" или "POWER". */
    static String jsonPath(String body, String path) {
        try {
            Object cur = new JSONObject(body);
            for (String part : path.split("\\.")) {
                if (cur instanceof JSONObject) {
                    cur = ((JSONObject) cur).opt(part);
                } else if (cur instanceof JSONArray) {
                    int idx = Integer.parseInt(part);
                    JSONArray arr = (JSONArray) cur;
                    cur = idx >= 0 && idx < arr.length() ? arr.opt(idx) : null;
                } else {
                    return null;
                }
                if (cur == null) return null;
            }
            return String.valueOf(cur);
        } catch (Exception e) {
            return null;
        }
    }

    static String lower(String s) {
        return s == null ? "" : s.toLowerCase(Locale.ROOT);
    }
}
