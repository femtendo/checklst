---
name: checklst
description: >-
  Author, render, and collect structured checklists for verification workflows.
  Use when an agent (or orchestrator delegating to subagents) must prove work:
  release acceptance gates, QA passes, chunk completion, debugging sweeps,
  review sign-offs. Zero dependencies, Python 3 stdlib only.
---

# CHECKLST — verification checklists for agent pipelines

`checklst.py` turns a JSON spec into a standalone dark-theme HTML checklist and
parses the filled results back into canonical JSON. Same spec always renders
byte-identical HTML. Python 3 stdlib only — no install step.

## WHEN TO USE THIS SKILL

Reach for CHECKLST whenever verification must be *demonstrable*, not asserted:

- **Orchestrator delegating to subagents** — you need workers to return
  evidence per item, not a prose "done".
- **Release / acceptance gates** — a human or reviewer signs off item by item.
- **QA sweeps, debugging passes, review sign-offs** — anything where
  Works/Doesn't/Bugged per item beats a paragraph.
- **You would otherwise write "here is a checklist:" in chat** — don't; render
  one instead.

Do NOT use it for: simple todos with no verification semantics, long-form task
tracking (use your harness's native plan/todo tool), or anything needing a
persistent database.

## QUICK REFERENCE

```bash
# 1. Author a spec (edit the emitted JSON, or write it directly)
python3 v1.0/checklst.py new spec.json

# 2. Render to standalone HTML (byte-deterministic)
python3 v1.0/checklst.py render spec.json > checklist.html

# 3. Delegate to a subagent (spec must set config.allow_passdown: true)
python3 v1.0/checklst.py passdown spec.json \
  --agent worker-1 --mission "verify the build chunk" \
  --scope build,qa -o delegated.html

# 4. Agent-pipeline dashboard grouped by owning agent
python3 v1.0/checklst.py home manifest.json -o pipeline.html

# 5. Normalize a filled results doc back to canonical JSON
python3 v1.0/checklst.py parse results.json > canonical.json
```

## SPEC CHEAT SHEET

Top level: `title`, `global_notes`, optional `theme`, optional `agent`
(webhook), optional `config.allow_passdown`. Categories: `id`, `name`,
`goal` (shown in section header), `collapsed_default`, `items[]`.
Items: `id`, `text`, `notes`, `options{}`.

`options` is an arbitrary dict — this is the core design. Widget selection:
- `choices: [...]` → pill radios; entries are strings or `{value, color}`
- boolean `value` → toggle switch
- anything else → text input
- `description` on an option → tooltip

The famous `status: Works/Doesn't/Bugged` is ONLY a preset:

```json
"options": {
  "status": {
    "value": "Works",
    "description": "Does this item work?",
    "choices": [
      {"value": "Works",   "color": "#3fb950"},
      {"value": "Doesn't", "color": "#f85149"},
      {"value": "Bugged",  "color": "#d29922"}
    ]
  }
}
```

Optional `theme` block: `{accent, accent2, font, fontsize, background, card,
text, muted, radius}`. Optional `agent` block:
`{"webhook_url": "...", "name": "...", "timeout_ms": 10000}` renders a Send
button that POSTs collected results (retry once; endpoint must allow CORS from
a `null` origin since pages open via `file://`).

Built-in theme presets (22): Umbrella Corp, Half-Life, Black Mesa, Aperture
Science, Cave Johnson, GLaDOS, Matrix, Amber Terminal, Hatsune Miku, Sakura,
Sakura Night, Hermes, Touhou (Reimu), Twilight Sparkle, Princess Celestia,
Princess Luna, Applejack, Rainbow Dash, Fluttershy, Rarity, Pinkie Pie,
TUI Classic. Rainbow Dash cycles a continuous hue wheel; Matrix/Amber Terminal
flicker like CRTs. Rendered pages also fire pixel-art confetti when an item is
marked done or given a positive status.

## ORCHESTRATION PATTERN (recommended flow)

1. Orchestrator authors spec with one category per worker lane, sets
   `config.allow_passdown: true` and its own webhook under `agent`.
2. For each subagent: `passdown --agent <name> --mission <text> --scope <cats>`
   → hand the rendered file to that agent.
3. Subagent opens the page, fills items + notes, uses **Results ▸ drawer →
   Send**, OR writes its results JSON through its own channel.
4. Orchestrator runs `parse` on every returned results file; canonical shape is
   identical across agents, so results diff cleanly per item.
5. Optionally regenerate `home` so the whole pipeline state is visible in one
   dashboard.

Strict mode (passdown default): per-category completion chips plus a banner
warning if any scoped item ships unanswered. Tell your subagents: answer EVERY
scoped item's status and leave notes wherever the status isn't Works.

## HARNESS INSTALL

### Hermes Agent
Copy this skill directory into `~/.hermes/skills/checklst/` (per-profile:
`~/.hermes/profiles/<profile>/skills/checklst/`). It is then auto-discovered;
invoke explicitly with `skill_view(name='checklst')`. Keep `checklst.py` at
`v1.0/checklst.py` relative to whatever repo you're verifying, or reference the
absolute path inside this skill directory.

### Claude Code / Claude Desktop
Claude Code (CLI): copy the skill folder into `.claude/skills/checklst/` of any
repo where you want it active, or `~/.claude/skills/checklst/` for all
projects. This file (`SKILL.md`) is already Claude-skill compatible — same YAML
frontmatter contract. Claude Desktop: paste the QUICK REFERENCE + SPEC CHEAT
SHEET sections into a Project's custom instructions if you prefer no files.

### OpenAI Codex CLI / other AGENTS.md-style harnesses
Add to your repo's `AGENTS.md`:

> Verification checklists: render with
> `python3 v1.0/checklst.py render <spec>.json > checklist.html`; never claim
> checklist items complete without a filled results document parsed via
> `checklst.py parse`.

### Generic (any harness, zero integration)
Every rule fits in two lines you can drop into any system prompt:

> To make work verifiable: author a spec per SPEC CHEAT SHEET below, run
> `render`, give humans/delegates the HTML file. Never assert completion
> without a `parse`d results JSON mapping every item id to a value.

## HARD RULES FOR AGENTS USING THIS SKILL

1. Never fabricate results. A checklist you fill must reflect what you actually
   verified — `Doesn't` with a note beats a lying `Works`.
2. Always `parse` before reporting. Canonical output is the only format an
   orchestrator should accept.
3. Determinism matters: never post-process rendered HTML (timestamps, ids);
   re-render from the spec instead.
4. Note fields are for evidence: exit codes, paths, one-line repros.
5. Respect the passdown gate — if `config.allow_passdown` is false, the author
   locked delegation; do not bypass it.
