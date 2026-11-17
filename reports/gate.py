#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""СКУД Gate — чтение журнала событий и отчёты по посещаемости.

Источник: сервер Gate-IP, SMB-шара //192.168.2.160/GATE
    Server\\Events\\nYYMMDD.mdb  — суточный журнал событий (таблица Events)
    Server\\config.mdb          — сотрудники, подразделения, устройства

MDB читаются утилитами mdbtools (tools/mdbroot), результат складывается
в SQLite (data/gate.sqlite). Никаких внешних Python-зависимостей.
"""

import csv
import datetime as dt
import io
import json
import os
import re
import sqlite3
import shutil
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
EVENTS_DIR = os.path.join(DATA, "events")
DB_PATH = os.path.join(DATA, "gate.sqlite")
CONFIG_MDB = os.path.join(DATA, "config.mdb")
CFG = json.load(open(os.path.join(ROOT, "gate.config.json"), encoding="utf-8"))

def _tool(cfg_path, name):
    """Путь из конфига, иначе системная утилита из PATH."""
    if cfg_path and os.path.exists(cfg_path):
        return cfg_path
    return shutil.which(name) or cfg_path or name


def _tool_dir(cfg_dir, probe):
    """Каталог с утилитами: из конфига, иначе рядом с системной утилитой."""
    if cfg_dir and os.path.isdir(cfg_dir) and os.path.exists(os.path.join(cfg_dir, probe)):
        return cfg_dir
    w = shutil.which(probe)
    return os.path.dirname(w) if w else (cfg_dir or "")


MDB = _tool_dir(CFG.get("mdbtools"), "mdb-export")
MDB_LIB = CFG.get("mdb_lib") or ""
SMB = _tool(CFG.get("smbclient"), "smbclient")
SMB_LIB = CFG.get("smb_lib") or ""
SHARE = CFG["share"]
SMB_USER = CFG["user"]
SMB_PASS = CFG["password"]

_lock = threading.Lock()

# --------------------------------------------------------------------------
# процессы: smbclient / mdbtools
# --------------------------------------------------------------------------


def _env(libpath):
    env = dict(os.environ)
    if libpath:
        env["LD_LIBRARY_PATH"] = libpath + ":" + env.get("LD_LIBRARY_PATH", "")
    env["LANG"] = "C.UTF-8"
    return env


def smb_run(command, timeout=120):
    """Выполнить команду smbclient (-c ...) и вернуть stdout."""
    args = [SMB, SHARE, "-U", "%s%%%s" % (SMB_USER, SMB_PASS),
            "-m", "SMB3", "-p", "445", "-c", command]
    p = subprocess.run(args, capture_output=True, env=_env(SMB_LIB), timeout=timeout)
    out = p.stdout.decode("utf-8", "replace")
    out = "\n".join(l for l in out.splitlines() if "smb.conf" not in l)
    if p.returncode != 0:
        raise RuntimeError("smbclient: %s" % (p.stderr.decode("utf-8", "replace").strip() or out.strip()))
    return out


_LS_RE = re.compile(r"^\s+(?P<name>.+?)\s{2,}(?P<attr>[AD])\s+(?P<size>\d+)\s+(?P<mtime>\w{3} \w{3} [ \d]\d .+?)\s*$")


def smb_list(remote_dir):
    """Список файлов каталога: {имя: (размер, mtime, is_dir)}."""
    out = smb_run("cd %s; ls" % remote_dir)
    items = {}
    for line in out.splitlines():
        m = _LS_RE.match(line)
        if not m:
            continue
        name = m.group("name").strip()
        if name in (".", ".."):
            continue
        items[name] = (int(m.group("size")), m.group("mtime"), m.group("attr") == "D")
    return items


def smb_get(remote_dir, name, local_path):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    tmp = local_path + ".part"
    smb_run("cd %s; get %s %s" % (remote_dir, name, tmp))
    if not os.path.exists(tmp):
        raise RuntimeError("smbclient не сохранил %s" % name)
    os.replace(tmp, local_path)
    return os.path.getsize(local_path)


def mdb_export(mdb_path, table, timeout=180):
    """Таблица MDB → список словарей."""
    p = subprocess.run([os.path.join(MDB, "mdb-export"), mdb_path, table],
                       capture_output=True, env=_env(MDB_LIB), timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError("mdb-export %s: %s" % (table, p.stderr.decode("utf-8", "replace").strip()))
    text = p.stdout.decode("utf-8", "replace")
    if not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]


def mdb_tables(mdb_path):
    p = subprocess.run([os.path.join(MDB, "mdb-tables"), "-1", mdb_path],
                       capture_output=True, env=_env(MDB_LIB), timeout=60)
    return [t.strip() for t in p.stdout.decode("utf-8", "replace").split() if t.strip()]


# --------------------------------------------------------------------------
# SQLite
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    day         TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    ts          TEXT NOT NULL,          -- ISO, локальное время сервера Gate
    event_type  INTEGER,
    event_code  INTEGER,
    dev_ptr     INTEGER,
    rdr_ptr     INTEGER,
    user_ptr    INTEGER,
    alarm_status INTEGER,
    unit        TEXT,
    message     TEXT,
    name        TEXT,
    PRIMARY KEY (day, idx)
);
CREATE INDEX IF NOT EXISTS ix_events_ts   ON events(ts);
CREATE INDEX IF NOT EXISTS ix_events_user ON events(user_ptr, day);
CREATE INDEX IF NOT EXISTS ix_events_pass ON events(event_type, event_code, day);
CREATE INDEX IF NOT EXISTS ix_events_day_type ON events(day, event_type, alarm_status);

CREATE TABLE IF NOT EXISTS users (
    user_ptr   INTEGER PRIMARY KEY,
    number     TEXT,
    last_name  TEXT,
    first_name TEXT,
    father_name TEXT,
    group_ptr  INTEGER,
    position   TEXT,
    deleted    INTEGER DEFAULT 0,
    visitor    INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS groups (
    group_ptr INTEGER PRIMARY KEY,
    name      TEXT
);
CREATE TABLE IF NOT EXISTS devices (
    dev_ptr  INTEGER PRIMARY KEY,
    name     TEXT,
    dev_type INTEGER
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS days (
    day      TEXT PRIMARY KEY,
    rows     INTEGER,
    imported TEXT
);
"""


