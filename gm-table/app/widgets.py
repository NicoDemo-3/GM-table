"""
Widget Library — the v1.1.7 "single source of all stats" abstraction, Option A.

A *widget* is a named stat definition that can be placed on Character Sheets,
Party Cards, Combat Cards, NPC Cards, and Bestiary Cards. There are two kinds:

  - SYSTEM widgets: provided by the active game system (here, D&D 5e). They map
    onto our live engine (rules.py) — AC, HP, saves, etc. — so the auto-computed
    5e brain MITHOS deliberately lacks is preserved. They're read-only definitions
    (you can't delete them) and always in sync with the engine.
  - CUSTOM widgets: user-defined per campaign. Plain stats the engine doesn't
    know about (morale, faction rep, sanity, ammo...). Their VALUES live on each
    character under definition.custom[widgetId].

Phase 1 establishes the model + library + custom-stat surfacing. Card placement
(the full Sheet Builder canvas) layers on top of this in Phase 2 without changing
the model.
"""

CARDS = ["sheet", "party", "combat", "npc", "bestiary"]
CUSTOM_TYPES = ["number", "text", "checkbox", "resource"]

# Built-in D&D 5e widgets. `describes` points at where the value comes from:
#   derived.<key>  -> computed live by rules.derive()
#   definition.<k> / state.<k> -> stored field
SYSTEM_5E = [
    {"key": "name", "label": "Name", "type": "text", "describes": "definition.name", "cards": ["sheet", "party", "combat", "npc", "bestiary"]},
    {"key": "level", "label": "Level", "type": "computed", "describes": "derived.totalLevel", "cards": ["sheet", "party"]},
    {"key": "ac", "label": "Armor Class", "type": "computed", "describes": "derived.armorClass.value", "cards": ["sheet", "party", "combat", "bestiary"]},
    {"key": "currentHp", "label": "Current HP", "type": "number", "describes": "state.currentHp", "cards": ["sheet", "party", "combat", "bestiary"]},
    {"key": "maxHp", "label": "Max HP", "type": "computed", "describes": "derived.maxHp.value", "cards": ["sheet", "party", "combat", "bestiary"]},
    {"key": "tempHp", "label": "Temp HP", "type": "number", "describes": "state.tempHp", "cards": ["sheet", "combat"]},
    {"key": "initiative", "label": "Initiative", "type": "computed", "describes": "derived.initiative", "cards": ["sheet", "combat"]},
    {"key": "speed", "label": "Speed", "type": "text", "describes": "definition.speed.walk", "cards": ["sheet"]},
    {"key": "proficiencyBonus", "label": "Proficiency Bonus", "type": "computed", "describes": "derived.proficiencyBonus", "cards": ["sheet"]},
    {"key": "spellSaveDc", "label": "Spell Save DC", "type": "computed", "describes": "derived.spellSaveDc", "cards": ["sheet"]},
    {"key": "spellAttack", "label": "Spell Attack", "type": "computed", "describes": "derived.spellAttack", "cards": ["sheet"]},
    {"key": "passivePerception", "label": "Passive Perception", "type": "computed", "describes": "derived.passivePerception", "cards": ["sheet", "party"]},
    {"key": "STR", "label": "Strength", "type": "computed", "describes": "derived.abilityMods.STR", "cards": ["sheet"]},
    {"key": "DEX", "label": "Dexterity", "type": "computed", "describes": "derived.abilityMods.DEX", "cards": ["sheet"]},
    {"key": "CON", "label": "Constitution", "type": "computed", "describes": "derived.abilityMods.CON", "cards": ["sheet"]},
    {"key": "INT", "label": "Intelligence", "type": "computed", "describes": "derived.abilityMods.INT", "cards": ["sheet"]},
    {"key": "WIS", "label": "Wisdom", "type": "computed", "describes": "derived.abilityMods.WIS", "cards": ["sheet"]},
    {"key": "CHA", "label": "Charisma", "type": "computed", "describes": "derived.abilityMods.CHA", "cards": ["sheet"]},
    {"key": "inspiration", "label": "Inspiration", "type": "checkbox", "describes": "state.inspiration", "cards": ["sheet", "party"]},
]


def system_widgets(system="dnd5e"):
    """Return the built-in widgets for a game system (only 5e for now)."""
    if system != "dnd5e":
        return []
    out = []
    for w in SYSTEM_5E:
        out.append({**w, "id": "sys_" + w["key"], "source": "system", "scope": "character"})
    return out


def library(campaign):
    """Full widget library for a campaign: system widgets + its custom widgets."""
    return system_widgets(campaign.get("system", "dnd5e")) + list(campaign.get("widgets", []))


def validate_custom(w):
    """Normalize/validate a user-submitted custom widget; raise ValueError if bad."""
    label = (w.get("label") or "").strip()
    if not label:
        raise ValueError("Custom widget needs a label.")
    wtype = w.get("type", "number")
    if wtype not in CUSTOM_TYPES:
        raise ValueError(f"Unknown widget type '{wtype}'.")
    cards = [c for c in (w.get("cards") or ["sheet"]) if c in CARDS] or ["sheet"]
    defaults = {"number": 0, "text": "", "checkbox": False, "resource": {"max": 1, "used": 0}}
    return {
        "label": label,
        "type": wtype,
        "cards": cards,
        "default": w.get("default", defaults[wtype]),
        "source": "custom",
        "scope": "character",
    }
