import ru.smartsystem39.gates.Device;
import ru.smartsystem39.gates.DirectClient;
import ru.smartsystem39.gates.HaClient;
import ru.smartsystem39.gates.Status;
import ru.smartsystem39.gates.UpdateChecker;

import java.io.File;

import java.util.List;

/** JVM-проверка прямой интеграции на мок-контроллерах и чтения HA. */
public class ProtoTest {
    private static final String BASE = "http://127.0.0.1:18080";
    private static int failures = 0;

    public static void main(String[] args) throws Exception {
        testTasmota();
        testShelly1();
        testShelly2();
        testCustom();
        testNormalize();
        testJson();
        testUpdate();
        testHaService();
        testHa(args);

        if (failures > 0) {
            System.out.println("FAILURES: " + failures);
            System.exit(1);
        }
        System.out.println("ALL TESTS PASSED");
    }

    private static void testTasmota() {
        Device d = dev(Device.TYPE_BARRIER, Device.P_TASMOTA);
        Status s = DirectClient.status(d, false);
        check("tasmota initial OFF", s.kind == Status.OFF, s.text);

        DirectClient.Result r = DirectClient.toggle(d, false);
        check("tasmota toggle", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("tasmota ON after toggle", s.kind == Status.ON, s.text);

        d.pulse = true;
        r = DirectClient.toggle(d, false);
        check("tasmota pulse", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("tasmota OFF after pulse", s.kind == Status.OFF, s.text);

        d = dev(Device.TYPE_WIDE, Device.P_TASMOTA);
        d.channel = 1;
        d.pulse = false;
        r = DirectClient.toggle(d, false);
        check("tasmota channel 2 toggle", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("tasmota channel 2 ON", s.kind == Status.ON, s.text);
    }

    private static void testShelly1() throws Exception {
        Device d = dev(Device.TYPE_GATE, Device.P_SHELLY1);
        Status s = DirectClient.status(d, false);
        check("shelly1 initial OFF", s.kind == Status.OFF, s.text);

        DirectClient.Result r = DirectClient.toggle(d, false);
        check("shelly1 toggle", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("shelly1 ON", s.kind == Status.ON, s.text);

        r = DirectClient.toggle(d, false);
        check("shelly1 toggle back", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("shelly1 OFF", s.kind == Status.OFF, s.text);

        d.pulse = true;
        r = DirectClient.toggle(d, false);
        check("shelly1 pulse", r.ok, r.error);
        Thread.sleep(1300);
        s = DirectClient.status(d, false);
        check("shelly1 OFF after pulse", s.kind == Status.OFF, s.text);
    }

    private static void testShelly2() throws Exception {
        Device d = dev(Device.TYPE_RELAY, Device.P_SHELLY2);
        Status s = DirectClient.status(d, false);
        check("shelly2 initial OFF", s.kind == Status.OFF, s.text);

        DirectClient.Result r = DirectClient.toggle(d, false);
        check("shelly2 toggle", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("shelly2 ON", s.kind == Status.ON, s.text);

        d.pulse = true;
        r = DirectClient.toggle(d, false);
        check("shelly2 pulse", r.ok, r.error);
        Thread.sleep(1300);
        s = DirectClient.status(d, false);
        check("shelly2 OFF after pulse", s.kind == Status.OFF, s.text);
    }

    private static void testCustom() {
        Device d = dev(Device.TYPE_BARRIER, Device.P_CUSTOM);
        d.address = BASE + "/custom";
        d.openUrl = "open";
        d.closeUrl = "close";
        d.statusUrl = "status";
        d.statusField = "state";
        d.onValue = "OPEN";

        Status s = DirectClient.status(d, false);
        check("custom initial OFF", s.kind == Status.OFF, s.text);

        DirectClient.Result r = DirectClient.toggle(d, false);
        check("custom open", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("custom ON after open", s.kind == Status.ON, s.text);

        r = DirectClient.toggle(d, false);
        check("custom close", r.ok, r.error);
        s = DirectClient.status(d, false);
        check("custom OFF after close", s.kind == Status.OFF, s.text);
    }

    private static void testUpdate() {
        UpdateChecker.Info older = UpdateChecker.check("0.9");
        check("update found for 0.9",
                older.error == null && older.newer && older.apkUrl.endsWith(".apk"),
                older.error + " tag=" + older.tag);
        String current_version = System.getenv("VOROTA_VERSION");
        if (current_version == null || current_version.isEmpty()) current_version = "2.3";
        UpdateChecker.Info current = UpdateChecker.check(current_version);
        check("no update for current " + current_version,
                current.error == null && !current.newer,
                current.error + " tag=" + current.tag);
        if (older.error == null && !older.apkUrl.isEmpty()) {
            try {
                File tmp = File.createTempFile("vorota-update", ".apk");
                String err = UpdateChecker.download(older.apkUrl, tmp);
                check("update APK downloaded", err == null && tmp.length() > 100_000,
                        err + " size=" + tmp.length());
                tmp.delete();
            } catch (Exception e) {
                check("update APK downloaded", false, e.toString());
            }
        }
    }

    private static void testJson() {
        Device d = new Device("id-1", "Калитка", Device.TYPE_GATE);
        d.source = Device.SRC_HTTP;
        d.protocol = Device.P_SHELLY2;
        d.address = "http://192.168.1.50";
        d.channel = 1;
        d.pulse = false;
        d.objectId = "gate";
        d.openUrl = "http://192.168.1.50/open";
        d.statusField = "state";
        d.onValue = "OPEN";
        d.favorite = true;

        Device e = Device.fromJson(d.toJson());
        boolean ok = e.id.equals(d.id) && e.name.equals(d.name) && e.type.equals(d.type)
                && e.source.equals(d.source) && e.protocol.equals(d.protocol)
                && e.address.equals(d.address) && e.channel == d.channel
                && e.pulse == d.pulse && e.objectId.equals(d.objectId)
                && e.openUrl.equals(d.openUrl) && e.statusField.equals(d.statusField)
                && e.onValue.equals(d.onValue) && e.favorite == d.favorite;
        check("device json roundtrip", ok, "fields differ");
        check("device configured", e.isConfigured(), "must be configured");
    }

    private static void testHaService() {
        HaClient ha = new HaClient(BASE + "/mockha", "test-token", false);
        HaClient.Result<String> r = ha.callService("cover", "open_cover", "cover.gate");
        check("HA service POST", r.error == null, r.error);

        HaClient bad = new HaClient(BASE + "/mockha", "bad-token", false);
        HaClient.Result<String> rb = bad.callService("cover", "open_cover", "cover.gate");
        check("HA service rejects bad token", rb.error != null, "unexpected ok");
    }

    private static void testNormalize() {
        check("normalize adds scheme",
                "http://192.168.2.39:8123".equals(HaClient.normalizeBase("192.168.2.39:8123/")),
                HaClient.normalizeBase("192.168.2.39:8123/"));
    }

    private static void testHa(String[] args) {
        if (args.length < 2) {
            System.out.println("skip HA tests (no url/token)");
            return;
        }
        HaClient ha = new HaClient(args[0], args[1], false);
        HaClient.Result<List<HaClient.State>> r = ha.states();
        check("HA states loaded", r.error == null && r.value != null && r.value.size() > 10,
                r.error + " n=" + (r.value == null ? 0 : r.value.size()));
        if (r.error == null) {
            boolean found = false;
            for (HaClient.State s : r.value) {
                if ("script.answer_incoming_call".equals(s.id) && !s.name.isEmpty()) found = true;
            }
            check("HA friendly_name parsed", found, "script.answer_incoming_call");
            System.out.println("HA states: " + r.value.size());
        }

        HaClient bad = new HaClient(args[0], "definitely-wrong-token", false);
        HaClient.Result<List<HaClient.State>> rb = bad.states();
        check("HA wrong token -> 401", rb.error != null && rb.error.contains("401"), rb.error);
    }

    private static Device dev(String type, String protocol) {
        Device d = new Device("test-" + protocol, "test", type);
        d.source = Device.SRC_HTTP;
        d.protocol = protocol;
        d.address = BASE + "/" + protocol;
        d.pulse = false;
        return d;
    }

    private static void check(String name, boolean ok, String detail) {
        if (ok) {
            System.out.println("PASS " + name);
        } else {
            failures++;
            System.out.println("FAIL " + name + " :: " + detail);
        }
    }
}
