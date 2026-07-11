"""
Beginner reference layer (D&D 2024 / SRD 5.2).

Plain-language explanations written for a player's first-ever session: no jargon,
no prior knowledge. Three blocks:

  GLOSSARY    - sheet terms (AC, HP, saves, skills, slots, ...) with a short
                "what it is" and, where relevant, "how to roll it" using PHYSICAL
                dice (d20, d4, ...).
  ABILITIES   - the six ability scores: what they cover and the exact dice steps.
  CATALOG     - selectable buffs & debuffs (the 15 official 2024 conditions plus
                common spell effects), each with a beginner blurb. This is the
                read-only base text; a player's own notes never overwrite it.

All text is original paraphrase. Served to the browser for tooltips + the
click-to-pin explainer bar.
"""

# {mod} is filled in on the client with the character's live modifier, e.g. "+4".
ABILITIES = {
    "STR": {
        "name": "Strength",
        "covers": "Raw physical power — lifting, shoving, breaking things, climbing, and melee muscle.",
        "roll": "Roll 1d20 (the twenty-sided die) and add your Strength modifier ({mod}). "
                "If the total is equal to or higher than the number the DM is looking for, you succeed.",
        "save": "A Strength save resists being shoved, pushed, or physically forced. "
                "Roll 1d20 {mod} and try to meet or beat the DM's number.",
    },
    "DEX": {
        "name": "Dexterity",
        "covers": "Agility and reflexes — sneaking, balancing, picking locks, dodging, and aiming ranged or finesse attacks.",
        "roll": "Roll 1d20 and add your Dexterity modifier ({mod}). Meet or beat the DM's number to succeed.",
        "save": "A Dexterity save is your dodge — diving away from a fireball or a trap. Roll 1d20 {mod}.",
    },
    "CON": {
        "name": "Constitution",
        "covers": "Toughness and stamina. You rarely 'check' it, but it sets your hit points and resists exhaustion and poison.",
        "roll": "Roll 1d20 and add your Constitution modifier ({mod}).",
        "save": "A Constitution save resists poison, disease, cold, and keeping concentration on a spell when you take damage. Roll 1d20 {mod}.",
    },
    "INT": {
        "name": "Intelligence",
        "covers": "Reasoning and memory — recalling lore, investigating clues, knowing arcane, history, or nature facts.",
        "roll": "Roll 1d20 and add your Intelligence modifier ({mod}).",
        "save": "An Intelligence save resists effects that attack your mind with illusions or mental force. Roll 1d20 {mod}.",
    },
    "WIS": {
        "name": "Wisdom",
        "covers": "Awareness and intuition — noticing things, reading people, tracking, and willpower against charm or fear.",
        "roll": "Roll 1d20 and add your Wisdom modifier ({mod}).",
        "save": "A Wisdom save resists being charmed, frightened, or mentally controlled. Roll 1d20 {mod}.",
    },
    "CHA": {
        "name": "Charisma",
        "covers": "Force of personality — persuading, deceiving, intimidating, and performing.",
        "roll": "Roll 1d20 and add your Charisma modifier ({mod}).",
        "save": "A Charisma save resists effects that try to possess you or banish you. Roll 1d20 {mod}.",
    },
}

