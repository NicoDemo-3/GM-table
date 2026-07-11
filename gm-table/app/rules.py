"""
5e derived-stat engine.

Hero's Diary stores *source* data and *current* mutable state, but NOT computed
stats (AC, initiative, max HP, save DCs, attack bonuses). Those are recomputed
live here. Every computed value that is fiddly enough to have edge cases (AC,
max HP) is "compute-with-override": if the character carries an explicit override,
that wins; otherwise we compute a best-effort value.

Nothing here mutates state. Pure functions of (definition, state) -> numbers.
"""

from math import floor

ABILITIES = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

# Base AC for armor, keyed by the Hero's Diary subType strings we expect.
# (dex_cap = None means add full Dex mod; 0 means add none; 2 means cap at +2)
ARMOR_TABLE = {
    # Light armor: full Dex
    "Padded Armor": (11, None), "Leather Armor": (11, None),
    "Studded Leather Armor": (12, None), "Studded Leather": (12, None),
    # Medium armor: Dex capped at +2
    "Hide Armor": (12, 2), "Chain Shirt": (13, 2), "Scale Mail": (14, 2),
    "Breastplate": (14, 2), "Half Plate Armor": (15, 2), "Half Plate": (15, 2),
    # Heavy armor: no Dex
    "Ring Mail": (14, 0), "Chain Mail": (16, 0), "Splint Armor": (17, 0),
    "Plate Armor": (18, 0), "Plate": (18, 0),
}

# Average hit points gained per level after 1st, by hit die.
HIT_DIE_AVG = {"d4": 3, "d6": 4, "d8": 5, "d10": 6, "d12": 7}
HIT_DIE_MAX = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12}


def ability_mod(score: int) -> int:
    return floor((score - 10) / 2)


def total_level(definition: dict) -> int:
    return sum(c.get("level", 0) for c in definition.get("classes", [])) or 1


def proficiency_bonus(definition: dict) -> int:
    if definition.get("proficiencyBonusOverride") is not None:
        return definition["proficiencyBonusOverride"]
    return 2 + (total_level(definition) - 1) // 4


def _mods(definition: dict) -> dict:
    scores = definition.get("abilityScores", {})
    return {a: ability_mod(scores.get(a, 10)) for a in ABILITIES}


def computed_max_hp(definition: dict) -> int:
    """Average-HP method: first level = max die + CON; each later level = avg + CON."""
    con = ability_mod(definition.get("abilityScores", {}).get("CON", 10))
    classes = definition.get("classes", [])
    if not classes:
        return 1
    total = 0
    first = True
    for cls in classes:
        die = cls.get("hitDie", "d8")
        lvl = cls.get("level", 0)
        for _ in range(lvl):
            if first:
                total += HIT_DIE_MAX.get(die, 8) + con
                first = False
            else:
                total += HIT_DIE_AVG.get(die, 5) + con
    return max(total, 1)


def max_hp(definition: dict) -> dict:
    """Returns {'value', 'computed', 'overridden'}."""
    computed = computed_max_hp(definition)
    override = definition.get("maxHpOverride")
    return {
        "value": override if override is not None else computed,
        "computed": computed,
        "overridden": override is not None,
    }


def computed_ac(definition: dict) -> int:
    """Best-effort AC from equipped armor; falls back to unarmored 10 + Dex."""
    dex = ability_mod(definition.get("abilityScores", {}).get("DEX", 10))
    items = definition.get("inventory", {}).get("items", [])
    base, dex_cap, has_shield = None, None, False
    for it in items:
        if not it.get("equipped"):
            continue
        sub = it.get("subType", "")
        name = it.get("name", "")
        if "Shield" in sub or name == "Shield":
            has_shield = True
        for key in (sub, name):
            if key in ARMOR_TABLE:
                base, dex_cap = ARMOR_TABLE[key]
    if base is None:
        ac = 10 + dex                      # unarmored
    elif dex_cap is None:
        ac = base + dex                    # light
    else:
        ac = base + min(dex, dex_cap)      # medium/heavy
    if has_shield:
        ac += 2
    # magic AC bonuses from item modifiers
    for it in items:
        if not it.get("equipped"):
            continue
        for mod in it.get("modifiers", []):
            if mod.get("target") in ("Armor Class", "AC"):
                ac += mod.get("value", 0)
    return ac


