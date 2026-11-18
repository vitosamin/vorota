#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Превью светлой и тёмной темы для СКУД Gate (рисуется по токенам панели)."""
import random
import re

from PIL import Image, ImageDraw, ImageFont

ICONS = {}


def body(name):
    if name not in ICONS:
        raw = open('.lucide/%s.svg' % name, encoding='utf-8').read()
        ICONS[name] = re.sub(r'\s+', ' ', raw[raw.find('>', raw.find('<svg')) + 1:raw.rfind('</svg>')]).strip()
    return ICONS[name]


def bez(p0, p1, p2, p3, steps=12):
    out = []
    for j in range(steps + 1):
        t = j / steps
        mt = 1 - t
        out.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                    mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def draw_icon(dr, spec, ox, oy, sc, col, w):
    for m in re.finditer(r'<(path|circle|line|rect|polyline)\b([^>]*?)/?>', spec):
        tag, at = m.group(1), m.group(2)

        def a(k, d=None):
            mm = re.search(k + r'="([^"]+)"', at)
            return mm.group(1) if mm else d

        if tag == 'path':
            d = a('d', '')
            toks = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])|(-?\d*\.?\d+)', d)
            cmds = [c.lower() for c, _ in toks if c]
            nums = [float(x) for _, x in toks if x]
            pts, cur, start, i = [], [0.0, 0.0], [0.0, 0.0], 0
            for c in cmds:
                if c in 'ml':
                    x, y = nums[i], nums[i + 1]
                    i += 2
                    cur = [cur[0] + x, cur[1] + y] if c == 'l' else [x, y]
                    if c == 'm':
                        start = list(cur)
                    pts.append(tuple(cur))
                elif c in 'hv':
                    v = nums[i]
                    i += 1
                    cur = [cur[0] + v, cur[1]] if c == 'h' else [cur[0], cur[1] + v]
                    pts.append(tuple(cur))
                elif c == 'c':
                    x1, y1, x2, y2, x, y = nums[i:i + 6]
                    i += 6
                    pts += bez(cur, [x1, y1], [x2, y2], [x, y])
                    cur = [x, y]
                elif c == 'a':
                    dx, dy = nums[i + 5], nums[i + 6]
                    i += 7
                    pts.append((cur[0] + dx, cur[1] + dy))
                    cur = [cur[0] + dx, cur[1] + dy]
                elif c == 'z':
                    pts.append(tuple(start))
                    cur = list(start)
            if len(pts) > 1:
                dr.line([(ox + px * sc, oy + py * sc) for px, py in pts], fill=col, width=w, joint='curve')
        elif tag == 'circle':
            cx, cy, r = float(a('cx', '0')), float(a('cy', '0')), float(a('r', '0'))
            dr.ellipse([ox + (cx - r) * sc, oy + (cy - r) * sc, ox + (cx + r) * sc, oy + (cy + r) * sc],
                       outline=col, width=w)
        elif tag == 'line':
            dr.line([ox + float(a('x1', '0')) * sc, oy + float(a('y1', '0')) * sc,
                     ox + float(a('x2', '0')) * sc, oy + float(a('y2', '0')) * sc], fill=col, width=w)
        elif tag == 'rect':
            x, y, ww, hh = (float(a('x', '0')), float(a('y', '0')),
                            float(a('width', '0')), float(a('height', '0')))
            dr.rounded_rectangle([ox + x * sc, oy + y * sc, ox + (x + ww) * sc, oy + (y + hh) * sc],
                                 radius=max(1, float(a('rx', '0')) * sc), outline=col, width=w)
        elif tag == 'polyline':
            n = [float(v) for v in re.findall(r'-?\d*\.?\d+', a('points', ''))]
            dr.line([(ox + n[j] * sc, oy + n[j + 1] * sc) for j in range(0, len(n), 2)],
                    fill=col, width=w, joint='curve')


LIGHT = dict(bg=(241, 242, 244), card=(251, 251, 252), head=(238, 240, 243), line=(220, 223, 228),
             text=(21, 24, 28), muted=(78, 85, 96), acc=(43, 98, 217), accf=(29, 78, 216),
             soft=(231, 236, 249), softline=(166, 187, 235), grid=(227, 232, 238),
             inb=(43, 98, 217), outb=(192, 52, 42), okbg=(232, 246, 236), oktx=(21, 128, 61), ic='sun')
DARK = dict(bg=(16, 20, 26), card=(26, 34, 44), head=(30, 39, 51), line=(39, 50, 63),
            text=(231, 236, 243), muted=(148, 162, 182), acc=(74, 158, 255), accf=(74, 158, 255),
            soft=(31, 46, 66), softline=(74, 158, 255), grid=(39, 50, 63),
            inb=(74, 158, 255), outb=(248, 113, 113), okbg=(28, 52, 40), oktx=(74, 222, 128), ic='moon')


