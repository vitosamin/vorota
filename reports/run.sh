#!/bin/sh
# СКУД Gate — запуск веб-сервиса мониторинга и отчётов.
# Порт: первый аргумент (по умолчанию 8095 из gate.config.json).
cd "$(dirname "$0")" || exit 1
exec python3 server.py "${1:-8095}"
