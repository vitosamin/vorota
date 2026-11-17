#!/usr/bin/env python3
"""УСТАРЕЛ: макет теперь в mockup.html (build_mockup_html.py) — там настоящие
иконки Lucide из панели sing-box. Этот файл рисует старый вариант.

Макеты «Доступ»: раскладка приложения в оформлении веб-панели моста.

Иконки — контурные, как в bridge/app.html: штрих 1.8, круглый фон #e4ede9,
зелёный #2f6b5b и синий #44699b. Кнопки — светлые с рамкой, радиус 11.

Запуск: python3 gates/design/mockup.py [out.png]
"""
import sys
from PIL import Image, ImageColor, ImageDraw, ImageFont

S = 2
W, H = 400, 860
GAP = 36
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
F_REG = FONT_DIR + "LiberationSans-Regular.ttf"
F_BOLD = FONT_DIR + "LiberationSans-Bold.ttf"

# Палитра взята из панели: bridge/app.html (:root и классы .card/.icon/.bin/.bout)
LIGHT = dict(
    bg="#E3E6EA", card="#EEF0F3", line="#D6DAE0",
    text="#2A3037", text2="#565F6B", muted="#828A95",
    green="#2F6B5B", green_bg="#E6EEE9", green_line="#CFDDD5",
    blue="#44699B", blue_bg="#E7EBF2", blue_line="#D2DAE6",
    icon_bg="#E4EDE9",
    stop="#8A5A18", stop_bg="#F3EADA", stop_line="#E0D2BC",
    danger="#A34A42", danger_bg="#F0E4E2", danger_line="#DECBC8",
)
# Тёмная тема в панели отсутствует — оттенки выведены из тех же цветов
DARK = dict(
    bg="#14181D", card="#1E242B", line="#2C343D",
    text="#E8ECF0", text2="#A9B2BD", muted="#8A939E",
    green="#7CCBAF", green_bg="#22332D", green_line="#33493F",
    blue="#A6BEE2", blue_bg="#1F2A38", blue_line="#2E3E52",
    icon_bg="#22332D",
    stop="#E0B878", stop_bg="#33291A", stop_line="#4A3B23",
    danger="#E79189", danger_bg="#33211F", danger_line="#4A302D",
)

_cache = {}


def font(size, bold=False):
    key = (int(size * S), bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(F_BOLD if bold else F_REG, int(size * S))
    return _cache[key]


def text(d, xy, s, size, color, bold=False, anchor="la", spacing=0.0):
    x, y = xy[0] * S, xy[1] * S
    if spacing:
        for ch in s:
            d.text((x, y), ch, font=font(size, bold), fill=color, anchor=anchor)
            x += d.textlength(ch, font=font(size, bold)) + spacing * S
        return
    d.text((x, y), s, font=font(size, bold), fill=color, anchor=anchor)


def rr(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([box[0] * S, box[1] * S, box[2] * S, box[3] * S],
                        radius=r * S, fill=fill, outline=outline, width=max(1, int(width * S)))


def circle(d, cx, cy, r, fill=None, outline=None, width=1):
    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S],
              fill=fill, outline=outline, width=max(1, int(width * S)))


def fit(d, s, size, max_w, bold=False):
    for candidate in (size, size - 1, size - 2):
        if d.textlength(s, font=font(candidate, bold)) / S <= max_w:
            return s, candidate
    f = font(size - 2, bold)
    while s and d.textlength(s + "…", font=f) / S > max_w:
        s = s[:-1]
    return s + "…", size - 2


# --- иконки в стиле панели: контур, штрих 1.8, viewBox 24×24 --------------

def _pt(box, x, y):
    x0, y0, size = box
    k = size / 24.0
    return ((x0 + x * k) * S, (y0 + y * k) * S)


def _line(d, box, x1, y1, x2, y2, color, lw):
    d.line([_pt(box, x1, y1), _pt(box, x2, y2)], fill=color, width=max(1, int(lw * S)), joint="curve")


def _arc(d, box, cx, cy, r, start, end, color, lw):
    x0, y0, size = box
    k = size / 24.0
    d.arc([(x0 + (cx - r) * k) * S, (y0 + (cy - r) * k) * S,
           (x0 + (cx + r) * k) * S, (y0 + (cy + r) * k) * S],
          start=start, end=end, fill=color, width=max(1, int(lw * S)))


def icon_door(d, box, color, lw=1.8):
    """Точная копия значка двери из панели."""
    _line(d, box, 4, 21, 4, 5, color, lw)
    _arc(d, box, 5, 5, 1, 180, 270, color, lw)
    _line(d, box, 5, 4, 14, 4, color, lw)
    _arc(d, box, 14, 5, 1, 270, 360, color, lw)
    _line(d, box, 15, 5, 15, 21, color, lw)
    _line(d, box, 15, 12, 20, 12, color, lw)
    _line(d, box, 2, 21, 22, 21, color, lw)
    cx, cy = _pt(box, 11, 12)
    r = box[2] / 24.0 * 1.0
    d.ellipse([cx - r * S, cy - r * S, cx + r * S, cy + r * S], fill=color)