def armor_class(definition: dict) -> dict:
    computed = computed_ac(definition)
    override = definition.get("acOverride")
    return {
        "value": override if override is not None else computed,
        "computed": computed,
        "overridden": override is not None,
    }


def initiative(definition: dict) -> int:
    return ability_mod(definition.get("abilityScores", {}).get("DEX", 10))


def spell_save_dc(definition: dict) -> int | None:
    sc = definition.get("spellcasting", {})
    abil = sc.get("ability")
    if not abil:
        return None
    return 8 + proficiency_bonus(definition) + _mods(definition).get(abil[:3].upper(), 0)


def spell_attack(definition: dict) -> int | None:
    sc = definition.get("spellcasting", {})
    abil = sc.get("ability")
    if not abil:
        return None
    return proficiency_bonus(definition) + _mods(definition).get(abil[:3].upper(), 0)


def passive_perception(definition: dict) -> int:
    wis = ability_mod(definition.get("abilityScores", {}).get("WIS", 10))
    skills = definition.get("skills", {})
    pb = proficiency_bonus(definition)
    lvl = skills.get("Perception", "untrained")
    bonus = {"proficient": pb, "expertise": pb * 2}.get(lvl, 0)
    return 10 + wis + bonus


def attack_line(atk: dict, definition: dict) -> dict:
    """Compute to-hit and damage string for a stored attack."""
    mods = _mods(definition)
    pb = proficiency_bonus(definition)
    abil = (atk.get("ability") or "Strength")[:3].upper()
    amod = mods.get(abil, 0)
    to_hit = amod + atk.get("magicalModifier", 0) + atk.get("customAttackModifier", 0)
    if atk.get("proficient"):
        to_hit += pb
    dmg_bonus = amod + atk.get("magicalModifier", 0) + atk.get("customDamageModifier", 0)
    dmg = atk.get("damage", "")
    dmg_str = f"{dmg}{dmg_bonus:+d}" if dmg else f"{dmg_bonus:+d}"
    return {
        "name": atk.get("name", ""),
        "toHit": f"{to_hit:+d}",
        "damage": dmg_str,
        "damageType": atk.get("damageType", ""),
        "range": atk.get("range", ""),
    }


def derive(character: dict) -> dict:
    """Full derived block for a character (definition + state)."""
    d = character["definition"]
    scores = d.get("abilityScores", {})
    mods = _mods(d)
    pb = proficiency_bonus(d)
    skills_out = {}
    for skill, level in d.get("skills", {}).items():
        # find governing ability for this skill
        gov = SKILL_ABILITY.get(skill, "DEX")
        bonus = mods.get(gov, 0)
        bonus += {"proficient": pb, "expertise": pb * 2}.get(level, 0)
        skills_out[skill] = bonus
    saves_out = {}
    for ab in ABILITIES:
        b = mods.get(ab, 0)
        if d.get("saves", {}).get(ab) in ("proficient", "expertise"):
            b += pb
        saves_out[ab] = b
    return {
        "abilityMods": mods,
        "proficiencyBonus": pb,
        "totalLevel": total_level(d),
        "maxHp": max_hp(d),
        "armorClass": armor_class(d),
        "initiative": initiative(d),
        "spellSaveDc": spell_save_dc(d),
        "spellAttack": spell_attack(d),
        "passivePerception": passive_perception(d),
        "saves": saves_out,
        "skills": skills_out,
        "attacks": [attack_line(a, d) for a in d.get("attacks", [])],
    }


SKILL_ABILITY = {
    "Athletics": "STR",
    "Acrobatics": "DEX", "Sleight of Hand": "DEX", "Stealth": "DEX",
    "Arcana": "INT", "History": "INT", "Investigation": "INT",
    "Nature": "INT", "Religion": "INT",
    "Animal Handling": "WIS", "Insight": "WIS", "Medicine": "WIS",
    "Perception": "WIS", "Survival": "WIS",
    "Deception": "CHA", "Intimidation": "CHA",
    "Performance": "CHA", "Persuasion": "CHA",
}
