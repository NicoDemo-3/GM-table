"""
Compendium — generic typed content (spells, feats, backgrounds, subclasses,
items, lore, hooks). Each entry separates math-bearing `mechanics` (engine-read)
from `text` (situational, shown not enforced).

Two import formats so any LLM can generate importable files:
  - JSON: {"entries": [ {type, name, ...fields...}, ... ]}  (or a bare list)
  - Markdown: blocks headed `## <type>: <name>`, then `key: value` lines and a
    free-text body after `text:`.
Both feed the same normalizer.
"""

import re
import uuid

TYPES = ["spell", "feat", "background", "subclass", "item", "monster", "lore", "hook"]

# math-bearing keys recognized per type -> folded into entry["mechanics"]
MECH_KEYS = {
    "spell": ["level", "school", "castingTime", "range", "components", "duration", "classes", "concentration", "ritual"],
    "feat": ["prerequisite", "abilityBonuses", "skills", "saves", "resource"],
    "background": ["skills", "tools", "languages", "items", "feature"],
    "subclass": ["className", "features"],
    "item": ["itemType", "subType", "rarity", "attunement", "equippable", "modifiers"],
    "monster": ["size", "creatureType", "alignment", "ac", "hp", "speed", "abilityScores",
                "saves", "skills", "senses", "languages", "cr", "traits", "actions"],
    "lore": ["category"],
    "hook": ["level", "summary"],
}

# aliases so flat LLM output maps in regardless of exact key
ALIASES = {
    "class": "className", "subtype": "subType", "item_type": "itemType",
    "casting_time": "castingTime", "ability_bonuses": "abilityBonuses",
    "attune": "attunement", "attunement_required": "attunement",
    "creature_type": "creatureType",
    "armor_class": "ac", "hit_points": "hp", "challenge": "cr",
    "ability_scores": "abilityScores", "stats": "abilityScores",
}


def _b(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "required")


LIST_FIELDS = {"skills", "saves", "classes", "tools", "languages", "tags"}

# lowercase (spaces/underscores stripped) -> canonical key, across all known fields
_LC2CANON = {}
for _canon in set(sum(MECH_KEYS.values(), [])) | {"type", "name", "source", "tags", "text", "folder"}:
    _LC2CANON[_canon.lower()] = _canon
for _a, _c in ALIASES.items():
    _LC2CANON[_a.lower().replace("_", "")] = _c


def _canonicalize(raw):
    out = {}
    for k, v in raw.items():
        kl = str(k).strip().lower().replace(" ", "").replace("_", "")
        out[_LC2CANON.get(kl, k)] = v
    return out


def _coerce_list(v):
    if isinstance(v, list):
        return v
    return [s.strip() for s in str(v).split(",") if s.strip()]


def _coerce_ability_bonuses(v):
    if isinstance(v, dict):
        return {k[:3].upper(): int(n) for k, n in v.items()}
    out = {}
    for part in str(v).split(","):
        bits = part.strip().split()
        if len(bits) >= 2:
            try:
                out[bits[0][:3].upper()] = int(bits[1])
            except ValueError:
                pass
    return out


def normalize(raw):
    """Take a flat or structured dict -> a clean compendium entry."""
    raw = _canonicalize(raw)
    etype = (raw.get("type") or "lore").strip().lower()
    if etype not in TYPES:
        etype = "lore"
    entry = {
        "id": "ce_" + uuid.uuid4().hex[:8],
        "type": etype,
        "name": str(raw.get("name") or "Untitled").strip(),
        "source": str(raw.get("source") or "").strip(),
        "folder": str(raw.get("folder") or "").strip(),
        "tags": _coerce_list(raw.get("tags", [])),
        "text": raw.get("text") or raw.get("html") or raw.get("description") or "",
        "mechanics": {},
    }
    for k in MECH_KEYS.get(etype, []):
        if k in raw and raw[k] not in (None, ""):
            v = raw[k]
            if k in ("concentration", "ritual", "attunement", "equippable"):
                v = _b(v)
            elif k in ("level", "cr"):
                v = _num(v)
            elif k in LIST_FIELDS:
                v = _coerce_list(v)
            elif k in ("abilityBonuses", "abilityScores"):
                v = _coerce_ability_bonuses(v) if k == "abilityBonuses" else _coerce_scores(v)
            entry["mechanics"][k] = v
    mods = entry["mechanics"].get("modifiers")
    if isinstance(mods, list):
        entry["mechanics"]["modifiers"] = [_norm_mod(m) for m in mods if m]
    return entry


