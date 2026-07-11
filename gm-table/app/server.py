"""
Self-hosted GM table — phase 1 spine.

Three views served from one server, kept in sync over WebSockets:
  /            DM dashboard  (import characters, open sheets/display)
  /sheet/<id>  character sheet (editable, live-synced)
  /display     player display (read-only party + initiative; phase-1 stub)

Sync model: the SQLite store on the host is the single source of truth. A client
sends a `patch` (a dotted path into state + a value); the server applies it,
recomputes derived stats, persists, and broadcasts the fresh character to every
client in the room. Full-character broadcast keeps phase 1 simple and correct.
"""

import json
from flask import Flask, render_template, request, jsonify, abort
from flask_socketio import SocketIO, emit, join_room

from . import store, rules, glossary, leveling, content, tools
from . import compendium as comp
from . import widgets as W
from . import heros_diary as hd

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

store.init()


def _schedule_backup():
    import threading
    try:
        store.backup_db()
    except Exception:
        pass
    t = threading.Timer(6 * 3600, _schedule_backup)
    t.daemon = True
    t.start()


_schedule_backup()  # backup on startup, then every 6 hours (keeps newest 10)


def _visible_chars(camp):
    """Characters for player/DM party views: drop benched, and honor an A/B split."""
    chars = store.characters_in(camp["id"])
    party = camp.get("party", {}) or {}
    benched = set(party.get("benched", []))
    split = party.get("split", {}) or {}
    active = split.get("active", "All")
    groups = split.get("groups", {}) or {}
    out = []
    for c in chars:
        if c["id"] in benched:
            continue
        if active != "All" and groups.get(c["id"], "All") not in (active, "All"):
            continue
        out.append(c)
    return out


def _thresholds():
    return store.get_setting("xp_thresholds", leveling.XP_TABLE)


def view_model(char: dict) -> dict:
    """What clients render: stored doc + live-computed derived block + XP info."""
    derived = rules.derive(char)
    xp = char.get("state", {}).get("xp", 0)
    th = _thresholds()
    total = derived["totalLevel"]
    implied = leveling.level_from_xp(xp, th)
    nxt = leveling.xp_for_level(min(total + 1, 20), th)
    cur_floor = leveling.xp_for_level(total, th)
    derived["xp"] = {
        "current": xp, "level": total, "impliedLevel": implied,
        "pending": max(0, implied - total),
        "thisLevelFloor": cur_floor, "nextLevelAt": nxt,
        "intoLevel": max(0, xp - cur_floor), "span": max(1, nxt - cur_floor),
    }
    return {**char, "derived": derived}


# ---------- HTTP ----------

def _campaign_or_404(cid):
    camp = store.get_campaign(cid)
    if not camp:
        abort(404)
    return camp


@app.route("/")
def picker():
    """Campaign picker — the clean-slate landing page."""
    return render_template("picker.html", campaigns=store.all_campaigns())


@app.route("/c/<cid>")
def dashboard(cid):
    camp = _campaign_or_404(cid)
    chars = [view_model(c) for c in store.characters_in(cid)]
    return render_template("dashboard.html", campaign=camp, characters=chars)


@app.route("/sheet/<char_id>")
def sheet(char_id):
    char = store.get(char_id)
    if not char:
        abort(404)
    camp = store.get_campaign(char.get("campaignId")) or {"id": "", "name": "", "widgets": []}
    custom = [w for w in camp.get("widgets", []) if "sheet" in w.get("cards", [])]
    return render_template("sheet.html", char=view_model(char), reference=glossary.REFERENCE,
                           campaign=camp, custom_widgets=custom)


@app.route("/c/<cid>/play")
def play(cid):
    camp = _campaign_or_404(cid)
    chars = [view_model(c) for c in _visible_chars(camp)]
    return render_template("play.html", characters=chars, campaign=camp)


@app.route("/c/<cid>/overview")
def overview(cid):
    camp = _campaign_or_404(cid)
    chars = [view_model(c) for c in _visible_chars(camp)]
    return render_template("overview.html", characters=chars, reference=glossary.REFERENCE, campaign=camp)


@app.route("/c/<cid>/widgets")
def widgets_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("widgets.html", campaign=camp,
                           system_widgets=W.system_widgets(camp.get("system", "dnd5e")),
                           cards=W.CARDS, types=W.CUSTOM_TYPES)


@app.route("/c/<cid>/builder")
def builder_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("builder.html", campaign=camp,
                           library=W.library(camp), cards=W.CARDS,
                           layouts=camp.get("layouts", {}))


def _canvas(camp):
    return camp.setdefault("canvas", {
        "windows": {}, "active": "p_default", "shared": False,
        "presets": [{"id": "p_default", "name": "Default", "members": [], "pan": {"x": 0, "y": 0}, "zoom": 1, "overrides": {}}],
    })


@app.route("/c/<cid>/canvas")
def canvas_page(cid):
    camp = _campaign_or_404(cid)
    tools_list = [
        ("combat", "Combat Tracker"), ("bestiary", "Bestiary"), ("npcs", "NPCs"),
        ("tables", "Roll Tables"), ("shop", "Shop"), ("world", "World & Time"),
        ("map", "Map"), ("sounds", "Soundboard"), ("overview", "DM Overview"),
        ("party-cards", "Party Cards"), ("widgets", "Widget Library"), ("builder", "Sheet Builder"),
    ]
    return render_template("canvas.html", campaign=camp, canvas=_canvas(camp), tools=tools_list)


@app.route("/api/campaign/<cid>/canvas", methods=["POST"])
def api_save_canvas(cid):
    camp = _campaign_or_404(cid)
    camp["canvas"] = request.get_json(silent=True) or _canvas(camp)
    store.save_campaign(camp)
    return jsonify(ok=True)


@app.route("/c/<cid>/party-cards")
def party_cards_page(cid):
    camp = _campaign_or_404(cid)
    chars = [view_model(c) for c in _visible_chars(camp)]
    return render_template("party_cards.html", campaign=camp, characters=chars,
                           library=W.library(camp), layout=camp.get("layouts", {}).get("party", []))


