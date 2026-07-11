"""
Procedural generators for the GM tools (NPCs, shops, weather, table rolls).

All content here is generic/original (no copyrighted rules text). Item and name
lists are deliberately small starter sets the GM can extend from the UI later.
"""

import random

# ---- NPC generator ----
_FIRST = ["Bryn", "Cael", "Doran", "Elowen", "Fenn", "Gilda", "Harlow", "Isolde",
          "Joss", "Kestrel", "Lyra", "Marrow", "Nyx", "Orin", "Petra", "Quill",
          "Rook", "Sable", "Tovin", "Ulric", "Vesna", "Wren", "Yarrow", "Zinn"]
_LAST = ["Ashdown", "Brightwater", "Coalfield", "Dunmoor", "Emberly", "Fairwind",
         "Greenhollow", "Harrowmere", "Ironwood", "Larkspur", "Mosswell",
         "Nightingale", "Oakhart", "Pinefall", "Stormridge", "Thornvale"]
_ROLES = ["Innkeeper", "Blacksmith", "Guard captain", "Merchant", "Hedge witch",
          "Farmer", "Acolyte", "Sellsword", "Scholar", "Fisher", "Noble's steward",
          "Smuggler", "Town drunk", "Apothecary", "Bard", "Beggar", "Tax collector"]
_TRAITS = ["nervous and fidgety", "warm and talkative", "gruff but fair",
           "secretly terrified", "endlessly curious", "weary and overworked",
           "proud to a fault", "quietly grieving", "sharp-tongued", "deeply devout",
           "always scheming", "kind to strangers", "suspicious of outsiders"]
_HOOKS = ["owes money to the wrong people", "knows a secret about the mayor",
          "is hiding a relative from the law", "lost something precious recently",
          "is not who they claim to be", "wants the party gone by morning",
          "has a job only adventurers can do", "saw something they shouldn't have"]


def npc(gender=None):
    name = f"{random.choice(_FIRST)} {random.choice(_LAST)}"
    return {
        "name": name,
        "role": random.choice(_ROLES),
        "trait": random.choice(_TRAITS),
        "hook": random.choice(_HOOKS),
        "age": random.randint(17, 72),
    }


# ---- shop generator ----
_SHOP_STOCK = {
    "General Store": [("Rope, 50 ft", 1), ("Torch", 0.01), ("Rations (1 day)", 0.5),
                      ("Backpack", 2), ("Bedroll", 1), ("Tinderbox", 0.5),
                      ("Waterskin", 0.2), ("Crowbar", 2), ("Lantern", 5), ("Oil flask", 0.1)],
    "Blacksmith": [("Dagger", 2), ("Shortsword", 10), ("Longsword", 15), ("Handaxe", 5),
                   ("Mace", 5), ("Chain shirt", 50), ("Shield", 10), ("Spear", 1),
                   ("War pick", 5), ("Crossbow bolts (20)", 1)],
    "Apothecary": [("Healing draught", 25), ("Antitoxin", 50), ("Herbal poultice", 5),
                   ("Sleeping powder", 15), ("Smelling salts", 2), ("Bandages", 1),
                   ("Tonic of vigor", 20), ("Numbing salve", 8)],
    "Magic Curios": [("Scroll (minor)", 30), ("Everburning candle", 40),
                     ("Charm of luck", 75), ("Vial of mystery", 15),
                     ("Cracked focus crystal", 50), ("Compass that points home", 120)],
}
_PRICE_MULT = {"Poor": 0.8, "Average": 1.0, "Wealthy": 1.4}


def shop(shop_type="General Store", economy="Average", count=8):
    stock = _SHOP_STOCK.get(shop_type, _SHOP_STOCK["General Store"])
    mult = _PRICE_MULT.get(economy, 1.0)
    chosen = random.sample(stock, min(count, len(stock)))
    items = []
    for name, base in chosen:
        price_cp = max(1, int(round(base * mult * random.uniform(0.9, 1.15) * 100)))
        items.append({"name": name, "priceBase": price_cp, "qty": random.randint(1, 6)})
    return {"type": shop_type, "economy": economy, "name": shop_name(shop_type), "items": items}


_SHOP_NAME_ADJ = ["Gilded", "Rusty", "Silver", "Crooked", "Brass", "Wandering", "Salty",
                  "Old", "Golden", "Broken", "Laughing", "Sleeping", "Copper", "Velvet",
                  "Hollow", "Iron", "Lucky", "Weary", "Crimson", "Whispering"]
_SHOP_NAME_NOUN = ["Lantern", "Anvil", "Flagon", "Wyrm", "Coin", "Compass", "Cauldron",
                   "Stag", "Raven", "Barrel", "Hearth", "Quill", "Boot", "Crown",
                   "Griffon", "Kettle", "Sigil", "Thimble", "Mug", "Spindle"]
_SHOP_NAME_FORM = ["The {adj} {noun}", "The {adj} {noun}", "{noun} & Sons",
                   "The {noun}", "{adj} {noun} Trading Co.", "Ye {adj} {noun}"]

# keeper names so the DM can rename to a person if they like
_KEEPER = ["Bram", "Hilda", "Olaf", "Mira", "Gus", "Senna", "Tobias", "Wren",
           "Dax", "Petra", "Cormac", "Yvette"]


def shop_name(shop_type="General Store"):
    form = random.choice(_SHOP_NAME_FORM)
    return form.format(adj=random.choice(_SHOP_NAME_ADJ), noun=random.choice(_SHOP_NAME_NOUN))


SHOP_TYPES = list(_SHOP_STOCK.keys())
ECONOMIES = list(_PRICE_MULT.keys())


# ---- weather generator ----
_PRECIP = ["Clear", "Overcast", "Light rain", "Heavy rain", "Fog", "Snow", "Storm"]
_WIND = ["Still", "Light breeze", "Gusty", "Strong winds", "Gale"]


def weather():
    temp = random.randint(-5, 38)
    feels = temp + random.choice([-4, -2, 0, 0, 2, 4])
    return {"precip": random.choice(_PRECIP), "wind": random.choice(_WIND),
            "temp_c": temp, "feels_c": feels}


# ---- roll table ----
def roll_table(entries):
    if not entries:
        return None
    return random.choice(entries)
