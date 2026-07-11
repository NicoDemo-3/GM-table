"""
Content catalog — feats, spells, and features available to the level-up flow.

Two layers:
  built-in  : SRD-clean feats (from leveling.SRD_FEATS). Always present.
  imported  : whatever the user loads via /api/content/import — produced by their
              own local LLM reading their own books, so the copyrighted text never
              ships with the app, it's supplied on their machine.

Imported content is stored in the settings table (key "content") so it persists.

Import schema (all keys optional; arrays):
{
  "feats":    [{ "name": str, "category": str?, "asi": ("choice"|"STR_or_DEX"|null)?,
                 "repeatable": bool?, "text": str }],
  "spells":   [{ "name": str, "level": int, "school": str?, "classes": [str]?, "text": str }],
  "features": [{ "name": str, "class": str?, "level": int?, "text": str }]
}
Unknown fields are ignored; bad entries are skipped and counted in the report.
"""

from . import store, leveling

_CONTENT_KEY = "content"


def _empty():
    return {"feats": [], "spells": [], "features": []}


def get_imported():
    return store.get_setting(_CONTENT_KEY, _empty())


def get_catalog():
    """Built-in + imported, deduped by (kind, name)."""
    imported = get_imported()
    feats = list(leveling.SRD_FEATS)
    seen = {f["name"].lower() for f in feats}
    for f in imported.get("feats", []):
        if f.get("name", "").lower() not in seen:
            feats.append(f)
            seen.add(f["name"].lower())
    return {
        "feats": feats,
        "spells": imported.get("spells", []),
        "features": imported.get("features", []),
        "counts": {
            "feats": len(feats), "builtinFeats": len(leveling.SRD_FEATS),
            "spells": len(imported.get("spells", [])),
            "features": len(imported.get("features", [])),
        },
    }


def _clean_feat(f):
    if not isinstance(f, dict) or not f.get("name") or not f.get("text"):
        return None
    return {
        "key": "imp-" + f["name"].lower().replace(" ", "-")[:40],
        "name": str(f["name"]), "category": str(f.get("category", "General")),
        "asi": f.get("asi") if f.get("asi") in ("choice", "STR_or_DEX") else None,
        "repeatable": bool(f.get("repeatable", False)), "text": str(f["text"]),
        "source": "imported",
    }


def _clean_spell(s):
    if not isinstance(s, dict) or not s.get("name"):
        return None
    return {
        "name": str(s["name"]), "level": int(s.get("level", 0)),
        "school": str(s.get("school", "")), "classes": list(s.get("classes", []) or []),
        "text": str(s.get("text", "")), "source": "imported",
    }


def _clean_feature(ft):
    if not isinstance(ft, dict) or not ft.get("name"):
        return None
    return {
        "name": str(ft["name"]), "class": str(ft.get("class", "")),
        "level": int(ft.get("level", 0)) if str(ft.get("level", "")).isdigit() else None,
        "text": str(ft.get("text", "")), "source": "imported",
    }


def import_content(data, mode="merge"):
    """Validate + store imported content. mode 'merge' adds; 'replace' overwrites.
    Returns a report of how many entries were accepted/skipped per kind."""
    if not isinstance(data, dict):
        return {"error": "Import must be a JSON object with feats/spells/features arrays."}

    cleaners = {"feats": _clean_feat, "spells": _clean_spell, "features": _clean_feature}
    existing = _empty() if mode == "replace" else get_imported()
    report = {}
    for kind, clean in cleaners.items():
        incoming = data.get(kind, []) or []
        accepted, skipped = [], 0
        for item in incoming:
            c = clean(item)
            if c:
                accepted.append(c)
            else:
                skipped += 1
        # dedupe against existing by name
        names = {x["name"].lower() for x in existing.get(kind, [])}
        added = [a for a in accepted if a["name"].lower() not in names]
        existing.setdefault(kind, [])
        existing[kind].extend(added)
        report[kind] = {"added": len(added), "skipped": skipped,
                        "duplicates": len(accepted) - len(added)}

    store.set_setting(_CONTENT_KEY, existing)
    report["totals"] = {k: len(existing.get(k, [])) for k in cleaners}
    return report
