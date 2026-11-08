import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.getenv("VANTARMOR_DATA_DIR", ".data"))
PREMIUM_USERS_FILE = DATA_DIR / "premium_users.json"
PREMIUM_KEYS_FILE = DATA_DIR / "premium_keys.json"
WEB_STATS_FILE = DATA_DIR / "web_stats.json"
_lock = threading.RLock()


def _read(path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(fallback)) else fallback
    except (OSError, json.JSONDecodeError):
        return fallback


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def is_premium_manager(user_id):
    ids = {str(x).strip() for x in os.getenv("PREMIUM_MANAGER_IDS", "").split(",") if x.strip()}
    return str(user_id) in ids


def premium_expiry(user_id):
    users = _read(PREMIUM_USERS_FILE, {})
    entry = users.get(str(user_id))
    if entry is True:
        return None
    if isinstance(entry, int) and not isinstance(entry, bool):
        return entry if entry > int(time.time()) else 0
    if isinstance(entry, dict):
        expires_at = entry.get("expires_at")
        if expires_at is None:
            return None
        try:
            expires_at = int(expires_at)
            return expires_at if expires_at > int(time.time()) else 0
        except (TypeError, ValueError):
            return 0
    env_ids = {x.strip() for x in os.getenv("PREMIUM_USER_IDS", "").split(",") if x.strip()}
    return None if str(user_id) in env_ids else 0


def is_premium_user(user_id):
    expiry = premium_expiry(user_id)
    return expiry is None or expiry > int(time.time())


def set_premium_user(user_id, enabled: bool = True, *, expires_at=None, source="manual"):
    users = _read(PREMIUM_USERS_FILE, {})
    uid = str(user_id)
    if enabled:
        if expires_at is None:
            users[uid] = {"expires_at": None, "source": source}
        else:
            users[uid] = {"expires_at": int(expires_at), "source": source}
    else:
        users.pop(uid, None)
    _write(PREMIUM_USERS_FILE, users)
    return users.get(uid)


def revoke_premium_user(user_id):
    set_premium_user(user_id, enabled=False)
    return True


def _key_hash(key):
    return hashlib.sha256(key.strip().upper().encode("utf-8")).hexdigest()


def generate_premium_key(days, creator_id):
    days = int(days)
    if not 1 <= days <= 3650:
        raise ValueError("La duración debe estar entre 1 y 3650 días.")
    key = "VANT-" + secrets.token_urlsafe(24).upper()
    digest = _key_hash(key)
    with _lock:
        keys = _read(PREMIUM_KEYS_FILE, {})
        keys[digest] = {
            "days": days,
            "created_at": int(time.time()),
            "created_by": str(creator_id),
            "redeemed_by": None,
            "redeemed_at": None,
            "active": True,
        }
        _write(PREMIUM_KEYS_FILE, keys)
    return key


def redeem_premium_key(key, user_id):
    if not isinstance(key, str) or not key.strip():
        return False
    digest = _key_hash(key)
    with _lock:
        keys = _read(PREMIUM_KEYS_FILE, {})
        record = keys.get(digest)
        if not isinstance(record, dict) or not record.get("active"):
            return False
        if record.get("redeemed_by") is not None:
            return False
        users = _read(PREMIUM_USERS_FILE, {})
        uid = str(user_id)
        if is_premium_user(uid):
            return False
        now = int(time.time())
        expiry = now + int(record.get("days", 0)) * 86400
        users[uid] = {"expires_at": expiry, "source": "key", "key_hash": digest}
        record["redeemed_by"] = uid
        record["redeemed_at"] = now
        record["active"] = True
        keys[digest] = record
        _write(PREMIUM_USERS_FILE, users)
        _write(PREMIUM_KEYS_FILE, keys)
    return True


def delete_premium_key(key):
    if not isinstance(key, str) or not key.strip():
        return False
    digest = _key_hash(key)
    with _lock:
        keys = _read(PREMIUM_KEYS_FILE, {})
        record = keys.get(digest)
        if not isinstance(record, dict):
            return False
        users = _read(PREMIUM_USERS_FILE, {})
        redeemed_by = record.get("redeemed_by")
        if redeemed_by:
            current = users.get(str(redeemed_by))
            if isinstance(current, dict) and current.get("key_hash") == digest:
                users.pop(str(redeemed_by), None)
        keys.pop(digest, None)
        _write(PREMIUM_USERS_FILE, users)
        _write(PREMIUM_KEYS_FILE, keys)
    return True


def register_web_user(user_id):
    with _lock:
        stats = _read(WEB_STATS_FILE, {"users": []})
        users = set(str(x) for x in stats.get("users", []))
        users.add(str(user_id))
        stats["users"] = sorted(users)
        _write(WEB_STATS_FILE, stats)
        return len(users)


def public_stats():
    stats = _read(WEB_STATS_FILE, {"users": []})
    return {"website_users": len(set(stats.get("users", []))), "servers": int(os.getenv("BOT_GUILD_COUNT", "0") or 0)}
