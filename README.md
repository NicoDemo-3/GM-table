# The Table — self-hosted GM toolkit (phase 1)

A Dockerized, LAN-hosted game-master toolkit. Phase 1 ships the **spine**: the
live-sync server and a character sheet that imports from Hero's Diary. The
MITHOS-style tools (combat tracker, bestiary, generators, map/display) layer onto
this same backbone in later phases.

## What's here

Three views, one server, kept in sync over WebSockets:

| URL | View | Who |
| --- | --- | --- |
| `/` | GM dashboard — import characters, open sheets/display | You |
| `/sheet/<id>` | Character sheet — live-editable | You + that player |
| `/display` | Player display — read-only party HP/AC | Second screen / TV |

The **single source of truth** is a SQLite file on the host. Any client sends a
field *patch*; the server applies it, recomputes derived stats, persists, and
broadcasts the fresh character to everyone viewing it. Open the same sheet on
your laptop and a player's tablet — every edit appears on both.

## Run it

```bash
docker compose up --build
```

Then from any device on your network: `http://<host-ip>:5000`
(find `<host-ip>` with `ip addr` / `ipconfig`). SQLite persists in `./data`.

For remote players later, don't port-forward raw — put the host on a
Tailscale/NetBird tailnet and share that address. The data model already carries
a per-character `owner`, so per-player auth is a clean phase-2 add.

## Character model — the important design

Each character is split into two partitions:

- **`definition`** — who they are (class, abilities, features, spells, inventory,
  max-HP/AC overrides). Hero's Diary owns this; it changes between sessions.
- **`state`** — what's happening now (current HP, temp HP, spent slots, expended
  resources, death saves, conditions, inspiration). *We* own this; it changes
  live at the table.

That split is what makes re-import safe.

### Importing & re-importing

Import a Hero's Diary JSON export from the dashboard. On **re-import** (player
leveled up and re-exported):

- **Merge (default)** — refresh `definition`, preserve `state`. Current HP is
  clamped to the new max; newly-opened spell-slot tiers start full.
  `POST /api/import?replace=<id>`
- **Replace** — wipe and rebuild from the export (player scrapped the character).
  `POST /api/import?replace=<id>&mode=full`

### Computed-with-override

Hero's Diary doesn't store AC, max HP, initiative, or save DCs — it recomputes
them live. So do we (`app/rules.py`). AC and max HP, the two fiddly ones, are
**compute-with-override**: type a value into the tile to pin it; clear it (or type
the computed value) to fall back to the formula. Example: Alenya's average-HP
formula gives 60, but her sheet shows 74 — set the max-HP override once and it
sticks, flagged "set".

## Layout

```
app/
  server.py       Flask + Socket.IO: routes, import, patch sync
  heros_diary.py  Hero's Diary adapter (ProseMirror→HTML, partition, merge)
  rules.py        5e derived-stat engine (mods, prof, AC, HP, DCs, attacks)
  store.py        SQLite document store
  templates/      index · sheet · display
  static/         style.css · sheet.js
Dockerfile · docker-compose.yml · requirements.txt
```

## Adapter notes / limits

- Targets Hero's Diary **1.24.x** (version-gated; other versions get a clear
  error instead of silent corruption). When the dev changes the format, patch
  `heros_diary.py` only — nothing else depends on their shape.
- Rich text (feature/item/spell descriptions) is TipTap/ProseMirror JSON, rendered
  to HTML once at import. Unknown nodes pass through rather than breaking.
- AC auto-detection reads *equipped* armor from inventory; exotic armor or
  feature-granted AC → use the override.


## Phase 2 — beginner reference, player portal, conditions

