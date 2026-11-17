#!/usr/bin/env python3
"""Макеты интерфейса «Ворота» — тёмная и светлая темы, крупные плитки.

Запуск: python3 gates/design/mockup.py [out.png]
Рисуется без Android: только Pillow, чтобы согласовать вид до правки кода.
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageColor

S = 2                      # масштаб отрисовки (retina)
W, H = 400, 860            # логический размер экрана
GAP = 36
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
F_REG = FONT_DIR + "LiberationSans-Regular.ttf"
F_BOLD = FONT_DIR + "LiberationSans-Bold.ttf"

DARK = dict(
    bg="#0A0D11", surface="#141A21", surface_hi="#1C242E", stroke="#242E3A",
    text="#F1F5F9", text2="#9AA6B4", muted="#8A94A4",
    mint="#3DDC97", mint_ink="#062117", blue="#9DBBFF", amber="#F5C25E",
    red="#FF8A8A", chip="#1B222B",
)
LIGHT = dict(
    bg="#F4F6FA", surface="#FFFFFF", surface_hi="#EDF1F8", stroke="#DFE5EF",
    text="#101827", text2="#5A6779", muted="#5C6B80",
    mint="#0B7A56", mint_ink="#FFFFFF", blue="#2F62D8", amber="#96600F",
    red="#B3313C", chip="#E9EEF7",
)

_cache = {}


def blend(fg, alpha, bg):
    """Непрозрачная смесь: Pillow на RGB-картинке игнорирует альфу в #RRGGBBAA."""
    f = ImageColor.getrgb(fg)
    b = ImageColor.getrgb(bg)
    return "#%02X%02X%02X" % tuple(round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3))


def font(size, bold=False):
    key = (size * S, bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(F_BOLD if bold else F_REG, size * S)
    return _cache[key]


def text(d, xy, s, size, color, bold=False, anchor="la", spacing=0):
    x, y = xy[0] * S, xy[1] * S
    if spacing:
        for ch in s:
            d.text((x, y), ch, font=font(size, bold), fill=color, anchor=anchor)
            x += d.textlength(ch, font=font(size, bold)) + spacing * S
        return
    d.text((x, y), s, font=font(size, bold), fill=color, anchor=anchor)


def rr(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([box[0] * S, box[1] * S, box[2] * S, box[3] * S],
                        radius=r * S, fill=fill, outline=outline, width=width * S)


def circle(d, cx, cy, r, fill=None, outline=None, width=1):
    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S],
              fill=fill, outline=outline, width=width * S)


def fit(d, s, size, max_w, bold=True):
    """Сначала пробует уменьшить кегль, потом обрезает строку многоточием."""
    for candidate in (size, size - 1, size - 2, size - 3):
        if d.textlength(s, font=font(candidate, bold)) / S <= max_w:
            return s, candidate
    f = font(size - 3, bold)
    s = s
    while s and d.textlength(s + "…", font=f) / S > max_w:
        s = s[:-1]
    return s + "…", size - 3


