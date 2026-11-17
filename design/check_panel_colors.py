#!/usr/bin/env python3
"""Проверка пар цветов палитры панели sing-box по WCAG (порог 4.5:1).

Значения взяты из internal/web/static/style.css панели. Панель сама разделяет
--accent (для текста и иконок) и --accent-fill (заливка под белый текст), потому
что светлый акцент не проходит порог — здесь это проверяется.

Запуск: python3 gates/design/check_panel_colors.py
"""
import sys

WANT = 4.5

THEMES = {
    "тёмная (панель по умолчанию)": dict(
        card="#1a222c", bg="#10141a", text="#e7ecf3", dim="#94a2b6",
        fill="#2b62d9", accent="#4a9eff", success="#4ade80", warn="#fbbf24", danger="#f87171"),
    "светлая": dict(
        card="#fbfbfc", bg="#f1f2f4", text="#15181c", dim="#4e5560",
        fill="#1d4ed8", accent="#2b62d9", success="#15803d", warn="#a8620b", danger="#c0342a"),
}

PAIRS = [
    ("название на карточке", "text", "card"),
    ("подпись на карточке", "dim", "card"),
    ("белый текст на кнопке", "#ffffff", "fill"),
    ("акцент на фоне", "accent", "bg"),
    ("иконка на подложке", "accent", "card"),
    ("статус «готов»", "success", "card"),
    ("статус «движется»", "warn", "card"),
    ("статус «нет связи»", "danger", "card"),
    ("текст на фоне", "text", "bg"),
]


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
    failures = []
    for name, theme in THEMES.items():
        print(f"=== {name} ===")
        for label, fg, bg in PAIRS:
            fg_color = fg if fg.startswith("#") else theme[fg]
            bg_color = bg if bg.startswith("#") else theme[bg]
            ratio = contrast(fg_color, bg_color)
            ok = ratio >= WANT
            if not ok:
                failures.append(f"{name}: {label} {ratio:.2f}")
            print(f"{'OK   ' if ok else 'ПЛОХО'} {label:24} {fg_color} на {bg_color} — {ratio:.2f}")
    if failures:
        print(f"\nПРОВАЛОВ: {len(failures)} — {'; '.join(failures)}")
        return 1
    print("\nвсе пары палитры панели проходят порог 4.5:1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
