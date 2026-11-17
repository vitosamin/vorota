#!/usr/bin/env python3
"""Извлекает иконки Lucide из бандла панели sing-box.

Панель использует lucide.min.js, поэтому значки берём оттуда же — тогда в
приложении будут ровно те же иконки, что в панели.

Умеет:
  python3 lucide.py list                     — какие иконки есть в бандле
  python3 lucide.py svg DoorOpen LogIn       — SVG-разметка (для макета в HTML)
  python3 lucide.py android out/ DoorOpen    — vector drawable для Android
"""
import re
import sys
from pathlib import Path

BUNDLE = Path("/home/dsh/projects/singbox-manager/internal/web/static/lucide.min.js")
# Иконки, которые нужны приложению «Доступ»
WANTED = ["DoorOpen", "DoorClosed", "Fence", "LogIn", "LogOut", "Square", "Settings",
          "LayoutGrid", "RefreshCw", "Star", "Trash2", "ChevronRight", "Check",
          "ShieldCheck", "Plus", "WifiOff", "Gauge", "ArrowRight", "ArrowLeft"]


def load(path=BUNDLE):
    """Возвращает {ИмяИконки: [(тег, атрибуты), ...]}."""
    src = path.read_text(encoding="utf-8")
    names = dict(re.findall(r"([A-Z][A-Za-z0-9]*):([A-Za-z_$][A-Za-z0-9_$]*)", src))
    icons = {}
    for name, var in names.items():
        if name not in WANTED or name in icons:
            continue
        match = re.search(r"\b" + re.escape(var) + r"=\[\[", src)
        if not match:
            continue
        start = match.start() + len(var) + 1
        depth = 0
        end = start
        while end < len(src):
            if src[end] == "[":
                depth += 1
            elif src[end] == "]":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        body = src[start:end + 1]
        icons[name] = parse_nodes(body)
    return icons


def parse_nodes(body):
    nodes = []
    for tag, attrs in re.findall(r'\["(\w+)",\{([^}]*)\}\]', body):
        pairs = dict(re.findall(r'(\w+):"([^"]*)"', attrs))
        nodes.append((tag, pairs))
    return nodes


def _num(pairs, key, default=0.0):
    try:
        return float(pairs.get(key, default))
    except (TypeError, ValueError):
        return default


def to_path_data(nodes):
    """Переводит фигуры Lucide в pathData: Android VectorDrawable не знает circle/line/rect."""
    parts = []
    for tag, a in nodes:
        if tag == "path":
            parts.append(a.get("d", ""))
        elif tag == "circle":
            cx, cy, r = _num(a, "cx"), _num(a, "cy"), _num(a, "r")
            parts.append(f"M{cx - r},{cy} a{r},{r} 0 1,0 {2 * r},0 a{r},{r} 0 1,0 {-2 * r},0")
        elif tag == "line":
            parts.append(f"M{_num(a, 'x1')},{_num(a, 'y1')} L{_num(a, 'x2')},{_num(a, 'y2')}")
        elif tag in ("rect", "square"):
            x, y = _num(a, "x"), _num(a, "y")
            w = _num(a, "width", _num(a, "w"))
            h = _num(a, "height", _num(a, "h"))
            r = _num(a, "rx", _num(a, "r"))
            if r:
                parts.append(f"M{x + r},{y} H{x + w - r} A{r},{r} 0 0 1 {x + w},{y + r} "
                             f"V{y + h - r} A{r},{r} 0 0 1 {x + w - r},{y + h} "
                             f"H{x + r} A{r},{r} 0 0 1 {x},{y + h - r} "
                             f"V{y + r} A{r},{r} 0 0 1 {x + r},{y} Z")
            else:
                parts.append(f"M{x},{y} H{x + w} V{y + h} H{x} Z")
    return " ".join(p for p in parts if p)


def svg(nodes, size=24, stroke=2, color="currentColor", cls=""):
    body = []
    for tag, a in nodes:
        attrs = " ".join(f'{k}="{v}"' for k, v in a.items())
        body.append(f"<{tag} {attrs}/>")
    klass = f' class="{cls}"' if cls else ""
    return (f'<svg{klass} width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round">' + "".join(body) + "</svg>")


def vector_xml(nodes, color_res="@color/icon_tint", size=24, stroke=2):
    data = to_path_data(nodes)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!-- Сгенерировано из Lucide (панель sing-box), не править вручную. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="{size}dp" android:height="{size}dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:pathData="{data}"
        android:fillColor="@android:color/transparent"
        android:strokeColor="{color_res}"
        android:strokeWidth="{stroke}"
        android:strokeLineCap="round"
        android:strokeLineJoin="round" />
</vector>
'''


def snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    icons = load()
    command = args[0]
    if command == "list":
        print("в бандле найдено:", ", ".join(sorted(icons)))
        print("нет в бандле:", ", ".join(n for n in WANTED if n not in icons))
        return 0
    if command == "svg":
        for name in args[1:]:
            print(f"<!-- {name} -->")
            print(svg(icons[name]))
        return 0
    if command == "android":
        out = Path(args[1])
        out.mkdir(parents=True, exist_ok=True)
        for name in args[2:]:
            path = out / f"ic_{snake(name)}.xml"
            path.write_text(vector_xml(icons[name]), encoding="utf-8")
            print("записан", path.name)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
