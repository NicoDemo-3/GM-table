"""
Hero's Diary import/export adapter.

Hero's Diary is a closed third-party app with an undocumented, version-stamped
JSON format. We never depend on it as our source of truth: this module is the
only place that knows their shape. It translates their export into our internal,
partitioned model:

    definition  -> who the character is (changes between sessions, Hero's Diary owns)
    state       -> what's happening now (changes live at the table, WE own)

That split is what makes re-import safe: a re-import refreshes `definition` and
(by default) preserves `state`.
"""

import uuid

SUPPORTED_VERSIONS = ("1.24",)   # match on major.minor prefix

ABILITY_MAP = {
    "Strength": "STR", "Dexterity": "DEX", "Constitution": "CON",
    "Intelligence": "INT", "Wisdom": "WIS", "Charisma": "CHA",
}


# ---------- ProseMirror / TipTap rich text -> HTML ----------

def _esc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _marks(text: str, marks: list) -> str:
    for m in marks or []:
        t = m.get("type")
        if t == "bold":
            text = f"<strong>{text}</strong>"
        elif t == "italic":
            text = f"<em>{text}</em>"
        elif t == "underline":
            text = f"<u>{text}</u>"
        elif t == "strike":
            text = f"<s>{text}</s>"
        elif t == "code":
            text = f"<code>{text}</code>"
    return text


def prosemirror_to_html(node) -> str:
    """Recursively render a TipTap doc. Unknown nodes degrade to their children."""
    if node is None:
        return ""
    t = node.get("type")
    children = "".join(prosemirror_to_html(c) for c in node.get("content", []))
    if t == "doc":
        return children
    if t == "paragraph":
        return f"<p>{children}</p>"
    if t == "text":
        return _marks(_esc(node.get("text", "")), node.get("marks"))
    if t == "hardBreak":
        return "<br>"
    if t == "heading":
        lvl = node.get("attrs", {}).get("level", 3)
        return f"<h{lvl}>{children}</h{lvl}>"
    if t == "bulletList":
        return f"<ul>{children}</ul>"
    if t == "orderedList":
        return f"<ol>{children}</ol>"
    if t == "listItem":
        return f"<li>{children}</li>"
    if t == "blockquote":
        return f"<blockquote>{children}</blockquote>"
    # Unknown node: pass through children so we never drop or mangle content.
    return children


# ---------- Import ----------

def version_ok(data: dict) -> bool:
    ver = data.get("metadata", {}).get("appVersion", "")
    return any(ver.startswith(v) for v in SUPPORTED_VERSIONS)


