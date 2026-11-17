package ru.smartsystem39.gates;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Настройки приложения: подключение к HA и список устройств. */
public class Config {
    private static final String PREFS = "gates_prefs";
    private static final String K_URL = "ha_url";
    private static final String K_TOKEN = "ha_token";
    private static final String K_INSECURE = "ha_insecure";
    private static final String K_DEVICES = "devices";

    private final SharedPreferences sp;

    public Config(Context context) {
        sp = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public String getHaUrl() {
        return sp.getString(K_URL, "");
    }

    public void setHaUrl(String v) {
        sp.edit().putString(K_URL, v == null ? "" : v).apply();
    }

    public String getHaToken() {
        return sp.getString(K_TOKEN, "");
    }

    public void setHaToken(String v) {
        sp.edit().putString(K_TOKEN, v == null ? "" : v).apply();
    }

    public boolean haInsecure() {
        return sp.getBoolean(K_INSECURE, false);
    }

    public void setHaInsecure(boolean v) {
        sp.edit().putBoolean(K_INSECURE, v).apply();
    }

    public String getGateUrl() {
        return sp.getString("gate_url", "http://192.168.2.160:8099");
    }

    public void setGateUrl(String v) {
        sp.edit().putString("gate_url", v == null ? "" : v).apply();
    }

    public String getGateToken() {
        return sp.getString("gate_token", "vorota-2026");
    }

    public void setGateToken(String v) {
        sp.edit().putString("gate_token", v == null ? "" : v).apply();
    }

    public boolean hasHa() {
        return !getHaUrl().trim().isEmpty() && !getHaToken().trim().isEmpty();
    }

    public String getPromptedUpdate() {
        return sp.getString("prompted_update", "");
    }

    public void setPromptedUpdate(String tag) {
        sp.edit().putString("prompted_update", tag == null ? "" : tag).apply();
    }

    public List<Device> getDevices() {
        List<Device> out = new ArrayList<>();
        String raw = sp.getString(K_DEVICES, null);
        if (raw == null) {
            Device barrier = new Device(Device.newId(), "Шлагбаум", Device.TYPE_BARRIER);
            Device gate = new Device(Device.newId(), "Калитка", Device.TYPE_GATE);
            out.add(barrier);
            out.add(gate);
            saveDevices(out);
            return out;
        }
        try {
            JSONArray arr = new JSONArray(raw);
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o != null) out.add(Device.fromJson(o));
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    public void saveDevices(List<Device> devices) {
        JSONArray arr = new JSONArray();
        for (Device d : devices) arr.put(d.toJson());
        sp.edit().putString(K_DEVICES, arr.toString()).apply();
    }

    public void upsert(Device device) {
        List<Device> list = getDevices();
        boolean replaced = false;
        for (int i = 0; i < list.size(); i++) {
            if (list.get(i).id.equals(device.id)) {
                list.set(i, device);
                replaced = true;
                break;
            }
        }
        if (!replaced) list.add(device);
        saveDevices(list);
    }

    public void delete(String id) {
        List<Device> list = getDevices();
        List<Device> out = new ArrayList<>();
        for (Device d : list) {
            if (!d.id.equals(id)) out.add(d);
        }
        saveDevices(out);
    }
}
