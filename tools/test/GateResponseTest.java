import ru.smartsystem39.gates.GateResponse;
import ru.smartsystem39.gates.Http;

/** Проверка ответов моста без сетевого доступа. */
public class GateResponseTest {
    private static void check(boolean value, String name) {
        if (!value) throw new AssertionError(name);
        System.out.println("PASS " + name);
    }
    private static Http.Response response(int code, String body, String error) {
        Http.Response r = new Http.Response();
        r.code = code;
        r.body = body;
        r.error = error;
        return r;
    }
    public static void main(String[] args) {
        check(GateResponse.commandError(response(200, "{\"ok\":true}", null)) == null, "bridge confirmed");
        check(GateResponse.commandError(response(200, "{\"ok\":false,\"failed\":[1]}", null)) != null, "partial failure");
        check(GateResponse.commandError(response(200, "{\"ok\":false,\"error\":\"not calibrated\"}", null)).contains("not calibrated"), "bridge error");
        check(GateResponse.commandError(response(200, "{}", null)) != null, "missing confirmation");
        check(GateResponse.commandError(response(200, "not json", null)) != null, "invalid response");
        check(GateResponse.commandError(response(0, "", "Таймаут соединения")) != null, "timeout uncertain");
        check(GateResponse.commandError(response(403, "", null)) != null, "HTTP error");
    }
}