**Beginner reference layer.** Hover any underlined term on a sheet for a plain
plain-English note; click it to pin the full explanation to the bar at the top.
Ability scores (STR/DEX/...) tell you exactly which physical die to roll and what
to do with it ("Roll 1d20, add your Dexterity modifier +4, meet or beat the DM's
number"). All text is in `app/glossary.py` — edit it freely; it's served to every
page as reference data.

**Views are now split by who's using them:**

| URL | For | Does |
| --- | --- | --- |
| `/` | DM | import + links |
| `/play` | Players | party status board; tap your own character to open & edit it |
| `/overview` | DM | whole-party vitals + active effects at a glance |
| `/sheet/<id>` | both | the live sheet |

Players self-serve from `/play` — you don't manage their sheets. `/display` still
works as an alias for `/overview` for a second screen.

**Conditions, buffs & debuffs.** On a sheet, "+ Add effect" opens the 2024
catalog (all 15 official conditions + common spell effects like Bless, Rage,
Hunter's Mark), each with a beginner explanation. Exhaustion tracks levels 1–6
with the 2024 math. Selecting one stores a fixed copy of the rules text plus your
own editable note/duration — your notes never overwrite the base rules. "Custom"
adds anything on the fly (name, buff/debuff, description). Effects show live on
the sheet, the player portal cards, and the DM overview.

## Later phases (same backbone)

Combat tracker (pull party + bestiary, initiative, the player-facing combat view
on `/display`), bestiary with JSON import, NPC/shop/loot generators, roll tables,
map display with fog, soundboard, dice log, per-player auth, full-campaign
export/import + auto-backup.

## Phase 3a — left rail: rests, dice, theme

A fixed tool rail runs down the left of the sheet (it drops to the bottom on
narrow screens):

- **Short Rest / Long Rest** buttons with rules-correct restores. Long rest:
  full HP, all spell slots, half your hit dice back (min 1), long-rest abilities,
  and drops one exhaustion level. Short rest: refreshes short-rest abilities
  (spend hit dice on the sheet to heal).
- **Dice Roller** popup. Tap D4–D100 to add dice to the tray one at a time (any
  mix of types and counts); nothing rolls until you press **Roll**. Tap a die in
  the tray to remove one. Results show per-die rolls and a total, and flag a
  natural 20 / natural 1 on a lone d20. It's an optional helper — your physical
  dice stay the default; this is just there when you want it.
- **Light / Dark toggle**, persisted per browser. Other pages have a matching
  toggle in the top-right corner.

Currency (gp/sp/cp) is now larger and editable inline.


## Phase 3b — inline section editing

Every structural section of the sheet is now hand-editable via an **Edit** toggle
in its header (the app, not Hero's Diary, owns the character once you edit):

- **Attacks** — add / edit / remove. Name, ability, proficiency, damage dice,
  type, range, magic bonus. To-hit and damage recompute live.
- **Inventory** — add / edit / remove items: name, quantity, equipped toggle,
  and armor subtype (which drives AC auto-calc). Currency stays editable above.
- **Features & traits** — add / edit / remove (plain-text editor; editing an
  imported rich-text feature flattens its formatting).
- **Spells** — add / edit / remove: name, level, prepared, description.
- **Spell slots** — edit max slots per level and the casting ability.
- **Resources** — add / edit / remove: name, max uses, short/long-rest restore.

Edits patch the whole section array; the server re-derives and broadcasts, so
changes appear live on every open copy. A section ignores inbound re-renders
while you're actively editing it, so it never clobbers a form mid-type.


## Phase 4 — XP, leveling & content import

**XP & leveling (on the sheet, top of the right column):**
- An XP bar showing progress to the next level, with an **Award XP** field.
- When XP crosses a threshold a pulsing **Level Up!** button appears.
- **Level-up modal:** choose the gaining class (multiclass), pick HP (fixed
  average or rolled + CON), choose an **Ability Score Improvement or a feat**
  (feats come from the catalog — SRD set built in, plus anything you import —
  with descriptions; half-feats also prompt the +1 ability), and get guided
  prompts for subclass / new features / new spells (which you then add via the
  section editors). Applying it bumps the class level, adds HP, applies the
  ASI/feat, records the subclass, and advances XP.
- **DM tools** (collapsible): quick **Set total level** (per class) to start a
  campaign above level 1, plus a link to the content/thresholds page.
- Single-class and multiclass both supported.

**Content & rules page (`/content`, linked from the dashboard):**
- **XP thresholds editor** — change the minimum XP per level (or use
  milestone-style numbers); applies to all characters. Reset-to-2024-default.
- **Content import** — the built-in catalog ships SRD feats only; to add your
  books' full content, your local LLM produces JSON in the documented schema
  (the page shows the schema and a suggested LLM prompt) and you paste/upload it
  here (merge or replace). Imported feats appear in the level-up picker; spells
  and features are stored in the catalog.
- **Catalog view** — browse everything currently loaded.

Note: bundled content is SRD-clean (our own paraphrase); the app never ships
copyrighted book text — that comes from your own import on your machine.

## Still to come (sequenced for quality, not yet built)

- Damage/heal quick-apply, death-saves UI, hit-dice spending
- Full backup export/import + auto-backup
- Player PIN as a DM-activatable toggle

## Phase 4a — Campaigns + Widget Library (MITHOS foundation, Option A)

The app is now **campaign-based** and built on a **Widget Library**, the keystone
for the full MITHOS-class toolkit.

- **Campaign picker** at `/` (clean slate): create, open, **export**, **import**,
  delete campaigns. Each campaign keeps its own party, widgets, and settings.
- **Everything is scoped to a campaign:** dashboard `/c/<id>`, player portal
  `/c/<id>/play`, DM overview `/c/<id>/overview`, Widget Library `/c/<id>/widgets`.
  Character sheets stay at `/sheet/<char_id>` and find their own campaign.
- **Campaign export/import** — one JSON bundle (campaign + all characters +
  widgets). Import restores under fresh IDs, so it never collides with existing data.
- **Widget Library** (`/c/<id>/widgets`) — the "single source of all stats":
  - **System widgets (D&D 5e):** built-in, computed live by the engine (AC, HP,
    saves, abilities, etc.) — placeable on cards, not deletable. This is the 5e
    brain MITHOS deliberately lacks (Option A: hybrid).
  - **Custom widgets:** define your own (number / text / checkbox / resource),
    choose which cards they appear on. Sheet-scoped custom widgets show in a
    "Custom stats" panel on each sheet, editable and live-synced. Their values
    live on the character at `definition.custom[widgetId]`.

Next phases build on this foundation without changing the model: the Sheet
Builder canvas (drag widgets onto Character/Party/Combat/NPC/Bestiary cards),
Party Manager (tints, extra card stats, Split & Bench), Combat Tracker,
Bestiary + NPCs, generators, map display, soundboard, world/time.

## Phase 4b — the session-running core (most of MITHOS, in one drop)

All campaign-scoped and live-synced over a per-campaign socket room.

- **Combat / Initiative Tracker** (`/c/<id>/combat`): add combatants from the
  party, bestiary, NPCs, or by hand; roll initiative; advance turns with a round
  counter; damage/heal; per-combatant conditions (matched to the 2024 list).
  A read-only **player combat view** (`/c/<id>/combat-view`) shows the order and
  current turn live, with enemy HP shown as Healthy/Wounded/Bloodied/Down rather
  than exact numbers.
- **Bestiary** (`/c/<id>/bestiary`): stat-block CRUD + tolerant **JSON import**
  (maps common field names: hp/hit_points, ac/armor_class, etc.).
- **NPC Library + Generator** (`/c/<id>/npcs`): CRUD plus a one-click random NPC
  (name, role, trait, plot hook, age).
- **Roll Tables** (`/c/<id>/tables`): create tables, roll for a random result.
- **Shop Generator** (`/c/<id>/shop`): generate priced inventories by shop type
  and town economy.
- **World & Time** (`/c/<id>/world`): live clock, custom calendar with day/month
  rollover, and a weather generator — synced across devices.
- **Party Manager** (on the dashboard): assign **tints** to characters and
  **bench** them; benched characters are hidden from the player portal and DM
  overview until you bring them back.

### Deliberately not in this drop (need specialized work, coming next)
The drag-and-drop **Sheet Builder canvas**, the fog-of-war **Map Display** with
tokens, the audio **Soundboard**, and full **A/B party split** (bench is done).
These need canvas interaction / file handling and are built next rather than
shipped half-working.

## Phase 4c — Map Display with fog of war

- **DM map page** (`/c/<id>/map`): upload a battlemap, then paint fog with a
  **Reveal/Hide brush** (adjustable size), or Reveal-all / Hide-all. Optional grid
  overlay (toggle + cell size).
- **Two independent fog opacities:** *My view* (a DM-local preference, default 40%,
  so you can see faintly through hidden areas) and *Player view* (default 100%),
  which you control here and is synced to the player screen.
- **Player map view** (`/c/<id>/map-view`) for the second screen: renders the map
  with the shared fog at the player opacity, live — areas reveal as you paint.
- One shared fog mask (revealed cells) syncs over the campaign room; the image is
  stored as a file and served by URL, so only the small mask travels per stroke.

## Phase 4d — big batch (sheet actions, soundboard, split, handout, backup, SRD seed)

- **Sheet quick-actions** (under HP): **Damage/Heal** apply with one click (damage
  eats temp HP first); **Death saves** (success/failure pips, auto-shown at 0 HP,
  with nat-20 revive and nat-1 double-fail); **Hit-dice** spend buttons (rolls the
  die + CON and heals, capped at max).
- **Soundboard** (`/c/<id>/sounds`): upload audio tiles (served by URL), play with
  per-tile volume + loop, Stop-all. Add/remove tiles.
- **A/B Party Split** (dashboard): assign each character to group All/A/B and pick
  the **active group**; non-active and benched characters drop out of the player
  portal and DM overview.
- **DM handout push**: from the DM overview, push text or an image URL to a banner
  on the player portal, or clear it — live.
- **Auto-backup**: `table.db` is copied to `data/backups/` on startup and every 6
  hours (newest 10 kept); a manual backup endpoint exists too.
- **Combat condition durations**: give a combat effect a round count; it ticks down
  at the top of each round and clears itself, shown as "(Nr)" on the chip.
- **Bestiary SRD seed**: one click adds a 15-creature starter bestiary drawn from
  the SRD 5.2 (Creative Commons) — goblins, orcs, wolves, ogres, a mage, etc.

### Still remaining (the heaviest, specialized pieces)
The drag-and-drop **Sheet Builder canvas**, **map tokens**, and the
**infinite-canvas dashboard / focus presets**. Bench+split are done; the canvas
and token work are next.

## Phase 4e — DM sidebar + editable initiative

- **Collapsible DM Tools sidebar** on every DM screen (dashboard, sheet, overview,
  combat, bestiary, NPCs, tables, shop, world, map, soundboard, widgets). One click
  collapses it to an icon rail; the state is remembered. It is intentionally absent
  from the pure player screens (player portal, player combat view, player map view)
  and the campaign picker. On the character sheet, the rests/dice/theme rail moved
  to the right edge so the two never collide.
- **Customisable initiative order** in the combat tracker: every combatant's
  initiative is an editable number, and ▲/▼ nudges move a combatant up or down the
  order. Editing re-sorts live for everyone.

## Phase 4f — multi-column tables + Reference Library + DM Links

- **Multi-column / weighted roll tables**: tables can now be "ranged" — roll a die
  (e.g. d100), match the row, and read across named columns. Build them in the UI
  (name, die, columns, and `min-max | col1 | col2 …` rows) or keep using simple
  one-result tables.
- **Crit-fail d100 table** baked from your CritFailTable.ods — one click on the Roll
  Tables page adds it with Melee / Ranged / Spell columns (ditto marks resolved,
  blanks filled), then roll d100 to read the result for the attack type.
- **Reference Library** (`/reference`): your Classic Fantasy GM & Player reference
  spreadsheets rendered as browsable tables (Hazards, Conditions, Combat, Melee,
  Ranged, etc.), with per-sheet tabs.
- **DM Links** (`/dm-links`): your "Massive DM's Toolkit" bookmarks as a tidy,
  categorised link directory (reference, generators, maps, music, homebrew…).
- Both pages are linked from the DM sidebar and the dashboard tools.

## Phase 4g — Map tokens + Sheet Builder canvas

### Map tokens
- Drag tokens on the map; positions sync live to the player map view.
- **Custom token images**: upload any image per token (stored as a file, served by URL).
- **Shape presets**: circle, square, triangle, diamond, hexagon, star — with a
  custom colour, size, and label per token. Image tokens are clipped to the shape.
- Quick-add: **From party** (uses each character's portrait) and **From combat**
  (one token per combatant in the live encounter).
- Tokens render on the player map view in real time alongside the fog.

### Sheet Builder canvas (v1.1.7 headline)
- `/c/<id>/builder`: pick a card type (Character, Party, Combat, NPC, Bestiary),
  click widgets from the **Widget Library** to drop them on the card canvas, and
  drag to position. Save per-card layouts.
- **Party Cards** (`/c/<id>/party-cards`) render each character using the saved
  Party Card layout, resolving **live values** — system widgets compute from the
  5e engine (AC, HP, level…), custom widgets read their stored value. This is the
  Widget Library finally driving a composed, custom-laid-out card.

### Remaining
Applying built layouts to the Combat/NPC/Bestiary cards and the main sheet (Party
Card is wired now), and the infinite-canvas dashboard / focus presets.

## Phase 4h — built layouts on all five card surfaces

The Sheet Builder now drives every card type, not just Party. A single resolver
reads each entity's real data, so a built layout shows live values per surface:

- **Character / Party cards** — values from the 5e engine + custom widgets.
- **Combat cards** (`/c/<id>/cards/combat`) — each encounter combatant (name, AC,
  current/max HP, initiative, conditions).
- **NPC cards** (`/c/<id>/cards/npc`) — name, role, tags, description.
- **Bestiary cards** (`/c/<id>/cards/bestiary`) — stat blocks (name, AC, HP, CR, speed).

Design a layout per card in the Sheet Builder (tabs across the top), hit **Preview ↗**
to see it rendered for the live entities of that type, and Save. Cards with no
layout yet fall back to a name card and point you to the builder.

## Phase 4i — infinite canvas, focus presets, custom calendar & weather

### Infinite canvas + focus presets (`/c/<id>/canvas`)
- A pannable, zoomable workspace where each tool (combat, bestiary, map, world,
  NPCs, soundboard, overview, party cards…) opens as a floating, draggable,
  resizable window that embeds the live tool. Drag the background to pan; +/−/reset
  to zoom.
- **Collapsible preset dock**: save **focus presets** (e.g. "Combat Night",
  "Roleplay") and switch between them in one click. Each preset remembers which
  windows are open, their geometry, and the pan/zoom.
- **Share-layout toggle**: ON = a window keeps one position/size across every
  preset; OFF = each preset keeps its own override for shared windows.
- **Non-destructive remove**: closing a window only drops it from the current
  preset — its config is kept in a "Removed (kept)" stash so you can add it back
  later without setting it up again (or purge it for good).
- Embedded tool pages auto-hide their own sidebar/header inside canvas windows.

### Custom calendar & weather (World & Time)
- **Set the date directly** (month, day, year, time).
- **Custom months**: rename months, set days-per-month, and add/remove months to
  change the length of the year.
- **Custom weather types**: add your own precipitation types; the generator rolls
  from your list.

## Phase 5 — Compendium system + engine integration + import

### Compendium (`/c/<id>/compendium`)
Generic typed content with a **math-first schema**: every entry separates
engine-read `mechanics` (bonuses, proficiencies, slots, rarity, modifiers) from
situational `text` (shown, not auto-applied). Types: spell, feat, background,
subclass, item, lore, hook. Browse, search by type, add/edit/delete.

### Engine integration ("apply to character")
From any entry you can apply it to a party member, and the engine takes it from there:
- **Item** → added to inventory; equip it and its modifiers feed AC / attack / etc.
- **Spell** → added to the character's spell list (slots & DC already compute).
- **Background** → grants its skill proficiencies, starting gear, and feature.
- **Feat** → applies ability-score bonuses, skill/save proficiencies, an optional
  tracked resource, and the feature text.
- **Subclass** → adds its static features (the bespoke subsystems stay as text to
  wire up per-subclass later).
Situational effects are shown as text you trigger — the engine handles all the math.

### Import (any LLM can feed it)
- **Structured file import**: upload or paste **JSON** or a simple **Markdown**
  format (`## type: Name`, `key: value` lines, free-text body). The page shows the
  format + a template, parses to a **preview**, and only adds on confirm. Hand the
  template to any LLM (local or not) and it can author import files like it authors
  characters.
- **PDF text extraction**: pull a PDF's text to give your LLM as source material
  (full auto-classification arrives with the assistant phase).
- Forgiving parser: case-insensitive keys, `modifier: AC +1` shorthand,
  comma-lists, `abilityBonuses: DEX 1`, all normalized server-side.

## Phase 5b - compendium folders + monster type

- **Folders**: every compendium entry can carry a `folder` label, so you can keep
  separate compendiums side by side (e.g. a full Circus set and a beasts-only set).
  Filter by folder, move entries between folders, and create folders on the fly.
- **Monster type**: a full stat-block entry type (size, type, AC, HP, speed, ability
  scores, saves, skills, senses, CR, traits, actions). Engine reads AC/HP/CR/scores;
  traits and actions ride as text. A monster entry can be sent straight to the live
  **Bestiary** with one click.
- The import template (v2) now covers all eight types including monsters, with a
  `folder:` line on every example.

## Phase 5c - bulk delete, folder management, expandable descriptions

- **Bulk delete**: a select-all checkbox plus per-entry checkboxes; choose any set
  and "Delete N" removes them in one call (with a confirm).
- **Folder management**: when a folder is selected, a row offers Rename, Delete
  folder (keep entries -> unfiled), and Delete folder + all entries.
- **Expandable descriptions**: click any entry's name to expand its full card -
  source, every mechanics field formatted, and the complete text body. Click
  again to collapse.

## Phase 5d - apply compendium entries to NPCs & beasts

- The compendium "apply to…" picker is now grouped into Player characters, NPCs,
  and Beasts. PCs apply through the full character engine (as before); NPCs and
  bestiary creatures are loose stat blocks, so an entry is attached as a readable
  note (shown in their description/notes) and safe flat fields are nudged: an
  item's AC modifier bumps the creature's AC, a feat's ability bonus bumps its
  matching ability score. Monster entries still route to the bestiary via → 🐉.

## Phase 6 - player view, currency, shop editor, rule imports

- **Player view is locked down.** The player character sheet and party portal now
  load a dedicated *player sidebar* instead of the DM tools sidebar (this fixes DM
  tools leaking onto the player sheet). The player sidebar has three tabs: Rules
  (read-only, DM-imported), From the DM (read-only pushed content), and My Notes
  (a private pad saved in the player's own browser via localStorage).
- **Player Content page (DM):** import player rules from Markdown (`## Title` +
  body) or JSON (`[{title,text}]`), push read-only notes, and remove anything
  you've shared. Updates stream live to players over the socket.
- **Shop generator is now a full editor:** edit item names, prices, and quantities;
  add/remove rows; choose how many to generate; name the shop; and push the whole
  list to players read-only (they can't edit or regenerate it).
- **Currency system:** prices are stored in the smallest unit (cp by default) so
  there's no more 0.01 gp rounding. A campaign-level currency config defines each
  unit's worth, and you can rename units, change rates, or add custom currencies;
  formatting breaks any amount into the largest denominations. Conversion between
  any two units (including custom ones) is exact.

## Phase 6b - SRD 5.2.1 rules glossary (Creative Commons)

- Bundled the **SRD 5.2.1 Rules Glossary** (160 terms: actions, conditions,
  hazards, areas of effect, and general rules), extracted from the official
  Creative Commons (CC-BY-4.0) release. One click on the Player Content page
  loads it into the player sidebar's Rules tab.
- The required CC-BY-4.0 attribution is added automatically as the first rule
  entry and travels with the content. Loading is idempotent and preserves any
  of your own custom rules.
- Standalone importable copies are also provided (srd-rules-glossary.json / .md)
  with the attribution embedded, in case you want to import them manually or edit
  them first.

## Phase 6c - player sidebar pages, dark mode, currency polish

- **Player sidebar reworked into pages.** Instead of cramped tabs it's now a menu
  that opens one page at a time (Rules, From the DM, My Notes), each with a back
  button. The menu's top item is "My Character" — a one-tap return to the sheet the
  player picked (remembered per browser). Rules are an A-Z searchable list; tapping
  a term opens it on its own page. The sidebar is also drag-resizable (200-640px,
  width remembered).
- **Dark mode** light areas (panels, cards, inputs) are noticeably darker now while
  staying a step above the page background.
- **Currency:** electrum no longer pollutes price breakdowns. Each currency unit has
  an "in prices" toggle; electrum defaults off (so 250 cp reads "2 gp, 5 sp", not
  "2 gp, 1 ep"). Legacy campaigns are auto-corrected; re-enable any coin if you want
  it back.
- **SRD loading made obvious:** the Player Content page now has a dedicated "D&D 2024
  rules (SRD 5.2.1)" panel explaining the one-click load.

## Phase 6d - guide page, slim player sidebar, pushed-content management

- **Player Guide is now its own full page** (/c/<id>/guide) with three collapsible
  sections (Rules with search, From the DM, My Notes). No more cramming into the
  sidebar or content starting halfway down.
- **Player sidebar is slim navigation only**: My Character (one tap back to the
  picked sheet), The Party, and Player Guide. It uses the standard sidebar styling,
  so the layout/positioning issues are gone.
- **Pushed content is fully manageable.** The DM can delete any pushed shop/note
  from two places: the Player Content page (now shows each item's contents via a
  "view" toggle) and the Shop page itself, which now has a persistent "Pushed shops"
  list with load-to-edit and remove. Removal updates players live.
- **Dark mode** light areas darkened again (panels ~#181510, cards/inputs ~#141109).

## Phase 6e - sidebar color, shop fix, name gen, player hide

- **Dark-mode sidebar** had inverted to cream (it used --ink, which is light in dark
  mode). It now has a dedicated dark background (--sidebar-bg #0c0b08) in both themes.
- **Shop generator fixed** — a bad apostrophe escape in a confirm() had broken the
  entire shop inline script (and the player-content script, which is why rules import
  also failed). Both restored.
- **Shop names are generated** automatically on Generate, with a 🎲 button to reroll
  and a fully editable field.
- **Players can hide pushed content** from their own guide view (per browser); a
  "Show N hidden items" button brings them back. The DM still controls deletion.

## Phase 6e - fixes: boot crash, sidebar dark, player hide

- **Fixed the crash that made shop + rules import "stop working":** a duplicate
  route (/api/gen/shop-name defined twice) made Flask raise on startup, so the
  whole app failed to boot. Removed the duplicate; app boots clean.
- **Sidebar now themes dark** (it was using a fixed light ink background). In dark
  mode the nav rail is ~#0c0a07 with light text.
- **Players can hide pushed content** from their Guide page ("hide" per item, and a
  "Show N hidden" toggle) — stored per-browser, so it never affects the DM or other
  players. DMs still delete pushed content from the Player Content page and the Shop
  page's "Pushed shops" list.
- Shop names are auto-generated on Generate, with a 🎲 button to re-roll and full
  edit control.

### Rebuilding (important)
docker rm -f gm-table 2>/dev/null; docker compose up --build
If a change ever seems missing, it is almost always a stale container — force the
rebuild with the two commands above.

## Phase 6f - dark mode: inverted bars + all input fields

- Fixed the remaining bright bars in dark mode: the "Live-synced" status footer
  and the right-side action rail (Short/Long/Dice/Theme), plus tooltips, the dice
  header, modal headers, JSON schema blocks, and the canvas bars. These all used
  the text color as a background (fine in light mode, wrong in dark); they now use a
  dark surface with readable text. Body text colors were left unchanged.
- Every text box, textarea, and dropdown now gets a dark field with light text in
  dark mode (they were defaulting to white — e.g. the "Push handout" input).
  Placeholders are dimmed; checkboxes/sliders use the accent color.

## Bestiary v2 & saved encounters

**Bestiary** is a two-pane view: searchable/sortable creature list on the left,
a full stat block on the right laid out like the character sheets —
ability-score tiles with modifiers, AC/HP/Speed/Initiative/CR tiles, then
Saves/Skills/Senses/Languages, Traits, Actions, Notes. Everything is editable
via Edit (Duplicate makes variants fast). Quick-add creates a shell and drops
you into the editor.

The SRD starter set ships **full stat blocks** (SRD 5.2, CC-BY-4.0, original
wording). Re-running *Seed SRD monsters* **enriches** old thin entries in place —
fills missing scores/traits/actions/senses by name, never overwrites your
AC/HP/CR/speed or notes. JSON import passes full-statblock fields through too.

**Saved encounters** live in the Combat Tracker. Build a lineup, name it, Save —
stored as a *recipe* (full HP, no initiative, no conditions). **Load** replaces
the current encounter with fresh instances; **＋** appends them (stack presets,
or drop reinforcements mid-fight). PCs re-resolve from their live sheet on load.
Persist per campaign; CRUD at `/api/campaign/<cid>/encounters`.