def _num(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        try:
            return float(v)
        except (ValueError, TypeError):
            return v


def _coerce_scores(v):
    """'STR 18, DEX 10, ...' or dict -> {STR:18,...}."""
    if isinstance(v, dict):
        return {k[:3].upper(): _num(n) for k, n in v.items()}
    out = {}
    for part in re.split(r"[,;]", str(v)):
        bits = part.strip().split()
        if len(bits) >= 2:
            out[bits[0][:3].upper()] = _num(re.sub(r"[()+]", "", bits[1]))
    return out


def _norm_mod(m):
    if isinstance(m, dict):
        return {"type": m.get("type", "Bonus"), "target": m.get("target", "AC"),
                "value": int(m.get("value", 0) or 0)}
    # string like "AC +1" / "Weapon Attack +2"
    mt = re.match(r"(.+?)\s*([+-]?\d+)\s*$", str(m).strip())
    if mt:
        return {"type": "Bonus", "target": mt.group(1).strip(), "value": int(mt.group(2))}
    return {"type": "Bonus", "target": str(m).strip(), "value": 0}


# ---------- parsers ----------

def parse_json(data):
    rows = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        rows = []
    return [normalize(r) for r in rows if isinstance(r, dict)]


def parse_markdown(text):
    entries = []
    blocks = re.split(r"^##\s+", text, flags=re.MULTILINE)
    for blk in blocks:
        blk = blk.strip()
        if not blk:
            continue
        lines = blk.splitlines()
        head = lines[0]
        m = re.match(r"(\w[\w ]*?)\s*[:\-]\s*(.+)$", head)
        if not m:
            continue
        raw = {"type": m.group(1).strip().lower(), "name": m.group(2).strip()}
        body, in_text, mods = [], False, []
        for ln in lines[1:]:
            if in_text:
                body.append(ln)
                continue
            kv = re.match(r"([\w ]+?)\s*:\s*(.*)$", ln)
            if not kv:
                if ln.strip():
                    in_text = True
                    body.append(ln)
                continue
            kraw = kv.group(1).strip()
            k = kraw.lower().replace(" ", "")
            v = kv.group(2).strip()
            if k == "text":
                in_text = True
                if v:
                    body.append(v)
            elif k in ("modifier", "mod"):
                mods.append(v)
            else:
                raw[kraw] = v
        if mods:
            raw["modifiers"] = mods
        if body:
            raw["text"] = "\n".join(body).strip()
        entries.append(normalize(raw))
    return entries


def parse_bundle(text, filename=""):
    import json
    text = text.strip()
    if filename.endswith(".json") or text.startswith("{") or text.startswith("["):
        return parse_json(json.loads(text))
    return parse_markdown(text)


# ---------- engine integration: apply an entry onto a character ----------

def to_bestiary(entry):
    """Convert a monster compendium entry into a bestiary stat block."""
    m = entry.get("mechanics", {})
    return {
        "id": uuid.uuid4().hex,
        "name": entry["name"],
        "size": m.get("size", ""),
        "creatureType": m.get("creatureType", ""),
        "alignment": m.get("alignment", ""),
        "ac": _num(m.get("ac", 10)),
        "hp": _num(m.get("hp", 1)),
        "speed": m.get("speed", ""),
        "abilityScores": m.get("abilityScores", {}),
        "saves": m.get("saves", []),
        "skills": m.get("skills", []),
        "senses": m.get("senses", ""),
        "languages": m.get("languages", ""),
        "cr": m.get("cr", ""),
        "traits": m.get("traits", ""),
        "actions": m.get("actions", ""),
        "notes": entry.get("text", ""),
        "source": entry.get("source", ""),
    }


def _flat_mod_total(modifiers, target):
    """Sum the values of modifiers whose target matches (case-insensitive contains)."""
    total = 0
    for m in modifiers or []:
        tgt = str(m.get("target", "")).lower()
        if target in tgt:
            try:
                total += int(m.get("value", 0))
            except (ValueError, TypeError):
                pass
    return total


def apply_to_entity(entry, ent):
    """Attach a compendium entry to a loose NPC/beast dict (not a full character).

    NPCs and bestiary creatures don't have the character schema, so we append the
    entry to a `features` list (rendered as notes) and nudge the simple flat fields
    we can safely compute: AC from item modifiers, ability scores from feat bonuses.
    Returns a note string.
    """
    t = entry["type"]
    mech = entry.get("mechanics", {})
    text = entry.get("text", "")
    feats = ent.setdefault("features", [])
    label = {"item": "Item", "spell": "Spell", "feat": "Feat", "background": "Background",
             "subclass": "Subclass", "lore": "Lore", "hook": "Hook", "monster": "Creature"}.get(t, "Note")

    # human-readable body: the text plus a compact mechanics summary
    body_bits = []
    if t == "item":
        rar = mech.get("rarity")
        if rar:
            body_bits.append(rar + (" (attunement)" if _b(mech.get("attunement")) else ""))
        if mech.get("modifiers"):
            body_bits.append(", ".join(f"{m.get('target')} {'+' if int(m.get('value',0))>=0 else ''}{m.get('value')}"
                                       for m in mech["modifiers"]))
    if t == "spell" and mech.get("level") is not None:
        body_bits.append(f"Level {mech['level']} {mech.get('school','')}".strip())
    summary = " · ".join(b for b in body_bits if b)
    html = (("<em>" + summary + "</em><br>") if summary else "") + (text or "")
    feats.append({"id": uuid.uuid4().hex, "name": f"{label}: {entry['name']}", "html": html})

    # also append a readable line to the notes/description field (NPC pages render
    # `description`, bestiary pages render `notes`) so the applied entry is visible
    plain = f"[{label}] {entry['name']}" + (f" — {summary}" if summary else "")
    if text:
        plain += ": " + re.sub(r"<[^>]+>", "", text)
    for fld in ("notes", "description"):
        prev = ent.get(fld)
        if prev or fld in ent:
            ent[fld] = (prev + "\n" if prev else "") + plain
    if "notes" not in ent and "description" not in ent:
        ent["notes"] = plain

    notes = []
    # nudge flat fields where it's unambiguous
    if t == "item":
        acm = _flat_mod_total(mech.get("modifiers"), "ac")
        if acm:
            try:
                ent["ac"] = int(ent.get("ac", 10)) + acm
                notes.append(f"AC {'+' if acm>=0 else ''}{acm}")
            except (ValueError, TypeError):
                pass
    if t == "feat":
        scores = ent.get("abilityScores")
        if isinstance(scores, dict):
            for ab, val in (mech.get("abilityBonuses") or {}).items():
                ab = ab[:3].upper()
                if ab in scores:
                    try:
                        scores[ab] = int(scores[ab]) + int(val)
                        notes.append(f"{ab} +{val}")
                    except (ValueError, TypeError):
                        pass

    extra = (" — " + ", ".join(notes)) if notes else ""
    return f'Attached {label.lower()} “{entry["name"]}” as a note{extra}.'


def apply_to_character(entry, definition):
    """Mutate a character's definition to add this entry. Returns a note string."""
    t = entry["type"]
    mech = entry.get("mechanics", {})
    text = entry.get("text", "")
    if t == "spell":
        definition.setdefault("spellcasting", {}).setdefault("spells", []).append({
            "name": entry["name"], "level": int(mech.get("level", 0) or 0),
            "prepared": False, "html": text,
        })
        return f'Added spell “{entry["name"]}” to the spell list.'

    if t == "item":
        definition.setdefault("inventory", {}).setdefault("items", []).append({
            "id": uuid.uuid4().hex, "name": entry["name"],
            "type": mech.get("itemType", "Gear"), "subType": mech.get("subType", ""),
            "rarity": mech.get("rarity", ""), "quantity": 1, "equipped": False,
            "attunable": _b(mech.get("attunement", False)), "attuned": False,
            "modifiers": mech.get("modifiers", []), "html": text,
        })
        return f'Added item “{entry["name"]}” to inventory (equip it to apply bonuses).'

    if t == "background":
        for sk in mech.get("skills", []):
            definition.setdefault("skills", {})[sk] = "proficient"
        items = mech.get("items", [])
        if isinstance(items, str):
            items = [s.strip() for s in items.split(",") if s.strip()]
        for it in items:
            nm = it.get("name") if isinstance(it, dict) else str(it)
            qty = it.get("qty", 1) if isinstance(it, dict) else 1
            definition.setdefault("inventory", {}).setdefault("items", []).append(
                {"id": uuid.uuid4().hex, "name": nm, "quantity": qty, "equipped": False, "modifiers": [], "html": ""})
        feat = mech.get("feature") or {}
        if isinstance(feat, str) and feat.strip().startswith("{"):
            try:
                import json
                feat = json.loads(feat)
            except Exception:
                feat = {"text": feat}
        definition.setdefault("features", []).append(
            {"id": uuid.uuid4().hex, "name": "Background: " + entry["name"],
             "html": (feat.get("text") if isinstance(feat, dict) else str(feat)) or text})
        definition["background"] = entry["name"]
        return f'Applied background “{entry["name"]}” (skills, gear, feature).'

    if t == "feat":
        for ab, val in (mech.get("abilityBonuses") or {}).items():
            ab = ab[:3].upper()
            definition.setdefault("abilityScores", {})[ab] = definition.get("abilityScores", {}).get(ab, 10) + int(val)
        for sk in mech.get("skills", []):
            definition.setdefault("skills", {})[sk] = "proficient"
        for sv in mech.get("saves", []):
            definition.setdefault("saves", {})[sv[:3].upper()] = "proficient"
        res = mech.get("resource")
        if isinstance(res, dict) and res.get("name"):
            definition.setdefault("resources", []).append({
                "id": uuid.uuid4().hex, "name": res["name"], "max": int(res.get("max", 1) or 1),
                "restoreOn": res.get("restore") or res.get("restoreOn") or ["Long Rest"]})
        definition.setdefault("features", []).append(
            {"id": uuid.uuid4().hex, "name": "Feat: " + entry["name"], "html": text})
        return f'Applied feat “{entry["name"]}” (bonuses + feature).'

    if t == "subclass":
        for f in mech.get("features", []):
            definition.setdefault("features", []).append({
                "id": uuid.uuid4().hex,
                "name": entry["name"] + (f" — {f.get('name')}" if isinstance(f, dict) and f.get("name") else ""),
                "html": (f.get("text") if isinstance(f, dict) else str(f)) or ""})
        return f'Added subclass features from “{entry["name"]}” (static parts; review the rest).'

    # lore / hook -> as a feature/note
    definition.setdefault("features", []).append(
        {"id": uuid.uuid4().hex, "name": entry["name"], "html": text})
    return f'Added “{entry["name"]}” as a note.'


# a documented example bundle the user can hand to any LLM
EXAMPLE_MARKDOWN = """\
## item: Bouncing Boots of Buffoonery
folder: Carnival Gear
rarity: Uncommon
attunement: yes
itemType: Wondrous Item
modifier: AC +1
text: While wearing these boots your jumping distance doubles and you take no damage from falling 20 feet or less.

## spell: Spectral Juggling
folder: Carnival Magic
level: 1
school: Conjuration
castingTime: 1 action
range: 30 feet
components: V, S
duration: Concentration, up to 1 minute
classes: Bard, Sorcerer, Wizard
text: You conjure spinning spectral pins that orbit you and harry a nearby foe.

## monster: Thornback Lurker
folder: Forest Beasts
size: Large
creatureType: Monstrosity
alignment: Unaligned
ac: 15
hp: 76
speed: 40 ft.
abilityScores: STR 18, DEX 12, CON 16, INT 3, WIS 12, CHA 6
cr: 4
senses: darkvision 60 ft., passive Perception 13
languages: \u2014
traits: Camouflage. The lurker has advantage on Stealth checks made in forest terrain.
actions: Bite. Melee Weapon Attack +6 to hit, reach 5 ft. Hit 13 (2d8+4) piercing damage.
text: A bramble-covered ambush predator that lies still until prey wanders close.
"""
