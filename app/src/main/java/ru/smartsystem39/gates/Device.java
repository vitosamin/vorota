package ru.smartsystem39.gates;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.UUID;

/** Описание устройства: сущность Home Assistant либо прямой HTTP-контроллер. */
public class Device {
    public static final String SRC_HA = "ha";
    public static final String SRC_HTTP = "http";

    public static final String TYPE_BARRIER = "barrier";
    public static final String TYPE_GATE = "gate";
    public static final String TYPE_WIDE = "wide";
    public static final String TYPE_RELAY = "relay";

    public static final String P_TASMOTA = "tasmota";
    public static final String P_SHELLY1 = "shelly1";
    public static final String P_SHELLY2 = "shelly2";
    public static final String P_ESPHOME = "esphome";
    public static final String P_CUSTOM = "custom";

    public String id = "";
    public String name = "";
    public String type = TYPE_BARRIER;
    public String source = SRC_HA;

    // Home Assistant
    public String entity = "";

    // Прямое подключение
    public String protocol = P_TASMOTA;
    public String address = "";
    public int channel = 0;
    public boolean pulse = true;
    public String objectId = "";
    public String openUrl = "";
    public String closeUrl = "";
    public String statusUrl = "";
    public String statusField = "";
    public String onValue = "ON";
    public boolean favorite = false;

    // Дверь Gate-IP (мост): id устройства и доступные направления
    public String gateId = "";
    public String gateToken = "";
    public boolean dirIn = false;
    public boolean dirOut = false;

    public Device() {}

    public Device(String id, String name, String type) {
        this.id = id;
        this.name = name;
        this.type = type;
    }

    public boolean isGate() {
        return gateId != null && !gateId.isEmpty();
    }

    public boolean isConfigured() {
        if (SRC_HA.equals(source)) {
            return entity != null && !entity.trim().isEmpty();
        }
        return address != null && !address.trim().isEmpty();
    }

    public static String typeLabel(String type) {
        if (TYPE_GATE.equals(type)) return "Калитка";
        if (TYPE_WIDE.equals(type)) return "Ворота";
        if (TYPE_RELAY.equals(type)) return "Реле";
        return "Шлагбаум";
    }

    public static int typeIcon(String type) {
        if (TYPE_GATE.equals(type)) return R.drawable.ic_door_closed;
        if (TYPE_WIDE.equals(type)) return R.drawable.ic_door_open;
        if (TYPE_RELAY.equals(type)) return R.drawable.ic_power;
        return R.drawable.ic_fence;
    }

    /** Цвет плашки устройства: у каждого типа свой, как у значков в настройках iOS. */
    public static int typeColor(String type) {
        if (TYPE_GATE.equals(type)) return R.color.type_gate;
        if (TYPE_WIDE.equals(type)) return R.color.type_wide;
        if (TYPE_RELAY.equals(type)) return R.color.type_relay;
        return R.color.type_barrier;
    }

    public static String protocolLabel(String protocol) {
        if (P_SHELLY1.equals(protocol)) return "Shelly Gen1";
        if (P_SHELLY2.equals(protocol)) return "Shelly Gen2";
        if (P_ESPHOME.equals(protocol)) return "ESPHome";
        if (P_CUSTOM.equals(protocol)) return "Свой HTTP";
        return "Tasmota";
    }

    public JSONObject toJson() {
        JSONObject o = new JSONObject();
        try {
            o.put("id", id);
            o.put("name", name);
            o.put("type", type);
            o.put("source", source);
            o.put("entity", entity);
            o.put("protocol", protocol);
            o.put("address", address);
            o.put("channel", channel);
            o.put("pulse", pulse);
            o.put("objectId", objectId);
            o.put("openUrl", openUrl);
            o.put("closeUrl", closeUrl);
            o.put("statusUrl", statusUrl);
            o.put("statusField", statusField);
            o.put("onValue", onValue);
            o.put("favorite", favorite);
            o.put("gateId", gateId);
            o.put("gateToken", gateToken);
            o.put("dirIn", dirIn);
            o.put("dirOut", dirOut);
        } catch (JSONException ignored) {
        }
        return o;
    }

    public static Device fromJson(JSONObject o) {
        Device d = new Device();
        d.id = o.optString("id", "");
        d.name = o.optString("name", "");
        d.type = o.optString("type", TYPE_BARRIER);
        d.source = o.optString("source", SRC_HA);
        d.entity = o.optString("entity", "");
        d.protocol = o.optString("protocol", P_TASMOTA);
        d.address = o.optString("address", "");
        d.channel = o.optInt("channel", 0);
        d.pulse = o.optBoolean("pulse", true);
        d.objectId = o.optString("objectId", "");
        d.openUrl = o.optString("openUrl", "");
        d.closeUrl = o.optString("closeUrl", "");
        d.statusUrl = o.optString("statusUrl", "");
        d.statusField = o.optString("statusField", "");
        d.onValue = o.optString("onValue", "ON");
        d.favorite = o.optBoolean("favorite", false);
        d.gateId = o.optString("gateId", "");
        d.gateToken = o.optString("gateToken", "");
        d.dirIn = o.optBoolean("dirIn", false);
        d.dirOut = o.optBoolean("dirOut", false);
        if (d.onValue.isEmpty()) d.onValue = "ON";
        if (d.id.isEmpty()) d.id = newId();
        return d;
    }

    public static String newId() {
        return UUID.randomUUID().toString();
    }
}
