import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

# Keep the store alongside premium_backup_system.py: the bot and web process must
# read and write the same entitlement/key files on Railway.
DATA_DIR = Path(os.getenv("VANTARMOR_DATA_DIR", "."))
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


def _key_hash(key):
    return hashlib.sha256(key.strip().upper().encode("utf-8")).hexdigest()


def is_premium_manager(user_id):
    configured = {item.strip() for item in os.getenv("PREMIUM_MANAGER_IDS", "").split(",") if item.strip().isdecimal()}
    return str(user_id) in configured


def is_premium_user(user_id):
    users = _read(PREMIUM_USERS_FILE, {})
    entry = users.get(str(user_id))
    now = int(time.time())
    if entry is True:
        return True
    if isinstance(entry, int) and not isinstance(entry, bool):
        return entry > now
    if isinstance(entry, dict):
        expiry = entry.get("expires_at")
        if expiry is None:
            return True
        try:
            return int(expiry) > now
        except (TypeError, ValueError):
            return False
    env_ids = {item.strip() for item in os.getenv("PREMIUM_USER_IDS", "").split(",") if item.strip().isdecimal()}
    return str(user_id) in env_ids


def generate_premium_key(days, creator_id):
    days = int(days)
    if not 1 <= days <= 3650:
        raise ValueError("La duración debe estar entre 1 y 3650 días.")
    key = "VANT-" + secrets.token_urlsafe(24)
    with _lock:
        keys = _read(PREMIUM_KEYS_FILE, {})
        keys[_key_hash(key)] = {
            "days": days,
            "created_at": int(time.time()),
            "created_by": str(creator_id),
            "redeemed_by": None,
            "redeemed_at": None,
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
        if not isinstance(record, dict) or record.get("redeemed_by") or record.get("redeemed_at"):
            return False
        users = _read(PREMIUM_USERS_FILE, {})
        uid = str(user_id)
        if is_premium_user(uid):
            return False
        now = int(time.time())
        users[uid] = {
            "expires_at": now + int(record.get("days", 0)) * 86400,
            "source": "key",
            "key_hash": digest,
        }
        record["redeemed_by"] = uid
        record["redeemed_at"] = now
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
        uid = record.get("redeemed_by")
        if uid is not None:
            entitlement = users.get(str(uid))
            if isinstance(entitlement, dict) and entitlement.get("key_hash") == digest:
                users.pop(str(uid), None)
        keys.pop(digest, None)
        _write(PREMIUM_USERS_FILE, users)
        _write(PREMIUM_KEYS_FILE, keys)
    return True


def register_web_user(user_id):
    with _lock:
        stats = _read(WEB_STATS_FILE, {"users": []})
        users = {str(value) for value in stats.get("users", [])}
        users.add(str(user_id))
        stats["users"] = sorted(users)
        _write(WEB_STATS_FILE, stats)
        return len(users)


def public_stats():
    stats = _read(WEB_STATS_FILE, {"users": []})
    try:
        servers = int(os.getenv("BOT_GUILD_COUNT", "0") or 0)
    except ValueError:
        servers = 0
    return {"website_users": len({str(value) for value in stats.get("users", [])}), "servers": servers}
