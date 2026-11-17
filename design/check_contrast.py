#!/usr/bin/env python3
"""Проверка читаемости макета: контраст текста к фону по WCAG (порог 4.5:1).

Считает реальные пиксели отрисованного макета, а не заявленные цвета, поэтому
ловит и ошибки вроде проигнорированной прозрачности.

Координаты прямоугольников привязаны к раскладке в mockup.py: при переносе
элементов их нужно обновлять, иначе проверка смотрит не туда.

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
    print(f"{'OK   ' if ok else 'ПЛОХО'} {label:30} фон {background} текст {text} — {ratio:.1f}")


def main():
    for name, palette, variant in (("тёмная", M.DARK, "dark"), ("светлая", M.LIGHT, "light")):
        img = M.screen_main(palette, variant)
        print(f"=== главный экран, {name} тема ===")
        # Карточки стоят на y = 124, 258, 392, 526, 660 при высоте 122.
        check(img, (30, 196, 180, 232), "кнопка «Вход»")
        check(img, (190, 196, 366, 232), "кнопка «Выход»")
        check(img, (30, 330, 366, 366), "кнопка «Закрыть»")
        check(img, (30, 464, 366, 500), "кнопка «Стоп»")
        check(img, (150, 600, 250, 634), "неактивная кнопка")
        check(img, (300, 138, 368, 158), "статус «Готов»")
        check(img, (300, 272, 368, 292), "статус «Открыто»")
        check(img, (276, 406, 368, 426), "статус «Открывается…»")
        check(img, (300, 540, 368, 560), "статус «Нет связи»")
        check(img, (72, 154, 300, 168), "подпись источника")
        check(img, (33, 88, 240, 106), "строка связи")
        check(img, (16, 32, 140, 72), "крупный заголовок")
        check(img, (200, 790, 300, 830), "подпись вкладки")

    img = M.screen_settings(M.LIGHT)
    print("=== настройки, светлая тема ===")
    check(img, (32, 132, 200, 150), "строка списка")
    check(img, (16, 96, 120, 112), "заголовок секции")
    check(img, (32, 298, 200, 312), "подпись поля")
    check(img, (44, 326, 300, 346), "текст в поле")
    check(img, (348, 170, 372, 192), "галочка выбранного")
    check(img, (330, 480, 368, 498), "значение в строке")

    if failures:
        print(f"\nПРОВАЛОВ: {len(failures)} — {', '.join(failures)}")
        return 1
    print("\nвсе проверки контраста пройдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
