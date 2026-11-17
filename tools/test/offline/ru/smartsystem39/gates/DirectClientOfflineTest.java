package ru.smartsystem39.gates;

import java.util.Arrays;

/** Изолированные JVM-проверки: используется только подставной Http. */
public final class DirectClientOfflineTest {
    private static final String BASE = "http://controller/base";
    private static int checks;

    public static void main(String[] args) {
        testEditorUrls();
        testToggle();
        testUnknownStatus();
        testPulse();
        testOtherPulse();
        System.out.println("ALL " + checks + " CHECKS PASSED");
    }

    private static void testEditorUrls() {
        String[] inputs = {"  /open/?x=1  ", " open/ ", " https://example.test/path/?q=x/ ", " ", null};
        String[] expected = {"/open/?x=1", "open/", "https://example.test/path/?q=x/", "", ""};
        for (int i = 0; i < inputs.length; i++) {
            eq(expected[i], DeviceEditActivity.commandUrl(inputs[i]), "editor preserves command URL " + i);
        }
        Device d = device();
        d.openUrl = DeviceEditActivity.commandUrl(" /open/?x=1 ");
        d.closeUrl = DeviceEditActivity.commandUrl("close/");
        d.statusUrl = DeviceEditActivity.commandUrl("https://example.test/status/");
        Device restored = Device.fromJson(d.toJson());
        eq(d.openUrl, restored.openUrl, "open JSON roundtrip");
        eq(d.closeUrl, restored.closeUrl, "close JSON roundtrip");
        eq(d.statusUrl, restored.statusUrl, "status JSON roundtrip");
    }

    private static void testToggle() {
        Device d = device();
        // У старых custom-устройств pulse=true, несмотря на настройку переключения.
        d.pulse = true;
        for (String[] pair : new String[][] {{"ON", "OFF"}, {"OPEN", "CLOSED"},
                {"TRUE", "FALSE"}, {"1", "0"}, {"YES", "NO"}, {"ENABLED", "DISABLED"}, {"OFF", "ON"}}) {
            d.onValue = pair[0];
            prepareStatus("{\"state\":\"" + pair[1] + "\"}");
            ok(DirectClient.toggle(d, false).ok, "known OFF opens: " + Arrays.toString(pair));
            requests("GET " + BASE + "/status", "GET " + BASE + "/open/?x=1");
            prepareStatus("{\"state\":\"" + pair[0].toLowerCase() + "\"}");
            ok(DirectClient.toggle(d, false).ok, "known ON closes: " + Arrays.toString(pair));
            requests("GET " + BASE + "/status", "GET http://other.test/close/");
        }
        d.onValue = "TRUE";
        prepareStatus("{\"state\":false}");
        ok(DirectClient.toggle(d, false).ok, "JSON boolean OFF opens");
        requests("GET " + BASE + "/status", "GET " + BASE + "/open/?x=1");
        d.onValue = "1";
        prepareStatus("{\"state\":0}");
        ok(DirectClient.toggle(d, false).ok, "JSON number OFF opens");
        requests("GET " + BASE + "/status", "GET " + BASE + "/open/?x=1");
        d.statusField = "relays.0.state";
        d.onValue = "ON";
        prepareStatus("{\"relays\":[{\"state\":\"OFF\"}]}");
        ok(DirectClient.toggle(d, false).ok, "nested array status");
        requests("GET " + BASE + "/status", "GET " + BASE + "/open/?x=1");
        d.statusField = "state";
        d.onValue = "CUSTOM";
        prepareStatus("{\"state\":\"CUSTOM\"}");
        ok(DirectClient.toggle(d, false).ok, "custom ON closes");
        requests("GET " + BASE + "/status", "GET http://other.test/close/");
    }