def icon_barrier(d, box, color, lw=1.8):
    """Шлагбаум в том же контуре: стойка и стрела."""
    _line(d, box, 4, 20, 4, 14, color, lw)
    _line(d, box, 8, 20, 8, 14, color, lw)
    _line(d, box, 3, 20, 9, 20, color, lw)
    _line(d, box, 6, 15, 21, 7, color, lw)
    _line(d, box, 17, 5, 21, 7, color, lw)


def icon_relay(d, box, color, lw=1.8):
    rr(d, (box[0] + box[2] * 0.18, box[1] + box[2] * 0.28,
           box[0] + box[2] * 0.82, box[1] + box[2] * 0.72), box[2] * 0.1,
       outline=color, width=lw)
    _line(d, box, 9, 12, 15, 12, color, lw)


def icon_arrow_in(d, cx, cy, size, color, lw=2.0):
    box = (cx - size / 2, cy - size / 2, size)
    _line(d, box, 5, 12, 19, 12, color, lw)
    _line(d, box, 13, 6, 19, 12, color, lw)
    _line(d, box, 19, 12, 13, 18, color, lw)


def icon_arrow_out(d, cx, cy, size, color, lw=2.0):
    box = (cx - size / 2, cy - size / 2, size)
    _line(d, box, 19, 12, 5, 12, color, lw)
    _line(d, box, 11, 6, 5, 12, color, lw)
    _line(d, box, 5, 12, 11, 18, color, lw)


ICONS = {"door": icon_door, "barrier": icon_barrier, "relay": icon_relay}


def icon_circle(d, P, cx, cy, kind="door"):
    circle(d, cx, cy, 21, fill=P["icon_bg"])
    ICONS[kind](d, (cx - 11, cy - 11, 22), P["green"])


def button(d, P, box, label, kind, size=15, icon=None):
    """Кнопка как в панели: светлая заливка, тонкая рамка, иконка слева."""
    fill = {"in": P["green_bg"], "out": P["blue_bg"],
            "stop": P["stop_bg"], "plain": P["bg"]}[kind]
    line = {"in": P["green_line"], "out": P["blue_line"],
            "stop": P["stop_line"], "plain": P["line"]}[kind]
    fg = {"in": P["green"], "out": P["blue"], "stop": P["stop"], "plain": P["text2"]}[kind]
    rr(d, box, 11, fill=fill, outline=line, width=1)
    cy = (box[1] + box[3]) / 2
    tw = d.textlength(label, font=font(size, True)) / S
    gap = 7 if icon else 0
    total = tw + (16 + gap if icon else 0)
    x = (box[0] + box[2]) / 2 - total / 2
    if icon == "in":
        icon_arrow_in(d, x + 8, cy, 16, fg)
    elif icon == "out":
        icon_arrow_out(d, x + 8, cy, 16, fg)
    text(d, (x + (16 + gap if icon else 0), cy), label, size, fg, bold=True, anchor="lm")


def device_card(d, P, y, name, source, status, status_fg, kind, buttons, height=134):
    x0, x1 = 18, 382
    rr(d, (x0, y, x1, y + height), 18, fill=P["card"], outline=P["line"], width=1)
    icon_circle(d, P, x0 + 39, y + 39, kind)

    name_text, name_size = fit(d, name, 16, 210, True)
    text(d, (x0 + 68, y + 22), name_text, name_size, P["text"], bold=True)
    src_text, src_size = fit(d, source, 12, 240, False)
    text(d, (x0 + 68, y + 42), src_text, src_size, P["text2"])
    text(d, (x1 - 18, y + 25), status, 13, status_fg, anchor="ra")

    by = y + height - 18 - 42
    if len(buttons) == 2:
        button(d, P, (x0 + 18, by, x0 + 179, by + 42), buttons[0][0], buttons[0][1], 15, buttons[0][2])
        button(d, P, (x0 + 189, by, x1 - 18, by + 42), buttons[1][0], buttons[1][1], 15, buttons[1][2])
    else:
        button(d, P, (x0 + 18, by, x1 - 18, by + 42), buttons[0][0], buttons[0][1], 15, buttons[0][2])


def tabbar(d, P, y, active=0):
    d.rectangle([0, y * S, W * S, H * S], fill=P["card"])
    d.rectangle([0, y * S, W * S, (y + 1) * S], fill=P["line"])
    for i, label in enumerate(("Устройства", "Настройки")):
        cx = W * (0.25 if i == 0 else 0.75)
        col = P["green"] if i == active else P["muted"]
        ICONS["door" if i == 0 else "relay"](d, (cx - 11, y + 16, 22), col)
        text(d, (cx, y + 52), label, 11, col, bold=(i == active), anchor="mm")