GLOSSARY = {
    "armorClass": {
        "title": "Armor Class (AC)",
        "text": "How hard you are to hit. When something attacks you it rolls 1d20 and adds its bonus; "
                "if that total is equal to or above your AC, the attack hits. Higher AC is better. "
                "You don't roll for this — it's a target number others have to beat.",
    },
    "currentHp": {
        "title": "Hit Points (HP)",
        "text": "Your health. Damage lowers it; healing raises it back up to your maximum. "
                "At 0 HP you drop and start making death saves, so keep an eye on this number.",
    },
    "maxHp": {
        "title": "Maximum HP",
        "text": "The most health you can have. Healing never takes you above it. "
                "If your sheet's computed value looks wrong, you can type the correct max in once and it stays.",
    },
    "tempHp": {
        "title": "Temporary HP",
        "text": "A short-lived shield of extra hit points that soak up damage before your real HP. "
                "They don't add together with other temp HP (take the higher), and they vanish on a long rest.",
    },
    "initiative": {
        "title": "Initiative",
        "text": "Turn order in a fight. When combat starts, everyone rolls 1d20 and adds their initiative bonus ({mod} for you). "
                "Highest total acts first, then down the line.",
    },
    "proficiencyBonus": {
        "title": "Proficiency Bonus",
        "text": "A bonus you add to things you're trained in — certain attacks, skills, and saving throws. "
                "It's the same number for all of them and slowly grows as you level up.",
    },
    "savingThrow": {
        "title": "Saving Throw",
        "text": "A roll to avoid or resist something bad happening TO you (a trap, poison, a spell). "
                "Roll 1d20, add that save's bonus, and try to meet or beat the number the DM names. "
                "A ◆ marks saves you're proficient in (you add your proficiency bonus).",
    },
    "skill": {
        "title": "Skill",
        "text": "A specific thing you can attempt. Roll 1d20, add the listed bonus, and compare to the DM's target. "
                "A ◆ means you're proficient; a ✦ means Expertise (you add double your proficiency bonus).",
    },
    "spellSaveDc": {
        "title": "Spell Save DC",
        "text": "When YOU cast a spell that forces an enemy to resist, this is the number they must reach on their saving throw. "
                "You don't roll it — it's their target. It's 8 + your proficiency bonus + your spellcasting modifier.",
    },
    "spellAttack": {
        "title": "Spell Attack Bonus",
        "text": "For spells you have to aim (like a bolt of fire), roll 1d20 and add this bonus, then compare to the target's AC — "
                "just like a weapon attack.",
    },
    "passivePerception": {
        "title": "Passive Perception",
        "text": "How much you notice without actively looking — the DM quietly compares it to how well something is hidden. "
                "It's just 10 + your Perception bonus, no roll needed.",
    },
    "speed": {
        "title": "Speed",
        "text": "How many feet you can move on your turn. On a battle grid, every 5 feet is usually one square.",
    },
    "spellSlots": {
        "title": "Spell Slots",
        "text": "Fuel for your spells. Casting a spell spends one slot of that spell's level. "
                "Tap a dot to mark a slot used (hollow) or restored (filled). You get them all back on a long rest.",
    },
    "resources": {
        "title": "Resources",
        "text": "Limited-use class or item abilities. Each dot is one use — tap to spend or restore. "
                "Most refill on a short or long rest, depending on the feature.",
    },
    "hitDice": {
        "title": "Hit Dice",
        "text": "Dice you can spend during a short rest to heal. You have roughly one per level. "
                "Spend one, roll it, add your Constitution modifier, and regain that many HP.",
    },
    "inspiration": {
        "title": "Heroic Inspiration",
        "text": "A reward you can hold onto and spend to reroll any one die — you must keep the new result. "
                "Tap to toggle whether you currently have it.",
    },
    "deathSaves": {
        "title": "Death Saving Throws",
        "text": "Made when you're at 0 HP. On your turn roll 1d20: 10 or higher is a success, 9 or lower a failure. "
                "Three successes and you stabilize; three failures and you die. A natural 20 = you wake with 1 HP; a natural 1 counts as two failures.",
    },
    "attacks": {
        "title": "Attacks",
        "text": "To attack: roll 1d20, add the 'to hit' number shown. If it meets or beats the target's AC, you hit — then roll the damage dice shown and add the bonus.",
    },
    "conditions": {
        "title": "Conditions, Buffs & Debuffs",
        "text": "Temporary effects on you right now. Debuffs (red) hinder you; buffs (green) help you. "
                "Pick from the 2024 list or add your own. The rules text is fixed — your notes sit alongside it.",
    },
    "advantage": {
        "title": "Advantage / Disadvantage",
        "text": "Advantage: roll two d20s and use the HIGHER. Disadvantage: roll two and use the LOWER. "
                "They don't stack — you either have it or you don't.",
    },
}