    private static void testUnknownStatus() {
        Device d = device();
        for (String body : new String[] {"not-json", "{}", "{\"state\":null}",
                "{\"state\":{}}", "{\"state\":[]}", "{\"state\":\"unknown\"}",
                "{\"state\":\"unavailable\"}", "{\"state\":\"garbage\"}", "{\"state\":\"\"}"}) {
            prepareStatus(body);
            ok(!DirectClient.toggle(d, false).ok, "unknown status denied: " + body);
            requests("GET " + BASE + "/status");
        }
        d.onValue = "CUSTOM";
        prepareStatus("{\"state\":\"other\"}");
        ok(!DirectClient.toggle(d, false).ok, "unknown custom OFF denied");
        requests("GET " + BASE + "/status");
        d.onValue = "ON";
        Http.reset();
        Http.reply(BASE + "/status", 503, "", "HTTP 503");
        ok(!DirectClient.toggle(d, false).ok, "HTTP failure denied");
        requests("GET " + BASE + "/status");
        Http.reset();
        Http.reply(BASE + "/status", 0, "", "connection error");
        ok(!DirectClient.toggle(d, false).ok, "connection failure denied");
        requests("GET " + BASE + "/status");
        d.statusField = "";
        prepareStatus("{}");
        ok(!DirectClient.toggle(d, false).ok, "missing field denied");
        requests("GET " + BASE + "/status");
        d.statusField = "state";
        d.statusUrl = "";
        Http.reset();
        ok(!DirectClient.toggle(d, false).ok, "close without status denied");
        requests();
        d.statusUrl = "status";
        d.closeUrl = "";
        prepareStatus("{\"state\":\"OFF\"}");
        ok(DirectClient.toggle(d, false).ok, "status-only OFF opens");
        requests("GET " + BASE + "/status", "GET " + BASE + "/open/?x=1");
        prepareStatus("{\"state\":\"ON\"}");
        ok(!DirectClient.toggle(d, false).ok, "ON without close denied");
        requests("GET " + BASE + "/status");
        d.openUrl = "";
        prepareStatus("{\"state\":\"OFF\"}");
        ok(!DirectClient.toggle(d, false).ok, "OFF without open denied");
        requests("GET " + BASE + "/status");
        d.openUrl = "/open/?x=1";
        d.statusUrl = "https://example.test/status/";
        Http.reset();
        Http.reply("https://example.test/status/", 200, "{\"state\":\"OFF\"}", null);
        Http.reply(BASE + "/open/?x=1", 500, "", "HTTP 500");
        ok(!DirectClient.toggle(d, false).ok, "command failure reported");
        requests("GET https://example.test/status/", "GET " + BASE + "/open/?x=1");
    }

    private static void testPulse() {
        for (boolean flag : new boolean[] {false, true}) {
            Device d = device();
            d.pulse = flag;
            d.closeUrl = "";
            d.statusUrl = "";
            Http.reset();
            Http.reply(BASE + "/open/?x=1", 200, "", null);
            ok(DirectClient.toggle(d, false).ok, "custom pulse works, legacy flag=" + flag);
            requests("GET " + BASE + "/open/?x=1");
        }
    }

    private static void testOtherPulse() {
        Device d = device();
        d.protocol = Device.P_SHELLY1;
        d.pulse = true;
        Http.reset();
        Http.reply(BASE + "/relay/0?turn=on&timer=1", 200, "", null);
        ok(DirectClient.toggle(d, false).ok, "Shelly pulse unchanged");
        requests("GET " + BASE + "/relay/0?turn=on&timer=1");
    }

    private static Device device() {
        Device d = new Device();
        d.protocol = Device.P_CUSTOM;
        d.address = "controller/base/";
        d.openUrl = "/open/?x=1";
        d.closeUrl = "http://other.test/close/";
        d.statusUrl = "status";
        d.statusField = "state";
        d.onValue = "ON";
        return d;
    }

    private static void prepareStatus(String body) {
        Http.reset();
        Http.reply(BASE + "/status", 200, body, null);
        Http.reply(BASE + "/open/?x=1", 200, "", null);
        Http.reply("http://other.test/close/", 200, "", null);
    }

    private static void requests(String... expected) {
        eq(Arrays.asList(expected), Http.requests, "exact requests");
    }
    private static void ok(boolean value, String name) {
        checks++;
        if (!value) throw new AssertionError(name);
    }
    private static void eq(Object expected, Object actual, String name) {
        checks++;
        if (!expected.equals(actual)) throw new AssertionError(name + ": expected " + expected + ", got " + actual);
    }
}