def icon(d, cx, cy, size, kind, color):
    """Простые глифы устройств: ворота, шлагбаум, дверь, реле, обновление, шестерня."""
    h = size / 2.0
    lw = max(2, int(size * 0.09))
    if kind == "gate":
        d.rectangle([(cx - h) * S, (cy - h) * S, (cx - h + lw) * S, (cy + h) * S], fill=color)
        d.rectangle([(cx + h - lw) * S, (cy - h) * S, (cx + h) * S, (cy + h) * S], fill=color)
        for i in range(3):
            yy = cy - h + size * (0.22 + 0.28 * i)
            d.rectangle([(cx - h + lw) * S, (yy - lw / 2) * S, (cx + h - lw) * S, (yy + lw / 2) * S], fill=color)
    elif kind == "barrier":
        d.rectangle([(cx - h) * S, (cy + h - size * 0.42) * S, (cx - h + size * 0.3) * S, (cy + h) * S], fill=color)
        d.line([(cx - h + size * 0.15) * S, (cy + h - size * 0.42) * S,
                (cx + h) * S, (cy - h + size * 0.12) * S], fill=color, width=lw)
    elif kind == "door":
        d.rectangle([(cx - h * 0.8) * S, (cy - h) * S, (cx + h * 0.8) * S, (cy + h) * S],
                    outline=color, width=lw)
        circle(d, cx + h * 0.35, cy, max(1.5, size * 0.06), fill=color)
    elif kind == "refresh":
        d.arc([(cx - h) * S, (cy - h) * S, (cx + h) * S, (cy + h) * S],
              start=40, end=320, fill=color, width=lw)
        d.polygon([(cx + h * 0.55, cy - h * 0.95), (cx + h * 0.55, cy - h * 0.15),
                   (cx + h * 1.15, cy - h * 0.55)], fill=color)
    elif kind == "gear":
        circle(d, cx, cy, h * 0.45, outline=color, width=lw)
        for i in range(8):
            import math
            a = math.radians(i * 45)
            x1, y1 = cx + math.cos(a) * h * 0.68, cy + math.sin(a) * h * 0.68
            x2, y2 = cx + math.cos(a) * h * 1.0, cy + math.sin(a) * h * 1.0
            d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=color, width=lw)
    else:  # relay
        rr(d, (cx - h, cy - h * 0.7, cx + h, cy + h * 0.7), size * 0.12, outline=color, width=lw)
        d.line([(cx - h * 0.5) * S, cy * S, (cx + h * 0.5) * S, cy * S], fill=color, width=lw)


def pill(d, x, y, label, size, fg, bg):
    w = d.textlength(label, font=font(size, True)) / S + 22
    rr(d, (x - w, y, x, y + 24), 12, fill=bg)
    text(d, (x - w / 2, y + 12), label, size, fg, bold=True, anchor="mm")
    return w


def button(d, box, label, size, fg, bg, outline=None, glyph=None, glyph_color=None):
    rr(d, box, 14, fill=bg, outline=outline)
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    tw = d.textlength(label, font=font(size, True)) / S
    shift = 12 if glyph else 0
    text(d, (cx + shift, cy), label, size, fg, bold=True, anchor="mm")
    if glyph:
        icon(d, cx - tw / 2 - 14, cy, 15, glyph, glyph_color or fg)


def wrap(d, s, size, max_w, bold=True, max_lines=2):
    """Разбивает строку по словам на несколько строк, последнюю обрезает многоточием."""
    f = font(size, bold)
    words = s.split()
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if d.textlength(candidate, font=f) / S <= max_w or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines - 1:
                break
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    used = " ".join(lines)
    if used != s:
        while lines and d.textlength(lines[-1] + "…", font=f) / S > max_w:
            lines[-1] = lines[-1][:-1]
        if lines:
            lines[-1] += "…"
    return lines


def tile(d, P, x, y, w, name, source, status, status_fg, status_bg,
         kind="gate", buttons=(), h=168):
    rr(d, (x, y, x + w, y + h), 22, fill=P["surface"], outline=P["stroke"])
    rr(d, (x + 16, y + 16, x + 16 + 46, y + 16 + 46), 14, fill=P["surface_hi"])
    icon(d, x + 39, y + 39, 26, kind, P["mint"])

    # Имя занимает всю ширину до края плитки: статус переехал на строку ниже.
    name_w = w - 76 - 16
    name_size = 20
    for candidate in (20, 19, 18, 17):
        if len(wrap(d, name, candidate, name_w, True)) == 1:
            name_size = candidate
            break
    else:
        name_size = 17
    lines = wrap(d, name, name_size, name_w, True)
    line_h = name_size + 5
    for i, line in enumerate(lines):
        text(d, (x + 76, y + 18 + i * line_h), line, name_size, P["text"], bold=True)

    # Строка источника и статуса идёт ниже иконки, иначе текст заходит под неё.
    meta_y = y + 72
    pill_w = d.textlength(status, font=font(11, True)) / S + 22
    src_text, src_size = fit(d, source, 10, w - 32 - pill_w - 12, True)
    text(d, (x + 16, meta_y + 6), src_text, src_size, P["text2"], bold=True, spacing=1.2)
    pill(d, x + w - 16, meta_y, status, 11, status_fg, status_bg)
    by = y + h - 62
    if len(buttons) == 2:
        bw = (w - 32 - 10) / 2
        button(d, (x + 16, by, x + 16 + bw, by + 46), buttons[0][0], 15,
               buttons[0][1], buttons[0][2], buttons[0][3], buttons[0][4], buttons[0][5])
        button(d, (x + 16 + bw + 10, by, x + w - 16, by + 46), buttons[1][0], 15,
               buttons[1][1], buttons[1][2], buttons[1][3], buttons[1][4], buttons[1][5])
    elif buttons:
        button(d, (x + 16, by, x + w - 16, by + 46), buttons[0][0], 16,
               buttons[0][1], buttons[0][2], buttons[0][3], buttons[0][4], buttons[0][5])


