# STATE — gates («Ворота»)

> Обновлено: 2026-11-17 09:30 (Europe/Kaliningrad)
> Не git-репозиторий · версия 1.0 (`versionCode 1`), пакет `ru.smartsystem39.gates`

## Что это

Android-пульт для шлагбаума и калитки: Java без Gradle, тёмный UI, две вкладки —
«Устройства» и «Настройки». Для каждого устройства источник выбирается отдельно:
Home Assistant REST либо прямой HTTP (Tasmota / Shelly Gen1/2 / ESPHome / свой).

## Сборка

`./build.sh` → `dist/Vorota-1.0.apk` (aapt2 → javac → d8 → zipalign → apksigner).
Ключ `release.keystore`, пароль в `build.sh`. JDK/SDK — `/home/dsh/projects/tools`.
Проверка подписи: `path/to/apksigner verify dist/Vorota-1.0.apk` (нужен `java` в PATH).

## Сделано (17.11.2026)

- Каркас без Gradle, манифест, адаптивная иконка, тёмная тема, экран пустого списка.
- Главный экран: карточки, статусы, опрос HA раз в 5 с, «стоп» для `cover`,
  быстрое обновление по кнопке.
- Настройки: адрес/токен HA (сохраняются на лету), проверка связи, список устройств,
  добавление/удаление.
- Редактор: имя, тип, источник, выбор сущности HA с поиском, протокол, адрес,
  канал, импульс, поля своего HTTP.
- HA: `/api/states`, `POST /api/services/...`, разбор 401/404, самоподписанный
  HTTPS (галочка «не проверять сертификат»).
- Прямые: Tasmota (в т.ч. каналы 1+), Shelly Gen1, Shelly Gen2, ESPHome,
  custom с JSON-путём статуса.
- JVM-тесты: 30 проверок на мок-контроллерах + реальный HA (221 state, 401) — все PASS.
- Токен в APK не зашит — вводится пользователем.
- Обновления: проверка последнего релиза GitHub, скачивание APK и установка
  через `UpdateProvider` + `REQUEST_INSTALL_PACKAGES`; автопроверка при запуске.
- Репозиторий: https://github.com/vitosamin/vorota (публичный), релизы с APK.

## Следующий шаг

- Установить APK на телефон, ввести адрес/токен HA и выбрать сущности.
- В HA на `192.168.2.39:8123` сущностей «ворота/шлагбаум/калитка» пока нет —
  сначала завести их в HA (cover/switch/script) либо настроить прямой режим.
- Проверить на реальном контроллере; при необходимости добавить протокол
  (например, ESPHome native API для статуса).

## Как прогнать тесты

```bash
JH=/home/dsh/projects/tools/jdk
CP="tools/test/json.jar:/home/dsh/projects/tools/sdk/platforms/android-34/android.jar:build/gen"
$JH/bin/javac -source 8 -target 8 -encoding UTF-8 -cp "$CP" -d tools/test/classes \
  app/src/main/java/ru/smartsystem39/gates/{Http,HaClient,DirectClient,Status,Device}.java \
  build/gen/ru/smartsystem39/gates/R.java tools/test/ProtoTest.java
python3 tools/test/mock_controllers.py &
TOKEN=$(python3 -c "import json;print(json.load(open('/home/dsh/projects/ha/token.json'))['access_token'])")
$JH/bin/java -cp "tools/test/classes:tools/test/json.jar:build/gen" ProtoTest http://192.168.2.39:8123 "$TOKEN"
```

## Грабли и решения

- `apksigner` требует `java` в PATH — `build.sh` экспортирует JDK.
- В JVM-тестах `json.jar` должен идти в classpath **раньше** `android.jar`, иначе
  подхватывается Android-заглушка `org.json` и падает с `Stub!`.
- ESPHome статус не читается (HTML web_server) — карточка показывает «Готов».
- HA `switch` не пульсирует: для реле-импульса — прямой режим или HA-скрипт.
- Песочница: APK собран без Gradle, поэтому новых зависимостей нет.
- `release.keystore` не коммитится (`.gitignore`): без него обновление
  не установится поверх — подпись другая.
- Для установки обновления нужен `REQUEST_INSTALL_PACKAGES` и разрешение
  «Установка неизвестных приложений» для «Ворот».

## СКУД Gate: отчёты и мониторинг (17.11.2026)

Отдельный модуль `reports/` — веб-сервис по журналу СКУД Gate-IP:

- **Адрес:** http://192.168.2.72:8095/ · **вход:** `vitosamin` / `Admin910327`
  (в `gate.config.json` → `auth`; сессия — подписанная cookie 12 ч, есть и Basic).
- **Оформление:** светлая деловая тема в стиле 1С (плотные таблицы, синие
  акценты, без градиентов/неона). Графики — собственный SVG, без CDN.
- **Данные:** SMB-шара `\\192.168.2.160\GATE` → `Server\Events\nГГММДД.mdb`
  (суточный журнал, таблица `Events`) и `Server\config.mdb` (Users/Groups/Devices).
  MDB читаются распакованными mdbtools (`reports/tools/mdbroot`), кэш — SQLite.
- **Что умеет:** лента проходов вживую через SSE (`/api/stream`), «на объекте
  сейчас», KPI дня; вкладка «Аналитика» — 7 графиков (динамика по дням, часы,
  опоздания, время на объекте, тепловая карта день×час, подразделения, топ
  опоздавших); отчёт посещаемости (приход = первый проход, уход = последний;
  опоздание/ранний уход от границ смены), виды «по дням / свод / не приходили»;
  выгрузка CSV для 1С (cp1251, «;»), Excel .xls, печать/PDF.
  Скачивание — через fetch+Blob (не блокируется браузером).
- **Сервис:** systemd-юнит `gate-reports` (`enabled`, `Restart=always`, от `dsh`),
  поставлен 17.11.2026: `systemctl status gate-reports`.
  Юнит — `reports/systemd/gate-reports.service`, ставится
  `sudo sh reports/systemd/install.sh` (только из обычного терминала: `sudo`
  для `dsh` в песочнице запрещён).
- **Резерв:** `reports/ensure.sh` — сторож для cron (не включать одновременно
  с systemd, будут драться за порт).
- **Запуск вручную:** `cd reports && ./run.sh` (или `python3 server.py 8095`).
- **Проверка:** `curl -s -u vitosamin:Admin910327 localhost:8095/api/status`.
- Подробности и API — `reports/README.md`.
