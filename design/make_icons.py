#!/usr/bin/env python3
"""Иконка приложения «Доступ»: изумрудный квадрат со знаком доступа (ключевина).

Рисует растровые mipmap-файлы и store-icon. Векторная версия для adaptive-icon
лежит в app/src/main/res/drawable/ic_launcher_foreground.xml и повторяет этот знак.

Запуск: python3 gates/design/make_icons.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app/src/main/res"
BG = "#0B7A56"          # изумрудный фон
MARK = "#FFFFFF"        # знак
SS = 4                  # суперсэмплинг для гладких краёв

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def rounded(size, radius_ratio=0.22):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size * radius_ratio
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)
    return img


def round_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=BG)
    return img


def draw_mark(img, size):
    """Ключевина: круг сверху и расширяющийся книзу стержень."""
    d = ImageDraw.Draw(img)
    cx = size / 2.0
    circle_r = size * 0.165
    circle_cy = size * 0.375
    d.ellipse([cx - circle_r, circle_cy - circle_r, cx + circle_r, circle_cy + circle_r], fill=MARK)

    top = circle_cy + circle_r * 0.35
    bottom = size * 0.735
    half_top = size * 0.072
    half_bottom = size * 0.118
    d.polygon([(cx - half_top, top), (cx + half_top, top),
               (cx + half_bottom, bottom), (cx - half_bottom, bottom)], fill=MARK)
    return img


def make(size, shape):
    big = size * SS
    img = rounded(big) if shape == "square" else round_icon(big)
    draw_mark(img, big)
    return img.resize((size, size), Image.LANCZOS)


def main():
    written = []
    for density, size in SIZES.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        for name, shape in (("ic_launcher.png", "square"), ("ic_launcher_round.png", "round")):
            make(size, shape).save(folder / name)
            written.append(folder / name)
    store = make(512, "square")
    store.save(ROOT / "store-icon-512.png")
    written.append(ROOT / "store-icon-512.png")
    print(f"готово: {len(written)} файлов, фон {BG}, знак {MARK}")


if __name__ == "__main__":
    main()
