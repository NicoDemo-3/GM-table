"""
Currency conversion + formatting.

A campaign carries a `currency` config: a base unit (smallest, e.g. cp) and a list
of units, each with `inBase` (how many base units it's worth). Prices are stored
internally in the base unit (an integer count of cp by default) so there's never a
0.01-gp rounding problem. Formatting breaks a base amount into the largest units
first. Custom currencies just need a code/name/inBase and they slot right in.
"""

DEFAULT = {
    "base": "cp",
    "units": [
        {"code": "pp", "name": "Platinum", "inBase": 1000},
        {"code": "gp", "name": "Gold", "inBase": 100},
        {"code": "ep", "name": "Electrum", "inBase": 50, "inBreakdown": False},
        {"code": "sp", "name": "Silver", "inBase": 10},
        {"code": "cp", "name": "Copper", "inBase": 1},
    ],
}


def config(camp):
    c = (camp or {}).get("currency") or {}
    units = c.get("units") or DEFAULT["units"]
    # back-compat: older saves predate the inBreakdown flag. Default electrum off
    # (so it stops polluting price breakdowns) and everything else on.
    norm = []
    for u in units:
        u = dict(u)
        if "inBreakdown" not in u:
            u["inBreakdown"] = (u.get("code", "").lower() != "ep")
        norm.append(u)
    return {"base": c.get("base", "cp"), "units": norm}


def _sorted_units(cfg):
    return sorted(cfg["units"], key=lambda u: u.get("inBase", 1), reverse=True)


def to_base(amount, code, cfg):
    """Convert `amount` of unit `code` into the base unit (integer base count)."""
    for u in cfg["units"]:
        if u["code"] == code:
            return int(round(amount * u.get("inBase", 1)))
    return int(round(amount))


def convert(amount, from_code, to_code, cfg):
    """Convert between two units. Returns a float (may be fractional)."""
    base = amount * _in_base(from_code, cfg)
    return base / _in_base(to_code, cfg)


def _in_base(code, cfg):
    for u in cfg["units"]:
        if u["code"] == code:
            return u.get("inBase", 1) or 1
    return 1


def format_base(base_amount, cfg, max_units=None):
    """Break an integer base amount into the largest units. e.g. 12345 cp ->
    '1 pp, 23 gp, 4 sp, 5 cp' (electrum skipped unless it divides cleanly first).
    Greedy over units sorted high->low; skips units that contribute 0."""
    base_amount = int(round(base_amount))
    if base_amount == 0:
        # show as 0 of the smallest in-breakdown unit
        usable = [u for u in cfg["units"] if u.get("inBreakdown", True)]
        return f"0 {(usable or cfg['units'])[-1]['code'] if cfg['units'] else cfg['base']}"
    parts = []
    remaining = base_amount
    for u in _sorted_units(cfg):
        if not u.get("inBreakdown", True):       # e.g. electrum: valid unit, not used in change-making
            continue
        worth = u.get("inBase", 1) or 1
        if worth <= 0:
            continue
        n, remaining = divmod(remaining, worth)
        if n:
            parts.append(f"{n} {u['code']}")
        if max_units and len(parts) >= max_units:
            break
    return ", ".join(parts) if parts else f"0 {cfg['base']}"
