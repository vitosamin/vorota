#!/usr/bin/env python3
"""Проверка читаемости макета: контраст текста к фону по WCAG (порог 4.5:1).

Считает реальные пиксели отрисованного макета, а не заявленные цвета, поэтому
ловит и ошибки вроде проигнорированной прозрачности.

Запуск: python3 gates/design/check_contrast.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mockup as M  # noqa: E402

WANT = 4.5
failures = []


def luminance(color):
    def channel(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = color[:3]
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def check(img, rect, label, want=WANT):
    x0, y0, x1, y1 = [v * M.S for v in rect]
    colors = Counter(img.crop((int(x0), int(y0), int(x1), int(y1))).getdata())
    background = colors.most_common(1)[0][0]
    text = max(colors, key=lambda c: abs(luminance(c) - luminance(background)))
    ratio = contrast(background, text)
    ok = ratio >= want
    if not ok:
        failures.append(label)
    print(f"{'OK   ' if ok else 'ПЛОХО'} {label:32} фон {background} текст {text} контраст {ratio:.1f}")


def main():
    for name, palette, variant in (("тёмная", M.DARK, "dark"), ("светлая", M.LIGHT, "light")):
        img = M.screen_main(palette, variant)
        print(f"=== главный экран, {name} тема ===")
        # Плитки стоят на y = 132, 314, 496, 678 при высоте 168.
        check(img, (40, 242, 190, 280), "кнопка «Вход»")
        check(img, (209, 242, 360, 280), "кнопка «Выход»")
        check(img, (40, 424, 360, 462), "кнопка «Закрыть»")
        check(img, (312, 206, 362, 226), "статус «Готов»")
        check(img, (295, 388, 362, 408), "статус «Открыто»")
        check(img, (260, 570, 362, 590), "статус «Открывается…»")
        check(img, (290, 752, 362, 772), "статус «Нет связи»")
        check(img, (36, 208, 290, 222), "подпись источника")
        check(img, (40, 96, 240, 118), "строка связи")

    img = M.screen_settings(M.DARK)
    print("=== настройки, тёмная тема ===")
    check(img, (20, 100, 140, 116), "заголовок секции")
    check(img, (36, 250, 364, 288), "плейсхолдер поля")
    check(img, (300, 402, 366, 424), "статус «на связи»")

    if failures:
        print(f"\nПРОВАЛОВ: {len(failures)} — {', '.join(failures)}")
        return 1
    print("\nвсе проверки контраста пройдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
