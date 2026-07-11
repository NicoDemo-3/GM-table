"""
Leveling engine (D&D 2024 mechanics; SRD-clean content).

- XP_TABLE: default 2024 thresholds (DM-editable; overrides live in settings).
- level_from_xp: implied character level for a given XP total.
- ASI_LEVELS: when a class grants an Ability Score Improvement / feat.
- SRD_FEATS: the feats actually in SRD 5.2 (Creative Commons), paraphrased in
  our own words. Anything beyond these comes from the user's content import.
- level_up_plan: given a class gaining a level, what choices the player must make.

Multiclass: ASI and subclass timing key off the *class* level reached in the
class gaining the level, not the total character level.
"""

from math import floor

# Default 2024 XP thresholds: character level -> minimum XP.
XP_TABLE = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000,
    9: 48000, 10: 64000, 11: 85000, 12: 100000, 13: 120000, 14: 140000,
    15: 165000, 16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}

# Generic ASI levels, plus class-specific extras (2024).
ASI_GENERIC = {4, 8, 12, 16, 19}
ASI_EXTRA = {"Fighter": {6, 14}, "Rogue": {10}}

SUBCLASS_LEVEL = 3  # all 2024 classes choose a subclass at class level 3

HIT_DIE_AVG = {"d4": 3, "d6": 4, "d8": 5, "d10": 6, "d12": 7}
HIT_DIE_MAX = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12}

# Classes that prepare/cast from level 1 (for the "new spells?" prompt).
CASTER_CLASSES = {"Bard", "Cleric", "Druid", "Sorcerer", "Warlock", "Wizard",
                  "Paladin", "Ranger", "Artificer"}


def _norm(thresholds):
    """Normalize a thresholds dict to {int level: int xp}."""
    t = thresholds or XP_TABLE
    return {int(k): int(v) for k, v in t.items()}


def level_from_xp(xp, thresholds=None):
    t = _norm(thresholds)
    lvl = 1
    for L in sorted(t):
        if xp >= t[L]:
            lvl = L
    return lvl


def xp_for_level(level, thresholds=None):
    return _norm(thresholds).get(int(level), 0)


def _asi_levels(class_name):
    return ASI_GENERIC | ASI_EXTRA.get(class_name, set())


# ---- SRD 5.2 feats (CC), original paraphrase ----
SRD_FEATS = [
    {"key": "asi", "name": "Ability Score Improvement", "category": "General", "asi": "choice",
     "text": "Increase one ability score by 2, or two different scores by 1 each (max 20). The plainest, always-solid choice."},
    {"key": "alert", "name": "Alert", "category": "Origin", "asi": None,
     "text": "Add your proficiency bonus to initiative rolls, and you may swap your initiative with a willing ally's."},
    {"key": "magic-initiate", "name": "Magic Initiate", "category": "Origin", "asi": None, "repeatable": True,
     "text": "Learn two cantrips and one level-1 spell from a chosen class's list. Cast the level-1 spell once free per long rest (or with your own slots)."},
    {"key": "savage-attacker", "name": "Savage Attacker", "category": "Origin", "asi": None,
     "text": "Once per turn when you hit with a weapon, roll its damage dice twice and use either total."},
    {"key": "skilled", "name": "Skilled", "category": "Origin", "asi": None, "repeatable": True,
     "text": "Gain proficiency in any three skills or tools of your choice."},
    {"key": "grappler", "name": "Grappler", "category": "General", "asi": "STR_or_DEX",
     "text": "Half-feat (+1 Str or Dex). Advantage on attacks against creatures you've grappled, and you can grapple as part of your Attack."},
    {"key": "archery", "name": "Fighting Style: Archery", "category": "Fighting Style", "asi": None,
     "text": "+2 bonus to attack rolls with ranged weapons. (Requires the Fighting Style feature.)"},
    {"key": "defense", "name": "Fighting Style: Defense", "category": "Fighting Style", "asi": None,
     "text": "+1 to AC while wearing armor. (Requires the Fighting Style feature.)"},
    {"key": "two-weapon", "name": "Fighting Style: Two-Weapon Fighting", "category": "Fighting Style", "asi": None,
     "text": "Add your ability modifier to the damage of your off-hand attack. (Requires the Fighting Style feature.)"},
    {"key": "great-weapon", "name": "Fighting Style: Great Weapon Fighting", "category": "Fighting Style", "asi": None,
     "text": "When you roll damage for a two-handed melee weapon, treat any 1 or 2 on a die as a 3. (Requires the Fighting Style feature.)"},
    {"key": "boon-combat", "name": "Epic Boon of Combat", "category": "Epic Boon", "asi": "choice",
     "text": "Level 19+. Half-feat. Once per turn add bonus weapon damage; gain extra reach. (One of several SRD Epic Boons.)"},
    {"key": "boon-skill", "name": "Epic Boon of Skill", "category": "Epic Boon", "asi": "choice",
     "text": "Level 19+. Half-feat. Gain proficiency in three skills, or expertise in proficiencies you already have."},
]


def level_up_plan(definition, gaining_class, thresholds=None):
    """Return the ordered choice-steps for taking a level in `gaining_class`."""
    classes = definition.get("classes", [])
    cls = next((c for c in classes if c["name"] == gaining_class), None)
    if not cls:
        return {"error": f"Character has no class named {gaining_class!r}."}
    new_class_level = cls.get("level", 0) + 1
    new_total = sum(c.get("level", 0) for c in classes) + 1
    die = cls.get("hitDie", "d8")
    con = floor((definition.get("abilityScores", {}).get("CON", 10) - 10) / 2)

    steps = []
    # 1. HP — always
    steps.append({
        "type": "hp", "die": die, "average": max(1, HIT_DIE_AVG.get(die, 5) + con),
        "conMod": con,
        "help": f"You gain hit points. Take the fixed average ({HIT_DIE_AVG.get(die,5)}) "
                f"or roll 1{die} — then add your Constitution modifier ({con:+d}).",
    })
    # 2. ASI / feat
    if new_class_level in _asi_levels(gaining_class):
        steps.append({
            "type": "asi_feat",
            "help": "Choose an Ability Score Improvement OR a feat. Feats below are the "
                    "SRD set; import your books' feats to see more, or type your own.",
        })
    # 3. Subclass at class level 3
    has_subclass = bool(cls.get("subclass"))
    if new_class_level == SUBCLASS_LEVEL and not has_subclass:
        steps.append({
            "type": "subclass",
            "help": f"At {gaining_class} level 3 you choose your subclass. Pick from your "
                    f"books and record its name — its level-3 feature is granted now.",
        })
    # 4. New class features (we can't enumerate non-SRD ones — prompt to add)
    steps.append({
        "type": "features",
        "help": f"Check your {gaining_class} table for any new feature at level {new_class_level}. "
                f"Add it under Features when you're done.",
    })
    # 5. Spells, for casters
    if gaining_class in CASTER_CLASSES:
        steps.append({
            "type": "spells",
            "help": "As a spellcaster you may learn/prepare new spells and gain higher slots. "
                    "Update Spells and Spell slots after leveling.",
        })
    return {
        "gainingClass": gaining_class, "newClassLevel": new_class_level,
        "newTotalLevel": new_total, "steps": steps,
    }