def nav(d, P, y, active=0):
    d.rectangle([0, y * S, W * S, H * S], fill=P["surface"])
    d.rectangle([0, y * S, W * S, (y + 1) * S], fill=P["stroke"])
    for i, label in enumerate(("Устройства", "Настройки")):
        cx = W * (0.25 if i == 0 else 0.75)
        col = P["mint"] if i == active else P["muted"]
        icon(d, cx, y + 30, 22, "gate" if i == 0 else "gear", col)
        text(d, (cx, y + 52), label, 11, col, bold=(i == active), anchor="mm")


def screen_main(P, variant="dark"):
    img = Image.new("RGB", (W * S, H * S), P["bg"])
    d = ImageDraw.Draw(img)
    text(d, (20, 38), "Доступ", 32, P["text"], bold=True)
    circle(d, 356, 56, 19, fill=P["surface"], outline=P["stroke"])
    icon(d, 356, 56, 19, "refresh", P["text2"])
    circle(d, 26, 108, 4.5, fill=P["mint"])
    text(d, (40, 99), "Мост СКУД доступен", 13, P["text2"])

    mint_soft = blend(P["mint"], 0.16, P["surface"])
    blue_soft = blend(P["blue"], 0.16, P["surface"])
    amber_soft = blend(P["amber"], 0.16, P["surface"])
    red_soft = blend(P["red"], 0.16, P["surface"])
    if variant == "light":
        mint_soft, blue_soft, amber_soft, red_soft = "#DFF6EC", "#E4EBFD", "#FBEEDA", "#FBE3E5"

    tile(d, P, 20, 132, 360, "Калитка", "GATE-IP · ВХОД И ВЫХОД", "Готов", P["mint"], mint_soft,
         kind="gate",
         buttons=[("Вход", P["mint_ink"], P["mint"], None, "door", None),
                  ("Выход", P["blue"], blue_soft, None, "door", None)])
    tile(d, P, 20, 314, 360, "Шлагбаум", "HOME ASSISTANT · COVER.BARRIER", "Открыто", P["mint"], mint_soft,
         kind="barrier",
         buttons=[("Закрыть", P["text"], P["surface_hi"], P["stroke"], None, None)])
    tile(d, P, 20, 496, 360, "КПП производство", "GATE-IP · 6 ДВЕРЕЙ", "Открывается…", P["amber"], amber_soft,
         kind="gate",
         buttons=[("Вход", P["mint_ink"], P["mint"], None, "door", None),
                  ("Выход", P["blue"], blue_soft, None, "door", None)])
    tile(d, P, 20, 678, 360, "Ворота", "GATE-IP · ВХОД И ВЫХОД", "Нет связи", P["red"], red_soft,
         kind="gate",
         buttons=[("Вход", P["text2"], P["surface_hi"], P["stroke"], "door", None),
                  ("Выход", P["text2"], P["surface_hi"], P["stroke"], "door", None)])
    nav(d, P, 776, active=0)
    return img


