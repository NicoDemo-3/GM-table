"""SQLite store. Campaigns hold characters; both are JSON documents.

Single source of truth on the host. The Widget Library lives inside each
campaign doc (custom widgets only — system widgets come from widgets.py).
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from . import widgets as W

_DB = Path(__file__).parent.parent / "data" / "table.db"
_lock = Lock()


def init():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS campaigns (id TEXT PRIMARY KEY, name TEXT, doc TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS characters "
            "(id TEXT PRIMARY KEY, campaign_id TEXT, name TEXT, owner TEXT, doc TEXT)"
        )


def _conn():
    return sqlite3.connect(_DB)


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------- campaigns ----------

def create_campaign(name, system="dnd5e"):
    camp = {
        "id": str(uuid.uuid4()),
        "name": name or "New Campaign",
        "system": system,
        "created": _now(),
        "widgets": [],     # custom widgets only
        "settings": {},
        "bestiary": [],
        "npcs": [],
        "rollTables": [],
        "compendium": [],
        "playerRules": [],   # DM-imported rules visible in the player sidebar
        "playerHandouts": [],  # read-only content pushed to players (shops, items, notes)
        "currency": {
            # value of each unit expressed in the base unit (cp). gp=100cp etc.
            "base": "cp",
            "units": [
                {"code": "pp", "name": "Platinum", "inBase": 1000},
                {"code": "gp", "name": "Gold", "inBase": 100},
                {"code": "ep", "name": "Electrum", "inBase": 50, "inBreakdown": False},
                {"code": "sp", "name": "Silver", "inBase": 10},
                {"code": "cp", "name": "Copper", "inBase": 1},
            ],
        },
        "encounter": {"active": False, "round": 1, "turn": 0, "combatants": []},
        "world": {
            "time": {"minutes": 480},   # 08:00
            "calendar": {"months": [{"name": "Month", "days": 30}], "year": 1, "monthIndex": 0, "day": 1},
            "weather": {"precip": "Clear", "wind": "Still", "temp_c": 18, "feels_c": 18},
            "weatherOptions": {
                "precip": ["Clear", "Overcast", "Light rain", "Heavy rain", "Fog", "Snow", "Storm"],
                "wind": ["Still", "Light breeze", "Gusty", "Strong winds", "Gale"],
            },
        },
        "party": {"tints": {}, "benched": [], "split": {"active": "All", "groups": {}}},
        "map": {"image": None, "grid": {"size": 70, "show": False},
                "fog": {"cols": 0, "rows": 0, "cell": 48, "revealed": []},
                "playerOpacity": 1.0, "tokens": []},
        "sounds": [],
        "handout": {"type": None, "content": None},
        "layouts": {},
        "compendium": [],
        "canvas": {
            "windows": {},
            "presets": [{"id": "p_default", "name": "Default", "members": [], "pan": {"x": 0, "y": 0}, "zoom": 1, "overrides": {}}],
            "active": "p_default",
            "shared": False,
        },
    }
    with _lock, _conn() as conn:
        conn.execute("INSERT INTO campaigns (id, name, doc) VALUES (?,?,?)",
                     (camp["id"], camp["name"], json.dumps(camp)))
    return camp


def get_campaign(cid):
    with _conn() as conn:
        row = conn.execute("SELECT doc FROM campaigns WHERE id=?", (cid,)).fetchone()
    return json.loads(row[0]) if row else None


def save_campaign(camp):
    with _lock, _conn() as conn:
        conn.execute("UPDATE campaigns SET name=?, doc=? WHERE id=?",
                     (camp["name"], json.dumps(camp), camp["id"]))


def all_campaigns():
    with _conn() as conn:
        rows = conn.execute("SELECT doc FROM campaigns ORDER BY name").fetchall()
    return [json.loads(r[0]) for r in rows]


def delete_campaign(cid):
    with _lock, _conn() as conn:
        conn.execute("DELETE FROM characters WHERE campaign_id=?", (cid,))
        conn.execute("DELETE FROM campaigns WHERE id=?", (cid,))


# ---------- characters ----------

def save(char, campaign_id=None):
    if campaign_id:
        char["campaignId"] = campaign_id
    cid = char.get("campaignId")
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO characters (id, campaign_id, name, owner, doc) VALUES (?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET campaign_id=excluded.campaign_id, "
            "name=excluded.name, owner=excluded.owner, doc=excluded.doc",
            (char["id"], cid, char["definition"]["name"], char.get("owner"), json.dumps(char)),
        )


def get(char_id):
    with _conn() as conn:
        row = conn.execute("SELECT doc FROM characters WHERE id=?", (char_id,)).fetchone()
    return json.loads(row[0]) if row else None


def characters_in(campaign_id):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT doc FROM characters WHERE campaign_id=? ORDER BY name", (campaign_id,)
        ).fetchall()
    return [json.loads(r[0]) for r in rows]


def delete(char_id):
    with _lock, _conn() as conn:
        conn.execute("DELETE FROM characters WHERE id=?", (char_id,))


# ---------- campaign import / export ----------

def export_campaign(cid):
    """A portable bundle: the campaign doc + all its characters."""
    camp = get_campaign(cid)
    if not camp:
        return None
    return {
        "format": "gm-table-campaign",
        "version": 1,
        "exported": _now(),
        "campaign": camp,
        "characters": characters_in(cid),
    }


def import_campaign(bundle):
    """Restore an exported bundle under fresh IDs (never collides with existing data)."""
    if bundle.get("format") != "gm-table-campaign":
        raise ValueError("Not a gm-table campaign export.")
    src = bundle.get("campaign", {})
    camp = create_campaign(src.get("name", "Imported Campaign") + " (imported)",
                           src.get("system", "dnd5e"))
    camp["widgets"] = src.get("widgets", [])
    camp["settings"] = src.get("settings", {})
    save_campaign(camp)
    for ch in bundle.get("characters", []):
        ch["id"] = str(uuid.uuid4())          # fresh id
        ch["campaignId"] = camp["id"]
        save(ch)
    return camp


# ---------- global settings (key/value) — used by XP thresholds etc. ----------

def _ensure_settings():
    with _conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)")


def get_setting(key, default=None):
    _ensure_settings()
    with _conn() as conn:
        row = conn.execute("SELECT v FROM settings WHERE k=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_setting(key, value):
    _ensure_settings()
    with _lock, _conn() as conn:
        conn.execute("INSERT INTO settings (k, v) VALUES (?,?) "
                     "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, json.dumps(value)))


def all_characters():
    """Every character across all campaigns (legacy/global helper)."""
    with _conn() as conn:
        rows = conn.execute("SELECT doc FROM characters ORDER BY name").fetchall()
    return [json.loads(r[0]) for r in rows]


# ---------- backups ----------

def backup_db(keep=10):
    """Copy table.db into data/backups with a timestamp; keep the newest `keep`."""
    import shutil
    if not _DB.exists():
        return None
    bdir = _DB.parent / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = bdir / f"table-{stamp}.db"
    with _lock:
        shutil.copy2(_DB, dest)
    backups = sorted(bdir.glob("table-*.db"))
    for old in backups[:-keep]:
        old.unlink(missing_ok=True)
    return str(dest)
