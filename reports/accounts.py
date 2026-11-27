#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пользователи веб-сервиса СКУД Gate: логин, пароль (хэш), роль.

Хранится в users.json рядом с сервером. При первом запуске админ
создаётся из секции `auth` в gate.config.json.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "users.json")

ROLES = ("admin", "operator", "viewer")
ROLE_TITLES = {"admin": "Администратор", "operator": "Оператор", "viewer": "Просмотр"}

_lock = threading.Lock()

DEFAULT = {"users": []}


def _hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return "%s$%s" % (salt, digest.hex())


def _verify_hash(password, stored):
    if not stored or "$" not in stored:
        return False
    salt = stored.split("$", 1)[0]
    return hmac.compare_digest(_hash(password, salt), stored)


def load():
    if not os.path.exists(PATH):
        return dict(DEFAULT)
    try:
        with open(PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data.get("users"), list):
            data["users"] = []
        return data
    except (OSError, ValueError):
        return dict(DEFAULT)


def save(data):
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, PATH)


def ensure_admin(cfg_auth):
    """Создать администратора из конфига, если пользователей ещё нет."""
    with _lock:
        data = load()
        if data["users"]:
            return False
        login = (cfg_auth or {}).get("user") or "vitosamin"
        password = (cfg_auth or {}).get("password") or "Admin910327"
        data["users"].append({"login": login, "name": "Администратор", "role": "admin",
                              "hash": _hash(password), "created": _now()})
        save(data)
        return True


def _now():
    import datetime as dt
    return dt.datetime.now().isoformat(timespec="seconds")


def public(users=None):
    """Список без хэшей."""
    data = load()
    out = []
    for u in data["users"]:
        out.append({"login": u.get("login", ""), "name": u.get("name", ""),
                    "role": u.get("role", "viewer"), "roleTitle": ROLE_TITLES.get(u.get("role"), "—"),
                    "created": u.get("created", ""), "tabs": u.get("tabs") or []})
    out.sort(key=lambda x: (x["role"] != "admin", x["login"]))
    return out


def get(login):
    for u in load()["users"]:
        if u.get("login", "").lower() == (login or "").lower():
            return u
    return None


def role_of(login):
    u = get(login)
    return (u or {}).get("role", "viewer")


def verify(login, password):
    u = get(login)
    if not u:
        return False
    return _verify_hash(password or "", u.get("hash", ""))


def add(login, password, role="viewer", name=""):
    login = (login or "").strip()
    if not login or len(login) < 2:
        raise ValueError("логин слишком короткий")
    if len(password or "") < 6:
        raise ValueError("пароль короче 6 символов")
    if role not in ROLES:
        raise ValueError("неизвестная роль")
    with _lock:
        data = load()
        if any(u.get("login", "").lower() == login.lower() for u in data["users"]):
            raise ValueError("такой логин уже есть")
        data["users"].append({"login": login, "name": (name or "").strip() or login,
                              "role": role, "hash": _hash(password), "created": _now()})
        save(data)
    return True


def delete(login):
    login = (login or "").strip()
    with _lock:
        data = load()
        admins = [u for u in data["users"] if u.get("role") == "admin"]
        target = next((u for u in data["users"] if u.get("login", "").lower() == login.lower()), None)
        if not target:
            raise ValueError("пользователь не найден")
        if target in admins and len(admins) == 1:
            raise ValueError("нельзя удалить последнего администратора")
        data["users"] = [u for u in data["users"]
                         if u.get("login", "").lower() != login.lower()]
        save(data)
    return True


def set_password(login, password):
    if len(password or "") < 6:
        raise ValueError("пароль короче 6 символов")
    with _lock:
        data = load()
        for u in data["users"]:
            if u.get("login", "").lower() == (login or "").lower():
                u["hash"] = _hash(password)
                save(data)
                return True
    raise ValueError("пользователь не найден")


def set_role(login, role):
    if role not in ROLES:
        raise ValueError("неизвестная роль")
    with _lock:
        data = load()
        admins = [u for u in data["users"] if u.get("role") == "admin"]
        target = next((u for u in data["users"] if u.get("login", "").lower() == (login or "").lower()), None)
        if not target:
            raise ValueError("пользователь не найден")
        if target in admins and len(admins) == 1 and role != "admin":
            raise ValueError("нельзя снять права с последнего администратора")
        target["role"] = role
        save(data)
    return True


# Вкладки панели: id как в nav.tabs. Пустой список = все доступные.
TAB_IDS = ("mon", "ana", "rep", "pas", "emp", "kpp", "rpt", "tsh", "brk",
           "ev", "pf", "acc", "exp", "set", "test")


def tabs_of(login):
    """Вкладки, разрешённые пользователю. Пусто — значит все."""
    u = get(login) or {}
    tabs = u.get("tabs") or []
    if not isinstance(tabs, list):
        return []
    return [t for t in tabs if t in TAB_IDS]


def set_tabs(login, tabs):
    clean = [t for t in (tabs or []) if t in TAB_IDS]
    if len(clean) == len(TAB_IDS):
        clean = []
    with _lock:
        data = load()
        for u in data["users"]:
            if u.get("login", "").lower() == (login or "").lower():
                if clean:
                    u["tabs"] = clean
                else:
                    u.pop("tabs", None)
                save(data)
                return clean
    raise ValueError("пользователь не найден")


def theme_of(login):
    """Выбранное оформление панели (classic/tablo/reestr/pult)."""
    u = get(login)
    return (u or {}).get("theme", "") or ""


def set_theme(login, theme):
    theme = (theme or "").strip()
    if theme not in ("", "classic", "tablo", "reestr", "pult"):
        raise ValueError("неизвестное оформление")
    with _lock:
        data = load()
        for u in data["users"]:
            if u.get("login", "").lower() == (login or "").lower():
                if theme:
                    u["theme"] = theme
                else:
                    u.pop("theme", None)
                save(data)
                return True
    raise ValueError("пользователь не найден")


def set_name(login, name):
    with _lock:
        data = load()
        for u in data["users"]:
            if u.get("login", "").lower() == (login or "").lower():
                u["name"] = (name or "").strip() or u.get("login")
                save(data)
                return True
    raise ValueError("пользователь не найден")
