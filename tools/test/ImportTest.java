import org.json.JSONArray;
import org.json.JSONObject;

import ru.smartsystem39.gates.Device;
import ru.smartsystem39.gates.Http;

/** Повторяет разбор /doors моста Gate (v3) — как в MainActivity.importGate. */
public class ImportTest {
    public static void main(String[] args) {
        String base = args.length > 0 ? args[0] : "http://192.168.2.160:8099";
        String token = args.length > 1 ? args[1] : "";
        if (token.isEmpty()) { System.out.println("Укажите ключ доступа вторым аргументом"); System.exit(2); }
        Http.Response r = Http.get(base + "/doors?token=" + java.net.URLEncoder.encode(token), null, false);
        System.out.println("code=" + r.code + " error=" + r.error);
        if (!r.ok()) { System.out.println("FAIL " + r.error); System.exit(1); }
        int doors = 0, readers = 0;
        try {
            JSONArray arr = new JSONObject(r.body).getJSONArray("doors");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                String id = o.optString("id", "");
                String name = o.optString("name", "");
                if (id.isEmpty() || name.isEmpty()) continue;
                boolean in = false, out = false;
                JSONArray rs = o.optJSONArray("readers");
                if (rs != null) {
                    for (int k = 0; k < rs.length(); k++) {
                        String dir = rs.getJSONObject(k).optString("dir", "in");
                        if ("out".equals(dir)) out = true; else in = true;
                        readers++;
                    }
                }
                Device d = new Device(Device.newId(), name, Device.TYPE_WIDE);
                d.source = Device.SRC_HTTP;
                d.protocol = Device.P_CUSTOM;
                d.address = base;
                d.gateId = id;
                d.gateToken = token;
                d.dirIn = in;
                d.dirOut = out;
                Device back = Device.fromJson(d.toJson());
                boolean ok = back.isGate() && back.gateId.equals(id) && back.dirIn == in && back.dirOut == out;
                System.out.println((ok ? "OK  " : "BAD ") + name + " id=" + id + " in=" + in + " out=" + out);
                if (!ok) { System.out.println("FAIL json roundtrip"); System.exit(1); }
                doors++;
            }
        } catch (Exception e) {
            System.out.println("FAIL parse " + e);
            System.exit(1);
        }
        System.out.println("doors=" + doors + " readers=" + readers);
        System.out.println(doors >= 5 ? "IMPORT OK" : "IMPORT TOO FEW DOORS");
    }
}
