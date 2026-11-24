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


def set_smb_credentials(user, password):
    """Сменить учётную запись для доступа к шаре Gate и сохранить в конфиг."""
    global SMB_USER, SMB_PASS
    user = (user or "").strip()
    password = password or ""
    if not user or not password:
        raise ValueError("нужны логин и пароль")
    SMB_USER, SMB_PASS = user, password
    CFG["user"] = user
    CFG["password"] = password
    path = os.path.join(ROOT, "gate.config.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(CFG, fh, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return True


def check_smb(timeout=25):
    """Проверить доступ к шаре Gate. Возвращает (ok, сообщение)."""
    try:
        items = smb_list("Server")
        return True, "связь есть, файлов в Server: %d" % len(items)
    except Exception as exc:                     # noqa: BLE001
        return False, str(exc)


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


def smb_put(remote_dir, local_path, name, timeout=60):
    tmp = name + ".part"
    smb_run("cd %s; put %s %s" % (remote_dir, local_path, tmp), timeout=timeout)
    smb_run("cd %s; rename %s %s" % (remote_dir, tmp, name), timeout=timeout)
    return True


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

CREATE TABLE IF NOT EXISTS readers (
    rdr_ptr INTEGER PRIMARY KEY,
    dev_ptr INTEGER,
    name    TEXT
);
CREATE TABLE IF NOT EXISTS access_table (
    rdr_ptr  INTEGER,
    user_ptr INTEGER,
    always   INTEGER
);
CREATE INDEX IF NOT EXISTS ix_access_user ON access_table(user_ptr);

CREATE TABLE IF NOT EXISTS breaks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_ptr INTEGER NOT NULL,
    start    TEXT,
    end_time TEXT,
    title    TEXT
);
CREATE INDEX IF NOT EXISTS ix_breaks_user ON breaks(user_ptr);

