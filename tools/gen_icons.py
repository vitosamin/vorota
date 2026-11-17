#!/usr/bin/env python3
"""Растровые иконки запуска для «Ворот» (резерв для лончеров без adaptive-icon)."""
from PIL import Image, ImageDraw

S = 512
BG1 = (14, 90, 63)
BG2 = (8, 37, 28)
FG = (241, 245, 249)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / (S - 1)
    gd.line([(0, y), (S, y)], fill=(
        int(BG1[0] + (BG2[0] - BG1[0]) * t),
        int(BG1[1] + (BG2[1] - BG1[1]) * t),
        int(BG1[2] + (BG2[2] - BG1[2]) * t),
        255))

mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=118, fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
bar_w = 34
xs = [126, 208, 290, 372]
top, bottom = 150, 396
for x in xs:
    d.rectangle([x, top, x + bar_w, bottom], fill=FG)
d.rectangle([108, top, 108 + 296, top + 26], fill=FG)
d.rectangle([108, 312, 108 + 296, 312 + 24], fill=FG)

for size, folder in ((48, "mipmap-mdpi"), (72, "mipmap-hdpi"), (96, "mipmap-xhdpi"),
                     (144, "mipmap-xxhdpi"), (192, "mipmap-xxxhdpi")):
    out = img.resize((size, size), Image.LANCZOS)
    out.save(f"app/src/main/res/{folder}/ic_launcher.png")
    out.save(f"app/src/main/res/{folder}/ic_launcher_round.png")

img.save("store-icon-512.png")
print("icons ok")