def screen_main(P, variant="light"):
    img = Image.new("RGB", (W * S, H * S), P["bg"])
    d = ImageDraw.Draw(img)
    text(d, (18, 32), "Доступ", 28, P["text"], bold=True, spacing=-0.3)
    circle(d, 22, 88, 4, fill=P["green"])
    text(d, (34, 80), "Мост СКУД доступен", 13, P["text2"])

    device_card(d, P, 108, "Калитка", "Gate-IP · вход и выход", "Готов", P["green"], "door",
                [("Вход", "in", "in"), ("Выход", "out", "out")])
    device_card(d, P, 256, "Шлагбаум", "Home Assistant · cover.barrier", "Открыто", P["green"], "barrier",
                [("Закрыть", "plain", None)])
    device_card(d, P, 404, "КПП производство", "Gate-IP · 6 дверей", "Открывается…", P["stop"], "door",
                [("Стоп", "stop", None)])
    device_card(d, P, 552, "Северные ворота склад №3", "Gate-IP · только вход", "Нет связи", P["danger"], "door",
                [("Вход", "plain", "in")])
    device_card(d, P, 700, "Ворота", "Gate-IP · вход и выход", "Готов", P["green"], "door",
                [("Вход", "in", "in"), ("Выход", "out", "out")])
    tabbar(d, P, 776, active=0)
    return img


def settings_row(d, P, y, label, value=None, check=False, chevron_=False):
    text(d, (x_ := 36, y + 13), label, 16, P["text"])
    if value:
        text(d, (364, y + 15), value, 14, P["text2"], anchor="ra")
    if check:
        lw = 2
        d.line([(348 * S, (y + 22) * S), (354 * S, (y + 28) * S)], fill=P["green"], width=lw * S)
        d.line([(354 * S, (y + 28) * S), (364 * S, (y + 16) * S)], fill=P["green"], width=lw * S)
    if chevron_:
        d.line([(358 * S, (y + 17) * S), (363 * S, (y + 22) * S)], fill=P["muted"], width=2 * S)
        d.line([(363 * S, (y + 22) * S), (358 * S, (y + 27) * S)], fill=P["muted"], width=2 * S)


def screen_settings(P):
    img = Image.new("RGB", (W * S, H * S), P["bg"])
    d = ImageDraw.Draw(img)
    text(d, (18, 32), "Настройки", 28, P["text"], bold=True, spacing=-0.3)

    text(d, (18, 90), "ОФОРМЛЕНИЕ", 11, P["muted"], bold=True, spacing=1.0)
    rr(d, (18, 108, 382, 240), 18, fill=P["card"], outline=P["line"], width=1)
    for i, (label, active) in enumerate((("Светлая", False), ("Тёмная", True), ("Системная", False))):
        y = 108 + i * 44
        if i:
            d.rectangle([36 * S, y * S, 382 * S, (y + 0.5) * S], fill=P["line"])
        settings_row(d, P, y, label, check=active)

    text(d, (18, 258), "ПОДКЛЮЧЕНИЕ", 11, P["muted"], bold=True, spacing=1.0)
    rr(d, (18, 276, 382, 420), 18, fill=P["card"], outline=P["line"], width=1)
    text(d, (36, 290), "Адрес Home Assistant", 12, P["text2"])
    rr(d, (36, 310, 364, 346), 11, fill=P["bg"], outline=P["line"], width=1)
    text(d, (48, 328), "http://192.168.2.39:8123", 14, P["text"], anchor="lm")
    text(d, (36, 358), "Долгоживущий токен", 12, P["text2"])
    rr(d, (36, 378, 364, 414), 11, fill=P["bg"], outline=P["line"], width=1)
    text(d, (48, 396), "••••••••••••••", 14, P["muted"], anchor="lm")

    text(d, (18, 438), "GATE-IP", 11, P["muted"], bold=True, spacing=1.0)
    rr(d, (18, 456, 382, 544), 18, fill=P["card"], outline=P["line"], width=1)
    settings_row(d, P, 456, "Мост", value="на связи")
    d.rectangle([36 * S, 500 * S, 382 * S, 500.5 * S], fill=P["line"])
    settings_row(d, P, 500, "Загрузить двери", chevron_=True)

    text(d, (18, 562), "УСТРОЙСТВА", 11, P["muted"], bold=True, spacing=1.0)
    rr(d, (18, 580, 382, 712), 18, fill=P["card"], outline=P["line"], width=1)
    for i, (label, value) in enumerate((("Калитка", "Gate-IP"), ("Шлагбаум", "HA"), ("КПП", "Gate-IP"))):
        y = 580 + i * 44
        if i:
            d.rectangle([36 * S, y * S, 382 * S, (y + 0.5) * S], fill=P["line"])
        settings_row(d, P, y, label, value=value, chevron_=True)

    tabbar(d, P, 776, active=1)
    return img


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "gates/design/mockup.png"
    screens = [screen_main(LIGHT, "light"), screen_main(DARK, "dark"), screen_settings(LIGHT)]
    width = W * S * len(screens) + GAP * S * (len(screens) - 1) + 40 * S
    canvas = Image.new("RGB", (width, H * S + 40 * S), "#05070A")
    x = 20 * S
    for s in screens:
        canvas.paste(s, (x, 20 * S))
        x += W * S + GAP * S
    canvas.save(out)
    print("saved", out, canvas.size)


if __name__ == "__main__":
    main()