def screen_settings(P):
    img = Image.new("RGB", (W * S, H * S), P["bg"])
    d = ImageDraw.Draw(img)
    text(d, (20, 38), "Настройки", 30, P["text"], bold=True)

    text(d, (20, 100), "ОФОРМЛЕНИЕ", 10, P["muted"], bold=True, spacing=1.4)
    chips = [("Светлая", False), ("Тёмная", True), ("Системная", False)]
    x = 20
    for label, active in chips:
        w = 112
        rr(d, (x, 122, x + w, 164), 14,
           fill=P["mint"] if active else P["surface"],
           outline=None if active else P["stroke"])
        text(d, (x + w / 2, 143), label, 13,
             P["mint_ink"] if active else P["text2"], bold=active, anchor="mm")
        x += w + 10

    text(d, (20, 196), "ПОДКЛЮЧЕНИЕ", 10, P["muted"], bold=True, spacing=1.4)
    rr(d, (20, 218, 380, 336), 22, fill=P["surface"], outline=P["stroke"])
    text(d, (36, 232), "Адрес Home Assistant", 11, P["text2"])
    rr(d, (36, 250, 364, 288), 12, fill=P["surface_hi"])
    text(d, (48, 269), "http://192.168.2.39:8123", 13, P["muted"], anchor="lm")
    text(d, (36, 298), "Долгоживущий токен", 11, P["text2"])
    rr(d, (36, 316, 364, 354), 12, fill=P["surface_hi"])
    text(d, (48, 335), "••••••••••••••••", 13, P["muted"], anchor="lm")

    text(d, (20, 368), "GATE-IP", 10, P["muted"], bold=True, spacing=1.4)
    rr(d, (20, 390, 380, 470), 22, fill=P["surface"], outline=P["stroke"])
    text(d, (36, 404), "Мост", 11, P["text2"])
    rr(d, (36, 422, 364, 460), 12, fill=P["surface_hi"])
    text(d, (48, 441), "https://kp.almak.ru", 13, P["text"], anchor="lm")
    pill(d, 364, 404, "на связи", 11, P["mint"], blend(P["mint"], 0.16, P["surface"]))

    text(d, (20, 492), "УСТРОЙСТВА", 10, P["muted"], bold=True, spacing=1.4)
    for i, (name, sub) in enumerate((("Калитка", "Gate-IP · вход и выход"),
                                     ("Шлагбаум", "Home Assistant · cover"),
                                     ("КПП производство", "Gate-IP · 6 дверей"))):
        y = 514 + i * 62
        rr(d, (20, y, 380, y + 54), 18, fill=P["surface"], outline=P["stroke"])
        rr(d, (32, y + 9, 68, y + 45), 12, fill=P["surface_hi"])
        icon(d, 50, y + 27, 20, "gate" if i != 1 else "barrier", P["mint"])
        text(d, (80, y + 12), name, 15, P["text"], bold=True)
        text(d, (80, y + 32), sub, 11, P["muted"])
        text(d, (356, y + 27), "⋮", 18, P["muted"], anchor="mm")

    rr(d, (20, 706, 380, 762), 18, fill=P["surface"], outline=P["stroke"])
    text(d, (36, 722), "Версия 2.7", 13, P["text"])
    text(d, (36, 741), "Проверить обновления", 11, P["mint"])
    nav(d, P, 776, active=1)
    return img


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "gates/design/mockup.png"
    screens = [screen_main(DARK, "dark"), screen_main(LIGHT, "light"), screen_settings(DARK)]
    width = W * S * len(screens) + GAP * S * (len(screens) - 1) + 40 * S
    height = H * S + 40 * S
    canvas = Image.new("RGB", (width, height), "#05070A")
    x = 20 * S
    for s in screens:
        canvas.paste(s, (x, 20 * S))
        x += W * S + GAP * S
    canvas.save(out)
    print("saved", out, canvas.size)


if __name__ == "__main__":
    main()
