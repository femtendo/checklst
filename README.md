<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo-dark.svg">
  <img width="96" height="96" alt="CHECKLST mascot — a blushing checkbox buddy with a sparkle friend" src="docs/logo-light.svg">
</picture>

# CHECKLST

**the zero-dependency checklist tool for agents and humans**

Agent-defined specs → byte-deterministic HTML. Stdlib only. One file. 

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.x-blue.svg)
![Dependencies](https://img.shields.io/badge/dependencies-zero-orange.svg)
![Made with ox-alpha + hermes agent](https://img.shields.io/badge/made%20with-ox--alpha%20%26%20hermes%20agent-2dd4bf.svg)

</div>

---

`checklst` turns a plain JSON spec into a polished, standalone, dark-theme
web checklist — then captures the filled results back out as canonical JSON.
No install, no build step, no framework. If you have `python3`, you have
everything you need.

It was built by agents, for agents: written and dogfooded personally by
`ox-alpha` (orchestrator) and `hermes agent` (subagents), each stage of the
pipeline driven by a `checklst` checklist. The tool renders the artifacts
that keep the whole operation honest.

## Features

- 🐍 **`new` / `render` / `parse` CLI** — three commands, Python 3 stdlib only,
  single `checklst.py` file. Nothing to install.
- 🧬 **Fully agent-defined schema** — arbitrary per-item `options` with
  descriptions; categories + retractable sections with per-category goals;
  per-item notes; global notes. Your data model, not ours.
- 🎛️ **`Works / Doesn't / Bugged` is just a preset** — the built-in `status`
  option is a plain `choices` list. Define your **own** colored choices
  (object form) for any option; no hardcoded magic anywhere.
- 🎨 **22 built-in theme presets** — Umbrella Corp, Half-Life, Black Mesa,
  Aperture Science, Cave Johnson, GLaDOS, Matrix, Amber Terminal, Hatsune
  Miku, Sakura… even a full Mane Six.
- 🌈 **Theme FX** — Rainbow Dash drives a continuous hue-wheel rainbow;
  Matrix & Amber Terminal flicker like a CRT; others reserve a hue-swap.
- 🎉 **Pixel-art confetti** — a canvas blast fires when you mark an item done
  and on positive status pills.
- 🎛️ **Customize panel** — pick colors, font, size, and corner radius live in
  the Results drawer; everything persists to `localStorage`.
- 🤖 **Send-to-agent webhook** — POST the collected canonical results JSON to
  an agent endpoint (`agent.timeout_ms`, retry-once, CORS-aware).
- 🔄 **`passdown` subcommand** — orchestrator → subagent delegation, gated by
  `config.allow_passdown`, with `--mission`, `--scope`, and strict-mode chips.
- 🏠 **`home` subcommand** — an agent-pipeline dashboard, grouped by agent,
  rendered from a manifest.
- ⚖️ **Byte-deterministic** — the same spec always produces byte-identical
  HTML. No timestamps, no random ids, stable `sha256` across runs.
- 🛰️ **Works offline from `file://`** — double-click the `.html` and go.

## Quick Start

No install. Clone once, or just grab `v1.0/checklst.py`:

```bash
git clone https://github.com/your-org/checklst
cd checklst

# 1. Generate a starter spec
python3 v1.0/checklst.py new spec.json

# 2. Render it to standalone HTML
python3 v1.0/checklst.py render spec.json > checklist.html

# 3. Hand it to a subagent
python3 v1.0/checklst.py passdown spec.json \
  --agent worker-1 --mission "verify the release" \
  --scope build,qa -o delegated.html

# 4. Sketch the pipeline dashboard
python3 v1.0/checklst.py home manifest.json -o pipeline.html
```

Open `checklist.html` in any browser — no server, no network needed. Fill it
out, tweak the theme, then copy the canonical results JSON out of the drawer.
`parse` normalizes any filled results document:

```bash
python3 v1.0/checklst.py parse results.json > canonical.json
```

## Schema Example

A compact spec. `options` are the whole story: booleans become checkboxes,
`choices` lists become segmented pill radios (optionally colored), everything
else a free-text input.

```json
{
  "title": "Release Acceptance Checklist",
  "config": { "allow_passdown": true },
  "categories": [
    {
      "id": "build",
      "name": "Build & Deployment",
      "goal": "The artifact builds cleanly, ships, and comes up healthy.",
      "collapsed_default": false,
      "items": [
        {
          "id": "build-clean",
          "text": "Project builds without errors or warnings",
          "notes": "Record the real exit code / wall-clock time.",
          "options": {
            "status": {
              "value": "Works",
              "choices": [
                { "value": "Works",   "color": "#3fb950" },
                { "value": "Doesn't", "color": "#f85149" },
                { "value": "Bugged",  "color": "#d29922" }
              ]
            }
          }
        }
      ]
    }
  ]
}
```

## Theme Gallery

Pick a preset from the Customize panel's dropdown, or drop a full `theme`
block into the spec. A subset:

| Preset | Key | Effect |
|--------|-----|--------|
| Umbrella Corp | `umbrella` | corporate red, radius 2 |
| Half-Life | `halflife` | hazard orange |
| Black Mesa | `black-mesa` | science-lab blue |
| Aperture Science | `portal` | portal blue/orange, hue-swap |
| Cave Johnson | `portal-cave` | lemons |
| GLaDOS | `glados` | sulfur yellow on near-black, radius 0 |
| Matrix | `matrix` | green CRT, **flicker** |
| Amber Terminal | `retro-terminal` | amber CRT, **flicker** |
| Hatsune Miku | `miku` | teal × pink, hue-swap |
| Sakura / Sakura Night | `sakura` / `sakura-dark` | blush / twilight |
| Hermes | `hermes` | amber-gold |
| Touhou (Reimu) | `touhou` | red × gold |
| Twilight Sparkle | `twilight` | lavender, hue-swap |
| Rainbow Dash | `rainbow-dash` | cyan × magenta, **continuous rainbow** |
| …and the rest of the Mane Six | each pony | committed palettes |

That's **20+ presets** across game franchises, vocaloids, ponies, and utility.

## Agent Pipeline

CHECKLST was built to keep multi-agent pipelines honest. Three moving parts:

1. **`passdown`** — hand a spec to a subagent. The spec must opt in via
   `config.allow_passdown: true`; otherwise the command exits `1` with
   `spec locked by author`. The rendered page embeds a delegation banner,
   scopes disable out-of-scope categories, and strict-mode completion chips
   keep the agent on task.
2. **`home`** — render a dashboard that groups every checklist by the agent
   that owns it (from a manifest), so a whole pipeline reads at a glance.
3. **webhook** — a subagent's rendered page can POST its collected results
   straight back to the orchestrator endpoint, wrapped in a `timeout_ms`
   timeout (default 10000) with one automatic retry. Note: from `file://`
   the browser origin is `null`, so the endpoint must set permissive CORS
   headers (e.g. `Access-Control-Allow-Origin: *`).

```
┌──────────────┐      passdown      ┌────────────────┐
│ orchestrator │ ───────────────────▶  subagent page │
└──────────────┘                    └────────────────┘
       ▲                                    │ results JSON (webhook)
       │            ┌──────────┐            ▼
       └────────────│  results │◀───────────┤
                    │  drawer  │
        home dashboard └──────────┘  (manifests → HTML)
```

## Determinism

`checklst` makes one promise above all: **the same spec always renders to
byte-identical HTML.** No timestamps, no random ids, no DOM-ordering dice.
This is what makes agent-produced pages mergeable, diffable, and hash-stable —
run `render` twice and diff the `sha256` to prove it. The canonical
round-trip — `parse(build_results(spec))` — is asserted over several specs in
`v1.0/test_golden.py`.

> **Why a "boring" single-file script?** Deployment friction kills agent
> checklists. One file, zero deps, works on a USB stick from `file://`.
> Agents and humans get the same honest, verifiable page — with a little
> pixel-art celebration when things pass. That's the whole point.

## License & Credits

MIT © 2026 femtendo contributors. More on the schema in [`v1.0/schema.md`](v1.0/schema.md).
Made with `ox-alpha` and `hermes agent`.