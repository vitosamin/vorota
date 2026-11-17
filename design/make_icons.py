#!/usr/bin/env python3
"""Иконка приложения «Доступ»: белая дверь Lucide на тёмно-зелёной плашке.

Значок тот же, что в плитках приложения (Lucide DoorOpen из панели sing-box),
фон — тёмно-зелёный с лёгким объёмом, как у плашек типов.

Рисует растровые mipmap-файлы и store-icon. Векторные версии для adaptive-icon
лежат в app/src/main/res/drawable/ic_launcher_foreground.xml и
ic_launcher_background.xml.

Запуск: python3 gates/design/make_icons.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app/src/main/res"
TOP = "#23734A"          # светлее сверху
BOTTOM = "#124430"       # темнее снизу
MARK = "#FFFFFF"
SS = 4                   # суперсэмплинг

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def background(size, shape):
    """Тёмно-зелёный фон с вертикальным градиентом и маской формы."""
    top = tuple(int(TOP[i:i + 2], 16) for i in (1, 3, 5))
    bottom = tuple(int(BOTTOM[i:i + 2], 16) for i in (1, 3, 5))
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        k = y / max(1, size - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * k) for i in range(3)))
    grad = grad.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    if shape == "round":
        d.ellipse([0, 0, size - 1, size - 1], fill=255)
    else:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size * 0.22, fill=255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    return img


def door(img, size):
    """Дверь Lucide DoorOpen в координатах 24×24, приведённых к размеру значка."""
    d = ImageDraw.Draw(img)
    # Знак занимает 56 % плашки, как foreground у adaptive-icon (scale 2.6 из 108)
    k = size / 24.0 * 0.56
    lw = max(2, round(size * 0.055))
    pad = size * 0.22          # отступ от края плашки

    def p(x, y):
        return (pad + x * k, pad + y * k)

    # пол и косяк
    d.line([p(2, 20), p(22, 20)], fill=MARK, width=lw)
    d.line([p(11, 4), p(8, 4)], fill=MARK, width=lw)
    d.line([p(6, 6), p(6, 20)], fill=MARK, width=lw)
    d.arc([p(6, 4)[0], p(6, 4)[1], p(8, 6)[0], p(8, 6)[1]], start=180, end=270, fill=MARK, width=lw)
    # полотно двери
    d.line([p(11, 4.6), p(19, 5.6), p(19, 20), p(11, 20.7), p(11, 4.6)],
           fill=MARK, width=lw, joint="curve")
    # ручка
    r = max(1, round(size * 0.028))
    cx, cy = p(14, 12)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=MARK)
    return img


def make(size, shape):
    big = size * SS
    img = background(big, shape)
    door(img, big)
    return img.resize((size, size), Image.LANCZOS)


def main():
    written = []
    for density, size in SIZES.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        for name, shape in (("ic_launcher.png", "square"), ("ic_launcher_round.png", "round")):
            make(size, shape).save(folder / name)
            written.append(folder / name)
    make(512, "square").save(ROOT / "store-icon-512.png")
    written.append(ROOT / "store-icon-512.png")
    print(f"готово: {len(written)} файлов, фон {TOP}→{BOTTOM}, знак — дверь")


if __name__ == "__main__":
    main()
