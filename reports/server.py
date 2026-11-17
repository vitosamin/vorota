#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""СКУД Gate — веб-сервис мониторинга и отчётов.

Запуск:  python3 server.py [порт]        (по умолчанию 8095 из gate.config.json)
Вход:    логин/пароль из gate.config.json → auth (по умолчанию vitosamin)

Возможности:
    • вход по логину/паролю, сессия в подписанной cookie (12 часов);
    • мониторинг вживую: Server-Sent Events (/api/stream) + опрос;
    • отчёты посещаемости, графики, выгрузка в 1С (CSV cp1251) и Excel.
"""

import base64
import csv
import datetime as dt
import hashlib
import hmac
import io
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gate

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
PORT = int(os.environ.get("GATE_PORT") or gate.CFG.get("port", 8095))

AUTH = gate.CFG.get("auth", {})
AUTH_USER = AUTH.get("user", "vitosamin")
AUTH_PASS = AUTH.get("password", "Admin910327")
REALM = AUTH.get("realm", "SKUD Gate")
SESSION_HOURS = int(AUTH.get("session_hours", 12))
SECRET = (gate.CFG.get("secret") or "gate-skud-secret").encode("utf-8")
COOKIE = "gate_session"

sync_lock = threading.Lock()
last_sync = {"at": None, "result": None, "error": None}


# --------------------------------------------------------------------------
# авторизация
# --------------------------------------------------------------------------

def make_token(user):
    exp = int(time.time()) + SESSION_HOURS * 3600
    payload = "%s|%d" % (user, exp)
    sig = hmac.new(SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return "%s|%s" % (payload, sig)


def check_token(token):
    if not token or token.count("|") != 2:
        return None
    user, exp, sig = token.rsplit("|", 2)
    payload = "%s|%s" % (user, exp)
    good = hmac.new(SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(good, sig):
        return None
    try:
        if int(exp) < time.time():
            return None
    except ValueError:
        return None
    return user


def parse_cookies(header):
    out = {}
    for part in (header or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def check_password(user, password):
    return hmac.compare_digest(user or "", AUTH_USER) and hmac.compare_digest(password or "", AUTH_PASS)


# --------------------------------------------------------------------------
# автосинхронизация
# --------------------------------------------------------------------------

def do_sync(days=None):
    if not sync_lock.acquire(blocking=False):
        return {"busy": True}
    try:
        con = gate.connect()
        gate.init_db(con)
        today = dt.date.today()
        if days is None:
            res = gate.sync_events(today.isoformat(), today.isoformat(), con=con)
            tick = str(int(time.time() // 600))
            if gate.meta_get(con, "_cfg_tick", "0") != tick:
                gate.sync_config(con=con)
                gate.meta_set(con, "_cfg_tick", tick)
                con.commit()
        else:
            gate.sync_config(con=con)
            start = today - dt.timedelta(days=max(0, int(days)))
            res = gate.sync_events(start.isoformat(), today.isoformat(), con=con)
        con.close()
        last_sync.update({"at": dt.datetime.now().isoformat(timespec="seconds"),
                          "result": res, "error": None})
        return res
    except Exception as exc:                     # noqa: BLE001
        last_sync.update({"at": dt.datetime.now().isoformat(timespec="seconds"),
                          "error": str(exc)})
        return {"error": str(exc)}
    finally:
        sync_lock.release()


def sync_worker():
    while True:
        try:
            do_sync()
        except Exception:                        # noqa: BLE001
            pass
        time.sleep(45)


# --------------------------------------------------------------------------
# выгрузки
# --------------------------------------------------------------------------

COLS_1C = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("day", "Дата"),
    ("enter", "Приход"),
    ("exit", "Уход"),
    ("hours", "Часов"),
    ("passes", "Проходов"),
    ("late", "ОпозданиеМин"),
    ("early", "РаннийУходМин"),
    ("points", "КонтрольныеТочки"),
]

COLS_SUM = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("days", "Дней"),
    ("hours", "Часов"),
    ("avg_hours", "СреднеВДень"),
    ("passes", "Проходов"),
    ("late_days", "ДнейСОпозданием"),
    ("late_total", "ОпозданиеМинВсего"),
]

COLS_LATE = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("late_days", "ДнейСОпозданием"),
    ("late_total", "ОпозданиеМинВсего"),
    ("avg_late", "СреднееОпозданиеМин"),
    ("max_late", "МаксимальноеОпозданиеМин"),
    ("worst_day", "ХудшийДень"),
    ("worst_time", "ПриходВХудшийДень"),
]

COLS_ABS = [
    ("number", "ТабельныйНомер"),
    ("fio", "ФИО"),
    ("group", "Подразделение"),
    ("position", "Должность"),
    ("days", "ДнейВПериоде"),
    ("passes", "Проходов"),
]


def rows_to_delimited(rows, cols, sep=";", enc="cp1251", dec=",", header=True, quotes=True):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep, quoting=csv.QUOTE_ALL if quotes else csv.QUOTE_MINIMAL,
                   lineterminator="\r\n")
    if header:
        w.writerow([title for _, title in cols])
    for r in rows:
        line = []
        for key, _ in cols:
            v = r.get(key, "")
            if v is None:
                v = ""
            if key in ("hours", "avg_hours") and isinstance(v, float):
                v = ("%.2f" % v).replace(".", dec)
            line.append(v)
        w.writerow(line)
    text = buf.getvalue()
    data = text.encode(enc, "replace")
    if enc.lower().replace("-", "") == "utf8":
        data = b"\xef\xbb\xbf" + data
    return data


def rows_to_xls(rows, cols, title):
    """HTML-таблица с mso-стилями — Excel открывает с оформлением."""
    def esc(v):
        return (str(v if v is not None else "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    style = (
        "<style>"
        "table{border-collapse:collapse}"
        "th{background:#1f6feb;color:#fff;padding:6px 10px;border:1px solid #b6c2cf;"
        "font-family:'Segoe UI',Arial;font-size:12px}"
        "td{padding:4px 8px;border:1px solid #d5dde6;font-family:'Segoe UI',Arial;font-size:12px}"
        "td.n{text-align:center}tr.e td{background:#f4f7fb}"
        "h3{font-family:'Segoe UI',Arial;font-size:14px}"
        "</style>"
    )
    head = "".join("<th>%s</th>" % esc(t) for _, t in cols)
    body = []
    for i, r in enumerate(rows):
        tds = []
        for key, _ in cols:
            v = r.get(key, "")
            if key in ("hours", "avg_hours") and isinstance(v, float):
                v = ("%.2f" % v).replace(".", ",")
            cls = ' class="n"' if key in ("enter", "exit", "hours", "passes", "late", "early",
                                          "day", "days", "avg_hours") else ""
            tds.append("<td%s>%s</td>" % (cls, esc(v)))
        body.append('<tr%s>%s</tr>' % (' class="e"' if i % 2 else "", "".join(tds)))
    return ('<html xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="utf-8">'
            + style + '</head><body><h3>' + esc(title) + '</h3>'
            '<table><thead><tr>' + head + '</tr></thead><tbody>' + "".join(body)
            + '</tbody></table></body></html>').encode("utf-8")


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "GateSkud/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # -- утилиты ---------------------------------------------------------
    def q(self):
        parsed = urllib.parse.urlparse(self.path)
        return parsed.path, {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

    def current_user(self):
        user = check_token(parse_cookies(self.headers.get("Cookie")).get(COOKIE))
        if user:
            return user
        hdr = self.headers.get("Authorization") or ""
        if hdr.startswith("Basic "):
            try:
                raw = base64.b64decode(hdr[6:]).decode("utf-8", "replace")
                u, _, p = raw.partition(":")
                if check_password(u, p):
                    return u
            except Exception:                    # noqa: BLE001
                pass
        return None

    def send_bytes(self, data, ctype, filename=None, ascii_name=None, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            disp = "attachment; filename=\"%s\"; filename*=UTF-8''%s" % (
                ascii_name or "report.csv", urllib.parse.quote(filename))
            self.send_header("Content-Disposition", disp)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, obj, code=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                        "application/json; charset=utf-8", code=code)

    def redirect(self, to, cookie=None):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    # -- GET -------------------------------------------------------------
    def do_GET(self):
        path, q = self.q()
        try:
            if path == "/login":
                return self.serve_static("login.html", ctype="text/html; charset=utf-8")
            if path == "/logout":
                return self.redirect("/login", cookie="%s=; Path=/; Max-Age=0; HttpOnly" % COOKIE)
            if path == "/favicon.ico":
                return self.send_bytes(b"", "image/x-icon")

            user = self.current_user()
            if not user:
                if path.startswith("/api/") or path.startswith("/export/"):
                    return self.send_json({"error": "unauthorized"}, code=401)
                return self.redirect("/login")

            if path in ("/", "/index.html"):
                return self.serve_static("index.html")
            if path.startswith("/static/"):
                return self.serve_static(path[len("/static/"):])
            if path == "/api/status":
                return self.api_status()
            if path == "/api/kpi":
                return self.api_kpi(q)
            if path == "/api/live":
                return self.api_live(q)
            if path == "/api/stream":
                return self.api_stream(q)
            if path == "/api/presence":
                return self.api_presence(q)
            if path == "/api/points":
                return self.api_points()
            if path == "/api/groups":
                return self.api_groups()
            if path == "/api/report":
                return self.api_report(q)
            if path == "/api/analytics":
                return self.api_analytics(q)
            if path == "/api/events/summary":
                return self.api_events_summary(q)
            if path == "/api/events/list":
                return self.api_events_list(q)
            if path == "/api/late":
                return self.api_late(q)
            if path == "/api/person":
                return self.api_person(q)
            if path == "/api/sync":
                return self.send_json(do_sync(days=q.get("days")))
            if path == "/export/1c.csv":
                return self.export_1c(q)
            if path == "/export/report.xls":
                return self.export_xls(q)
            if path == "/print":
                return self.export_print(q)
            return self.send_bytes(b"not found", "text/plain; charset=utf-8", code=404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                return self.send_json({"error": str(exc)}, code=500)
            except Exception:                     # noqa: BLE001
                pass

    def serve_static(self, name, ctype=None):
        name = name.replace("..", "")
        full = os.path.join(WEB, name)
        if not os.path.isfile(full):
            return self.send_bytes(b"not found", "text/plain; charset=utf-8", code=404)
        ctype = ctype or {"html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
                          "js": "application/javascript; charset=utf-8",
                          "svg": "image/svg+xml", "png": "image/png",
                          "ico": "image/x-icon"}.get(name.rsplit(".", 1)[-1],
                                                     "application/octet-stream")
        with open(full, "rb") as fh:
            return self.send_bytes(fh.read(), ctype)

    # -- API -------------------------------------------------------------
    def api_status(self):
        con = gate.connect()
        gate.init_db(con)
        st = gate.db_status(con)
        con.close()
        st.update({"last_sync": last_sync, "server_time": dt.datetime.now().isoformat(timespec="seconds"),
                   "shift_start": gate.CFG.get("shift_start"), "shift_end": gate.CFG.get("shift_end")})
        return self.send_json(st)

    def api_kpi(self, q):
        con = gate.connect()
        day = q.get("day") or dt.date.today().isoformat()
        data = gate.kpi(con, day)
        con.close()
        return self.send_json(data)

    def api_live(self, q):
        con = gate.connect()
        day = q.get("day") or dt.date.today().isoformat()
        limit = min(500, int(q.get("limit", 60)))
        feed = gate.live_feed(con, day=day, limit=limit, only_passes=(q.get("all") != "1"))
        con.close()
        return self.send_json({"day": day, "items": feed})

    def api_presence(self, q):
        con = gate.connect()
        day = q.get("day") or dt.date.today().isoformat()
        people = gate.presence_now(con, day)
        con.close()
        return self.send_json({"day": day, "count": len(people), "people": people})

    def api_points(self):
        con = gate.connect()
        data = gate.points_list(con)
        con.close()
        return self.send_json(data)

    def api_groups(self):
        con = gate.connect()
        data = gate.groups_list(con)
        con.close()
        return self.send_json(data)

    def api_report(self, q):
        frm = q.get("from") or dt.date.today().isoformat()
        to = q.get("to") or frm
        view = q.get("view", "detail")
        con = gate.connect()
        if view == "absent":
            rows = gate.absent(con, frm, to, group=q.get("group"), search=q.get("search"))
            con.close()
            return self.send_json({"from": frm, "to": to, "view": view, "count": len(rows),
                                   "people": len(rows), "total_hours": 0, "late_days": 0,
                                   "rows": rows, "summary": rows})
        if view == "late":
            items = gate.late_report(con, frm, to, group=q.get("group"), search=q.get("search"),
                                     shift_start=q.get("shift_start"), shift_end=q.get("shift_end"))
            con.close()
            return self.send_json({"from": frm, "to": to, "view": view, "count": len(items),
                                   "people": len(items),
                                   "total_hours": 0,
                                   "late_days": sum(x["late_days"] for x in items),
                                   "rows": items, "summary": items})
        rows = gate.attendance(con, frm, to, group=q.get("group"), search=q.get("search"),
                               point=q.get("point"), include_deleted=q.get("deleted") == "1",
                               include_visitors=q.get("visitors") == "1",
                               shift_start=q.get("shift_start"), shift_end=q.get("shift_end"))
        summary = gate.attendance_summary(rows)
        con.close()
        return self.send_json({
            "from": frm, "to": to, "view": view,
            "count": len(rows), "people": len(summary),
            "total_hours": round(sum(r["hours"] or 0 for r in rows), 2),
            "late_days": sum(1 for r in rows if r["late"]),
            "rows": rows if view == "detail" else [],
            "summary": summary,
        })

    def api_analytics(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.analytics(con, frm, to, group=q.get("group"), point=q.get("point"))
        con.close()
        return self.send_json(data)

    def api_late(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        items = gate.late_report(con, frm, to, group=q.get("group"), search=q.get("search"),
                                 shift_start=q.get("shift_start"), shift_end=q.get("shift_end"))
        con.close()
        return self.send_json({"from": frm, "to": to, "count": len(items), "items": items})

    def api_person(self, q):
        try:
            uid = int(q.get("user_ptr", "0"))
        except ValueError:
            return self.send_json({"error": "user_ptr"}, code=400)
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=29)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.person_history(con, uid, frm, to)
        con.close()
        if data is None:
            return self.send_json({"error": "not found"}, code=404)
        return self.send_json(data)

    def api_events_summary(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.events_summary(con, frm, to)
        con.close()
        return self.send_json(data)

    def api_events_list(self, q):
        frm = q.get("from") or (dt.date.today() - dt.timedelta(days=6)).isoformat()
        to = q.get("to") or dt.date.today().isoformat()
        con = gate.connect()
        data = gate.events_list(
            con, frm, to,
            etype=q.get("type") or None,
            search=(q.get("search") or "").strip() or None,
            alarms_only=(q.get("alarms") == "1"),
            limit=max(1, min(500, int(q.get("limit", 200)))),
            offset=max(0, int(q.get("offset", 0))))
        con.close()
        return self.send_json(data)

    # -- живой поток (SSE) ------------------------------------------------
    def api_stream(self, q):
        day = q.get("day") or dt.date.today().isoformat()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        con = gate.connect()
        users = gate._user_names(con)

        def item_of(r):
            u = users.get(r["user_ptr"])
            return {"ts": r["ts"], "time": r["ts"][11:19], "user_ptr": r["user_ptr"],
                    "fio": u["fio"] if u else (r["name"] or "—"),
                    "group": u["group"] if u else "", "unit": r["unit"] or "",
                    "direction": gate.direction(r["unit"]), "message": r["message"] or "",
                    "event_type": r["event_type"], "event_code": r["event_code"]}

        def send(obj):
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        try:
            rows = con.execute(
                "SELECT * FROM events WHERE day=? AND event_type=1 AND event_code=8"
                " ORDER BY idx DESC LIMIT 30", (day,)).fetchall()
            send({"type": "init", "day": day, "items": [item_of(r) for r in rows]})
            last = con.execute("SELECT COALESCE(MAX(idx),0) m FROM events WHERE day=?", (day,)).fetchone()["m"]
            idle = 0
            while True:
                time.sleep(2.5)
                if dt.date.today().isoformat() != day:
                    send({"type": "reload"})
                    break
                new = con.execute(
                    "SELECT * FROM events WHERE day=? AND idx>? AND event_type=1 AND event_code=8"
                    " ORDER BY idx LIMIT 50", (day, last)).fetchall()
                if new:
                    for r in new:
                        last = max(last, r["idx"])
                    send({"type": "events", "items": [item_of(r) for r in new]})
                    idle = 0
                else:
                    idle += 1
                    if idle % 8 == 0:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            con.close()
            self.close_connection = True

    # -- выгрузки --------------------------------------------------------
    def _export_rows(self, q):
        frm = q.get("from") or dt.date.today().isoformat()
        to = q.get("to") or frm
        view = q.get("view")
        con = gate.connect()
        if view == "absent":
            rows = gate.absent(con, frm, to, group=q.get("group"), search=q.get("search"))
            con.close()
            return rows, COLS_ABS, frm, to
        if view == "late":
            rows = gate.late_report(con, frm, to, group=q.get("group"), search=q.get("search"),
                                    shift_start=q.get("shift_start"), shift_end=q.get("shift_end"))
            con.close()
            return rows, COLS_LATE, frm, to
        rows = gate.attendance(con, frm, to, group=q.get("group"), search=q.get("search"),
                               point=q.get("point"), include_deleted=q.get("deleted") == "1",
                               include_visitors=q.get("visitors") == "1",
                               shift_start=q.get("shift_start"), shift_end=q.get("shift_end"))
        con.close()
        if view == "summary":
            return gate.attendance_summary(rows), COLS_SUM, frm, to
        return rows, COLS_1C, frm, to

    def export_1c(self, q):
        rows, cols, frm, to = self._export_rows(q)
        enc = q.get("enc", "cp1251")
        sep = {"tab": "\t", "comma": ",", "semicolon": ";"}.get(q.get("sep", "semicolon"), ";")
        dec = q.get("dec", ",")
        data = rows_to_delimited(rows, cols, sep=sep, enc=enc, dec=dec,
                                 header=q.get("header", "1") == "1")
        name = "СКУД_Gate_%s_%s.csv" % (frm, to)
        return self.send_bytes(data, "text/csv; charset=%s" % enc, filename=name,
                               ascii_name="skud_gate_%s_%s.csv" % (frm, to))

    def export_xls(self, q):
        rows, cols, frm, to = self._export_rows(q)
        title = "Посещаемость СКУД Gate за %s" % (frm if frm == to else "%s — %s" % (frm, to))
        data = rows_to_xls(rows, cols, title)
        name = "Посещаемость_%s_%s.xls" % (frm, to)
        return self.send_bytes(data, "application/vnd.ms-excel; charset=utf-8", filename=name,
                               ascii_name="poseshchaemost_%s_%s.xls" % (frm, to))

    def export_print(self, q):
        rows, cols, frm, to = self._export_rows(q)
        title = "Отчёт посещаемости СКУД Gate"
        period = frm if frm == to else "%s — %s" % (frm, to)
        th = "".join("<th>%s</th>" % t for _, t in cols)
        trs = []
        for r in rows:
            tds = []
            for key, _ in cols:
                v = r.get(key, "")
                if key in ("hours", "avg_hours") and isinstance(v, float):
                    v = ("%.2f" % v).replace(".", ",")
                cls = ' class="num"' if key in ("enter", "exit", "hours", "passes", "late",
                                                "early", "day", "days", "avg_hours") else ""
                tds.append("<td%s>%s</td>" % (cls, v))
            trs.append("<tr>%s</tr>" % "".join(tds))
        html = PRINT_TEMPLATE.format(title=title, period=period, head=th, rows="\n".join(trs),
                                     n=len(rows), stamp=dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
        return self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    # -- POST ------------------------------------------------------------
    def do_POST(self):
        path, q = self.q()
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if path == "/login":
            form = {k: v[0] for k, v in urllib.parse.parse_qs(body.decode("utf-8", "replace")).items()}
            if check_password(form.get("username", ""), form.get("password", "")):
                cookie = "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax" % (
                    COOKIE, make_token(AUTH_USER), SESSION_HOURS * 3600)
                return self.redirect("/", cookie=cookie)
            return self.redirect("/login?e=1")
        if not self.current_user():
            return self.send_json({"error": "unauthorized"}, code=401)
        if path == "/api/sync":
            try:
                payload = json.loads(body or b"{}")
            except ValueError:
                payload = {}
            return self.send_json(do_sync(days=payload.get("days")))
        return self.send_bytes(b"not found", "text/plain; charset=utf-8", code=404)


PRINT_TEMPLATE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>{title} · {period}</title>
<style>
 body{{font:13px/1.45 "Segoe UI",system-ui,Arial,sans-serif;color:#111;margin:24px}}
 h1{{font-size:19px;margin:0 0 4px}} .sub{{color:#555;margin-bottom:14px}}
 table{{border-collapse:collapse;width:100%}}
 th{{background:#eef2f7;border:1px solid #c3ccd6;padding:6px 8px;text-align:left;font-size:12px}}
 td{{border:1px solid #d7dee6;padding:5px 8px;font-size:12px}}
 td.num{{text-align:center}} tr:nth-child(even) td{{background:#fafcfe}}
 .foot{{margin-top:12px;color:#666;font-size:11px}}
 @media print{{ body{{margin:8mm}} h1{{font-size:16px}} }}
</style></head><body>
<h1>{title}</h1>
<div class="sub">Период: <b>{period}</b> · записей: <b>{n}</b> · сформировано {stamp}</div>
<table><thead><tr>{head}</tr></thead><tbody>
{rows}
</tbody></table>
<div class="foot">Источник: СКУД Gate-IP, сервер 192.168.2.160 · отчёт «Ворота»</div>
</body></html>"""


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    gate.init_db()
    threading.Thread(target=sync_worker, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("СКУД Gate: http://0.0.0.0:%d/  вход: %s  (Ctrl+C — стоп)" % (port, AUTH_USER), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
