#!/bin/sh
# Установка СКУД Gate как systemd-сервиса (автозапуск при загрузке машины).
# Запускать ВНЕ песочницы DSH, от пользователя с sudo:
#
#     sudo sh /home/dsh/projects/gates/reports/systemd/install.sh
#
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/gate-reports.service"
DST=/etc/systemd/system/gate-reports.service

echo "→ копирую $SRC в $DST"
install -m 644 "$SRC" "$DST"
systemctl daemon-reload
systemctl enable --now gate-reports.service
sleep 2
systemctl --no-pager --full status gate-reports.service || true
echo
echo "Проверка: curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:8095/login"
echo "Остановить: sudo systemctl stop gate-reports"
echo "Логи:       tail -f /home/dsh/projects/gates/reports/gate-reports.log"