CREATE TABLE IF NOT EXISTS schedules (
    user_ptr INTEGER PRIMARY KEY,
    start    TEXT,
    end_time TEXT,
    days     TEXT,
    updated  TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_ptr   INTEGER PRIMARY KEY,
    number     TEXT,
    number_u   TEXT,
    number_mifare TEXT,
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
CREATE TABLE IF NOT EXISTS passes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    number     TEXT UNIQUE,
    visitor    TEXT NOT NULL,
    card       TEXT,
    position   TEXT,
    schedule   TEXT,
    document   TEXT,
    phone      TEXT,
    org        TEXT,
    host       TEXT,
    purpose    TEXT,
    visit_date TEXT,
    valid_from TEXT,
    valid_to   TEXT,
    doors      TEXT,
    note       TEXT,
    status     TEXT DEFAULT 'active',
    gate_job   TEXT,
    gate_state TEXT,
    gate_error TEXT,
    created_by TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_passes_to ON passes(valid_to);

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


def _migrate(con):
    """Добавить недостающие колонки в существующие таблицы."""
    try:
        cols = {r["name"] for r in con.execute("PRAGMA table_info(passes)")}
    except Exception:                            # noqa: BLE001
        return
    for col in ("card", "position", "schedule", "gate_job", "gate_state", "gate_error"):
        if cols and col not in cols:
            con.execute("ALTER TABLE passes ADD COLUMN %s TEXT" % col)
    try:
        ucols = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
        for col in ("number_u", "number_mifare"):
            if ucols and col not in ucols:
                con.execute("ALTER TABLE users ADD COLUMN %s TEXT" % col)
    except Exception:                            # noqa: BLE001
        pass
    con.commit()


def init_db(con=None):
    own = con is None
    con = con or connect()
    con.executescript(SCHEMA)
    _migrate(con)
    con.commit()
    if own:
        con.close()


def meta_get(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def meta_set(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))


def schedules_map(con):
    """{user_ptr: (начало, конец)} — личные графики работы."""
    out = {}
    for r in con.execute("SELECT user_ptr, start, end_time FROM schedules"):
        if r["start"] and r["end_time"]:
            out[r["user_ptr"]] = (r["start"], r["end_time"])
    return out


def get_schedule(con, user_ptr):
    r = con.execute("SELECT start, end_time FROM schedules WHERE user_ptr=?",
                    (int(user_ptr),)).fetchone()
    if not r:
        return {"start": "", "end": ""}
    return {"start": r["start"] or "", "end": r["end_time"] or ""}


def breaks_map(con):
    """{user_ptr: [(начало, конец, название), ...]} — перерывы по расписанию."""
    out = {}
    for r in con.execute("SELECT user_ptr, start, end_time, title FROM breaks ORDER BY user_ptr, start"):
        if r["start"] and r["end_time"]:
            out.setdefault(r["user_ptr"], []).append(
                (r["start"], r["end_time"], r["title"] or "перерыв"))
    return out


def get_breaks(con, user_ptr):
    rows = con.execute("SELECT start, end_time, title FROM breaks WHERE user_ptr=? ORDER BY start",
                       (int(user_ptr),)).fetchall()
    return [{"start": r["start"], "end": r["end_time"], "title": r["title"] or "перерыв"}
            for r in rows]


def set_breaks(con, user_ptr, items):
    """Заменить список перерывов сотрудника. items: [{"start","end","title"}, ...]."""
    clean = []
    for it in items or []:
        st = (it.get("start") or "").strip()
        en = (it.get("end") or "").strip()
        if not st or not en:
            continue
        for v in (st, en):
            dt.time.fromisoformat(v)          # ValueError на мусоре
        if en <= st:
            raise ValueError("перерыв %s–%s: конец раньше начала" % (st, en))
        clean.append((int(user_ptr), st, en, (it.get("title") or "перерыв").strip()[:40]))
    with _lock:
        con.execute("DELETE FROM breaks WHERE user_ptr=?", (int(user_ptr),))
        con.executemany("INSERT INTO breaks(user_ptr,start,end_time,title) VALUES(?,?,?,?)", clean)
        con.commit()
    return get_breaks(con, user_ptr)


def _break_minutes(breaks, t1, end):
    """Минуты перерывов, попавшие в интервал [t1, end] одного дня."""
    total = 0
    for st, en, _title in breaks or ():
        bs = dt.datetime.combine(t1.date(), dt.time.fromisoformat(st))
        be = dt.datetime.combine(t1.date(), dt.time.fromisoformat(en))
        if be <= bs:
            be += dt.timedelta(days=1)
        a, b = max(t1, bs), min(end, be)
        if b > a:
            total += int((b - a).total_seconds() // 60)
    return total


def set_schedule(con, user_ptr, start, end):
    """Сохранить личный график; пустые значения — удалить."""
    start = (start or "").strip()
    end = (end or "").strip()
    with _lock:
        if not start or not end:
            con.execute("DELETE FROM schedules WHERE user_ptr=?", (int(user_ptr),))
        else:
            for v in (start, end):
                dt.time.fromisoformat(v)          # ValueError на мусоре
            con.execute(
                "INSERT INTO schedules(user_ptr,start,end_time,updated) VALUES(?,?,?,?)"
                " ON CONFLICT(user_ptr) DO UPDATE SET start=excluded.start,"
                " end_time=excluded.end_time, updated=excluded.updated",
                (int(user_ptr), start, end, dt.datetime.now().isoformat(timespec="seconds")))
        con.commit()
    return get_schedule(con, user_ptr)


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


CONFIG_IMPORT_VERSION = "2"   # менять при изменении набора импортируемых таблиц


def sync_config(force=False, con=None):
    """Скачать config.mdb и обновить сотрудников/подразделения/устройства."""
    own = con is None
    con = con or connect()
    init_db(con)
    listing = smb_list("Server")
    if "config.mdb" not in listing:
        raise RuntimeError("config.mdb не найден в Server")
    size, mtime, _ = listing["config.mdb"]
    stamp = "%s|%s|v%s" % (size, mtime, CONFIG_IMPORT_VERSION)
    need = force or meta_get(con, "config_stamp") != stamp or not os.path.exists(CONFIG_MDB)
    if not need:
        # страховка: производные таблицы должны быть заполнены
        try:
            if con.execute("SELECT COUNT(*) c FROM readers").fetchone()["c"] == 0:
                need = True
        except Exception:                        # noqa: BLE001
            need = True
    if not need:
        # обновить отметки даже без переимпорта
        try:
            cnt = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            meta_set(con, "config_mtime", mtime)
            meta_set(con, "config_users", cnt)
            con.commit()
        except Exception:                        # noqa: BLE001
            pass
        if own:
            con.close()
        return False
    smb_get("Server", "config.mdb", CONFIG_MDB)

    users = []
    for r in mdb_export(CONFIG_MDB, "Users"):
        last = (r.get("LastName") or r.get("Фамилия") or "").strip()
        first = (r.get("FirstName") or r.get("Имя") or "").strip()
        father = (r.get("FatherName") or r.get("Отчество") or "").strip()
        users.append((_int(r.get("UserPtr")), (r.get("Number") or "").strip(),
                      (r.get("NumberU") or "").strip(), (r.get("NumberMifare") or "").strip(),
                      last, first, father,
                      _int(r.get("GroupPtr")), (r.get("Details1") or "").strip(),
                      1 if str(r.get("Deleted")).strip() in ("1", "-1", "True") else 0,
                      1 if str(r.get("Visitor")).strip() in ("1", "-1", "True") else 0))
    groups = [(_int(r.get("GroupPtr")), (r.get("Name") or "").strip()) for r in mdb_export(CONFIG_MDB, "Groups")]
    devices = [(_int(r.get("DevPtr")), (r.get("Name") or "").strip(), _int(r.get("DevType")))
               for r in mdb_export(CONFIG_MDB, "Devices")]

    readers = [(_int(r.get("RdrPtr")), _int(r.get("DevPtr")), (r.get("Name") or "").strip())
               for r in mdb_export(CONFIG_MDB, "Readers")]
    access = [(_int(r.get("RdrPtr")), _int(r.get("UserPtr")), _int(r.get("Always")))
              for r in mdb_export(CONFIG_MDB, "AccessTable")]

    with _lock:
        con.execute("DELETE FROM users")
        con.executemany(
            "INSERT OR REPLACE INTO users(user_ptr, number, number_u, number_mifare,"
            " last_name, first_name, father_name, group_ptr, position, deleted, visitor)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)", users)
        con.execute("DELETE FROM readers")
        con.executemany("INSERT OR REPLACE INTO readers(rdr_ptr, dev_ptr, name) VALUES(?,?,?)", readers)
        con.execute("DELETE FROM access_table")
        con.executemany("INSERT INTO access_table(rdr_ptr, user_ptr, always) VALUES(?,?,?)", access)
        con.execute("DELETE FROM groups")
        con.executemany("INSERT OR REPLACE INTO groups VALUES(?,?)", groups)
        con.execute("DELETE FROM devices")
        con.executemany("INSERT OR REPLACE INTO devices VALUES(?,?,?)", devices)
        meta_set(con, "config_stamp", stamp)
        meta_set(con, "config_mtime", mtime)
        meta_set(con, "config_users", len(users))
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
               shift_start=None, shift_end=None, user_ptr=None,
               in_points=None, out_points=None, personal=True, breaks=True):
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
    sched = schedules_map(con) if personal else {}
    brk = breaks_map(con) if breaks else {}

    in_needles = [x.lower() for x in _points(in_points)]
    out_needles = [x.lower() for x in _points(out_points)]

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
        unit = p["unit"] or ""
        low = unit.lower()
        in_ok = (not in_needles) or any(n in low for n in in_needles)
        out_ok = (not out_needles) or any(n in low for n in out_needles)
        rec["passes"] += 1
        if in_ok and (rec["enter"] is None or t < rec["enter"]):
            rec["enter"] = t
        if out_ok and (rec["exit"] is None or t > rec["exit"]):
            rec["exit"] = t
            rec["last_dir"] = direction(unit)
        d = direction(unit)
        if d == "in" and in_ok and (rec["first_in"] is None or t < rec["first_in"]):
            rec["first_in"] = t
            rec["in_unit"] = unit
        if d == "out" and out_ok and (rec["last_out"] is None or t > rec["last_out"]):
            rec["last_out"] = t
            rec["out_unit"] = unit
        rec["points"].add(unit)

    rows = []
    for (pid, day), rec in per.items():
        enter, exit_ = rec["enter"], rec["exit"]
        s2 = sched.get(pid)
        sh_s_u = dt.time.fromisoformat(s2[0]) if s2 else sh_s
        sh_e_u = dt.time.fromisoformat(s2[1]) if s2 else sh_e
        open_now = (day == today) and rec["last_dir"] == "in"
        if enter and (exit_ or open_now):
            t1 = dt.datetime.fromisoformat(enter)
            t2 = dt.datetime.fromisoformat(exit_) if exit_ else now
            end = now if open_now else t2
            brk_min = _break_minutes(brk.get(pid), t1, end)
            hours = round(max(0.0, (end - t1).total_seconds() / 3600.0 - brk_min / 60.0), 2)
            late = max(0, int((dt.datetime.combine(t1.date(), t1.time())
                               - dt.datetime.combine(t1.date(), sh_s_u)).total_seconds() // 60))
        else:
            hours, late, brk_min = 0.0, 0, 0
        early = None
        if exit_ and not open_now:
            t2 = dt.datetime.fromisoformat(exit_)
            early = max(0, int((dt.datetime.combine(t2.date(), sh_e_u)
                                - dt.datetime.combine(t2.date(), t2.time())).total_seconds() // 60))
        rows.append({
            "user_ptr": pid,
            "number": rec["user"]["number"],
            "fio": rec["user"]["fio"],
            "group": rec["user"]["group"],
            "position": rec["user"]["position"],
            "day": day,
            "enter": enter[11:19] if enter else "",
            "exit": exit_[11:19] if exit_ else "",
            "first_in": rec["first_in"][11:19] if rec["first_in"] else "",
            "last_out": rec["last_out"][11:19] if rec["last_out"] else "",
            "hours": hours,
            "break_min": brk_min,
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


MONTHS_RU = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


def hm(minutes):
    """480 → «8:00»."""
    minutes = int(minutes or 0)
    return "%d:%02d" % (minutes // 60, minutes % 60)


def breaks_report(con, from_day, to_day, group=None, user_ptr=None, points=None,
                  min_minutes=1):
    """Перекуры: пары «вышел — вернулся» через выбранные точки (по умолчанию все)."""
    users = _user_names(con)
    frag, pparams = _point_sql(points) if points else ("", [])
    cur = con.execute(
        "SELECT ts, user_ptr, unit FROM events"
        " WHERE day BETWEEN ? AND ? AND event_type=? AND event_code=? AND user_ptr>0"
        + frag + " ORDER BY user_ptr, ts",
        [from_day, to_day, PASS_TYPE, PASS_CODE] + pparams)
    opened = {}
    pairs = []
    for ts, pid, unit in cur:
        u = users.get(pid)
        if u is None or u["deleted"] or u["visitor"]:
            continue
        if user_ptr and pid != int(user_ptr):
            continue
        if group and group not in ("", "all") and u["group"] != group:
            continue
        d = direction(unit)
        key = (pid, ts[:10])               # пара ищется только внутри одних суток
        if d == "out":
            opened.setdefault(key, ts)     # первую «вышел» и считаем началом
        elif d == "in" and key in opened:
            a = dt.datetime.fromisoformat(opened.pop(key))
            b = dt.datetime.fromisoformat(ts)
            minutes = int((b - a).total_seconds() // 60)
            if minutes < min_minutes:
                continue
            pairs.append({
                "user_ptr": pid, "fio": u["fio"], "number": u["number"],
                "group": u["group"], "position": u["position"],
                "day": a.date().isoformat(), "out": a.strftime("%H:%M"),
                "in": b.strftime("%H:%M"), "minutes": minutes,
            })
    pairs.sort(key=lambda r: (r["day"], r["out"], r["fio"]))
    agg = {}
    for r in pairs:
        a = agg.setdefault(r["user_ptr"], {
            "user_ptr": r["user_ptr"], "fio": r["fio"], "number": r["number"],
            "group": r["group"], "position": r["position"],
            "count": 0, "minutes": 0, "max_minutes": 0})
        a["count"] += 1
        a["minutes"] += r["minutes"]
        a["max_minutes"] = max(a["max_minutes"], r["minutes"])
    summary = sorted(agg.values(), key=lambda a: (-a["minutes"], a["fio"]))
    for a in summary:
        a["avg_minutes"] = int(round(a["minutes"] / a["count"])) if a["count"] else 0
    return {
        "rows": pairs,
        "summary": summary,
        "total_count": len(pairs),
        "total_minutes": sum(p["minutes"] for p in pairs),
        "count": len(summary),
    }


def _first_last_rows(con, first, last, group, user_ptr, start_hour):
    """Первое и последнее предъявление ключа за «сутки», начинающиеся с start_hour."""
    users = _user_names(con)
    t0 = dt.datetime.combine(first, dt.time(0)) - dt.timedelta(hours=start_hour)
    t1 = dt.datetime.combine(last, dt.time(23, 59, 59))
    cur = con.execute(
        "SELECT ts, user_ptr, unit FROM events"
        " WHERE ts>=? AND ts<=? AND event_type=? AND event_code=? AND user_ptr>0"
        " ORDER BY ts", (t0.isoformat(sep=" "), t1.isoformat(sep=" "),
                         PASS_TYPE, PASS_CODE))
    per = {}
    for ts, pid, _unit in cur:
        u = users.get(pid)
        if u is None or u["deleted"] or u["visitor"]:
            continue
        if user_ptr and pid != int(user_ptr):
            continue
        if group and group not in ("", "all") and u["group"] != group:
            continue
        t = dt.datetime.fromisoformat(ts)
        day = (t - dt.timedelta(hours=start_hour)).date()
        if day < first or day > last:
            continue
        rec = per.get((pid, day))
        if rec is None:
            per[(pid, day)] = [t, t, u]
        else:
            if t < rec[0]:
                rec[0] = t
            if t > rec[1]:
                rec[1] = t
    out = []
    for (pid, day), (a, b, u) in per.items():
        out.append({
            "user_ptr": pid, "number": u["number"], "fio": u["fio"],
            "group": u["group"], "position": u["position"],
            "day": day.isoformat(),
            "hours": round((b - a).total_seconds() / 3600.0, 2),
        })
    return out


def timesheet(con, month, group=None, user_ptr=None, in_points=None, out_points=None,
              mode="normal", start_hour=0):
    """Табель за месяц: сотрудники × дни, часы в минутах (формат — в шаблоне)."""
    first = dt.date.fromisoformat(month + "-01")
    last = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    if str(mode) == "first_last":
        rows = _first_last_rows(con, first, last, group, user_ptr, int(start_hour or 0))
    else:
        rows = attendance(con, first.isoformat(), last.isoformat(),
                          group=group, user_ptr=user_ptr,
                          in_points=in_points, out_points=out_points)
    ndays = last.day
    wd_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    weekend = [first.replace(day=d).weekday() >= 5 for d in range(1, ndays + 1)]
    weekday = [wd_ru[first.replace(day=d).weekday()] for d in range(1, ndays + 1)]
    today = dt.date.today()
    today_day = today.day if (today.year, today.month) == (first.year, first.month) else 0
    per, day_tot = {}, [0] * ndays
    for r in rows:
        minutes = int(round((r["hours"] or 0) * 60))
        if minutes <= 0:            # фильтр по точкам не дал пары «вход-выход»
            continue
        u = per.setdefault(r["user_ptr"], {
            "user_ptr": r["user_ptr"], "number": r["number"], "fio": r["fio"],
            "position": r["position"], "group": r["group"],
            "cells": {}, "total": 0, "days": 0})
        day = int(r["day"][8:10])
        u["cells"][day] = minutes
        u["total"] += minutes
        u["days"] += 1
        day_tot[day - 1] += minutes
    out = sorted(per.values(), key=lambda x: (x["group"], x["fio"]))
    return {
        "month": month,
        "title": "%s %d" % (MONTHS_RU[first.month - 1], first.year),
        "days": ndays,
        "weekend": weekend,
        "weekday": weekday,
        "today": today_day,
        "rows": out,
        "day_totals": day_tot,
        "total": sum(day_tot),
        "count": len(out),
    }


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
# запись ключей в Gate: очередь SQL-заданий для агента на сервере
# --------------------------------------------------------------------------

QUEUE_DIR = "_skud_queue"   # от корня шары GATE (она же C:\GATE)


def card_to_gate(number):
    """«140/39939» → (facility, card, NumberU)."""
    raw = (number or "").strip()
    if "/" in raw:
        a, b = raw.split("/", 1)
        if a.isdigit() and b.isdigit():
            fac, card = int(a), int(b)
            return fac, card, "%012X" % ((fac << 16) | card)
    return None


def build_add_user_sql(con, data, user_ptr):
    """SQL для агента: создать пользователя и раздать доступы на двери."""
    cfg = os.path.join(DATA, "config.mdb")
    users = mdb_export(cfg, "Users")
    access = mdb_export(cfg, "AccessTable")
    readers = mdb_export(cfg, "Readers")
    devices = mdb_export(cfg, "Devices")
    if not users:
        raise ValueError("нет картотеки Gate")
    tpl = max(users, key=lambda u: _int(u.get("UserPtr")))
    parsed = card_to_gate(data.get("card"))
    if not parsed:
        raise ValueError("номер карты должен быть в виде 140/39939")
    fac, card, number_u = parsed
    number = "%03d/%05d" % (fac, card)
    dev_by_name = {}
    for d in devices:
        dev_by_name.setdefault((d.get("Name") or "").strip().lower(), set()).add(_int(d.get("DevPtr")))
    # Память ключей у контроллера одна на устройство, поэтому слот (InnerNum)
    # должен быть один и тот же для всех считывателей устройства и свободный
    # на самом устройстве. Если выделять слот отдельно каждому считывателю,
    # ключ попадает в занятый слот и контроллер его не принимает
    # («Нет доступа. Неразрешенный ключ»).
    # Строки доступа Gate держит на «считывателе доступа» — том, где уже есть
    # картотека (обычно Num=1); на служебных считывателях строк нет.
    dev_ptrs = set()
    for name in (data.get("doors") or []):
        dev_ptrs |= dev_by_name.get(str(name).strip().lower(), set())
    access_by_rdr = {}
    for a in access:
        access_by_rdr.setdefault(_int(a.get("RdrPtr")), []).append(a)
    rdrs_slots = []
    for dev in sorted(dev_ptrs):
        dev_rdrs = [r for r in readers if _int(r.get("DevPtr")) == dev]
        if not dev_rdrs:
            continue
        counts = {_int(r.get("RdrPtr")): len(access_by_rdr.get(_int(r.get("RdrPtr")), []))
                  for r in dev_rdrs}
        top = max(counts.values()) if counts else 0
        active = [r for r in dev_rdrs
                  if counts[_int(r.get("RdrPtr"))] >= max(1, top // 2)] if top else []
        if not active:                       # новое устройство — берём первый считыватель
            active = [r for r in dev_rdrs if _int(r.get("Num")) == 1] or dev_rdrs[:1]
        used = [_int(a.get("InnerNum"))
                for r in active for a in access_by_rdr.get(_int(r.get("RdrPtr")), [])]
        slot = (max(used) + 1) if used else 1
        for r in active:
            rdrs_slots.append((_int(r.get("RdrPtr")), slot))
    if not rdrs_slots:
        raise ValueError("не найдены считыватели выбранных дверей")

    def q(v):
        if v is None or v == "":
            return "NULL"
        return "'" + str(v).replace("'", "''") + "'"

    fio = (data.get("visitor") or "").replace("Карта ", "").split()
    last = fio[0] if fio else "Гость"
    first = fio[1] if len(fio) > 1 else ""
    father = fio[2] if len(fio) > 2 else ""
    # «Попов П.П» и «Попов П.П.» — это инициалы: разносим имя и отчество,
    # иначе отчество остаётся пустым (ФИО делится по пробелам)
    if len(fio) == 2 and not father:
        t = fio[1]
        if "." in t or (len(t) == 2 and t.isupper()):
            ini = re.findall(r"[А-ЯЁA-Zа-яёa-z]", t)
            if len(ini) == 2:
                first, father = ini[0].upper() + ".", ini[1].upper() + "."
    cols = ["UserPtr", "KeyType", "Number", "NumberU", "NumberMifare", "LastName", "FirstName",
            "FatherName", "GroupPtr", "Deleted", "UseExpiry", "ExpiryDate", "ExpiryTime",
            "IdleNotLimited", "NoFacility", "Details1", "Status", "Visitor", "SendSms", "Phone",
            "SendMail", "Mail", "UniPassMode", "FormatW26"]
    # Срок действия в записи Gate НЕ выставляем: у всех 288 сотрудников он пуст,
    # а пользователя с заполненным сроком Gate не сопоставляет с событием —
    # проход в журнале остаётся без имени. Срок пропуска ведёт наше приложение,
    # а ключ из Gate убирается при отзыве и по истечении (queue_remove_card).
    # подразделение берём у реальных сотрудников: у наших гостевых записей его нет
    groups = {}
    for u in users:
        if u.get("Deleted") == "0" and (u.get("LastName") or "").strip():
            g = (u.get("GroupPtr") or "").strip()
            if g:
                groups[g] = groups.get(g, 0) + 1
    group_ptr = max(groups, key=groups.get) if groups else (tpl.get("GroupPtr") or "2")
    vals = [str(user_ptr), tpl.get("KeyType") or "1", q(number), q(number_u), "NULL",
            q(last), q(first), q(father), group_ptr, "0",
            "0", "NULL", "NULL", "0", "0",
            q("Водитель"), "0", "0", "0", "NULL", "0", "NULL", "0", "0"]
    lines = ["# СКУД Gate: новый пользователь из приложения",
             "INSERT INTO [Users] (%s) VALUES (%s)" % (", ".join("[%s]" % c for c in cols), ", ".join(vals))]
    for rdr, inner in rdrs_slots:
        lines.append(
            "INSERT INTO [AccessTable] ([RdrPtr],[UserPtr],[InnerNum],[Always],[Schedule1],[Schedule2],"
            "[Schedule3],[Schedule4],[Schedule5],[Schedule6],[Schedule7],[RecordState],[APB],[Inside],"
            "[CardType],[CardCode],[NoEntry],[NoExit]) VALUES (%d,%d,%d,1,0,0,0,0,0,0,0,0,0,0,0,NULL,0,0)"
            % (rdr, user_ptr, inner))
    return "\r\n".join(lines) + "\r\n"


def queue_put(name, sql_text):
    """Положить SQL-задание в очередь на сервере Gate (cp1251)."""
    os.makedirs(DATA, exist_ok=True)
    local = os.path.join(DATA, name)
    with open(local, "wb") as fh:
        fh.write(sql_text.encode("cp1251", "replace"))
    smb_put(QUEUE_DIR, local, name)
    return name


RESTART_JOB = "zz_gateserv_restart.cmd"


def queue_restart():
    """Поставить в очередь перезапуск GateServ.

    Картотеку GateServ читает при старте: пока службу не перезапустить, карта
    лежит в базе, но контроллер её не знает и отвечает «Неразрешенный ключ».
    Агент выполняет .cmd построчно, поэтому здесь только простые команды.
    Имя файла постоянное — несколько пропусков подряд дают один перезапуск.
    """
    user = CFG.get("user") or ""
    pwd = CFG.get("password") or ""
    lines = [
        "taskkill /F /IM GateServ.exe",
        "ping -n 4 127.0.0.1",
        'C:\\Users\\Public\\PsExec64.exe -accepteula -nobanner -i 1 -u "%s" -p "%s"'
        ' -d "C:\\GATE\\Server\\GateServ.exe"' % (user, pwd),
        "ping -n 12 127.0.0.1",
    ]
    os.makedirs(DATA, exist_ok=True)
    local = os.path.join(DATA, RESTART_JOB)
    with open(local, "wb") as fh:
        fh.write(("\r\n".join(lines) + "\r\n").encode("cp1251", "replace"))
    smb_put(QUEUE_DIR, local, RESTART_JOB)
    return RESTART_JOB


def build_remove_card_sql(card):
    """SQL: убрать карту из Gate — доступы и саму запись пользователя."""
    parsed = card_to_gate(card)
    if not parsed:
        raise ValueError("номер карты должен быть в виде 140/39939")
    fac, num, _ = parsed
    number = ("%03d/%05d" % (fac, num)).replace("'", "''")
    return ("DELETE FROM [AccessTable] WHERE [UserPtr] IN"
            " (SELECT [UserPtr] FROM [Users] WHERE [Number]='%s')\r\n"
            "DELETE FROM [Users] WHERE [Number]='%s'\r\n" % (number, number))


def queue_remove_card(card):
    """Убрать карту из Gate и перезапустить службу, чтобы её забыли контроллеры."""
    name = "rm_%s.sql" % re.sub(r"\W+", "", card)
    queue_put(name, build_remove_card_sql(card))
    queue_restart()
    return name


def expire_passes(con):
    """Истёкшие пропуска: убрать ключ из Gate и пометить пропуск истёкшим.

    Ключ в Gate записан без срока действия, поэтому убирать его нужно самим —
    иначе карта посетителя продолжит открывать двери после окончания пропуска.
    """
    today = dt.date.today().isoformat()
    rows = con.execute(
        "SELECT id, card FROM passes WHERE status='active'"
        " AND valid_to IS NOT NULL AND valid_to <> '' AND valid_to < ?"
        " AND card IS NOT NULL AND card <> ''", (today,)).fetchall()
    done = 0
    for r in rows:
        # карту убираем, только если она не нужна другому действующему пропуску
        busy = con.execute(
            "SELECT COUNT(*) c FROM passes WHERE card=? AND id<>? AND status='active'"
            " AND (valid_to IS NULL OR valid_to='' OR valid_to>=?)",
            (r["card"], r["id"], today)).fetchone()["c"]
        if not busy:
            try:
                if card_to_gate(r["card"]):
                    queue_remove_card(r["card"])
                    done += 1
            except Exception:                 # noqa: BLE001
                pass
        with _lock:
            con.execute("UPDATE passes SET status='expired' WHERE id=?", (r["id"],))
            con.commit()
    return done


def queue_result(name):
    """Прочитать результат задания из очереди (если уже есть)."""
    local = os.path.join(DATA, "res_" + name)
    try:
        smb_get(QUEUE_DIR, name + ".result", local)
    except Exception:                            # noqa: BLE001
        return None
    try:
        return open(local, "rb").read().decode("cp1251", "replace")
    except OSError:
        return None


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
    sched = schedules_map(con)
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
        s2 = sched.get(pid)
        out.append({"user_ptr": pid, "fio": u["fio"], "number": u["number"],
                    "group": u["group"], "position": u["position"],
                    "schedule_start": s2[0] if s2 else "",
                    "schedule_end": s2[1] if s2 else ""})
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
    """Карточка сотрудника: дни, часы, опоздания, реквизиты карты."""
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
    extra = {}
    r = con.execute("SELECT number_u, number_mifare FROM users WHERE user_ptr=?",
                    (int(user_ptr),)).fetchone()
    if r:
        extra["number_u"] = (r["number_u"] or "").strip()
        extra["number_mifare"] = (r["number_mifare"] or "").strip()
    acc = con.execute("SELECT COUNT(*) c FROM access_table WHERE user_ptr=?",
                      (int(user_ptr),)).fetchone()
    extra["access_points"] = acc["c"] if acc else 0
    last = con.execute(
        "SELECT ts, unit FROM events WHERE user_ptr=? AND event_type=? AND event_code=?"
        " ORDER BY ts DESC LIMIT 1", (int(user_ptr), PASS_TYPE, PASS_CODE)).fetchone()
    extra["last_ts"] = last["ts"] if last else ""
    extra["last_unit"] = (last["unit"] or "") if last else ""
    digits = re.sub(r"\D", "", u["number"] or "")
    pr = None
    if digits:
        pr = con.execute(
            "SELECT number, valid_to, status FROM passes"
            " WHERE replace(replace(card,'/',''),' ','')=?"
            " ORDER BY id DESC LIMIT 1", (digits,)).fetchone()
    extra["pass"] = ({"number": pr["number"], "valid_to": pr["valid_to"],
                      "status": pr["status"]} if pr else None)
    extra["status"] = "удалён" if u["deleted"] else ("гость" if u["visitor"] else "активен")
    extra["gate_id"] = u["user_ptr"]
    return {"user": u, "from": from_day, "to": to_day, "rows": rows,
            "summary": summary, "details": extra, "breaks": get_breaks(con, user_ptr)}



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



WD_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def schedule_text(sched):
    """Человеческий вид графика: «Пн–Пт, 08:00–20:00»."""
    if not sched:
        return "—"
    days = sched.get("days") or []
    t1, t2 = (sched.get("from") or ""), (sched.get("to") or "")
    days = sorted({int(d) for d in days if str(d).lstrip("-").isdigit() and 0 <= int(d) <= 6})
    if len(days) == 7:
        d = "ежедневно"
    elif days == [0, 1, 2, 3, 4]:
        d = "Пн–Пт"
    elif days == [5, 6]:
        d = "Сб–Вс"
    elif not days:
        d = "ни одного дня"
    else:
        d = ", ".join(WD_SHORT[i] for i in days)
    if t1 and t2:
        d += ", %s–%s" % (t1, t2)
    return d


def schedule_allows(sched, when=None):
    """Разрешён ли проход в этот момент по графику."""
    if not sched:
        return True
    when = when or dt.datetime.now()
    days = sched.get("days")
    if days:
        days = {int(d) for d in days if str(d).lstrip("-").isdigit()}
        if when.weekday() not in days:
            return False
    t1, t2 = sched.get("from"), sched.get("to")
    if t1 and t2:
        cur = when.strftime("%H:%M")
        return t1 <= cur <= t2
    return True


PASS_STATUS = {"active": "Действует", "expired": "Истёк", "upcoming": "Ещё не действует",
               "revoked": "Отозван"}


def _pass_status(row):
    if (row["status"] or "") == "revoked":
        return "revoked"
    today = dt.date.today().isoformat()
    if row["valid_to"] and row["valid_to"] < today:
        return "expired"
    if row["valid_from"] and row["valid_from"] > today:
        return "upcoming"
    return "active"


def _pass_row(row):
    d = dict(row)
    try:
        d["doors"] = json.loads(d.get("doors") or "[]")
    except ValueError:
        d["doors"] = []
    try:
        d["schedule"] = json.loads(d.get("schedule") or "null") if d.get("schedule") else None
    except ValueError:
        d["schedule"] = None
    d["schedule_text"] = schedule_text(d["schedule"])
    d["in_schedule"] = schedule_allows(d["schedule"])
    d["state"] = _pass_status(row)
    d["state_title"] = PASS_STATUS.get(d["state"], d["state"])
    return d


def doors_list(con):
    """Двери (устройства) из картотеки Gate."""
    out = []
    for r in con.execute("SELECT dev_ptr, name FROM devices ORDER BY name"):
        name = (r["name"] or "").strip()
        if not name or name.lower() in ("нет", "нет "):
            continue
        out.append({"dev_ptr": r["dev_ptr"], "name": name})
    return out


def _norm_card(v):
    return (v or "").upper().replace(" ", "").replace("-", "").replace(":", "").replace(".", "")


def _card_variants(card):
    """Варианты записи номера: как есть, хвост после «/», без нулей, добивка до 12."""
    n = _norm_card(card)
    if not n:
        return []
    out = {n}
    if "/" in n:
        parts = n.split("/")
        out.add(parts[-1])                 # «140/39939» → 39939
        out.add("".join(parts))            # → 14039939
    s = n.lstrip("0")
    if s:
        out.add(s)
    if len(n) < 12 and all(c in "0123456789ABCDEF" for c in n):
        out.add(n.rjust(12, "0"))
    if len(n) == 12:
        out.add(n[-8:])
    return list(out)


def gate_index(con):
    """Индексы картотеки Gate: карта → пользователь, доступы по считывателям."""
    by_card, users = {}, {}
    for r in con.execute("SELECT user_ptr, number, number_u, number_mifare, last_name,"
                         " first_name, father_name, deleted FROM users"):
        users[r["user_ptr"]] = r
        keys = set()
        for k in (r["number_u"], r["number_mifare"]):
            n = _norm_card(k)
            if n:
                keys.add(n)
        num = r["number"] or ""
        if "/" in num:
            parts = num.split("/")
            keys.add(_norm_card(parts[-1]))
            keys.add(_norm_card("".join(parts)))
            keys.add(_norm_card(num))
        else:
            keys.add(_norm_card(num))
        for k in keys:
            if k:
                by_card.setdefault(k, r["user_ptr"])
    access = {}
    for r in con.execute("SELECT rdr_ptr, user_ptr FROM access_table"):
        access.setdefault(r["user_ptr"], set()).add(r["rdr_ptr"])
    readers = {r["rdr_ptr"]: r for r in con.execute("SELECT rdr_ptr, dev_ptr, name FROM readers")}
    devices = {}
    for r in con.execute("SELECT dev_ptr, name FROM devices"):
        name = (r["name"] or "").strip()
        if name and name.lower() != "нет":
            devices.setdefault(name, set()).add(r["dev_ptr"])
    return {"by_card": by_card, "users": users, "access": access,
            "readers": readers, "devices": devices}


def find_cards(con, query, limit=25):
    """Поиск карты в картотеке Gate: точное и частичное совпадение, плюс последние добавленные."""
    q = _norm_card(query)
    idx = gate_index(con)
    hits = []
    for uid, r in idx["users"].items():
        keys = [_norm_card(r["number"]), _norm_card(r["number_u"]), _norm_card(r["number_mifare"])]
        if q and any(q in k for k in keys if k):
            hits.append((uid, r))
    # точное совпадение — первым
    hits.sort(key=lambda x: (0 if any(_norm_card(k) == q for k in (x[1]["number"], x[1]["number_u"], x[1]["number_mifare"])) else 1,
                             x[1]["last_name"] or ""))
    out = []
    for uid, r in hits[:limit]:
        acc = idx["access"].get(uid, set())
        devs = {idx["readers"][x]["dev_ptr"] for x in acc if x in idx["readers"]}
        names = sorted(n for n, ptrs in idx["devices"].items() if ptrs & devs)
        fio = " ".join(x for x in (r["last_name"], r["first_name"], r["father_name"]) if x).strip()
        out.append({"user_ptr": uid, "fio": fio or "ID %s" % uid, "number": r["number"],
                    "number_u": r["number_u"], "number_mifare": r["number_mifare"],
                    "deleted": bool(r["deleted"]), "doors": names,
                    "exact": any(_norm_card(k) == q for k in (r["number"], r["number_u"], r["number_mifare"]) if k)})
    recent = []
    for r in con.execute("SELECT user_ptr, number, number_u, last_name, first_name, father_name"
                         " FROM users ORDER BY user_ptr DESC LIMIT 10"):
        recent.append({"user_ptr": r["user_ptr"], "number": r["number"], "number_u": r["number_u"],
                       "fio": " ".join(x for x in (r["last_name"], r["first_name"], r["father_name"]) if x).strip()})
    return {"query": query, "count": len(out), "items": out, "recent": recent}


def pass_gate_status(con, p, index=None):
    """Готовность ключа в Gate: есть ли карта и на какие двери она открыта."""
    idx = index or gate_index(con)
    doors = p.get("doors") or []
    total = len(doors)
    card = _norm_card(p.get("card"))
    uid = None
    if card:
        for cand in _card_variants(card):
            uid = idx["by_card"].get(cand)
            if uid:
                break
    if uid is None:
        return {"in_gate": False, "user": None, "card": p.get("card") or "",
                "doors": [{"name": d, "ok": False} for d in doors],
                "ok_count": 0, "total": total, "all_doors": [], "granted": 0,
                "note": "ключа нет в картотеке Gate" if card else "карта не указана"}
    u = idx["users"][uid]
    allowed = idx["access"].get(uid, set())
    dev_ok = {idx["readers"][r]["dev_ptr"] for r in allowed if r in idx["readers"]}
    result_doors, ok_count = [], 0
    for d in doors:
        devs = idx["devices"].get(d, set())
        ok = bool(devs & dev_ok)
        ok_count += 1 if ok else 0
        result_doors.append({"name": d, "ok": ok})
    # все двери Gate — куда ключ реально прошёл
    chosen = set(doors)
    all_doors = [{"name": name, "ok": bool(devs & dev_ok), "chosen": name in chosen}
                 for name, devs in sorted(idx["devices"].items())]
    fio = " ".join(x for x in (u["last_name"], u["first_name"], u["father_name"]) if x).strip()
    return {"in_gate": True,
            "user": {"user_ptr": uid, "fio": fio or "ID %s" % uid, "number": u["number"],
                     "deleted": bool(u["deleted"])},
            "card": p.get("card") or "",
            "doors": result_doors, "ok_count": ok_count, "total": total,
            "all_doors": all_doors,
            "granted": sum(1 for d in all_doors if d["ok"]),
            "note": "" if ok_count else "карта есть, но ни на одну из этих дверей доступа нет"}


def pass_check_job(con, p):
    """Проверить результат задания в очереди (если ждём)."""
    if not p.get("gate_job") or (p.get("gate_state") or "") in ("ok", "error"):
        return p
    res = queue_result(p["gate_job"])
    if res is None:
        return p
    bad = [l for l in res.splitlines() if l.startswith("err=")]
    with _lock:
        if bad:
            con.execute("UPDATE passes SET gate_state='error', gate_error=? WHERE id=?",
                        ("; ".join(b[4:] for b in bad)[:400], p["id"]))
        else:
            con.execute("UPDATE passes SET gate_state='ok', gate_error='' WHERE id=?", (p["id"],))
        con.commit()
    if not bad:
        try:
            sync_config(con=con)      # сразу перечитываем картотеку Gate
        except Exception:             # noqa: BLE001
            pass
    return pass_get(con, p["id"])


def passes_list(con, from_day=None, to_day=None, state=None, search=None, limit=500):
    """Пропуска: свежие сверху."""
    where, params = [], []
    if from_day:
        where.append("(valid_to IS NULL OR valid_to >= ?)")
        params.append(from_day)
    if to_day:
        where.append("(valid_from IS NULL OR valid_from <= ?)")
        params.append(to_day)
    if search:
        where.append("(instr_ru(visitor, ?) OR instr_ru(org, ?) OR instr_ru(host, ?)"
                     " OR instr_ru(number, ?) OR instr_ru(card, ?) OR instr_ru(document, ?))")
        params += [search] * 6
    sql = "SELECT * FROM passes"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    rows = [ _pass_row(r) for r in con.execute(sql, params)]
    for i, r in enumerate(rows):
        if (r.get("gate_state") or "") == "sent":
            upd = pass_check_job(con, r)
            if upd:
                rows[i] = upd
    if state and state not in ("", "all"):
        rows = [r for r in rows if r["state"] == state]
    return rows


def pass_get(con, pid):
    r = con.execute("SELECT * FROM passes WHERE id=?", (int(pid),)).fetchone()
    return _pass_row(r) if r else None


def pass_create(con, data, created_by=""):
    visitor = (data.get("visitor") or "").strip()
    card = (data.get("card") or "").strip()
    if not visitor and card:
        visitor = "Карта %s" % card          # выдача по номеру карты
    if not visitor:
        raise ValueError("укажите ФИО посетителя или номер карты")
    visit = (data.get("visit_date") or dt.date.today().isoformat()).strip()
    valid_to = (data.get("valid_to") or visit).strip()
    if valid_to < visit:
        raise ValueError("срок действия раньше даты приёма")
    doors = data.get("doors") or []
    if isinstance(doors, str):
        doors = [x.strip() for x in doors.split("|") if x.strip()]
    year = visit[:4] if len(visit) >= 4 else str(dt.date.today().year)
    n = con.execute("SELECT COUNT(*) c FROM passes WHERE number LIKE ?", ("П-%s-%%" % year,)).fetchone()["c"]
    number = "П-%s-%04d" % (year, n + 1)
    with _lock:
        con.execute(
            "INSERT INTO passes(number,visitor,card,position,schedule,document,phone,org,host,purpose,visit_date,"
            "valid_from,valid_to,doors,note,status,created_by,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (number, visitor, (data.get("card") or "").strip(),
             (data.get("position") or "").strip(),
             json.dumps(data.get("schedule"), ensure_ascii=False) if data.get("schedule") else None,
             (data.get("document") or "").strip(), (data.get("phone") or "").strip(),
             (data.get("org") or "").strip(), (data.get("host") or "").strip(),
             (data.get("purpose") or "").strip(), visit, visit, valid_to,
             json.dumps(doors, ensure_ascii=False), (data.get("note") or "").strip(),
             "active", created_by, dt.datetime.now().isoformat(timespec="seconds")))
        con.commit()
        pid = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
    result = pass_get(con, pid)
    # если карта в формате Gate и выбраны двери — ставим задание агенту
    if card and card_to_gate(card) and (data.get("doors") or []):
        try:
            users = mdb_export(os.path.join(DATA, "config.mdb"), "Users")
            next_ptr = max((_int(u.get("UserPtr")) for u in users), default=0) + 1
            job = "pass_%s" % pid
            sql = build_add_user_sql(con, dict(data, card=card, visitor=visitor, valid_to=valid_to), next_ptr)
            queue_put(job + ".sql", sql)
            queue_restart()          # GateServ разошлёт новый ключ по контроллерам
            with _lock:
                con.execute("UPDATE passes SET gate_job=?, gate_state='sent' WHERE id=?", (job, pid))
                con.commit()
            result = pass_get(con, pid)
        except Exception as exc:                 # noqa: BLE001
            with _lock:
                con.execute("UPDATE passes SET gate_state='queue_error', gate_error=? WHERE id=?",
                            (str(exc)[:200], pid))
                con.commit()
            result = pass_get(con, pid)
    if card:
        dup = con.execute(
            "SELECT number FROM passes WHERE card=? AND id<>? AND status='active'"
            " AND (valid_to IS NULL OR valid_to>=?)",
            (card, pid, dt.date.today().isoformat())).fetchone()
        if dup:
            result["warning"] = "карта уже используется действующим пропуском %s" % dup["number"]
    return result


def pass_revoke(con, pid):
    p = pass_get(con, pid)
    with _lock:
        con.execute("UPDATE passes SET status='revoked' WHERE id=?", (int(pid),))
        con.commit()
    if p and (p.get("card") or "").strip():
        try:
            queue_remove_card(p["card"])      # ключ должен исчезнуть и в контроллерах
        except Exception:                     # noqa: BLE001
            pass
    return pass_get(con, pid)


def pass_delete(con, pid):
    p = pass_get(con, pid)
    with _lock:
        con.execute("DELETE FROM passes WHERE id=?", (int(pid),))
        con.commit()
    if p and (p.get("card") or "").strip():
        try:
            queue_remove_card(p["card"])
        except Exception:                     # noqa: BLE001
            pass
    return True


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
        "config_mtime": meta_get(con, "config_mtime", ""),
        "config_users": int(meta_get(con, "config_users", "0") or 0),
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
