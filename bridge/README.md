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

Ключ доступа **не зашит в exe**: мост читает его из файла
`C:\GATE\gate_token.txt` на каждый запрос (запасной путь —
`C:\Users\Public\gate_token.txt`). Нет файла — API закрыт (`401 auth`).
Поэтому смена ключа — это запись новой строки в файл, без пересборки и
перезапуска. Администратор выдаёт ключ людям; в приложении он вводится один раз
и запоминается.

| Запрос | Действие |
|---|---|
| `GET /doors?token=...` | список дверей (id, name) |
| `GET /open?id=N&token=...` | открыть дверь N |
| `GET /lock?id=N&token=...` | заблокировать |
| `GET /unlock?id=N&token=...` | разблокировать |
| `GET /status?id=N&token=...` | `{"state":"CLOSED"}` |

## Сборка

`csc.exe /nologo /target:winexe /out:GateBridge.exe GateBridge.cs WebAuth.cs`
(Windows .NET Framework 4.x), `GateCtl.cs` — вход в GateTerm.

Развёртывание без прямого доступа к `C:\Users\Public` — через очередь
`C:\GATE\_skud_queue` (агент выполняет `.cmd` построчно). Готовые шаги лежат в
`C:\GATE\deploy\`: `compile.bat` (собирает `GateBridge.new.exe` и пишет
`compile.log`), `swap.bat` (бэкап → подмена → перезапуск), `restore.bat` (откат
на `GateBridge.bak.exe`). `.bat` вызывается строкой
`C:\Windows\System32\cmd.exe /c C:\GATE\deploy\compile.bat` — перенаправление
вывода внутри `.cmd`-задания очереди не работает, внутри `.bat` работает.

## Ограничения

- Зависит от версии GateTerm и порядка строк в таблице «Управление точками доступа»;
  при обновлении GateTerm список/координаты могут измениться.
- Работает, пока в сессии 1 запущен GateTerm и пользователь не вышел из системы.
- Токен передаётся в URL; не публиковать мост в интернет.
- Ключ лежит в `C:\GATE\gate_token.txt` — на шаре GATE, доступ только у СКУД.
- Ещё есть вход в веб-интерфейс моста (логин/пароль, `C:\Users\Public\gate_users.json`)
  — он не зависит от ключа API.
