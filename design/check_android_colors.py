#!/usr/bin/env python3
"""Проверка пар цветов Android-ресурсов по WCAG (порог 4.5:1).

Читает values/colors.xml (светлая) и values-night/colors.xml (тёмная) и считает
контраст для тех пар «текст на фоне», которые реально использует интерфейс.

Запуск: python3 gates/design/check_android_colors.py
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WANT = 4.5

# (подпись, цвет текста, цвет фона)
PAIRS = [
    ("название устройства", "text_primary", "card"),
    ("подпись источника", "text_secondary", "card"),
    ("заголовок раздела", "text_muted", "bg"),
    ("строка связи", "text_secondary", "bg"),
    ("кнопка «Вход»", "accent", "accent_soft"),
    ("кнопка «Выход»", "info", "info_soft"),
    ("статус «готов/открыто»", "accent", "accent_soft"),
    ("статус «движется»", "warn", "warn_soft"),
    ("статус «нет связи»", "danger", "danger_soft"),
    ("статус «закрыто»", "text_secondary", "field"),
    ("главная кнопка", "on_accent", "accent"),
    ("вторичная кнопка", "text_primary", "card_high"),
    ("текст в поле ввода", "text_primary", "field"),
    ("подсказка в поле", "text_muted", "field"),
]


def load(path):
    colors = {}
    for node in ET.parse(path).getroot():
        if node.tag == "color":
            colors[node.get("name")] = node.text.strip()
    return colors


def luminance(value):
    value = value.lstrip("#")
    rgb = [int(value[i:i + 2], 16) for i in (0, 2, 4)]

    def channel(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def main():
    themes = [("светлая", load(ROOT / "app/src/main/res/values/colors.xml")),
              ("тёмная", load(ROOT / "app/src/main/res/values-night/colors.xml"))]
    failures = []
    for name, colors in themes:
        print(f"=== {name} тема ===")
        for label, fg, bg in PAIRS:
            if fg not in colors or bg not in colors:
                failures.append(f"{name}: {label} (нет цвета {fg} или {bg})")
                print(f"ПЛОХО {label:26} нет цвета {fg} или {bg}")
                continue
            ratio = contrast(colors[fg], colors[bg])
            ok = ratio >= WANT
            if not ok:
                failures.append(f"{name}: {label} {ratio:.1f}")
            print(f"{'OK   ' if ok else 'ПЛОХО'} {label:26} {colors[fg]} на {colors[bg]} — {ratio:.1f}")
    if failures:
        print(f"\nПРОВАЛОВ: {len(failures)} — {'; '.join(failures)}")
        return 1
    print("\nвсе пары цветов Android проходят порог 4.5:1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