def from_heros_diary(data: dict, owner: str | None = None) -> dict:
    """Convert a Hero's Diary export into our internal character document."""
    c = data["character"]

    # --- abilities, skills, saves ---
    scores, skills, saves = {}, {}, {}
    for ab in c.get("abilities", {}).get("values", []):
        key = ABILITY_MAP.get(ab["name"], ab["name"][:3].upper())
        scores[key] = ab.get("score", 10)
        for sk in ab.get("skills", []):
            if sk["name"] == "Saving Throws":
                saves[key] = sk.get("skillLevel", "untrained")
            else:
                skills[sk["name"]] = sk.get("skillLevel", "untrained")

    # --- classes ---
    classes = [
        {"name": cl["name"], "level": cl["level"], "hitDie": cl.get("hitDice", "d8")}
        for cl in c.get("classes", {}).get("classes", [])
    ]

    # --- spellcasting (split max vs current) ---
    sc = c.get("spellCasting", {})
    slots_max, slots_current = {}, {}
    for lvl_key, slot in sc.get("slots", {}).items():
        n = lvl_key.replace("level", "")
        slots_max[n] = slot.get("totalLongRest", 0)
        slots_current[n] = slot.get("currentLongRest", 0)
    spells = []
    for sp in sc.get("spells", []):
        spells.append({
            "name": sp.get("name", ""),
            "level": sp.get("level", 0),
            "prepared": sp.get("prepared", False),
            "html": prosemirror_to_html(sp.get("description")) if isinstance(sp.get("description"), dict) else "",
        })

    # --- resources (def = name/max/restore, state = expended) ---
    resources_def, resources_state = [], {}
    for r in c.get("resources", []):
        tr = r.get("tracking", {})
        rid = r.get("id", str(uuid.uuid4()))
        resources_def.append({
            "id": rid,
            "name": r.get("name", ""),
            "max": tr.get("maximum") or tr.get("value", 1),
            "restoreOn": [x.get("restoreOn") for x in tr.get("restoreOn", [])],
        })
        resources_state[rid] = tr.get("expended", 0)

    # --- features / attacks / inventory (render rich text once, at import) ---
    features = [
        {"id": f.get("id"), "name": f.get("name", ""),
         "html": prosemirror_to_html(f.get("description"))}
        for f in c.get("features", [])
    ]
    attacks = [
        {k: v for k, v in a.items() if k not in ("description", "notes")}
        | {"html": prosemirror_to_html(a.get("description")),
           "notesHtml": prosemirror_to_html(a.get("notes"))}
        for a in c.get("attacks", [])
    ]
    items = [
        {k: v for k, v in it.items() if k not in ("description", "notes")}
        | {"html": prosemirror_to_html(it.get("description"))}
        for it in c.get("inventory", {}).get("items", [])
    ]

    health = c.get("health", {})
    hit_dice = c.get("classes", {}).get("hitDice", {})
    from . import leveling
    start_level = sum(cl["level"] for cl in classes) or 1

    definition = {
        "name": c.get("name", "Unnamed"),
        "species": c.get("species", ""),
        "background": c.get("background", ""),
        "classes": classes,
        "abilityScores": scores,
        "skills": skills,
        "saves": saves,
        "proficiencies": c.get("proficiencies", {}),
        "speed": c.get("speed", {}),
        "senses": c.get("conditions", []),        # HD "conditions" = darkvision etc.
        "traits": c.get("defenses", []),           # e.g. Fey Ancestry
        "features": features,
        "attacks": attacks,
        "inventory": {"currency": c.get("inventory", {}).get("currency", {}), "items": items},
        "spellcasting": {"ability": sc.get("ability"), "slotsMax": slots_max, "spells": spells},
        "resources": resources_def,
        "hitDiceMax": {k: v.get("totalDice", 0) for k, v in hit_dice.items() if v.get("totalDice")},
        "notes": prosemirror_to_html(c.get("notes")) if isinstance(c.get("notes"), dict) else "",
        "maxHpOverride": None,
        "acOverride": None,
        "proficiencyBonusOverride": None,
        "portrait": data.get("characterImage", ""),
    }

    state = {
        "currentHp": health.get("currentHitPoints", 0),
        "tempHp": health.get("temporaryHitPoints", 0),
        "deathSaves": {"success": health.get("deathSavesSuccess", 0),
                       "failure": health.get("deathSavesFailure", 0)},
        "slotsCurrent": slots_current,
        "resourcesExpended": resources_state,
        "hitDiceCurrent": {k: v.get("currentDice", 0) for k, v in hit_dice.items() if v.get("totalDice")},
        "conditionsActive": [],
        "inspiration": bool(c.get("inspiration", False)),
        "xp": leveling.xp_for_level(start_level),
    }

    return {
        "id": str(uuid.uuid4()),
        "owner": owner,
        "source": "heros-diary",
        "sourceVersion": data.get("metadata", {}).get("appVersion", ""),
        "definition": definition,
        "state": state,
    }


def merge_reimport(existing: dict, incoming: dict, replace: bool = False) -> dict:
    """Re-import: refresh definition, preserve live state (unless replace=True).

    On merge we also reconcile the few couplings between the two partitions:
      - current HP is clamped to the (possibly new) max HP
      - newly-opened spell-slot tiers start full; existing tiers keep current
    """
    if replace:
        incoming["id"] = existing["id"]
        incoming["owner"] = existing.get("owner")
        return incoming

    merged = dict(existing)
    merged["definition"] = incoming["definition"]
    merged["sourceVersion"] = incoming["sourceVersion"]

    state = dict(existing["state"])
    # clamp current HP to new computed/override max
    from . import rules
    new_max = rules.max_hp(incoming["definition"])["value"]
    state["currentHp"] = min(state.get("currentHp", new_max), new_max)
    # reconcile slots: keep current where tier existed, fill new tiers
    new_slots_max = incoming["definition"]["spellcasting"]["slotsMax"]
    cur = state.get("slotsCurrent", {})
    state["slotsCurrent"] = {
        lvl: cur.get(lvl, mx) for lvl, mx in new_slots_max.items()
    }
    merged["state"] = state
    return merged