def F(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


fT = F('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
fB = F('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
fS = F('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
fH = F('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
fN = F('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)

W, H = 560, 570
img = Image.new('RGB', (1180, 650), (88, 92, 98))
dr = ImageDraw.Draw(img)


def rrect(box, radius, fill, outline):
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        return
    dr.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)


def rect(box, fill):
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        return
    dr.rectangle(box, fill=fill)


def panel(x, y, P, title):
    rrect([x, y, x + W, y + H], 12, P['bg'], (60, 64, 70))
    dr.text((x + 16, y + 12), title, font=fT, fill=P['text'])
    rrect([x + 16, y + 44, x + W - 16, y + 86], 10, P['card'], P['line'])
    dr.text((x + 30, y + 56), 'СКУД Gate', font=fH, fill=P['text'])
    draw_icon(dr, body('refresh-cw'), x + W - 150, y + 57, 0.667, P['muted'], 2)
    draw_icon(dr, body(P['ic']), x + W - 66, y + 56, 0.75, P['muted'], 2)
    tx = x + 16
    for name, act, tw in (('Мониторинг', 1, 108), ('Отчёты', 0, 86), ('Пропуска', 0, 98)):
        bg = P['soft'] if act else P['bg']
        bd = P['softline'] if act else P['line']
        fg = P['accf'] if act else P['muted']
        rrect([tx, y + 98, tx + tw, y + 134], 8, bg, bd)
        if act:
            rect([tx + 2, y + 100, tx + tw - 2, y + 104], (242, 194, 0))
        dr.text((tx + 14, y + 108), name, font=fB, fill=fg)
        tx += tw + 6
    cw = (W - 48) // 3
    for i, (lbl, val, col) in enumerate((('ПРОХОДОВ', '1 027', P['inb']),
                                         ('НА ОБЪЕКТЕ', '144', P['oktx']),
                                         ('ТРЕВОГ', '24', P['outb']))):
        cx = x + 16 + i * (cw + 8)
        rrect([cx, y + 146, cx + cw, y + 214], 12, P['card'], P['line'])
        rect([cx + 2, y + 147, cx + cw - 2, y + 150], col)
        dr.text((cx + 12, y + 158), lbl, font=fS, fill=P['muted'])
        dr.text((cx + 12, y + 176), val, font=fN, fill=P['text'])
    rrect([x + 16, y + 226, x + W - 16, y + 400], 12, P['card'], P['line'])
    rrect([x + 17, y + 227, x + W - 17, y + 262], 12, P['head'], P['line'])
    rect([x + 17, y + 254, x + W - 17, y + 262], P['head'])
    dr.text((x + 30, y + 236), 'Проходы по часам', font=fH, fill=P['text'])
    for i in range(5):
        dr.line([x + 52, y + 285 + i * 22, x + W - 30, y + 285 + i * 22], fill=P['grid'])
    random.seed(7)
    bw = ((x + W - 30) - (x + 52)) / 22
    for i in range(22):
        hgt = random.randint(4, 42)
        bx = x + 52 + i * bw + bw * 0.2
        rect([bx, y + 375 - hgt, bx + bw * 0.6, y + 375], P['inb'])
    by = y + 414
    for i, (lbl, kind) in enumerate((('Обновить', 'plain'), ('Показать отчёт', 'prim'), ('Excel', 'plain'))):
        bw2 = 150
        bx = x + 16 + i * (bw2 + 10)
        if kind == 'plain':
            bg, bd, fg = P['bg'], P['line'], P['text']
        else:
            bg, bd, fg = P['soft'], P['softline'], P['acc']
        rrect([bx, by, bx + bw2, by + 34], 8, bg, bd)
        ic = 'refresh-cw' if i == 0 else ('download' if i == 2 else 'printer')
        draw_icon(dr, body(ic), bx + 14, by + 9, 0.667, fg, 2)
        dr.text((bx + 38, by + 9), lbl, font=fB, fill=fg)
    bx = x + 16
    for lbl, bgc, fgc in (('вход', P['okbg'], P['oktx']), ('нет в Gate', (60, 30, 30), P['outb'])):
        wdt = len(lbl) * 7 + 28
        rrect([bx, y + 464, bx + wdt, y + 486], 6, bgc, fgc)
        dr.text((bx + 9, y + 469), lbl, font=fS, fill=fgc)
        bx += wdt + 10


panel(20, 20, LIGHT, 'Светлая тема')
panel(600, 20, DARK, 'Тёмная тема')
img.save('theme-preview.png')
print('готово', img.size)
