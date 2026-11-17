package ru.smartsystem39.gates;

import org.json.JSONObject;

/** Мост может ответить HTTP 200 даже при частичном отказе. */
public final class GateResponse {
    private GateResponse() {}

    /** null означает подтверждение мостом; ошибка связи не доказывает, что команда не выполнена. */
    public static String commandError(Http.Response response) {
        if (!response.ok()) {
            return "Нет подтверждения команды: " +
                    (response.error == null ? "HTTP " + response.code : response.error);
        }
        try {
            JSONObject body = new JSONObject(response.body);
            if (!body.has("ok") || !body.getBoolean("ok")) {
                return "Мост не подтвердил команду: " + body.optString("error", "возможен частичный отказ");
            }
            return null;
        } catch (Exception e) {
            return "Некорректный ответ моста: результат неизвестен";
        }
    }
}
