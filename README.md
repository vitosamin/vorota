# Ворота

Android-пульт для шлагбаума, калитки и ворот: крупные карточки, живой статус,
настройка подключения внутри приложения.

Собрано без Gradle — Java и штатные View, только `android.jar` из SDK
(см. `build.sh`). minSdk 26 (Android 8.0), targetSdk 34.

## Что умеет

- **Два источника на каждое устройство:**
  - **Home Assistant** — REST API (`GET /api/states`, `POST /api/services/...`).
    Сущности `cover`, `switch`, `input_boolean`, `button`, `script`, `lock`, `light`.
    Состояние обновляется каждые 5 секунд; у `cover` видно «открывается/закрывается»,
    во время движения кнопка превращается в «стоп».
  - **Напрямую по HTTP** — Tasmota, Shelly Gen1, Shelly Gen2 (Plus/Pro),
    ESPHome `web_server`, произвольные URL (открытие / закрытие / статус).
- Типы карточек: шлагбаум, калитка, ворота, реле.
- Импульс для реле в прямом режиме (включить → пауза → выключить).
- Проверка связи с HA и выбор сущностей из списка с поиском.
- Тёмное оформление, статусы цветом: открыто / закрыто / движется / нет связи.
- Токен HA не зашит в APK — вводится в настройках и хранится в приватных prefs.

## Сборка

```bash
./build.sh
```

APK: `dist/Vorota-1.0.apk`. Нужны JDK 17 и Android SDK из
`/home/dsh/projects/tools` (пути уже прописаны в `build.sh`).

## Установка

1. Скопировать APK на телефон и разрешить установку из неизвестных источников.
2. Открыть приложение → вкладка «Настройки».

## Настройка Home Assistant

1. В HA: профиль → Безопасность → Долгоживущие токены → Создать токен.
2. В приложении: адрес (`http://192.168.2.39:8123` или ваш `https://…`) и токен,
   затем «Проверить связь».
3. «+ Добавить устройство» → имя, тип, источник «Home Assistant» →
   «Выбрать из Home Assistant».

Для `cover` нажатие открывает или закрывает ворота, во время движения —
останавливает. Для `switch`/`input_boolean` — переключает, `button` — нажимает,
`script` — запускает.

## Прямое подключение

| Протокол | Команда | Статус |
|---|---|---|
| Tasmota | `Power TOGGLE` (канал → `Power1`, `Power2`…) | `Power` |
| Shelly Gen1 | `/relay/<ch>?turn=toggle` | `/status` |
| Shelly Gen2 | `/rpc/Switch.Toggle?id=<ch>` | `/rpc/Shelly.GetStatus` |
| ESPHome | `POST /switch/<id>/toggle` | не читается (показывает «Готов») |
| Свой HTTP | URL открытия / закрытия | URL статуса + JSON-поле |

Импульс: Tasmota — `ON`, пауза, `OFF`; Shelly — `timer=1` / `toggle_after=1`;
ESPHome — `turn_on`, пауза, `turn_off`.

## Обновления

Приложение само проверяет последний релиз
`github.com/vitosamin/vorota/releases/latest` (при запуске и по кнопке
«Настройки → Обновления»). Если версия новее — предлагает скачать APK и
открывает системный установщик. Первый раз APK ставится вручную, дальше —
поверх, подпись сохраняется.

Релизы: https://github.com/vitosamin/vorota/releases

## Проверка

`tools/test/` — JVM-тесты на мок-контроллерах (`mock_controllers.py`) плюс
чтение реального HA (только `GET /api/states`, без команд). Команда запуска —
в `STATE.md`.

## Состав

```
AndroidManifest.xml        манифест (пакет ru.smartsystem39.gates)
build.sh                   aapt2 → javac → d8 → zipalign → apksigner
app/src/main/java/...      MainActivity, DeviceEditActivity, Config, HaClient,
                           DirectClient, Http, Device, Status, Ui
app/src/main/res/...       layout, drawable, values, mipmap
tools/gen_icons.py         растровые иконки
tools/test/                мок-контроллеры и JVM-проверки
dist/                      готовый APK
```
