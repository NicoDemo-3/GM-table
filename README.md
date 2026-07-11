# The Table

A self-hosted, local-first toolkit for running D&D 5e at the table. One Docker
container serves a game-master control panel and a separate player view over
your LAN, kept in sync in real time. Your data lives in a SQLite file on your
own machine — no accounts, no cloud, no subscription.

Built for a single table's personal use: prep your campaign, run combat, push
handouts to a second screen, and keep the whole night on one laptop.

## Features

- **Character sheets** — live-editable 5e sheets with derived stats
  (modifiers, AC, HP, proficiency) recomputed server-side. Import from JSON.
- **Bestiary** — searchable, sortable creature library with full stat blocks
  laid out like the character sheets: ability tiles, AC/HP/Speed/Initiative/CR,
  saves, skills, senses, traits, and actions. Edit and duplicate in place. Ships
  with an SRD 5.2 starter set you can seed with one click.
- **Combat tracker** — initiative order, HP and condition tracking, and
  **saved encounters**: build a lineup once, then load it to start a fight or
  drop it in as reinforcements mid-combat. Player characters re-resolve from
  their live sheets on load.
- **Compendium** — folders, monster stat blocks, bulk operations, and import
  from JSON or Markdown.
- **Shop generator** — copper-based pricing, name generation, a full item
  editor, and persistent shops you can push to players.
- **Currency system** — configurable denominations with automatic breakdown.
- **Player view** — a slim, read-only interface for your players: party status,
  a collapsible player guide, pushed handouts and rules, and private local
  notes that never leave their browser.
- **Rules reference** — an SRD 5.2.1 glossary (160+ terms) plus rollable
  tables, all searchable.
- **Live sync** — every edit broadcasts over WebSockets, so the same sheet open
  on your laptop and a player's tablet stays identical.

## Quick start

```bash
docker compose up --build
```

Then, from any device on the same network:

```
http://<host-ip>:5000
```

Find `<host-ip>` with `ip addr` (Linux/macOS) or `ipconfig` (Windows). The
SQLite database persists in `./data`, so it survives restarts and rebuilds.

## Requirements

- Docker and Docker Compose. That's it — Python, Flask, and all dependencies
  are installed inside the container.

To run without Docker for development:

```bash
pip install -r requirements.txt
python -m app.server
```

## How it works

The server is the single source of truth. Clients send a **patch** describing
the field that changed; the server applies it, recomputes any derived stats,
writes it to SQLite, and broadcasts the updated object to everyone viewing it.

Each character is split into two partitions:

- **`definition`** — who they are: class, ability scores, features, spells,
  inventory. Rarely changes mid-session.
- **`state`** — what's happening now: current HP, conditions, resources spent.
  Changes constantly during play.

Derived values (modifiers, AC, spell save DCs, and so on) are never stored —
they're computed from the definition on every read, so the math is always
consistent and a corrupted number can't get baked in.

## Remote play

Don't port-forward the container to the open internet. Instead, put the host on
a private mesh network (Tailscale, NetBird, or similar) and share that address
with your players. Every character already carries an `owner` field, so
per-player access control is a natural next step.

## Content & licensing

Game content included in this repository is drawn from the **System Reference
Document 5.2**, released by Wizards of the Coast under the
[Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/legalcode)
(CC-BY-4.0), and is reproduced with attribution. This project is unofficial and
is not affiliated with or endorsed by Wizards of the Coast.

The application code is provided for personal, at-the-table use.

## Project layout

```
app/
  server.py          # Flask + Socket.IO server, routes, live sync
  store.py           # SQLite persistence
  rules.py           # 5e rules engine (derived stats, resource math)
  compendium.py      # JSON/Markdown import + stat-block parsing
  currency.py        # configurable currency + breakdown
  srd_content.py     # SRD 5.2 starter bestiary
  glossary.py        # SRD rules glossary
  templates/         # GM and player HTML views
  static/            # CSS + client JavaScript
data/                # SQLite database (created on first run)
Dockerfile
docker-compose.yml
```
