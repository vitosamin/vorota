# Gate-IP мост

Мост работает на сервере Gate-IP (`192.168.2.160`) и превращает UI-автоматизацию
GateTerm в простой HTTP API для приложения «Ворота».

## Что нужно

- Запущенный `GateTerm` с открытым окном «Управление точками доступа»
  (мост сам запускает GateTerm и логинится через `GateCtl.exe`, если его нет).
- `GateBridge.exe` в `C:\Users\Public`, запуск в сессии 1 (там же, где GateTerm):
  `PsExec64.exe -i 1 -s -d C:\Users\Public\GateBridge.exe`.
- Правило firewall на TCP 8099 и URL ACL `http://+:8099/`.
- Задача автозапуска `GateBridgeStartup` (при входе пользователя запускает мост).

## API

Токен по умолчанию: `vorota-2026`.

| Запрос | Действие |
|---|---|
| `GET /doors?token=...` | список дверей (id, name) |
| `GET /open?id=N&token=...` | открыть дверь N |
| `GET /lock?id=N&token=...` | заблокировать |
| `GET /unlock?id=N&token=...` | разблокировать |
| `GET /status?id=N&token=...` | `{"state":"CLOSED"}` |

## Сборка

`csc.exe /nologo /out:GateBridge.exe GateBridge.cs` (Windows .NET Framework 4.x),
`GateCtl.cs` — вход в GateTerm.

## Ограничения

- Зависит от версии GateTerm и порядка строк в таблице «Управление точками доступа»;
  при обновлении GateTerm список/координаты могут измениться.
- Работает, пока в сессии 1 запущен GateTerm и пользователь не вышел из системы.
- Токен передаётся в URL; не публиковать мост в интернет.