@app.route("/c/<cid>/cards/<card>")
def cards_page(cid, card):
    camp = _campaign_or_404(cid)
    if card not in W.CARDS:
        abort(404)
    if card in ("sheet", "party"):
        entities = [view_model(c) for c in _visible_chars(camp)]
    elif card == "combat":
        entities = (camp.get("encounter") or {}).get("combatants", [])
    elif card == "npc":
        entities = camp.get("npcs", [])
    elif card == "bestiary":
        entities = camp.get("bestiary", [])
    else:
        entities = []
    return render_template("cards.html", campaign=camp, card=card, entities=entities,
                           library=W.library(camp), layout=camp.get("layouts", {}).get(card, []))


@app.route("/api/campaign/<cid>/layout/<card>", methods=["POST"])
def api_save_layout(cid, card):
    camp = _campaign_or_404(cid)
    if card not in W.CARDS:
        abort(404)
    camp.setdefault("layouts", {})[card] = request.get_json(silent=True) or []
    store.save_campaign(camp)
    return jsonify(ok=True)


# ---------- campaign API ----------

@app.route("/api/campaign", methods=["POST"])
def api_create_campaign():
    data = request.get_json(silent=True) or {}
    camp = store.create_campaign((data.get("name") or "New Campaign").strip(),
                                 data.get("system", "dnd5e"))
    return jsonify(id=camp["id"])


@app.route("/api/campaign/<cid>", methods=["DELETE"])
def api_delete_campaign(cid):
    store.delete_campaign(cid)
    return jsonify(ok=True)