def connect():
    os.makedirs(DATA, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=20000")
    # SQLite lower()/LIKE не понимают кириллицу — добавляем свой lower
    con.create_function("lower_ru", 1, lambda v: (v or "").lower(), deterministic=True)
    con.create_function("instr_ru", 2,
                        lambda hay, needle: 1 if (needle or "").lower() in (hay or "").lower() else 0,
                        deterministic=True)
    return con


def init_db(con=None):
    own = con is None
    con = con or connect()
    con.executescript(SCHEMA)
    con.commit()
    if own:
        con.close()


def meta_get(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def meta_set(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))


# --------------------------------------------------------------------------
# разбор событий
# --------------------------------------------------------------------------

DT_FORMATS = ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S")


def parse_dt(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in DT_FORMATS:
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def direction(unit):
    """Направление прохода по названию точки: in / out / na."""
    u = (unit or "").lower()
    if "вход" in u:
        return "in"
    if "выход" in u:
        return "out"
    return "na"


def import_day(con, day, path):
    """Импортировать суточный MDB в SQLite. Возвращает число строк."""
    rows = mdb_export(path, "Events")
    prepared = []
    for r in rows:
        t = parse_dt(r.get("DateTime"))
        if t is None:
            continue
        try:
            idx = int(r.get("Index") or 0)
        except ValueError:
            idx = 0
        prepared.append((
            day, idx, t.isoformat(sep=" "),
            _int(r.get("EventType")), _int(r.get("EventCode")),
            _int(r.get("DevPtr")), _int(r.get("RdrPtr")), _int(r.get("UserPtr")),
            _int(r.get("AlarmStatus")),
            (r.get("Unit") or "").strip(), (r.get("Message") or "").strip(),
            (r.get("Name") or "").strip(),
        ))
    with _lock:
        con.execute("DELETE FROM events WHERE day=?", (day,))
        con.executemany(
            "INSERT OR REPLACE INTO events(day,idx,ts,event_type,event_code,dev_ptr,rdr_ptr,user_ptr,alarm_status,unit,message,name)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", prepared)
        con.execute("INSERT INTO days(day,rows,imported) VALUES(?,?,?)"
                    " ON CONFLICT(day) DO UPDATE SET rows=excluded.rows, imported=excluded.imported",
                    (day, len(prepared), dt.datetime.now().isoformat(timespec="seconds")))
        con.commit()
    return len(prepared)


def _int(v):
    try:
        return int(str(v).strip() or 0)
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------
# синхронизация с сервером Gate
# --------------------------------------------------------------------------


def sync_config(force=False, con=None):
    """Скачать config.mdb и обновить сотрудников/подразделения/устройства."""
    own = con is None
    con = con or connect()
    init_db(con)
    listing = smb_list("Server")
    if "config.mdb" not in listing:
        raise RuntimeError("config.mdb не найден в Server")
    size, mtime, _ = listing["config.mdb"]
    stamp = "%s|%s" % (size, mtime)
    if not force and meta_get(con, "config_stamp") == stamp and os.path.exists(CONFIG_MDB):
        if own:
            con.close()
        return False
    smb_get("Server", "config.mdb", CONFIG_MDB)

    users = []
    for r in mdb_export(CONFIG_MDB, "Users"):
        last = (r.get("LastName") or r.get("Фамилия") or "").strip()
        first = (r.get("FirstName") or r.get("Имя") or "").strip()
        father = (r.get("FatherName") or r.get("Отчество") or "").strip()
        users.append((_int(r.get("UserPtr")), (r.get("Number") or "").strip(), last, first, father,
                      _int(r.get("GroupPtr")), (r.get("Details1") or "").strip(),
                      1 if str(r.get("Deleted")).strip() in ("1", "-1", "True") else 0,
                      1 if str(r.get("Visitor")).strip() in ("1", "-1", "True") else 0))
    groups = [(_int(r.get("GroupPtr")), (r.get("Name") or "").strip()) for r in mdb_export(CONFIG_MDB, "Groups")]
    devices = [(_int(r.get("DevPtr")), (r.get("Name") or "").strip(), _int(r.get("DevType")))
               for r in mdb_export(CONFIG_MDB, "Devices")]

    with _lock:
        con.execute("DELETE FROM users")
        con.executemany("INSERT OR REPLACE INTO users VALUES(?,?,?,?,?,?,?,?,?)", users)
        con.execute("DELETE FROM groups")
        con.executemany("INSERT OR REPLACE INTO groups VALUES(?,?)", groups)
        con.execute("DELETE FROM devices")
        con.executemany("INSERT OR REPLACE INTO devices VALUES(?,?,?)", devices)
        meta_set(con, "config_stamp", stamp)
        meta_set(con, "config_synced", dt.datetime.now().isoformat(timespec="seconds"))
        con.commit()
    if own:
        con.close()
    return True


def remote_event_days():
    """{дата ISO: (имя файла, размер, mtime)} для всех суточных журналов."""
    out = {}
    for name, (size, mtime, isdir) in smb_list(CFG["events_remote"]).items():
        if isdir:
            continue
        m = re.fullmatch(r"n(\d{2})(\d{2})(\d{2})\.mdb", name)
        if not m:
            continue
        yy, mm, dd = (int(x) for x in m.groups())
        try:
            day = dt.date(2000 + yy, mm, dd).isoformat()
        except ValueError:
            continue
        out[day] = (name, size, mtime)
    return out


def sync_events(from_day, to_day, force=False, con=None, progress=None):
    """Догрузить суточные журналы за период. Возвращает статистику."""
    own = con is None
    con = con or connect()
    init_db(con)
    remote = remote_event_days()
    days = [d for d in sorted(remote) if from_day <= d <= to_day]
    got, skipped, missing = 0, 0, []
    for day in days:
        name, size, mtime = remote[day]
        local = os.path.join(EVENTS_DIR, name)
        stamp = "%s|%s" % (size, mtime)
        if not force and meta_get(con, "day_stamp:" + day) == stamp and os.path.exists(local):
            skipped += 1
            continue
        smb_get(CFG["events_remote"], name, local)
        n = import_day(con, day, local)
        with _lock:
            meta_set(con, "day_stamp:" + day, stamp)
            con.commit()
        got += 1
        if progress:
            progress(day, n)
    want = []
    d = dt.date.fromisoformat(from_day)
    end = dt.date.fromisoformat(to_day)
    while d <= end:
        if d.isoformat() not in remote:
            missing.append(d.isoformat())
        d += dt.timedelta(days=1)
    if own:
        con.close()
    return {"days": len(days), "downloaded": got, "cached": skipped, "missing": missing}


def sync_all(days_back=7, con=None):
    today = dt.date.today()
    start = today - dt.timedelta(days=days_back)
    sync_config(con=con)
    return sync_events(start.isoformat(), today.isoformat(), con=con)


# --------------------------------------------------------------------------
# отчёты
# --------------------------------------------------------------------------

PASS_TYPE, PASS_CODE = 1, 8          # «Проход совершен» — факт прохода


def _user_names(con):
    out = {}
    for r in con.execute("SELECT u.user_ptr, u.number, u.last_name, u.first_name, u.father_name,"
                         " u.position, u.deleted, u.visitor, g.name AS grp"
                         " FROM users u LEFT JOIN groups g ON g.group_ptr=u.group_ptr"):
        fio = " ".join(x for x in (r["last_name"], r["first_name"], r["father_name"]) if x).strip()
        out[r["user_ptr"]] = {
            "user_ptr": r["user_ptr"],
            "number": r["number"] or "",
            "fio": fio or ("ID %s" % r["user_ptr"]),
            "position": r["position"] or "",
            "group": r["grp"] or "Без подразделения",
            "deleted": bool(r["deleted"]),
            "visitor": bool(r["visitor"]),
        }
    return out


def live_feed(con, day=None, limit=40, only_passes=True):
    day = day or dt.date.today().isoformat()
    where = "day=? AND event_type=1 AND event_code=8" if only_passes else "day=?"
    rows = con.execute(
        "SELECT ts, user_ptr, unit, message, name, event_type, event_code FROM events"
        " WHERE %s ORDER BY ts DESC, idx DESC LIMIT ?" % where, (day, limit)).fetchall()
    users = _user_names(con)
    feed = []
    for r in rows:
        u = users.get(r["user_ptr"])
        feed.append({
            "ts": r["ts"],
            "time": r["ts"][11:19],
            "user_ptr": r["user_ptr"],
            "fio": u["fio"] if u else (r["name"] or "—"),
            "number": u["number"] if u else "",
            "group": u["group"] if u else "",
            "unit": r["unit"] or "",
            "direction": direction(r["unit"]),
            "message": r["message"] or "",
            "event_type": r["event_type"],
            "event_code": r["event_code"],
        })
    return feed


def kpi(con, day=None):
    day = day or dt.date.today().isoformat()
    users = _user_names(con)
    passes = con.execute(
        "SELECT ts, user_ptr, unit FROM events WHERE day=? AND event_type=? AND event_code=?"
        " ORDER BY ts", (day, PASS_TYPE, PASS_CODE)).fetchall()
    present = {}
    ins = outs = 0
    people = set()
    by_hour = {}
    for p in passes:
        people.add(p["user_ptr"])
        d = direction(p["unit"])
        if d == "in":
            ins += 1
        elif d == "out":
            outs += 1
        if p["user_ptr"]:
            present[p["user_ptr"]] = d
        h = p["ts"][11:13]
        by_hour[h] = by_hour.get(h, 0) + 1
    on_site = [pid for pid, d in present.items() if d == "in" and pid in users]
    alerts = con.execute(
        "SELECT COUNT(*) c FROM events WHERE day=? AND event_type=2 AND alarm_status=1", (day,)).fetchone()["c"]

    prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    cutoff = dt.datetime.now().strftime("%H:%M:%S") if day == dt.date.today().isoformat() else "23:59:59"
    pc = con.execute(
        "SELECT COUNT(*) c, COUNT(DISTINCT user_ptr) u FROM events WHERE day=? AND event_type=?"
        " AND event_code=? AND ts<=?", (prev, PASS_TYPE, PASS_CODE, prev + " " + cutoff)).fetchone()

    return {
        "day": day,
        "passes": len(passes),
        "people": len(people),
        "in": ins,
        "out": outs,
        "on_site": len(on_site),
        "on_site_people": [{"user_ptr": pid, "fio": users[pid]["fio"], "group": users[pid]["group"]}
                           for pid in sorted(on_site, key=lambda x: users[x]["fio"])],
        "alerts": alerts,
        "by_hour": by_hour,
        "prev": {"day": prev, "passes": pc["c"] or 0, "people": pc["u"] or 0, "cutoff": cutoff},
    }


def _points(point):
    """Нормализовать выбор контрольных точек: строка, список или «A|B»."""
    if not point:
        return []
    if isinstance(point, str):
        parts = point.split("|")          # названия точек могут содержать запятые
    else:
        parts = list(point)
    out = []
    for x in parts:
        x = str(x).strip()
        if x and x not in out:
            out.append(x)
    return out


def _point_sql(point, column="unit"):
    """SQL-условие по выбранным точкам (ИЛИ по подстроке) и параметры."""
    pts = _points(point)
    if not pts:
        return "", []
    clauses = ["%s LIKE ?" % column] * len(pts)
    return " AND (" + " OR ".join(clauses) + ")", ["%" + p + "%" for p in pts]


def attendance(con, from_day, to_day, group=None, search=None, point=None,
               include_deleted=False, include_visitors=False,
               shift_start=None, shift_end=None, user_ptr=None):
    """Свод посещаемости по сотрудникам и дням.

    Приход — первый проход дня, уход — последний проход дня.
    `point` — фильтр по контрольной точке (подстрока названия, напр. «КПП1»).
    """
    users = _user_names(con)
    sql = ("SELECT day, ts, user_ptr, unit, message FROM events"
           " WHERE day BETWEEN ? AND ? AND event_type=? AND event_code=? AND user_ptr>0")
    params = [from_day, to_day, PASS_TYPE, PASS_CODE]
    frag, pparams = _point_sql(point)
    sql += frag
    params += pparams
    if user_ptr:
        sql += " AND user_ptr = ?"
        params.append(int(user_ptr))
    sql += " ORDER BY ts"
    passes = con.execute(sql, params).fetchall()

    today = dt.date.today().isoformat()
    now = dt.datetime.now()
    shift_start = shift_start or CFG.get("shift_start", "08:00")
    shift_end = shift_end or CFG.get("shift_end", "17:00")
    sh_s = dt.time.fromisoformat(shift_start)
    sh_e = dt.time.fromisoformat(shift_end)

    per = {}
    for p in passes:
        pid = p["user_ptr"]
        u = users.get(pid)
        if u is None:
            continue
        if u["visitor"] and not include_visitors:
            continue
        if u["deleted"] and not include_deleted:
            continue
        if group and group not in ("", "all") and u["group"] != group:
            continue
        if search:
            needle = search.lower()
            if needle not in u["fio"].lower() and needle not in u["number"].lower():
                continue
        rec = per.setdefault((pid, p["day"]), {
            "user": u, "day": p["day"], "enter": None, "exit": None,
            "first_in": None, "last_out": None, "passes": 0,
            "in_unit": "", "out_unit": "", "points": set(), "last_dir": "",
        })
        t = p["ts"]
        rec["passes"] += 1
        if rec["enter"] is None or t < rec["enter"]:
            rec["enter"] = t
        if rec["exit"] is None or t > rec["exit"]:
            rec["exit"] = t
            rec["last_dir"] = direction(p["unit"])
        d = direction(p["unit"])
        if d == "in" and (rec["first_in"] is None or t < rec["first_in"]):
            rec["first_in"] = t
            rec["in_unit"] = p["unit"]
        if d == "out" and (rec["last_out"] is None or t > rec["last_out"]):
            rec["last_out"] = t
            rec["out_unit"] = p["unit"]
        rec["points"].add(p["unit"])

    rows = []
    for (pid, day), rec in per.items():
        enter, exit_ = rec["enter"], rec["exit"]
        t1 = dt.datetime.fromisoformat(enter)
        t2 = dt.datetime.fromisoformat(exit_)
        open_now = (day == today) and rec["last_dir"] == "in"
        end = now if open_now else t2
        hours = round(max(0.0, (end - t1).total_seconds() / 3600.0), 2)
        late = max(0, int((dt.datetime.combine(t1.date(), t1.time())
                           - dt.datetime.combine(t1.date(), sh_s)).total_seconds() // 60))
        early = None
        if not open_now:
            early = max(0, int((dt.datetime.combine(t2.date(), sh_e)
                                - dt.datetime.combine(t2.date(), t2.time())).total_seconds() // 60))
        rows.append({
            "user_ptr": pid,
            "number": rec["user"]["number"],
            "fio": rec["user"]["fio"],
            "group": rec["user"]["group"],
            "position": rec["user"]["position"],
            "day": day,
            "enter": enter[11:19],
            "exit": exit_[11:19],
            "first_in": rec["first_in"][11:19] if rec["first_in"] else "",
            "last_out": rec["last_out"][11:19] if rec["last_out"] else "",
            "hours": hours,
            "passes": rec["passes"],
            "late": late,
            "early": early,
            "open": open_now,
            "in_unit": rec["in_unit"],
            "out_unit": rec["out_unit"],
            "points": ", ".join(sorted(rec["points"])),
        })
    rows.sort(key=lambda r: (r["day"], r["enter"], r["fio"]))
    return rows


def attendance_summary(rows):
    """Итоги по сотрудникам за период."""
    agg = {}
    for r in rows:
        a = agg.setdefault(r["user_ptr"], {
            "user_ptr": r["user_ptr"], "fio": r["fio"], "number": r["number"],
            "group": r["group"], "position": r["position"], "days": 0, "hours": 0.0,
            "late_total": 0, "late_days": 0, "early_total": 0, "passes": 0, "open": False})
        a["days"] += 1
        a["hours"] += r["hours"] or 0
        a["passes"] += r["passes"]
        a["open"] = a["open"] or r["open"]
        if r["late"]:
            a["late_total"] += r["late"]
            a["late_days"] += 1
        if r["early"]:
            a["early_total"] += r["early"]
    out = list(agg.values())
    for a in out:
        a["hours"] = round(a["hours"], 2)
        a["avg_hours"] = round(a["hours"] / a["days"], 2) if a["days"] else 0
    out.sort(key=lambda a: a["fio"])
    return out


_SERVICE_NAME = re.compile(r"^(ID \d+|\d+|[A-Za-z_\-\.]{0,3})$")


def _real_name(fio):
    """Отсеять служебные записи без настоящего имени («1», «ID 1727»)."""
    fio = (fio or "").strip()
    return len(fio) >= 3 and not _SERVICE_NAME.match(fio)


def absent(con, from_day, to_day, group=None, search=None, user_ptr=None, point=None):
    """Сотрудники без единого прохода за период («не приходили»).

    Если заданы контрольные точки — считаются только проходы через них.
    """
    users = _user_names(con)
    frag, pparams = _point_sql(point)
    seen = {r["user_ptr"] for r in con.execute(
        "SELECT DISTINCT user_ptr FROM events WHERE day BETWEEN ? AND ? AND event_type=? AND event_code=?"
        " AND user_ptr>0" + frag, [from_day, to_day, PASS_TYPE, PASS_CODE] + pparams)}
    d0 = dt.date.fromisoformat(from_day)
    d1 = dt.date.fromisoformat(to_day)
    days = (d1 - d0).days + 1
    out = []
    for pid, u in users.items():
        if user_ptr and pid != int(user_ptr):
            continue
        if u["deleted"] or u["visitor"] or pid in seen:
            continue
        if not _real_name(u["fio"]):
            continue
        if group and group not in ("", "all") and u["group"] != group:
            continue
        if search:
            needle = search.lower()
            if needle not in u["fio"].lower() and needle not in u["number"].lower():
                continue
        out.append({"user_ptr": pid, "number": u["number"], "fio": u["fio"], "group": u["group"],
                    "position": u["position"], "days": days, "hours": 0.0, "passes": 0,
                    "late": 0, "early": None, "open": False, "enter": "", "exit": "",
                    "points": "", "day": from_day})
    out.sort(key=lambda r: r["fio"])
    return out


def analytics(con, from_day, to_day, group=None, point=None):
    """Данные для графиков: динамика по дням, часы, подразделения, опоздания."""
    rows = attendance(con, from_day, to_day, group=group, point=point)
    users = _user_names(con)

    by_day = {}
    for r in rows:
        d = by_day.setdefault(r["day"], {"day": r["day"], "passes": 0, "hours": 0.0,
                                         "late": 0, "people": set()})
        d["passes"] += r["passes"]
        d["hours"] += r["hours"] or 0
        d["people"].add(r["user_ptr"])
        if r["late"]:
            d["late"] += 1
    days = []
    cur = dt.date.fromisoformat(from_day)
    end = dt.date.fromisoformat(to_day)
    while cur <= end:
        key = cur.isoformat()
        d = by_day.get(key, {"day": key, "passes": 0, "hours": 0.0, "late": 0, "people": set()})
        days.append({"day": key, "passes": d["passes"], "hours": round(d["hours"], 2),
                     "late": d["late"], "people": len(d["people"]),
                     "weekday": cur.weekday()})
        cur += dt.timedelta(days=1)

    sql = ("SELECT day, ts, unit, user_ptr FROM events WHERE day BETWEEN ? AND ?"
           " AND event_type=? AND event_code=? AND user_ptr>0")
    params = [from_day, to_day, PASS_TYPE, PASS_CODE]
    frag, pparams = _point_sql(point)
    sql += frag
    params += pparams
    hourly = [{"hour": h, "in": 0, "out": 0} for h in range(24)]
    heat = [[0] * 24 for _ in range(7)]
    for ev in con.execute(sql, params):
        u = users.get(ev["user_ptr"])
        if u is None:
            continue
        if group and group not in ("", "all") and u["group"] != group:
            continue
        h = int(ev["ts"][11:13])
        d = direction(ev["unit"])
        if d == "in":
            hourly[h]["in"] += 1
        elif d == "out":
            hourly[h]["out"] += 1
        heat[dt.date.fromisoformat(ev["day"]).weekday()][h] += 1

    grp = {}
    for r in rows:
        g = grp.setdefault(r["group"], {"group": r["group"], "people": set(),
                                        "days": 0, "hours": 0.0, "late": 0})
        g["people"].add(r["user_ptr"])
        g["days"] += 1
        g["hours"] += r["hours"] or 0
        if r["late"]:
            g["late"] += 1
    groups = sorted(({"group": g["group"], "people": len(g["people"]), "days": g["days"],
                      "hours": round(g["hours"], 1), "late": g["late"]} for g in grp.values()),
                    key=lambda x: -x["days"])[:12]

    buckets = [("до 4 ч", 0), ("4–8 ч", 0), ("8–10 ч", 0), ("10–12 ч", 0), ("12 ч и более", 0)]
    for r in rows:
        h = r["hours"] or 0
        idx = 0 if h < 4 else 1 if h < 8 else 2 if h < 10 else 3 if h < 12 else 4
        buckets[idx] = (buckets[idx][0], buckets[idx][1] + 1)

    top_late = sorted(attendance_summary(rows), key=lambda a: -a["late_total"])[:10]

    d0 = dt.date.fromisoformat(from_day)
    d1 = dt.date.fromisoformat(to_day)
    n = (d1 - d0).days + 1
    prev_rows = attendance(con, (d0 - dt.timedelta(days=n)).isoformat(),
                           (d0 - dt.timedelta(days=1)).isoformat(), group=group, point=point)

    return {
        "from": from_day, "to": to_day,
        "by_day": days,
        "by_hour": hourly,
        "heatmap": heat,
        "groups": groups,
        "hours_dist": [{"label": b[0], "count": b[1]} for b in buckets],
        "late": {"on_time": sum(1 for r in rows if not r["late"]),
                 "late": sum(1 for r in rows if r["late"])},
        "top_late": [{"fio": a["fio"], "group": a["group"], "late_total": a["late_total"],
                      "late_days": a["late_days"]} for a in top_late
                     if a["late_total"] and _real_name(a["fio"])
                     and "гост" not in (a["group"] or "").lower()],
        "totals": {"rows": len(rows), "people": len({r["user_ptr"] for r in rows}),
                   "hours": round(sum(r["hours"] or 0 for r in rows), 2)},
        "prev_totals": {"rows": len(prev_rows),
                        "people": len({r["user_ptr"] for r in prev_rows}),
                        "hours": round(sum(r["hours"] or 0 for r in prev_rows), 2),
                        "late": sum(1 for r in prev_rows if r["late"])},
    }



# --------------------------------------------------------------------------
# журнал событий СКУД (все типы: устройства, тревоги, связь, операторы…)
# --------------------------------------------------------------------------

EVENT_TYPES = {
    1: "События пользователей",
    2: "События устройств",
    3: "Диагностика связи",
    4: "Запуск-остановка",
    5: "Действия операторов",
    6: "Удаление пользователей",
}


def events_summary(con, from_day, to_day):
    """Сводка по журналу: по типам, дням, часам и частым сообщениям."""
    params = (from_day, to_day)
    types = [{"type": r["et"], "title": EVENT_TYPES.get(r["et"], "Тип %s" % r["et"]),
              "count": r["c"], "alarms": r["al"] or 0}
             for r in con.execute(
                 "SELECT event_type et, COUNT(*) c, COALESCE(SUM(alarm_status),0) al"
                 " FROM events WHERE day BETWEEN ? AND ? GROUP BY event_type", params)]
    types.sort(key=lambda x: -x["count"])
    total = sum(t["count"] for t in types)
    alarms = sum(t["alarms"] for t in types)
    top = [{"message": r["message"] or "—", "type": r["et"], "count": r["c"]}
           for r in con.execute(
               "SELECT message, event_type et, COUNT(*) c FROM events"
               " WHERE day BETWEEN ? AND ? GROUP BY message, event_type"
               " ORDER BY c DESC LIMIT 12", params)]
    by_day = [{"day": r["d"], "count": r["c"], "alarms": r["al"] or 0}
              for r in con.execute(
                  "SELECT day d, COUNT(*) c, COALESCE(SUM(alarm_status),0) al FROM events"
                  " WHERE day BETWEEN ? AND ? GROUP BY day ORDER BY day", params)]
    by_hour = [{"hour": r["h"], "count": r["c"]}
               for r in con.execute(
                   "SELECT CAST(substr(ts,12,2) AS INTEGER) h, COUNT(*) c FROM events"
                   " WHERE day BETWEEN ? AND ? GROUP BY h ORDER BY h", params)]
    messages = [{"message": (r["message"] or "—"), "type": r["et"], "count": r["c"]}
                for r in con.execute(
                    "SELECT message, MIN(event_type) et, COUNT(*) c FROM events"
                    " WHERE day BETWEEN ? AND ? GROUP BY message ORDER BY c DESC LIMIT 80", params)]
    return {"from": from_day, "to": to_day, "total": total, "alarms": alarms,
            "types": types, "top": top, "by_day": by_day, "by_hour": by_hour,
            "messages": messages}


def events_list(con, from_day, to_day, etype=None, search=None, alarms_only=False,
                limit=200, offset=0, message=None, user_ptr=None, point=None):
    """Страница журнала событий (новые сверху).

    `search` — ФИО, табельный номер или текст события (без учёта регистра);
    `message` — точное название события из выпадающего списка.
    """
    where = ["day BETWEEN ? AND ?"]
    params = [from_day, to_day]
    if etype:
        where.append("event_type = ?")
        params.append(int(etype))
    if alarms_only:
        where.append("alarm_status = 1")
    if message:
        where.append("message = ?")
        params.append(message)
    if user_ptr:
        where.append("user_ptr = ?")
        params.append(int(user_ptr))
    frag, pparams = _point_sql(point)
    if frag:
        where.append(frag[5:])          # убираем ведущее " AND "
        params += pparams
    if search:
        clauses = ["instr_ru(message, ?)", "instr_ru(unit, ?)", "instr_ru(name, ?)"]
        sparams = [search, search, search]
        uids = [r["user_ptr"] for r in con.execute(
            "SELECT user_ptr FROM users WHERE"
            " instr_ru(last_name || ' ' || first_name || ' ' || father_name, ?)"
            " OR instr_ru(last_name, ?) OR instr_ru(number, ?)",
            (search, search, search))]
        if uids:
            clauses.append("user_ptr IN (%s)" % ",".join("?" * len(uids)))
            sparams += uids
        where.append("(" + " OR ".join(clauses) + ")")
        params += sparams
    w = " AND ".join(where)
    total = con.execute("SELECT COUNT(*) c FROM events WHERE " + w, params).fetchone()["c"]
    rows = con.execute(
        "SELECT day, ts, event_type, event_code, unit, message, name, alarm_status"
        " FROM events WHERE " + w + " ORDER BY day DESC, idx DESC LIMIT ? OFFSET ?",
        params + [int(limit), int(offset)]).fetchall()
    items = [{"day": r["day"], "ts": r["ts"], "time": r["ts"][11:19],
              "type": r["event_type"], "type_title": EVENT_TYPES.get(r["event_type"], "—"),
              "code": r["event_code"], "unit": r["unit"] or "", "message": r["message"] or "",
              "name": (r["name"] or "").strip(), "alarm": bool(r["alarm_status"])}
             for r in rows]
    return {"total": total, "offset": int(offset), "limit": int(limit), "items": items}




def employees(con, group=None, include_visitors=False):
    """Справочник сотрудников по алфавиту (для выбора в отчётах)."""
    out = []
    for pid, u in _user_names(con).items():
        if u["deleted"]:
            continue
        if u["visitor"] and not include_visitors:
            continue
        if not _real_name(u["fio"]):
            continue
        if group and group not in ("", "all") and u["group"] != group:
            continue
        out.append({"user_ptr": pid, "fio": u["fio"], "number": u["number"],
                    "group": u["group"], "position": u["position"]})
    out.sort(key=lambda x: x["fio"])
    return out


def late_report(con, from_day, to_day, group=None, search=None,
                shift_start=None, shift_end=None, user_ptr=None, point=None):
    """Опоздания за период: по сотрудникам, с худшим днём."""
    rows = attendance(con, from_day, to_day, group=group, search=search,
                      shift_start=shift_start, shift_end=shift_end, user_ptr=user_ptr,
                      point=point)
    per = {}
    for r in rows:
        a = per.setdefault(r["user_ptr"], {
            "user_ptr": r["user_ptr"], "fio": r["fio"], "number": r["number"],
            "group": r["group"], "position": r["position"], "days": 0, "hours": 0.0,
            "late_days": 0, "late_total": 0, "max_late": 0,
            "worst_day": "", "worst_time": "", "worst_shift": ""})
        a["days"] += 1
        a["hours"] += r["hours"] or 0
        if r["late"]:
            a["late_days"] += 1
            a["late_total"] += r["late"]
            if r["late"] > a["max_late"]:
                a["max_late"] = r["late"]
                a["worst_day"] = r["day"]
                a["worst_time"] = r["enter"]
                a["worst_shift"] = r["group"]
    out = [a for a in per.values() if a["late_days"]
           and _real_name(a["fio"]) and "гост" not in (a["group"] or "").lower()]
    for a in out:
        a["hours"] = round(a["hours"], 2)
        a["avg_late"] = int(round(a["late_total"] / a["late_days"])) if a["late_days"] else 0
    out.sort(key=lambda x: (-x["late_total"], x["fio"]))
    return out


def person_history(con, user_ptr, from_day, to_day):
    """Карточка сотрудника: дни, часы, опоздания за период."""
    users = _user_names(con)
    u = users.get(int(user_ptr))
    if u is None:
        return None
    rows = attendance(con, from_day, to_day, user_ptr=user_ptr,
                      include_deleted=True, include_visitors=True)
    summ = attendance_summary(rows)
    summary = summ[0] if summ else {
        "days": 0, "hours": 0.0, "passes": 0, "late_days": 0, "late_total": 0,
        "avg_hours": 0.0, "early_total": 0, "open": False}
    return {"user": u, "from": from_day, "to": to_day, "rows": rows, "summary": summary}



def users_report(con, group=None, search=None, include_deleted=False, user_ptr=None):
    """Отчёт о пользователях: табельный, ФИО, подразделение, должность, последний проход."""
    last = {}
    for r in con.execute(
            "SELECT user_ptr, MAX(ts) t FROM events WHERE event_type=? AND event_code=?"
            " AND user_ptr>0 GROUP BY user_ptr", (PASS_TYPE, PASS_CODE)):
        last[r["user_ptr"]] = r["t"]
    last_unit = {}
    for r in con.execute(
            "SELECT user_ptr, unit, MAX(ts) t FROM events WHERE event_type=? AND event_code=?"
            " AND user_ptr>0 GROUP BY user_ptr", (PASS_TYPE, PASS_CODE)):
        last_unit[r["user_ptr"]] = r["unit"]
    out = []
    for pid, u in _user_names(con).items():
        if user_ptr and pid != int(user_ptr):
            continue
        if u["deleted"] and not include_deleted:
            continue
        if group and group not in ("", "all") and u["group"] != group:
            continue
        if search:
            needle = search.lower()
            if needle not in u["fio"].lower() and needle not in u["number"].lower():
                continue
        lt = last.get(pid, "")
        out.append({
            "user_ptr": pid, "number": u["number"], "fio": u["fio"],
            "group": u["group"], "position": u["position"],
            "status": "Гость" if u["visitor"] else ("Удалён" if u["deleted"] else "Работает"),
            "last_used": (lt[11:19] if lt else ""), "last_day": (lt[:10] if lt else ""),
            "last_unit": last_unit.get(pid, ""),
        })
    out.sort(key=lambda x: (x["group"], x["fio"]))
    return out


EVENTS_COLS_CSV = [
    ("day", "Дата"), ("time", "Время"), ("type_title", "Тип"), ("unit", "Точка"),
    ("message", "Событие"), ("name", "Сотрудник"), ("alarm", "Тревога"),
]


def events_csv(con, from_day, to_day, etype=None, search=None, message=None,
               alarms_only=False, sep=";", enc="cp1251", user_ptr=None, point=None):
    """Весь журнал событий за период в CSV (потоком, без загрузки всех строк в память)."""
    where = ["day BETWEEN ? AND ?"]
    params = [from_day, to_day]
    if etype:
        where.append("event_type = ?")
        params.append(int(etype))
    if message:
        where.append("message = ?")
        params.append(message)
    if alarms_only:
        where.append("alarm_status = 1")
    if user_ptr:
        where.append("user_ptr = ?")
        params.append(int(user_ptr))
    frag, pparams = _point_sql(point)
    if frag:
        where.append(frag[5:])          # убираем ведущее " AND "
        params += pparams
    if search:
        where.append("(instr_ru(message, ?) OR instr_ru(unit, ?) OR instr_ru(name, ?))")
        params += [search, search, search]
    w = " AND ".join(where)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=sep, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([t for _, t in EVENTS_COLS_CSV])
    cur = con.execute(
        "SELECT day, ts, event_type, unit, message, name, alarm_status FROM events"
        " WHERE " + w + " ORDER BY day, idx", params)
    n = 0
    while True:
        chunk = cur.fetchmany(2000)
        if not chunk:
            break
        for r in chunk:
            writer.writerow([
                r["day"], r["ts"][11:19], EVENT_TYPES.get(r["event_type"], "—"),
                r["unit"] or "", r["message"] or "", (r["name"] or "").strip(),
                "да" if r["alarm_status"] else "",
            ])
            n += 1
    data = buf.getvalue().encode(enc, "replace")
    if enc.lower().replace("-", "") == "utf8":
        data = b"\xef\xbb\xbf" + data
    return data, n


def points_list(con):
    """Контрольные точки (двери), встречающиеся в журнале."""
    rows = con.execute("SELECT unit, COUNT(*) c FROM events"
                       " WHERE event_type=? AND event_code=? GROUP BY unit ORDER BY c DESC",
                       (PASS_TYPE, PASS_CODE)).fetchall()
    return [{"unit": r["unit"], "count": r["c"]} for r in rows if r["unit"]]


def presence_now(con, day=None):
    """Кто сейчас на объекте: последний проход за день — вход."""
    day = day or dt.date.today().isoformat()
    users = _user_names(con)
    rows = con.execute("SELECT user_ptr, ts, unit FROM events"
                       " WHERE day=? AND event_type=? AND event_code=? AND user_ptr>0"
                       " ORDER BY ts, idx", (day, PASS_TYPE, PASS_CODE)).fetchall()
    last = {}
    for r in rows:
        last[r["user_ptr"]] = (r["ts"], r["unit"])
    out = []
    for pid, (ts, unit) in last.items():
        if direction(unit) != "in" or pid not in users:
            continue
        out.append({"user_ptr": pid, "fio": users[pid]["fio"], "group": users[pid]["group"],
                    "position": users[pid]["position"], "since": ts[11:19], "unit": unit})
    out.sort(key=lambda x: x["since"])
    return out


def groups_list(con):
    return [r["name"] for r in con.execute("SELECT name FROM groups ORDER BY name") if r["name"]]


def db_status(con):
    days = con.execute("SELECT COUNT(*) c, MAX(day) last, MIN(day) first FROM days").fetchone()
    ev = con.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
    us = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    return {
        "events": ev,
        "users": us,
        "days": days["c"],
        "first_day": days["first"],
        "last_day": days["last"],
        "config_synced": meta_get(con, "config_synced", ""),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv):
    init_db()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("команды: sync [дней] | report ГГГГ-ММ-ДД [ГГГГ-ММ-ДД] | status | tables FILE")
        return 0
    cmd = argv[0]
    con = connect()
    if cmd == "sync":
        days = int(argv[1]) if len(argv) > 1 else 7
        print(json.dumps(sync_all(days, con=con), ensure_ascii=False, indent=2))
    elif cmd == "report":
        f = argv[1] if len(argv) > 1 else dt.date.today().isoformat()
        t = argv[2] if len(argv) > 2 else f
        sync_events(f, t, con=con)
        rows = attendance(con, f, t)
        print(json.dumps(attendance_summary(rows), ensure_ascii=False, indent=2))
    elif cmd == "status":
        print(json.dumps(db_status(con), ensure_ascii=False, indent=2))
    elif cmd == "tables":
        print("\n".join(mdb_tables(argv[1])))
    else:
        print("неизвестная команда: %s" % cmd, file=sys.stderr)
        return 2
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