# ---- Buffs & debuffs catalog (2024 conditions + common spell effects) ----
# kind: "debuff" | "buff". `levels` flags exhaustion's stacking.
CATALOG = [
    # ----- Official 2024 conditions -----
    {"key": "blinded", "name": "Blinded", "kind": "debuff",
     "text": "You can't see: you fail anything needing sight, attacks against you have Advantage, and your own attacks have Disadvantage."},
    {"key": "charmed", "name": "Charmed", "kind": "debuff",
     "text": "You can't attack or harm whoever charmed you, and they have an easier time persuading you."},
    {"key": "deafened", "name": "Deafened", "kind": "debuff",
     "text": "You can't hear, and you fail anything that relies on hearing."},
    {"key": "exhaustion", "name": "Exhaustion", "kind": "debuff", "levels": True,
     "text": "Stacks in levels 1–6. Every d20 roll you make is lowered by 2 × your level, and your speed drops 5 ft × your level. "
             "At level 6 you die. A long rest removes one level."},
    {"key": "frightened", "name": "Frightened", "kind": "debuff",
     "text": "While you can see the thing scaring you, your attacks and checks have Disadvantage, and you can't move closer to it."},
    {"key": "grappled", "name": "Grappled", "kind": "debuff",
     "text": "Your speed is 0 and you're being held in place. Your attacks have Disadvantage against anyone but the grabber."},
    {"key": "incapacitated", "name": "Incapacitated", "kind": "debuff",
     "text": "You can't take actions, bonus actions, or reactions, and you can't concentrate on spells."},
    {"key": "invisible", "name": "Invisible", "kind": "buff",
     "text": "You can't be seen without magic. Attacks against you have Disadvantage and your attacks have Advantage."},
    {"key": "paralyzed", "name": "Paralyzed", "kind": "debuff",
     "text": "You can't move, act, or speak; you auto-fail Strength and Dexterity saves; attacks against you have Advantage and any hit from within 5 ft is a critical."},
    {"key": "petrified", "name": "Petrified", "kind": "debuff",
     "text": "You're turned to stone: unconscious and unaware, resistant to all damage, but auto-failing Strength and Dexterity saves."},
    {"key": "poisoned", "name": "Poisoned", "kind": "debuff",
     "text": "Your attack rolls and ability checks have Disadvantage."},
    {"key": "prone", "name": "Prone", "kind": "debuff",
     "text": "You're on the ground. You can only crawl, your attacks have Disadvantage, melee attacks against you have Advantage (ranged ones have Disadvantage). Stand up to end it."},
    {"key": "restrained", "name": "Restrained", "kind": "debuff",
     "text": "Your speed is 0, attacks against you have Advantage, your attacks have Disadvantage, and your Dexterity saves have Disadvantage."},
    {"key": "stunned", "name": "Stunned", "kind": "debuff",
     "text": "You can't move and can barely speak; you auto-fail Strength and Dexterity saves, and attacks against you have Advantage."},
    {"key": "unconscious", "name": "Unconscious", "kind": "debuff",
     "text": "You're knocked out: prone, unaware, dropping what you hold, auto-failing Strength and Dexterity saves; attacks against you have Advantage and any hit from within 5 ft is a critical."},
    # ----- Common spell effects (buffs/debuffs) -----
    {"key": "bless", "name": "Bless", "kind": "buff",
     "text": "Add 1d4 to your attack rolls and saving throws while it lasts. Roll the d4 and add it after a d20 roll."},
    {"key": "bane", "name": "Bane", "kind": "debuff",
     "text": "Subtract 1d4 from your attack rolls and saving throws. Roll the d4 and take it off your total."},
    {"key": "guidance", "name": "Guidance", "kind": "buff",
     "text": "Add 1d4 to ONE ability check of your choice (not an attack or save). One-time use, then it's gone."},
    {"key": "hunters-mark", "name": "Hunter's Mark", "kind": "buff",
     "text": "Deal an extra 1d6 damage when you hit your marked target. Roll the d6 with your damage."},
    {"key": "hex", "name": "Hex", "kind": "buff",
     "text": "Deal an extra 1d6 necrotic damage on hits against the cursed target, and they have Disadvantage on one chosen ability."},
    {"key": "rage", "name": "Rage", "kind": "buff",
     "text": "Resistance to physical (bludgeoning/piercing/slashing) damage, bonus damage on melee Strength attacks, and Advantage on Strength checks and saves."},
    {"key": "haste", "name": "Haste", "kind": "buff",
     "text": "+2 AC, Advantage on Dexterity saves, double speed, and one extra limited action each turn."},
    {"key": "shield-of-faith", "name": "Shield of Faith", "kind": "buff",
     "text": "+2 to your AC while it lasts."},
    {"key": "concentration", "name": "Concentrating", "kind": "buff",
     "text": "You're holding a spell active. If you take damage, make a Constitution save (DC 10 or half the damage, whichever is higher) or it ends."},
]

REFERENCE = {"abilities": ABILITIES, "glossary": GLOSSARY, "catalog": CATALOG}