@app.route("/api/campaign/<cid>/export")
def api_export_campaign(cid):
    bundle = store.export_campaign(cid)
    if not bundle:
        abort(404)
    from flask import Response
    fname = (bundle["campaign"]["name"] or "campaign").replace(" ", "_")
    return Response(json.dumps(bundle, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.gmtable.json"'})


@app.route("/api/campaign/import", methods=["POST"])
def api_import_campaign():
    try:
        data = json.load(request.files["file"]) if "file" in request.files else request.get_json()
    except Exception:
        return jsonify(error="Couldn't read that as JSON."), 400
    try:
        camp = store.import_campaign(data)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(id=camp["id"])


# ---------- widget library API ----------

@app.route("/api/campaign/<cid>/widget", methods=["POST"])
def api_add_widget(cid):
    camp = _campaign_or_404(cid)
    try:
        w = W.validate_custom(request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    import uuid
    w["id"] = "cw_" + uuid.uuid4().hex[:8]
    camp.setdefault("widgets", []).append(w)
    store.save_campaign(camp)
    return jsonify(widget=w)


@app.route("/api/campaign/<cid>/widget/<wid>", methods=["PUT", "DELETE"])
def api_edit_widget(cid, wid):
    camp = _campaign_or_404(cid)
    widgets = camp.setdefault("widgets", [])
    idx = next((i for i, w in enumerate(widgets) if w["id"] == wid), None)
    if idx is None:
        abort(404)
    if request.method == "DELETE":
        widgets.pop(idx)
        store.save_campaign(camp)
        return jsonify(ok=True)
    try:
        upd = W.validate_custom(request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    upd["id"] = wid
    widgets[idx] = upd
    store.save_campaign(camp)
    return jsonify(widget=upd)


@app.route("/content")
def content_page():
    return render_template("content.html", catalog=content.get_catalog(),
                           thresholds=_thresholds(), default_thresholds=leveling.XP_TABLE)


@app.route("/api/content", methods=["GET"])
def api_content():
    return jsonify(content.get_catalog())


@app.route("/api/content/import", methods=["POST"])
def api_content_import():
    try:
        data = json.load(request.files["file"]) if "file" in request.files else request.get_json()
    except Exception:
        return jsonify(error="Couldn't read that as JSON."), 400
    report = content.import_content(data, mode=request.args.get("mode", "merge"))
    if "error" in report:
        return jsonify(report), 400
    return jsonify(report)


@app.route("/api/settings/thresholds", methods=["POST"])
def api_set_thresholds():
    data = request.get_json(silent=True) or {}
    th = data.get("thresholds")
    if not isinstance(th, dict):
        return jsonify(error="Expected a thresholds object."), 400
    try:
        clean = {str(int(k)): int(v) for k, v in th.items()}
    except (ValueError, TypeError):
        return jsonify(error="Thresholds must be level:xp integer pairs."), 400
    store.set_setting("xp_thresholds", clean)
    return jsonify(ok=True, thresholds=clean)


@app.route("/api/levelup/plan/<char_id>")
def api_levelup_plan(char_id):
    char = store.get(char_id)
    if not char:
        abort(404)
    gaining = request.args.get("class") or (char["definition"]["classes"][0]["name"]
                                            if char["definition"]["classes"] else None)
    return jsonify(leveling.level_up_plan(char["definition"], gaining, _thresholds()))


@app.route("/api/import", methods=["POST"])
def api_import():
    """Import a Hero's Diary JSON. ?replace=<id> to rebuild an existing character."""
    try:
        data = json.load(request.files["file"])
    except Exception:
        return jsonify(error="Couldn't read that file as JSON."), 400
    if "character" not in data:
        return jsonify(error="That doesn't look like a Hero's Diary export."), 400
    if not hd.version_ok(data):
        ver = data.get("metadata", {}).get("appVersion", "unknown")
        return jsonify(error=f"Unsupported Hero's Diary version ({ver}). "
                             f"Importer targets {', '.join(hd.SUPPORTED_VERSIONS)}.x."), 400

    incoming = hd.from_heros_diary(data, owner=request.form.get("owner"))
    campaign_id = request.args.get("campaign") or request.form.get("campaign")
    replace_id = request.args.get("replace")
    if replace_id:
        existing = store.get(replace_id)
        if not existing:
            return jsonify(error="Character to replace no longer exists."), 404
        full = request.args.get("mode") == "full"
        merged = hd.merge_reimport(existing, incoming, replace=full)
        merged["campaignId"] = existing.get("campaignId", campaign_id)
        store.save(merged)
        socketio.emit("character:update", view_model(merged), room=merged["id"])
        return jsonify(id=merged["id"], merged=not full)

    store.save(incoming, campaign_id=campaign_id)
    return jsonify(id=incoming["id"])


@app.route("/api/character/<char_id>", methods=["DELETE"])
def api_delete(char_id):
    store.delete(char_id)
    return jsonify(ok=True)


# ---------- WebSocket sync ----------

def _set_path(obj: dict, path: str, value):
    """Set a dotted path like 'state.currentHp' or 'definition.acOverride'."""
    keys = path.split(".")
    for k in keys[:-1]:
        obj = obj.setdefault(k, {})
    obj[keys[-1]] = value


@socketio.on("join")
def on_join(data):
    """Subscribe to a character room and/or a campaign room."""
    char_id = data.get("characterId")
    if char_id:
        join_room(char_id)
    camp_id = data.get("campaignId")
    if camp_id:
        join_room("camp:" + camp_id)


@socketio.on("patch")
def on_patch(data):
    """Apply one field change and broadcast the updated character to the room."""
    char_id = data.get("characterId")
    path = data.get("path", "")
    value = data.get("value")
    char = store.get(char_id)
    if not char or not (path.startswith("state.") or path.startswith("definition.")):
        return  # ignore unknown character or out-of-bounds path
    _set_path(char, path, value)
    store.save(char)
    emit("character:update", view_model(char), room=char_id)


@socketio.on("xp:award")
def on_xp_award(data):
    """Add (or remove) XP. Doesn't auto-level — the client offers the level-up."""
    char = store.get(data.get("characterId"))
    if not char:
        return
    char["state"]["xp"] = max(0, char["state"].get("xp", 0) + int(data.get("amount", 0)))
    store.save(char)
    emit("character:update", view_model(char), room=char["id"])


@socketio.on("level:set")
def on_level_set(data):
    """DM quick-set: put a class at an exact total level (for starting high)."""
    char = store.get(data.get("characterId"))
    if not char:
        return
    target = max(1, min(20, int(data.get("level", 1))))
    classes = char["definition"]["classes"]
    if not classes:
        return
    name = data.get("class") or classes[0]["name"]
    cls = next((c for c in classes if c["name"] == name), classes[0])
    others = sum(c["level"] for c in classes if c is not cls)
    cls["level"] = max(1, target - others)
    new_total = sum(c["level"] for c in classes)
    char["state"]["xp"] = leveling.xp_for_level(new_total, _thresholds())
    char["definition"]["maxHpOverride"] = None
    char["state"]["currentHp"] = rules.max_hp(char["definition"])["value"]
    store.save(char)
    emit("character:update", view_model(char), room=char["id"])


@socketio.on("levelup:apply")
def on_levelup_apply(data):
    """Apply a completed level-up: bump the class, add HP, apply ASI/feat, subclass."""
    char = store.get(data.get("characterId"))
    if not char:
        return
    d, s = char["definition"], char["state"]
    name = data.get("gainingClass") or (d["classes"][0]["name"] if d["classes"] else None)
    cls = next((c for c in d["classes"] if c["name"] == name), None)
    if not cls:
        return

    cur_max = rules.max_hp(d)["value"]
    cls["level"] += 1
    hp_gain = int(data.get("hpGain", 0))
    if hp_gain:
        d["maxHpOverride"] = cur_max + hp_gain
        s["currentHp"] = min(s.get("currentHp", 0) + hp_gain, d["maxHpOverride"])

    if data.get("subclassName"):
        cls["subclass"] = data["subclassName"]

    for ab, inc in (data.get("asi") or {}).items():
        if ab in rules.ABILITIES:
            d.setdefault("abilityScores", {})[ab] = min(20, d["abilityScores"].get(ab, 10) + int(inc))

    feat = data.get("feat")
    if feat and feat.get("name"):
        d.setdefault("features", []).append({
            "id": "feat-" + str(feat["name"]).lower().replace(" ", "-")[:30],
            "name": "Feat: " + feat["name"],
            "html": "<p>" + str(feat.get("text", "")) + "</p>",
        })

    new_total = sum(c["level"] for c in d["classes"])
    s["xp"] = max(s.get("xp", 0), leveling.xp_for_level(new_total, _thresholds()))
    store.save(char)
    emit("character:update", view_model(char), room=char["id"])


def _restores_on(restore_list, *kinds):
    """True if a resource's restoreOn list mentions any of the given rest kinds."""
    text = " ".join(str(x) for x in (restore_list or [])).lower()
    return any(k in text for k in kinds)


@socketio.on("rest")
def on_rest(data):
    """Apply a short or long rest's restores and broadcast the result."""
    char_id = data.get("characterId")
    kind = data.get("kind")  # 'short' | 'long'
    char = store.get(char_id)
    if not char or kind not in ("short", "long"):
        return
    d, s = char["definition"], char["state"]

    if kind == "long":
        max_hp = rules.max_hp(d)["value"]
        s["currentHp"] = max_hp
        s["tempHp"] = 0
        s["deathSaves"] = {"success": 0, "failure": 0}
        # all spell slots back
        s["slotsCurrent"] = dict(d.get("spellcasting", {}).get("slotsMax", {}))
        # hit dice: regain half your total (min 1), capped at each die's max
        hd_max = d.get("hitDiceMax", {})
        total = sum(hd_max.values())
        regain = max(1, total // 2)
        cur = dict(s.get("hitDiceCurrent", {}))
        for die, mx in hd_max.items():
            if regain <= 0:
                break
            room = mx - cur.get(die, 0)
            add = min(room, regain)
            cur[die] = cur.get(die, 0) + add
            regain -= add
        s["hitDiceCurrent"] = cur
        # drop one exhaustion level
        conds = []
        for c in s.get("conditions", []):
            if c.get("key") == "exhaustion":
                lvl = (c.get("level") or 1) - 1
                if lvl <= 0:
                    continue  # exhaustion cleared
                c["level"] = lvl
            conds.append(c)
        s["conditions"] = conds
        # long rest also covers short-rest resources
        for r in d.get("resources", []):
            if _restores_on(r.get("restoreOn"), "short", "long", "dawn", "day"):
                s.setdefault("resourcesExpended", {})[r["id"]] = 0

    else:  # short rest — refresh short-rest resources only (HP via hit dice is manual)
        for r in d.get("resources", []):
            if _restores_on(r.get("restoreOn"), "short"):
                s.setdefault("resourcesExpended", {})[r["id"]] = 0

    store.save(char)
    emit("character:update", view_model(char), room=char_id)


@socketio.on("combat:update")
def on_combat_update(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    camp["encounter"] = data.get("encounter") or camp.get("encounter")
    store.save_campaign(camp)
    emit("combat:update", {"encounter": camp["encounter"]}, room="camp:" + camp["id"])


@socketio.on("world:update")
def on_world_update(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    camp["world"] = data.get("world") or camp.get("world")
    store.save_campaign(camp)
    emit("world:update", {"world": camp["world"]}, room="camp:" + camp["id"])


@socketio.on("party:update")
def on_party_update(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    camp["party"] = data.get("party") or camp.get("party")
    store.save_campaign(camp)
    emit("party:update", {"party": camp["party"]}, room="camp:" + camp["id"])


def _map(camp):
    return camp.setdefault("map", {"image": None, "grid": {"size": 70, "show": False},
                                   "fog": {"cols": 0, "rows": 0, "cell": 48, "revealed": []},
                                   "playerOpacity": 1.0})


@socketio.on("map:fog")
def on_map_fog(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    _map(camp)["fog"] = data.get("fog") or _map(camp)["fog"]
    store.save_campaign(camp)
    emit("map:fog", {"fog": _map(camp)["fog"]}, room="camp:" + camp["id"])


@socketio.on("map:opacity")
def on_map_opacity(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    _map(camp)["playerOpacity"] = float(data.get("playerOpacity", 1.0))
    store.save_campaign(camp)
    emit("map:opacity", {"playerOpacity": _map(camp)["playerOpacity"]}, room="camp:" + camp["id"])


@socketio.on("map:grid")
def on_map_grid(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    _map(camp)["grid"] = data.get("grid") or _map(camp)["grid"]
    store.save_campaign(camp)
    emit("map:grid", {"grid": _map(camp)["grid"]}, room="camp:" + camp["id"])


@socketio.on("map:tokens")
def on_map_tokens(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    _map(camp)["tokens"] = data.get("tokens", [])
    store.save_campaign(camp)
    emit("map:tokens", {"tokens": _map(camp)["tokens"]}, room="camp:" + camp["id"])


# ---------- tool pages ----------

@app.route("/c/<cid>/combat")
def combat_page(cid):
    camp = _campaign_or_404(cid)
    party = [view_model(c) for c in store.characters_in(cid)]
    return render_template("combat.html", campaign=camp, party=party,
                           bestiary=camp.get("bestiary", []), npcs=camp.get("npcs", []),
                           presets=camp.get("encounterPresets", []),
                           reference=glossary.REFERENCE)


@app.route("/c/<cid>/combat-view")
def combat_view(cid):
    camp = _campaign_or_404(cid)
    return render_template("combat_view.html", campaign=camp)


@app.route("/c/<cid>/bestiary")
def bestiary_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("bestiary.html", campaign=camp, bestiary=camp.get("bestiary", []))


@app.route("/c/<cid>/npcs")
def npcs_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("npcs.html", campaign=camp, npcs=camp.get("npcs", []))


@app.route("/c/<cid>/tables")
def tables_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("tables.html", campaign=camp, tables=camp.get("rollTables", []))


@app.route("/api/campaign/<cid>/player-rules/load-srd", methods=["POST"])
def api_load_srd(cid):
    """Load the bundled CC-licensed SRD 5.2.1 rules glossary into player rules."""
    import uuid
    from . import srd_rules
    camp = _campaign_or_404(cid)
    replace = (request.get_json(silent=True) or {}).get("replace")
    srd_titles = {g["title"] for g in srd_rules.GLOSSARY}
    # keep only the user's own (non-SRD) rules; we re-add the SRD set fresh each time
    kept = [] if replace else [r for r in camp.get("playerRules", [])
                               if r.get("id") != "pr_srd_attr" and r["title"] not in srd_titles]
    srd = [{"id": "pr_srd_attr", "title": "SRD 5.2.1 — Attribution & License",
            "text": srd_rules.ATTRIBUTION}]
    for r in srd_rules.GLOSSARY:
        srd.append({"id": "pr_" + uuid.uuid4().hex[:8], "title": r["title"], "text": r["text"]})
    camp["playerRules"] = srd + kept
    store.save_campaign(camp)
    socketio.emit("player:rules", {"rules": camp["playerRules"]}, room=cid)
    return jsonify(added=len(srd) - 1, total=len(camp["playerRules"]))


@app.route("/api/campaign/<cid>/player-rules", methods=["GET", "POST"])
def api_player_rules(cid):
    """DM imports rules (md or json) shown read-only in the player sidebar.
    JSON: [{title, text}] or {rules:[...]}. Markdown: '## Title' then body."""
    import uuid
    camp = _campaign_or_404(cid)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        raw = data.get("text", "")
        rules = []
        stripped = raw.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                j = json.loads(raw)
                arr = j if isinstance(j, list) else j.get("rules", [])
                for r in arr:
                    if isinstance(r, dict) and r.get("title"):
                        rules.append({"id": "pr_" + uuid.uuid4().hex[:8],
                                      "title": str(r["title"]), "text": str(r.get("text", ""))})
            except Exception:
                return jsonify(error="Couldn't parse JSON."), 400
        else:
            cur = None
            for line in raw.splitlines():
                if line.startswith("## "):
                    if cur:
                        rules.append(cur)
                    cur = {"id": "pr_" + uuid.uuid4().hex[:8], "title": line[3:].strip(), "text": ""}
                elif cur is not None:
                    cur["text"] += line + "\n"
            if cur:
                rules.append(cur)
        for r in rules:
            r["text"] = r["text"].strip()
        if data.get("replace"):
            camp["playerRules"] = rules
        else:
            camp.setdefault("playerRules", []).extend(rules)
        store.save_campaign(camp)
        socketio.emit("player:rules", {"rules": camp["playerRules"]}, room=cid)
        return jsonify(added=len(rules), total=len(camp["playerRules"]))
    return jsonify(rules=camp.get("playerRules", []))


@app.route("/api/campaign/<cid>/player-rules/<rid>", methods=["DELETE"])
def api_player_rules_del(cid, rid):
    camp = _campaign_or_404(cid)
    camp["playerRules"] = [r for r in camp.get("playerRules", []) if r.get("id") != rid]
    store.save_campaign(camp)
    socketio.emit("player:rules", {"rules": camp["playerRules"]}, room=cid)
    return jsonify(total=len(camp["playerRules"]))


@app.route("/api/campaign/<cid>/player-data")
def api_player_data(cid):
    """Everything the player sidebar needs: rules + pushed handouts (read-only)."""
    camp = _campaign_or_404(cid)
    return jsonify(rules=camp.get("playerRules", []), handouts=camp.get("playerHandouts", []))


@app.route("/c/<cid>/guide")
def player_guide_page(cid):
    """Full-page player guide: rules, pushed content, private notes — all collapsible."""
    camp = _campaign_or_404(cid)
    chars = [{"id": c["id"], "name": c["definition"]["name"]} for c in store.characters_in(cid)]
    return render_template("player_guide.html", campaign=camp, characters=chars)


@app.route("/c/<cid>/player-content")
def player_content_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("player_content.html", campaign=camp)


@app.route("/c/<cid>/shop")
def shop_page(cid):
    camp = _campaign_or_404(cid)
    from . import currency
    return render_template("shop.html", campaign=camp,
                           shop_types=tools.SHOP_TYPES, economies=tools.ECONOMIES,
                           currency=currency.config(camp))


@app.route("/api/campaign/<cid>/currency", methods=["GET", "POST"])
def api_currency(cid):
    from . import currency
    camp = _campaign_or_404(cid)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        units = [u for u in data.get("units", []) if u.get("code") and u.get("inBase")]
        if units:
            camp["currency"] = {"base": data.get("base") or min(units, key=lambda u: u["inBase"])["code"],
                                "units": [{"code": u["code"], "name": u.get("name", u["code"]),
                                           "inBase": int(u["inBase"]),
                                           "inBreakdown": u.get("inBreakdown", True)} for u in units]}
            store.save_campaign(camp)
    return jsonify(currency.config(camp))


@app.route("/api/campaign/<cid>/push-handout", methods=["POST"])
def api_push_handout(cid):
    """DM pushes read-only content (a shop, an item list, a note) to players."""
    import uuid
    camp = _campaign_or_404(cid)
    data = request.get_json(silent=True) or {}
    h = {"id": "h_" + uuid.uuid4().hex[:8], "kind": data.get("kind", "note"),
         "title": data.get("title", "Untitled"), "payload": data.get("payload"),
         "ts": store._now() if hasattr(store, "_now") else ""}
    camp.setdefault("playerHandouts", []).append(h)
    store.save_campaign(camp)
    socketio.emit("player:handouts", {"handouts": camp["playerHandouts"]}, room=cid)
    return jsonify(handout=h, count=len(camp["playerHandouts"]))


@app.route("/api/campaign/<cid>/push-handout/<hid>", methods=["DELETE"])
def api_unpush_handout(cid, hid):
    camp = _campaign_or_404(cid)
    camp["playerHandouts"] = [h for h in camp.get("playerHandouts", []) if h.get("id") != hid]
    store.save_campaign(camp)
    socketio.emit("player:handouts", {"handouts": camp["playerHandouts"]}, room=cid)
    return jsonify(count=len(camp["playerHandouts"]))


@app.route("/c/<cid>/world")
def world_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("world.html", campaign=camp)


@app.route("/c/<cid>/map")
def map_page(cid):
    camp = _campaign_or_404(cid)
    party = [view_model(c) for c in store.characters_in(cid)]
    return render_template("map.html", campaign=camp, mapdata=_map(camp), party=party, encounter=camp.get("encounter"))


@app.route("/c/<cid>/map-view")
def map_view(cid):
    camp = _campaign_or_404(cid)
    return render_template("map_view.html", campaign=camp, mapdata=_map(camp))


_MAPS_DIR = (store._DB.parent / "maps")


@app.route("/maps/<path:fn>")
def serve_map(fn):
    from flask import send_from_directory
    return send_from_directory(_MAPS_DIR, fn)


@app.route("/api/campaign/<cid>/map/image", methods=["POST"])
def api_map_image(cid):
    camp = _campaign_or_404(cid)
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file."), 400
    import uuid
    _MAPS_DIR.mkdir(parents=True, exist_ok=True)
    ext = (f.filename.rsplit(".", 1)[-1] if "." in f.filename else "png").lower()[:5]
    fn = f"{cid}_{uuid.uuid4().hex[:8]}.{ext}"
    f.save(str(_MAPS_DIR / fn))
    m = _map(camp)
    m["image"] = "/maps/" + fn
    m["fog"] = {"cols": 0, "rows": 0, "cell": int(request.form.get("cell", 48)), "revealed": []}
    store.save_campaign(camp)
    socketio.emit("map:image", {"image": m["image"], "fog": m["fog"], "grid": m["grid"]},
                  room="camp:" + cid)
    return jsonify(image=m["image"])


@app.route("/api/campaign/<cid>/token/image", methods=["POST"])
def api_token_image(cid):
    _campaign_or_404(cid)
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file."), 400
    import uuid
    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext = (f.filename.rsplit(".", 1)[-1] if "." in f.filename else "png").lower()[:5]
    fn = f"tok_{cid}_{uuid.uuid4().hex[:8]}.{ext}"
    f.save(str(_MEDIA_DIR / fn))
    return jsonify(url="/media/" + fn)


# ---------- soundboard ----------

_MEDIA_DIR = (store._DB.parent / "media")


@app.route("/media/<path:fn>")
def serve_media(fn):
    from flask import send_from_directory
    return send_from_directory(_MEDIA_DIR, fn)


@app.route("/c/<cid>/sounds")
def sounds_page(cid):
    camp = _campaign_or_404(cid)
    return render_template("sounds.html", campaign=camp, sounds=camp.get("sounds", []))


@app.route("/api/campaign/<cid>/sound", methods=["POST"])
def api_sound_add(cid):
    camp = _campaign_or_404(cid)
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file."), 400
    import uuid
    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext = (f.filename.rsplit(".", 1)[-1] if "." in f.filename else "mp3").lower()[:5]
    fn = f"{cid}_{uuid.uuid4().hex[:8]}.{ext}"
    f.save(str(_MEDIA_DIR / fn))
    tile = {"id": "snd_" + uuid.uuid4().hex[:8],
            "label": request.form.get("label") or f.filename.rsplit(".", 1)[0],
            "url": "/media/" + fn, "loop": request.form.get("loop") == "1"}
    camp.setdefault("sounds", []).append(tile)
    store.save_campaign(camp)
    return jsonify(tile=tile)


@app.route("/api/campaign/<cid>/sound/<sid>", methods=["DELETE"])
def api_sound_del(cid, sid):
    camp = _campaign_or_404(cid)
    camp["sounds"] = [s for s in camp.get("sounds", []) if s.get("id") != sid]
    store.save_campaign(camp)
    return jsonify(ok=True)


# ---------- SRD starter content ----------

@app.route("/api/campaign/<cid>/seed-srd", methods=["POST"])
def api_seed_srd(cid):
    from . import srd_content
    camp = _campaign_or_404(cid)
    import uuid
    existing = {b.get("name"): b for b in camp.get("bestiary", [])}
    added = 0
    enriched = 0
    for m in srd_content.STARTER_BESTIARY:
        cur = existing.get(m["name"])
        if cur is not None:
            # Enrich a pre-full-statblock entry in place: fill only missing fields,
            # never overwrite numbers or text the GM may have customized.
            changed = False
            for k, v in m.items():
                if k in ("ac", "hp", "cr", "speed", "notes"):
                    continue
                if v and not cur.get(k):
                    cur[k] = v
                    changed = True
            if changed:
                enriched += 1
            continue
        camp.setdefault("bestiary", []).append({**m, "id": "it_" + uuid.uuid4().hex[:8], "hpMax": m["hp"]})
        added += 1
    store.save_campaign(camp)
    return jsonify(added=added, enriched=enriched)


@app.route("/api/campaign/<cid>/backup", methods=["POST"])
def api_backup(cid):
    path = store.backup_db()
    return jsonify(ok=bool(path))


# ---------- compendium ----------

@app.route("/c/<cid>/compendium")
def compendium_page(cid):
    camp = _campaign_or_404(cid)
    chars = [{"id": c["id"], "name": c["definition"]["name"]} for c in store.characters_in(cid)]
    npcs = [{"id": x["id"], "name": x.get("name", "NPC")} for x in camp.get("npcs", [])]
    beasts = [{"id": x["id"], "name": x.get("name", "Creature")} for x in camp.get("bestiary", [])]
    return render_template("compendium.html", campaign=camp, entries=camp.get("compendium", []),
                           types=comp.TYPES, characters=chars, npcs=npcs, beasts=beasts,
                           example=comp.EXAMPLE_MARKDOWN)


@app.route("/api/campaign/<cid>/compendium", methods=["POST"])
def api_comp_add(cid):
    camp = _campaign_or_404(cid)
    entry = comp.normalize(request.get_json(silent=True) or {})
    camp.setdefault("compendium", []).append(entry)
    store.save_campaign(camp)
    return jsonify(entry=entry)


@app.route("/api/campaign/<cid>/compendium/<eid>", methods=["PUT", "DELETE"])
def api_comp_edit(cid, eid):
    camp = _campaign_or_404(cid)
    arr = camp.setdefault("compendium", [])
    idx = next((i for i, e in enumerate(arr) if e.get("id") == eid), None)
    if idx is None:
        abort(404)
    if request.method == "DELETE":
        arr.pop(idx)
    else:
        upd = comp.normalize(request.get_json(silent=True) or {})
        upd["id"] = eid
        arr[idx] = upd
    store.save_campaign(camp)
    return jsonify(ok=True)


@app.route("/api/campaign/<cid>/compendium/import/preview", methods=["POST"])
def api_comp_preview(cid):
    _campaign_or_404(cid)
    if "file" in request.files:
        f = request.files["file"]
        text = f.read().decode("utf-8", "ignore")
        fname = f.filename or ""
    else:
        data = request.get_json(silent=True) or {}
        text, fname = data.get("text", ""), data.get("filename", "")
    try:
        entries = comp.parse_bundle(text, fname)
    except Exception as e:
        return jsonify(error=f"Couldn't parse that: {e}"), 400
    return jsonify(entries=entries, count=len(entries))


@app.route("/api/campaign/<cid>/compendium/import/commit", methods=["POST"])
def api_comp_commit(cid):
    camp = _campaign_or_404(cid)
    entries = (request.get_json(silent=True) or {}).get("entries", [])
    for e in entries:
        if "id" not in e:
            e["id"] = "ce_" + __import__("uuid").uuid4().hex[:8]
    camp.setdefault("compendium", []).extend(entries)
    store.save_campaign(camp)
    return jsonify(added=len(entries))


@app.route("/api/campaign/<cid>/compendium/pdf-text", methods=["POST"])
def api_comp_pdf_text(cid):
    """Extract a PDF's text so you can hand it to an LLM to produce an import file."""
    _campaign_or_404(cid)
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file."), 400
    try:
        from pypdf import PdfReader
        reader = PdfReader(f)
        text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        return jsonify(error=f"Couldn't read PDF: {e}"), 400
    return jsonify(text=text, pages=len(text.split("\n\n")))


@app.route("/api/campaign/<cid>/compendium/bulk-delete", methods=["POST"])
def api_comp_bulk_delete(cid):
    camp = _campaign_or_404(cid)
    ids = set((request.get_json(silent=True) or {}).get("ids", []))
    before = len(camp.get("compendium", []))
    camp["compendium"] = [e for e in camp.get("compendium", []) if e.get("id") not in ids]
    store.save_campaign(camp)
    return jsonify(deleted=before - len(camp["compendium"]))


@app.route("/api/campaign/<cid>/compendium/folder", methods=["POST"])
def api_comp_folder_op(cid):
    camp = _campaign_or_404(cid)
    data = request.get_json(silent=True) or {}
    op, name = data.get("op"), data.get("name", "")
    arr = camp.get("compendium", [])
    if op == "rename":
        new = data.get("newName", "")
        n = sum(1 for e in arr if e.get("folder") == name)
        for e in arr:
            if e.get("folder") == name:
                e["folder"] = new
        store.save_campaign(camp)
        return jsonify(updated=n)
    if op == "delete":
        # delete folder: move its entries to unfiled (does NOT delete entries)
        n = sum(1 for e in arr if e.get("folder") == name)
        for e in arr:
            if e.get("folder") == name:
                e["folder"] = ""
        store.save_campaign(camp)
        return jsonify(unfiled=n)
    if op == "delete-contents":
        # delete folder AND every entry in it
        before = len(arr)
        camp["compendium"] = [e for e in arr if e.get("folder") != name]
        store.save_campaign(camp)
        return jsonify(deleted=before - len(camp["compendium"]))
    return jsonify(error="Unknown op."), 400


@app.route("/api/campaign/<cid>/compendium/<eid>/to-bestiary", methods=["POST"])
def api_comp_to_bestiary(cid, eid):
    camp = _campaign_or_404(cid)
    entry = next((e for e in camp.get("compendium", []) if e.get("id") == eid), None)
    if not entry or entry.get("type") != "monster":
        abort(404)
    camp.setdefault("bestiary", []).append(comp.to_bestiary(entry))
    store.save_campaign(camp)
    return jsonify(ok=True)


@app.route("/api/campaign/<cid>/compendium/<eid>/apply/<char_id>", methods=["POST"])
def api_comp_apply(cid, eid, char_id):
    camp = _campaign_or_404(cid)
    entry = next((e for e in camp.get("compendium", []) if e.get("id") == eid), None)
    char = store.get(char_id)
    if not entry or not char or char.get("campaignId") != cid:
        abort(404)
    note = comp.apply_to_character(entry, char["definition"])
    store.save(char)
    socketio.emit("character:update", view_model(char), room=char["id"])
    return jsonify(note=note)


@app.route("/api/campaign/<cid>/compendium/<eid>/apply-entity/<col>/<iid>", methods=["POST"])
def api_comp_apply_entity(cid, eid, col, iid):
    """Apply a compendium entry to a loose NPC or bestiary creature."""
    key = {"npcs": "npcs", "bestiary": "bestiary"}.get(col)
    if not key:
        abort(404)
    camp = _campaign_or_404(cid)
    entry = next((e for e in camp.get("compendium", []) if e.get("id") == eid), None)
    ent = next((x for x in camp.get(key, []) if x.get("id") == iid), None)
    if not entry or not ent:
        abort(404)
    note = comp.apply_to_entity(entry, ent)
    store.save_campaign(camp)
    return jsonify(note=note)


@app.route("/reference")
def reference_library():
    from . import reference_content
    return render_template("reference.html", data=reference_content.CLASSIC_FANTASY,
                           cid=request.args.get("c"))


@app.route("/dm-links")
def dm_links_page():
    from . import dm_links
    return render_template("dm_links.html", groups=dm_links.DM_LINKS,
                           cid=request.args.get("c"))


# ---------- collection CRUD (bestiary / npcs / rollTables) ----------

_COLLECTIONS = {"bestiary": "bestiary", "npcs": "npcs", "tables": "rollTables",
                "encounters": "encounterPresets"}


@app.route("/api/campaign/<cid>/<col>", methods=["POST"])
def api_col_add(cid, col):
    key = _COLLECTIONS.get(col)
    if not key:
        abort(404)
    camp = _campaign_or_404(cid)
    import uuid
    item = request.get_json(silent=True) or {}
    item["id"] = "it_" + uuid.uuid4().hex[:8]
    camp.setdefault(key, []).append(item)
    store.save_campaign(camp)
    return jsonify(item=item)


@app.route("/api/campaign/<cid>/<col>/<iid>", methods=["PUT", "DELETE"])
def api_col_edit(cid, col, iid):
    key = _COLLECTIONS.get(col)
    if not key:
        abort(404)
    camp = _campaign_or_404(cid)
    arr = camp.setdefault(key, [])
    idx = next((i for i, x in enumerate(arr) if x.get("id") == iid), None)
    if idx is None:
        abort(404)
    if request.method == "DELETE":
        arr.pop(idx)
    else:
        upd = request.get_json(silent=True) or {}
        upd["id"] = iid
        arr[idx] = upd
    store.save_campaign(camp)
    return jsonify(ok=True)


@app.route("/api/campaign/<cid>/bestiary/import", methods=["POST"])
def api_bestiary_import(cid):
    """Import monsters from a JSON array; maps common field names tolerantly."""
    camp = _campaign_or_404(cid)
    try:
        data = json.load(request.files["file"]) if "file" in request.files else request.get_json()
    except Exception:
        return jsonify(error="Couldn't read that as JSON."), 400
    rows = data if isinstance(data, list) else data.get("monsters") or data.get("results") or []
    import uuid
    added = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        hp = r.get("hp") or r.get("hit_points") or r.get("maxHp") or 1
        item = {
            "id": "it_" + uuid.uuid4().hex[:8],
            "name": r.get("name") or r.get("Name") or "Creature",
            "ac": r.get("ac") or r.get("armor_class") or r.get("AC") or 10,
            "hp": hp, "hpMax": hp,
            "cr": r.get("cr") or r.get("challenge_rating") or "",
            "speed": r.get("speed") or "",
            "tags": r.get("tags") or [],
            "notes": r.get("notes") or r.get("desc") or "",
        }
        for k, alts in {
            "size": ("size",), "creatureType": ("creatureType", "type"),
            "alignment": ("alignment",), "xp": ("xp",),
            "abilityScores": ("abilityScores", "ability_scores"),
            "saves": ("saves", "saving_throws"), "skills": ("skills",),
            "senses": ("senses",), "languages": ("languages",),
            "traits": ("traits", "special_abilities"), "actions": ("actions",),
            "source": ("source",),
        }.items():
            for a in alts:
                if r.get(a):
                    item[k] = r[a]
                    break
        camp.setdefault("bestiary", []).append(item)
        added += 1
    store.save_campaign(camp)
    return jsonify(added=added)


# ---------- generators ----------

@app.route("/api/gen/npc")
def api_gen_npc():
    return jsonify(tools.npc())


@app.route("/api/gen/shop-name")
def api_gen_shop_name():
    return jsonify(name=tools.shop_name(request.args.get("type", "General Store")))


@app.route("/api/gen/shop")
def api_gen_shop():
    return jsonify(tools.shop(request.args.get("type", "General Store"),
                              request.args.get("economy", "Average"),
                              int(request.args.get("count", 8))))


@app.route("/api/gen/weather")
def api_gen_weather():
    return jsonify(tools.weather())


@app.route("/api/campaign/<cid>/tables/<iid>/roll")
def api_roll_table(cid, iid):
    import random
    camp = _campaign_or_404(cid)
    t = next((x for x in camp.get("rollTables", []) if x.get("id") == iid), None)
    if not t:
        abort(404)
    if t.get("type") == "ranged":
        die = t.get("die", "d100")
        sides = int(die[1:]) if die and die[0] == "d" else 100
        roll = random.randint(1, sides)
        row = next((r for r in t.get("rows", []) if r["min"] <= roll <= r["max"]), None)
        return jsonify(roll=roll, die=die, columns=t.get("columns", ["Result"]),
                       values=(row["values"] if row else []))
    return jsonify(result=tools.roll_table(t.get("entries", [])))


@app.route("/api/campaign/<cid>/tables/seed-critfail", methods=["POST"])
def api_seed_critfail(cid):
    from . import tables_content
    camp = _campaign_or_404(cid)
    import uuid
    if any(x.get("name") == tables_content.CRIT_FAIL["name"] for x in camp.get("rollTables", [])):
        return jsonify(added=0)
    camp.setdefault("rollTables", []).append({**tables_content.CRIT_FAIL, "id": "it_" + uuid.uuid4().hex[:8], "type": "ranged"})
    store.save_campaign(camp)
    return jsonify(added=1)


@socketio.on("hp:apply")
def on_hp_apply(data):
    """Apply damage (negative) or healing (positive); damage eats temp HP first."""
    char = store.get(data.get("characterId"))
    if not char:
        return
    s, d = char["state"], char["definition"]
    delta = int(data.get("delta", 0))
    max_hp = rules.max_hp(d)["value"]
    if delta < 0:
        dmg = -delta
        temp = s.get("tempHp", 0)
        absorbed = min(temp, dmg)
        s["tempHp"] = temp - absorbed
        s["currentHp"] = max(0, s.get("currentHp", 0) - (dmg - absorbed))
    else:
        s["currentHp"] = min(max_hp, s.get("currentHp", 0) + delta)
        if s["currentHp"] > 0:
            s["deathSaves"] = {"success": 0, "failure": 0}
    store.save(char)
    emit("character:update", view_model(char), room=char["id"])


@socketio.on("deathsave")
def on_deathsave(data):
    char = store.get(data.get("characterId"))
    if not char:
        return
    s = char["state"]
    ds = s.setdefault("deathSaves", {"success": 0, "failure": 0})
    r = data.get("result")
    if r == "reset":
        s["deathSaves"] = {"success": 0, "failure": 0}
    elif r == "success":
        ds["success"] = min(3, ds["success"] + 1)
    elif r == "failure":
        ds["failure"] = min(3, ds["failure"] + 1)
    elif r == "nat20":
        s["deathSaves"] = {"success": 0, "failure": 0}
        s["currentHp"] = max(1, s.get("currentHp", 0))
    elif r == "nat1":
        ds["failure"] = min(3, ds["failure"] + 2)
    store.save(char)
    emit("character:update", view_model(char), room=char["id"])


@socketio.on("spendhd")
def on_spendhd(data):
    """Spend one hit die on a short rest: roll it + CON, heal, capped at max."""
    import random
    char = store.get(data.get("characterId"))
    if not char:
        return
    s, d = char["state"], char["definition"]
    die = data.get("die")
    cur = s.setdefault("hitDiceCurrent", {})
    if cur.get(die, 0) <= 0:
        return
    cur[die] -= 1
    sides = int(die[1:]) if die and die[0] == "d" else 8
    con = rules.ability_mod(d.get("abilityScores", {}).get("CON", 10))
    heal = max(1, random.randint(1, sides) + con)
    max_hp = rules.max_hp(d)["value"]
    s["currentHp"] = min(max_hp, s.get("currentHp", 0) + heal)
    store.save(char)
    emit("hd:healed", {"amount": heal, "die": die}, room=char["id"])
    emit("character:update", view_model(char), room=char["id"])


@socketio.on("handout")
def on_handout(data):
    camp = store.get_campaign(data.get("campaignId"))
    if not camp:
        return
    camp["handout"] = data.get("handout") or {"type": None, "content": None}
    store.save_campaign(camp)
    emit("handout", {"handout": camp["handout"]}, room="camp:" + camp["id"])


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
