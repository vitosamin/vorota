#!/bin/sh
# Поднять веб-сервис СКУД Gate, если он ещё не слушает порт.
# Вызывается из cron: @reboot и каждые 5 минут (сторож).
# Повторные запуски безопасны: flock + проверка порта.

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PORT="${1:-8095}"
LOG="$DIR/gate-reports.log"
LOCK="$DIR/.watchdog.lock"

# один сторож за раз
exec 9>"$LOCK" || exit 0
flock -n 9 || exit 0

# уже работает — выходим
if ss -tln 2>/dev/null | grep -q ":$PORT "; then
    exit 0
fi

cd "$DIR" || exit 1
{
    echo "--- $(date '+%Y-%m-%d %H:%M:%S') запуск сервиса на порту $PORT ---"
} >> "$LOG" 2>&1

setsid nohup python3 server.py "$PORT" >> "$LOG" 2>&1 < /dev/null &
exit 0
