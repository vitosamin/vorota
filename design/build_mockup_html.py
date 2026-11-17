#!/usr/bin/env python3
"""Собирает HTML-макет приложения «Доступ» в оформлении панели sing-box.

Берёт палитру и компоненты из internal/web/static/style.css (переменные --bg,
--card, --accent-fill и т. д.) и настоящие иконки Lucide из того же бандла,
поэтому браузер рисует ровно то, что попадёт в приложение.

Устройства — компактные плитки по две в ряд; у каждого типа свой цвет значка,
чтобы список не выглядел серым.

Запуск: python3 gates/design/build_mockup_html.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lucide  # noqa: E402

OUT = Path(__file__).resolve().parent


def icon(name, size=16, stroke=2):
    return lucide.svg(lucide.load()[name], size=size, stroke=stroke)


def tile(name, sub, status, status_class, icon_name, tint, buttons):
    """Компактная плитка: значок своего цвета, имя в две строки, кнопки."""
    parts = [f'''        <div class="tile">
          <div class="trow">
            <div class="chip {tint}">{icon(icon_name, 16)}</div>
            <div class="status {status_class}">{status}</div>
          </div>
          <div class="tname">{name}</div>
          <div class="tsub">{sub}</div>
          <div class="btns">''']
    for label, kind, ic in buttons:
        ic_html = icon(ic, 14) if ic else ""
        parts.append(f'            <button class="btn {kind}">{ic_html}<span>{label}</span></button>')
    parts.append("          </div>\n        </div>")
    return "\n".join(parts)


def grid(tiles):
    return '      <div class="grid">\n' + "\n".join(tiles) + "\n      </div>"


def settings_row(label, value="", check=False, chevron=False):
    right = ""
    if value:
        right = f'<span class="dim">{value}</span>'
    if check:
        right = f'<span class="tick">{icon("Check", 17)}</span>'
    if chevron:
        right = f'<span class="chev">{icon("ChevronRight", 17)}</span>'
    return f'        <div class="srow"><span>{label}</span>{right}</div>'


def field(label, value):
    return (f'        <div class="field-label">{label}</div>\n'
            f'        <div class="input mono">{value}</div>')


def screen(title, subtitle, body, active_tab=0, theme="dark", pulse_err=False):
    tabs = ""
    for i, (label, ic) in enumerate((("Устройства", "LayoutGrid"), ("Настройки", "Settings"))):
        cls = "tab active" if i == active_tab else "tab"
        tabs += f'      <div class="{cls}">{icon(ic, 20)}<span>{label}</span></div>\n'
    sub = f'<div class="pulse{" err" if pulse_err else ""}"></div>' if subtitle else ""
    return f'''  <div class="phone" data-theme="{theme}">
    <div class="screen">
      <div class="head">
        <div class="title">{title}</div>
        {sub}
      </div>
      <div class="list">
{body}
      </div>
      <div class="tabbar">
{tabs}      </div>
    </div>
  </div>'''


CSS = """
/* Палитра и компоненты взяты из панели sing-box (internal/web/static/style.css) */
:root {
  --bg:#10141a; --bg-side:#151b23; --card:#1a222c; --card-hover:#212b37;
  --border:#27323f; --border-hi:#3a4859;
  --text:#e7ecf3; --text-dim:#94a2b6;
  --accent:#4a9eff; --accent-hi:#5fb0ff; --accent-fill:#2b62d9; --accent-fill-hi:#3568dd;
  --success:#4ade80; --danger:#f87171; --warn:#fbbf24; --purple:#a78bfa; --cyan:#22d3ee;
  --accent-soft:rgba(74,158,255,0.10); --accent-soft-2:rgba(74,158,255,0.18);
  --shadow-accent:0 2px 10px rgba(74,158,255,0.3);
  --radius-xs:6px; --radius-s:8px; --radius-m:10px; --radius-l:12px; --radius-xl:16px;
  --control-h:34px; --fs-xs:11px; --fs-s:12px; --fs-m:13px; --fs-l:15px;
  --fs-xl:18px; --fs-xxl:21px;
}
[data-theme="light"] {
  --bg:#f1f2f4; --bg-side:#e9ebef; --card:#fbfbfc; --card-hover:#f4f5f7;
  --border:#dcdfe4; --border-hi:#c6cbd3;
  --text:#15181c; --text-dim:#4e5560;
  --accent:#2b62d9; --accent-hi:#3b78ec; --accent-fill:#1d4ed8; --accent-fill-hi:#2b62d9;
  --success:#15803d; --danger:#c0342a; --warn:#9a5909; --purple:#7154cc; --cyan:#0d6f8a;
  --accent-soft:rgba(43,98,217,0.08); --accent-soft-2:rgba(43,98,217,0.15);
  --shadow-accent:0 2px 10px rgba(43,98,217,0.22);
}
* { box-sizing: border-box; }
svg { flex: 0 0 auto; display: block; }
body {
  margin: 0; padding: 24px 16px 48px;
  background: #0b0e12; color: #e7ecf3;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
h1 { font-size: var(--fs-xxl); font-weight: 600; margin: 0 0 6px; }
.note { color: #94a2b6; font-size: var(--fs-m); margin: 0 0 24px; max-width: 900px; }
.frames { display: flex; gap: 24px; flex-wrap: wrap; }
.caption { font-size: var(--fs-s); color: #94a2b6; margin: 10px 0 0 4px; }

.phone { width: min(390px, 100%); height: 780px; border-radius: 28px; overflow: hidden;
         border: 1px solid #27323f; background: var(--bg); flex: 0 0 auto; }
@media (max-width: 460px) {
  body { padding: 18px 12px 40px; }
  .frames { gap: 18px; }
  .phone { height: 720px; border-radius: 22px; }
}
.screen { height: 100%; display: flex; flex-direction: column; background: var(--bg); color: var(--text); }
.head { padding: 20px 14px 10px; }
.title { font-size: var(--fs-xxl); font-weight: 600; letter-spacing: -0.01em; }
.pulse { margin-top: 10px; width: 11px; height: 11px; border-radius: 999px;
         background: var(--success); animation: pulse 1.8s ease-in-out infinite; }
.pulse.err { background: var(--danger); }
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .35; transform: scale(.8); }
}
.list { flex: 1; overflow-y: auto; padding: 2px 14px 14px; }
.tabbar { display: flex; background: var(--bg-side); border-top: 1px solid var(--border); }
.tab { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px;
       padding: 9px 0 12px; font-size: var(--fs-xs); color: var(--text-dim); }
.tab.active { color: var(--accent); }

/* Компактные плитки: две в ряд */
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.tile { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-l);
        padding: 12px; display: flex; flex-direction: column; min-height: 158px; }
.trow { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.chip { width: 28px; height: 28px; border-radius: var(--radius-xs); flex: 0 0 auto;
        display: flex; align-items: center; justify-content: center; }
/* Плашки как у значков в настройках iOS: сплошной цвет, белый глиф */
/* Плашки: сплошной цвет с лёгким объёмом — светлее сверху, темнее снизу */
.tint-gate, .tint-wide { background: linear-gradient(180deg, #217347, #174f31); color: #fff; }
.tint-barrier { background: linear-gradient(180deg, #d97a0f, #a85800); color: #fff; }
.tint-relay { background: linear-gradient(180deg, #a967cf, #8344a8); color: #fff; }
[data-theme="dark"] .tint-gate, [data-theme="dark"] .tint-wide {
  background: linear-gradient(180deg, #39a96f, #27744c); }
[data-theme="dark"] .tint-barrier { background: linear-gradient(180deg, #d97a0f, #a85800); }
[data-theme="dark"] .tint-relay { background: linear-gradient(180deg, #c76ff0, #9b4ec4); }
.tname { margin-top: 8px; font-size: var(--fs-l); font-weight: 600; line-height: 1.25; }
.tsub { margin-top: 2px; font-size: var(--fs-xs); color: var(--text-dim);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status { font-size: var(--fs-xs); font-weight: 500; white-space: nowrap; }
.status.ok { color: var(--success); }
.status.warn { color: var(--warn); }
.status.err { color: var(--danger); }
.status.dim { color: var(--text-dim); }

.btns { display: flex; gap: 6px; margin-top: auto; padding-top: 8px; }
.btn { flex: 1; height: var(--control-h); display: inline-flex; align-items: center;
       justify-content: center; gap: 5px; border-radius: var(--radius-s);
       border: 1px solid var(--border); background: rgba(128,128,128,0.08);
       color: var(--text); font-family: inherit; font-size: var(--fs-s);
       font-weight: 500; cursor: pointer; padding: 0 6px; }
.btn.accent { background: var(--accent-soft); border-color: transparent; color: var(--accent); }
.btn.primary { background: var(--accent-fill); border-color: var(--accent-fill);
               color: #fff; box-shadow: var(--shadow-accent); }
.btn.warn { background: rgba(251,191,36,0.12); border-color: rgba(251,191,36,0.35);
            color: var(--warn); }
.btn:disabled { opacity: .5; }

.srow { display: flex; align-items: center; justify-content: space-between;
        min-height: 42px; padding: 0 14px; font-size: var(--fs-l);
        background: var(--card); border: 1px solid var(--border); }
.srow:first-child { border-radius: var(--radius-l) var(--radius-l) 0 0; }
.srow:last-child { border-radius: 0 0 var(--radius-l) var(--radius-l); }
.srow + .srow { border-top: none; }
.srow .dim { color: var(--text-dim); font-size: var(--fs-m); }
.srow .tick { color: var(--accent); display: flex; }
.srow .chev { color: var(--text-dim); display: flex; }
.slabel { font-size: var(--fs-xs); color: var(--text-dim); text-transform: uppercase;
          letter-spacing: .06em; margin: 12px 0 6px 4px; font-weight: 600; }
.field-label { font-size: var(--fs-s); color: var(--text-dim); margin: 10px 0 5px 4px; }
.input { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-s);
         padding: 9px 11px; font-size: var(--fs-s); color: var(--text); }
.input.mono { font-family: "SF Mono", ui-monospace, Consolas, monospace; }
.box { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-l);
       padding: 4px 12px 12px; }
.group { display: flex; flex-direction: column; }
"""


def build():
    icons = lucide.load()
    main = grid([
        tile("Калитка", "Gate-IP · вход и выход", "Готов", "ok", "DoorOpen", "tint-gate",
             [("Вход", "accent", "LogIn"), ("Выход", "", "LogOut")]),
        tile("Шлагбаум", "Home Assistant · cover", "Открыто", "ok", "Fence", "tint-barrier",
             [("Закрыть", "", None)]),
        tile("КПП производство", "Gate-IP · 6 дверей", "Открывается…", "warn", "DoorOpen", "tint-gate",
             [("Стоп", "warn", "Square")]),
        tile("Северные ворота склад №3", "Gate-IP · только вход", "Нет связи", "err", "DoorClosed", "tint-wide",
             [("Вход", "", "LogIn")]),
        tile("Ворота", "Gate-IP · вход и выход", "Готов", "ok", "DoorOpen", "tint-wide",
             [("Вход", "accent", "LogIn"), ("Выход", "", "LogOut")]),
        tile("Реле освещения", "Tasmota · реле 1", "Выключено", "dim", "Power", "tint-relay",
             [("Включить", "accent", "Power")]),
    ])

    settings = "\n".join([
        '      <div class="slabel">Оформление</div>',
        '      <div class="group">',
        settings_row("Светлая"),
        settings_row("Тёмная", check=True),
        settings_row("Системная"),
        '      </div>',
        '      <div class="slabel">Подключение</div>',
        '      <div class="box">',
        field("Адрес Home Assistant", "http://192.168.2.39:8123"),
        field("Долгоживущий токен", "••••••••••••••"),
        '      </div>',
        '      <div class="slabel">Gate-IP</div>',
        '      <div class="group">',
        settings_row("Мост", value="на связи"),
        settings_row("Загрузить двери", chevron=True),
        '      </div>',
        '      <div class="slabel">Устройства</div>',
        '      <div class="group">',
        settings_row("Калитка", value="Gate-IP", chevron=True),
        settings_row("Шлагбаум", value="Home Assistant", chevron=True),
        settings_row("КПП производство", value="Gate-IP", chevron=True),
        '      </div>',
    ])

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Доступ — макет в стиле панели sing-box</title>
<style>{CSS}
</style>
</head>
<body>
<h1>Приложение «Доступ»</h1>
<p class="note">Оформление панели sing-box: её палитра, радиусы, высота элементов и иконки Lucide.
Устройства — компактные плитки по две в ряд, у каждого типа свой цвет значка: калитка зелёная,
ворота синие, шлагбаум оранжевый, реле сиреневое. Название занимает две строки и подбирает кегль,
поэтому длинное имя видно целиком.</p>
<div class="frames">
{screen("Доступ", "Мост СКУД доступен", main, active_tab=0, theme="light")}
{screen("Доступ", "Мост СКУД доступен", main, active_tab=0, theme="dark")}
{screen("Настройки", "", settings, active_tab=1, theme="light")}
</div>
<p class="caption">Слева — светлая тема, в центре — тёмная (как в панели по умолчанию), справа — настройки.</p>
</body>
</html>
"""
    (OUT / "mockup.html").write_text(html, encoding="utf-8")
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print("готово: mockup.html и index.html")
    print("иконок в наборе:", len(icons))


if __name__ == "__main__":
    build()
