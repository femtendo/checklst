#!/usr/bin/env python3
"""checklst — a zero-dependency (Python stdlib only) checklist tool.

Subcommands:
    new    <path>      emit a starter specification file (JSON)
    render <spec>      emit a standalone dark-theme HTML checklist (to stdout)
    parse  <results>   normalize a filled results JSON into canonical JSON

Spec format
-----------
A spec is a JSON document:
    title        : str
    categories   : [ {id, name, goal (optional str), collapsed_default (bool),
                       items: [ {id, text, notes (optional str), options:{}} ]} ]

Each item's ``options`` is an arbitrary dict
    option-name -> {"value": <default>, "description": optional str}

and may carry one extra rendering hint: ``"choices": [ ... ]``.
Rendering maps an option to an input as follows:
    * value is a Python bool (no choices)      -> checkbox toggle
    * "choices" list present                   -> segmented "pill" radio
    * otherwise                                -> free-text input

The built-in preset option ``status`` (choices Works/Doesn't/Bugged) is
implemented as nothing more than a regular option with a choices list — no
hardcoded magic in the renderer.

Filled results
--------------
The HTML serializes a filled-results object (spec order, defaults pre-filled)
to an embedded JSON "Readout". It is shaped exactly like parse()'s input and
its output:

    { "title", "global_notes", "categories":
        [ {id, name, goal, items:
            [ {id, text, options:{option:value,...}, notes} ] } ] }

Round-trip contract (parse / build_results)
-------------------------------------------
render(spec) is **deterministic**: the same spec always yields byte-identical
HTML (no timestamps, random ids, or date strings).

parse(results) emits **canonical JSON** with keys

    { "title", "global_notes",
      "categories": [ { "id", "name", "goal", "items":
          [ { "id", "text", "options": {name: value, ...}, "notes" } ] } ] }

in SPEC ORDER — categories and items appear in exactly the order they occur in
the spec, and options in option-name order. Defaults are INCLUDED consistently:
build_results() pre-fills every option with its spec default and parse()
preserves whatever the filled results contain — nothing is dropped and nothing
is defaulted-out, so the output is byte-deterministic.

**Round-trip property**: for any valid spec *S*,

    parse(build_results(S))  deep-equals  build_results(S)

parse echoes the canonical categories form, so feeding it exactly what
build_results() produces returns an identical document. This property is
checked explicitly over several specs in test_golden.py.

Optional theming, drawer, and agent
-----------------------------------
A spec may carry three optional top-level keys:

``theme`` : {"accent": "#hex", "accent2": "#hex", "font": "css font-family",
             "fontsize": <px number>, "background": "#hex", "card": "#hex",
             "text": "#hex", "muted": "#hex", "radius": "css length"}
    Injected as CSS variables (``--accent``, ``--accent2``, ``--font``,
    ``--fontsize``, ``--bg``, ``--card``, ``--txt``, ``--muted``, ``--radius``)
    on :root so a single renderer stays pure (stdlib + vanilla CSS/JS) yet
    fully themed. When the key — or any subfield — is absent, the built-in
    defaults are used unchanged. ``fontsize`` is a plain pixel number; the
    legacy ``font_size`` alias is also accepted for backward compatibility.
    ``radius`` is any CSS length (a bare number is treated as px).

``agent`` : {"webhook_url": "https://...", "name": "optional label",
             "timeout_ms": <number>, default 10000}
    When present (with a non-empty webhook_url), a primary **Send to
    <name|agent>** button renders in the results drawer. Clicking it POSTs the
    *collected results JSON* (the same payload shown in ``#results-json``) to
    webhook_url via ``fetch`` with ``Content-Type: application/json`` and
    shows an inline status line ('Sent ✓' on success, 'Failed: <reason>'
    otherwise).

    **Send contract.** The ``agent`` listens on ``webhook_url``. The POST
    *request body* is exactly the collected canonical results JSON — the same
    object ``build_results()``/``parse()`` produce, including ``theme`` when
    customized — with **no** ``sent_at``/timestamp field (the renderer never
    adds non-deterministic timestamps). It is serialized with a 2-space
    indent. The webhook must respond with a 2xx status to be treated as
    success; any other status or a network error is reported inline.

    Reliability. The request runs through an ``AbortController``; if it does
    not complete within ``agent.timeout_ms`` (default 10000 ms) it is aborted
    and reported as a timeout. A transient network error retries once
    automatically before a failure is shown. While the request is in flight
    the Send button is disabled. CORS reality: open from ``file://`` the
    browser origin is ``null``, so the webhook server must respond with
    permissive CORS headers (e.g. ``Access-Control-Allow-Origin: *``) or the
    POST is blocked and the drawer shows an error. When ``agent`` is absent
    the button is not rendered at all.

Custom status / colored choices
-------------------------------
A normal option's ``choices`` entries may be either plain strings (current
behaviour) or objects {"value": str, "color": "#hex"}. Both forms are handled
identically at the *value* level: the selected ``value`` string is what the
results JSON / parse() stores. The object form's ``color`` is only a rendering
hint — the selected pill uses that color instead of the default accent
gradient. This means a user defines their own status option with custom
colored choices exactly like the built-in ``status`` preset; e.g.::

    "options": {
      "status": {
        "value": "pass",
        "choices": [
          {"value": "pass", "color": "#3fb950"},
          {"value": "fail", "color": "#f85149"},
          {"value": "skip", "color": "#d29922"}
        ]
      }
    }

Results drawer
--------------
The live results JSON is NOT on the main page. It lives in a fixed slide-in
drawer on the right, toggled by the "Results ▸" button in the sidebar (shown
above as chromebar) — a smooth CSS transition, works locally on file://. The
drawer holds the monospace ``#results-json`` textarea (refreshed on every
input change), the "Copy results" button, a close control, and (when an agent
is configured) the "Send to agent" button.

Pass-through delegation (``passdown``)
--------------------------------------
An orchestrator can hand a checklist to a subagent with the ``passdown``
subcommand (see §9 in the CLI docstrings / schema.md):

    python3 v1.0/checklst.py passdown <spec> --agent <name> \\
        [--mission '<text>'] [--scope cat1,cat2] [-o out.html] [--from <orchestrator>]

The spec MUST opt in via the top-level ``config`` key::

    "config": {"allow_passdown": true}

If ``config.allow_passdown`` is missing or false, the command exits **1** with
a clear "spec locked by author" message. When allowed, the rendered page
embeds a ``passdown`` metadata block inside the spec JSON::

    {"from": <--from or 'orchestrator'>, "to": <--agent>,
     "mission": <--mission>, "scope": [<scoped category ids>], "mode": "strict"}

The page then shows a banner "Passdown from X -> Y | mission". When ``--scope``
is given, categories NOT in scope render collapsed with class
``passdown-skipped`` and every one of their controls is disabled. In strict
mode (the only mode), a per-category completion chip (``n/m``) sits in each
section header and an unanswered-item warning banner guards the export.

Round-trip metadata: ``config`` and ``passdown`` are preserved as metadata keys
in the canonical results document (see the "Config / pass-down contract" note
in this docstring) so the subagent's answer carries the delegation context back
to the orchestrator. ``parse_results`` ignores any unexpected top-level keys —
the round-trip property still holds for non-passdown specs.
"""

import argparse
import html as html_mod
import json
import os
import sys

# ---------------------------------------------------------------------------
# Starter spec
# ---------------------------------------------------------------------------

STATUS_OPTION = {
    "value": "Works",
    "description": "Does this item work, fail, or is it broken/bugged?",
    "choices": ["Works", "Doesn't", "Bugged"],
}


def default_spec():
    def item(iid, text, notes=None, extra_opts=None):
        opts = {"status": dict(STATUS_OPTION)}
        if extra_opts:
            opts.update(extra_opts)
        it = {"id": iid, "text": text, "options": opts}
        if notes:
            it["notes"] = notes
        return it

    return {
        "title": "Release Acceptance Checklist",
        "categories": [
            {
                "id": "build",
                "name": "Build & Deployment",
                "goal": "The artifact builds cleanly, ships, and comes up healthy.",
                "collapsed_default": False,
                "items": [
                    item(
                        "build-clean",
                        "Project builds without errors or warnings",
                        notes="Record the real exit code / wall-clock time.",
                    ),
                    item("build-artifacts", "All expected artifacts are produced"),
                    item(
                        "build-deploy",
                        "Latest build deployed to a staging environment",
                        extra_opts={
                            "rollback_required": {
                                "value": False,
                                "description": "Do we need a documented rollback path?",
                            },
                            "deploy_risk": {
                                "value": "low",
                                "description": "Assessed risk of this deployment",
                                "choices": [
                                    {"value": "low", "color": "#3fb950"},
                                    {"value": "medium", "color": "#d29922"},
                                    {"value": "high", "color": "#f85149"},
                                ],
                            },
                        },
                    ),
                ],
            },
            {
                "id": "qa",
                "name": "Quality & Behaviors",
                "goal": "Core user flows behave correctly across the surface area.",
                "collapsed_default": False,
                "items": [
                    item("qa-login", "Login flow works for a valid user"),
                    item("qa-danger", "Danger-zone actions ask for confirmation"),
                    item(
                        "qa-depth",
                        "Smoke-testing performed at the requested depth",
                        extra_opts={
                            "testing_depth": {
                                "value": "basic",
                                "description": "How far did verification go?",
                                "choices": ["none", "basic", "deep"],
                            }
                        },
                    ),
                ],
            },
            {
                "id": "polish",
                "name": "Polish & Handoff",
                "goal": "The deliverable looks professional and is easy to pick up.",
                "collapsed_default": True,
                "items": [
                    item("handoff-notes", "Handoff notes are written and current"),
                    item("handoff-docs", "Docs mention the changed behaviour"),
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Filled-results object builder (defaults pre-filled, spec order kept).
# ---------------------------------------------------------------------------

def build_results(spec):
    res = {"title": spec.get("title", ""), "global_notes": "",
           "categories": []}
    if spec.get("theme"):
        res["theme"] = spec["theme"]
    if spec.get("config"):
        res["config"] = spec["config"]
    if spec.get("passdown"):
        res["passdown"] = spec["passdown"]
    for cat in spec.get("categories", []):
        items = []
        for it in cat.get("items", []):
            opts = {}
            for name, opt in (it.get("options") or {}).items():
                opts[name] = opt["value"]
            items.append({
                "id": it["id"],
                "text": it.get("text", ""),
                "options": opts,
                "notes": it.get("notes", ""),
            })
        res["categories"].append({
            "id": cat.get("id", ""),
            "name": cat.get("name", ""),
            "goal": cat.get("goal", ""),
            "items": items,
        })
    return res


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def _inline_js(value):
    """json-embed safe for inside a <script> block (guards against </script>)."""
    return (json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026"))


# Default palette: a deep, layered ember-ink backdrop with a characterful
# warm-teal -> spring-emerald accent pair. The previous blue/violet
# (#58a6ff/#bc8cff) was the generic "AI coding tool" look; teal/emerald reads
# fresher on dark while staying high-contrast and fully user-themeable (the
# Customize panel overrides these CSS vars 1:1).
DEFAULT_CSS_VARS = (
    "--bg:#0b0f14; --bg2:#121923; --card:#151d28; --card2:#1e2a35;"
    "--line:#23303f; --line2:#33425a; --txt:#e7eef4; --muted:#8fa3b8;"
    "--accent:#2dd4bf; --accent2:#34d399; --ok:#3fb950; --warn:#d29922;"
    "--bad:#f85149;"
    "--shadow:inset 0 1px 0 rgba(255,255,255,.04),0 20px 45px -22px rgba(0,0,0,.7);"
    "--glow:0 0 0 1px rgba(45,212,191,.4),0 8px 22px -6px rgba(45,212,191,.35);"
    "--radius:14px;"
    '--font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;'
    "--fontsize:16px;"
)

THEME_DEFAULT_FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif'
THEME_DEFAULT_FONT_SIZE = 16
THEME_DEFAULT_RADIUS = 14
FONT_MIN_SIZE = 14
FONT_MAX_SIZE = 18
RADIUS_MIN_SIZE = 4
RADIUS_MAX_SIZE = 40
# Tasteful, web-safe font-family stacks for the Customize panel's selector.
FONT_STACKS = [
    ("System UI", THEME_DEFAULT_FONT),
    ("Arial / Helvetica", 'Arial,"Helvetica Neue",Helvetica,sans-serif'),
    ("Georgia (serif)", 'Georgia,"Times New Roman",serif'),
    ("Trebuchet MS", '"Trebuchet MS","Segoe UI",sans-serif'),
    ("Verdana", 'Verdana,Geneva,Tahoma,sans-serif'),
    ("Courier (mono)", '"Courier New",Courier,monospace'),
]


def _strip_str(v):
    """Return the trimmed string for a spec value, or '' when truthy-unusable."""
    return (v or "").strip() if isinstance(v, str) else ""


def _px_number(value, default):
    """Coerce a CSS length / number into an int px (leading number extracted)."""
    if value is None:
        return default
    s = str(value).strip()
    num = ""
    for ch in s:
        if ch in "0123456789.":
            num += ch
        else:
            break
    try:
        return int(float(num))
    except ValueError:
        return default


def theme_defaults(theme):
    """Normalize a spec ``theme`` dict into the panel's default values
    (spec values win, built-in CSS defaults fill the gaps). Returns a dict
    carrying every key the Customize panel and the export theme can hold."""
    theme = theme or {}
    fs = theme.get("fontsize") if theme.get("fontsize") is not None else theme.get("font_size")
    return {
        "accent": _strip_str(theme.get("accent")) or "#2dd4bf",
        "accent2": _strip_str(theme.get("accent2")) or "#34d399",
        "font": _strip_str(theme.get("font")) or THEME_DEFAULT_FONT,
        "fontsize": _px_number(fs, THEME_DEFAULT_FONT_SIZE),
        "background": _strip_str(theme.get("background")) or "#0b0f14",
        "card": _strip_str(theme.get("card")) or "#151d28",
        "text": _strip_str(theme.get("text")) or "#e7eef4",
        "muted": _strip_str(theme.get("muted")) or "#8fa3b8",
        "radius": _px_number(theme.get("radius"), THEME_DEFAULT_RADIUS),
    }


# ---------------------------------------------------------------------------
# Theme presets — one line each: (key, label, palette override dict).
# Keys are deterministic and stable; palettes only set what they style.
# ---------------------------------------------------------------------------

THEME_PRESETS = [
    # --- nerdy / game franchises ---
    ("umbrella",  "Umbrella Corp", {
        "accent": "#e10600", "accent2": "#ff4a3d", "background": "#0a0a0a",
        "card": "#141414", "text": "#f2f2f2", "muted": "#7a7a7a", "radius": 2}),
    ("halflife",  "Half-Life", {
        "accent": "#ff7a18", "accent2": "#ffb066", "background": "#151210",
        "card": "#1f1b16", "text": "#f5efe8", "muted": "#96795a", "radius": 2}),
    ("black-mesa", "Black Mesa", {
        "accent": "#ffaa33", "accent2": "#6fa8dc", "background": "#101214",
        "card": "#181c20", "text": "#eef2f5", "muted": "#8593a0", "radius": 4}),
    ("portal",    "Aperture Science", {
        "accent": "#3ba7f0", "accent2": "#ff9a3c", "background": "#17181a",
        "card": "#212327", "text": "#f0f3f6", "muted": "#93a09a", "radius": 24, "effect": "swap", }),
    ("portal-cave", "Cave Johnson", {
        "accent": "#ffb04a", "accent2": "#ff5c33", "background": "#1c120a",
        "card": "#28190f", "text": "#fff1dd", "muted": "#ab8f6d", "radius": 6}),
    ("glados",    "GLaDOS", {
        "accent": "#f5d76e", "accent2": "#5fd6f2", "background": "#08080c",
        "card": "#10121a", "text": "#eef7fb", "muted": "#5d7580", "radius": 0}),
    ("matrix",    "Matrix", {
        "accent": "#00ff66", "accent2": "#00b347", "background": "#000000",
        "card": "#051408", "text": "#c9ffd8", "muted": "#3f9955", "radius": 0, "effect": "flicker", }),
    ("retro-terminal", "Amber Terminal", {
        "accent": "#ffb000", "accent2": "#ff7300", "background": "#0d0800",
        "card": "#150e00", "text": "#ffd9a0", "muted": "#8a6b35", "radius": 0, "effect": "flicker", }),
    # --- cute / vocaloid ---
    ("miku",      "Hatsune Miku", {
        "accent": "#39c5bb", "accent2": "#ff66aa", "background": "#07141a",
        "card": "#0d2028", "text": "#d8fdf8", "muted": "#56868f", "radius": 22, "effect": "swap", }),
    ("sakura",    "Sakura", {
        "accent": "#ff8fab", "accent2": "#ff5c8a", "background": "#fff1f4",
        "card": "#ffffff", "text": "#5b3a47", "muted": "#b08a97", "radius": 18}),
    ("sakura-dark", "Sakura Night", {
        "accent": "#ff8fab", "accent2": "#ffb7ca", "background": "#1a1216",
        "card": "#26191f", "text": "#ffe9ef", "muted": "#a98d97", "radius": 18}),
    ("hermes",    "Hermes", {
        "accent": "#ffc233", "accent2": "#ff9533", "background": "#141008",
        "card": "#1f1809", "text": "#fff4de", "muted": "#a8925f", "radius": 12}),
    ("touhou",    "Touhou (Reimu)", {
        "accent": "#e03030", "accent2": "#ffe08a", "background": "#171014",
        "card": "#211719", "text": "#fbeee6", "muted": "#a58794", "radius": 4}),
    # --- mlp: one palette per pony, each committed to her colors ---
    ("twilight",  "Twilight Sparkle", {
        "accent": "#ec6ed0", "accent2": "#c297ff", "background": "#17092b",
        "card": "#221038", "text": "#f6ecff", "muted": "#8e76ad", "radius": 14, "effect": "swap", }),
    ("celestia",  "Princess Celestia", {
        "accent": "#f7e59b", "accent2": "#7fd4ee", "background": "#12202b",
        "card": "#1a2c3a", "text": "#fffdf4", "muted": "#87a3b3", "radius": 20, "effect": "swap", }),
    ("luna",      "Princess Luna", {
        "accent": "#5b8cff", "accent2": "#8fb0ff", "background": "#02040d",
        "card": "#070c1c", "text": "#d6e2ff", "muted": "#46557e", "radius": 10}),
    ("applejack", "Applejack", {
        "accent": "#e88a2e", "accent2": "#bf4a2a", "background": "#181006",
        "card": "#241708", "text": "#fdefd9", "muted": "#a38255", "radius": 6}),
    ("rainbow-dash", "Rainbow Dash", {
        "accent": "#40c4ff", "accent2": "#ff3fd8", "background": "#04101f",
        "card": "#081a33", "text": "#eaf6ff", "muted": "#5f83a8", "radius": 6, "effect": "rainbow", }),
    ("fluttershy", "Fluttershy", {
        "accent": "#ffd489", "accent2": "#ffa5c0", "background": "#161208",
        "card": "#221c10", "text": "#fdf6ea", "muted": "#a39684", "radius": 24}),
    ("rarity",    "Rarity", {
        "accent": "#b78cf5", "accent2": "#f0edf7", "background": "#12101a",
        "card": "#1d1930", "text": "#f6f4ff", "muted": "#877fa6", "radius": 16}),
    ("pinkie-pie", "Pinkie Pie", {
        "accent": "#ff4fb8", "accent2": "#57d7f2", "background": "#1c0916",
        "card": "#2b0f24", "text": "#ffeaf7", "muted": "#ab6b95", "radius": 28, "effect": "swap", }),
    # --- utility ---
    ("tui",       "TUI Classic", {
        "accent": "#2dd4bf", "accent2": "#34d399", "background": "#0c0e11",
        "card": "#101318", "text": "#d8dee6", "muted": "#7a8593", "radius": 0}),
]

def preset_options_html(selected_key=None):
    """<option> list for the preset <select>. Deterministic order."""
    esc = lambda s: html_mod.escape(s, quote=True)
    out = ['<option value="">Custom</option>']
    for key, label, _ in THEME_PRESETS:
        sel = " selected" if key == selected_key else ""
        out.append('<option value="%s"%s>%s</option>' % (esc(key), sel, esc(label)))
    return "".join(out)


def theme_root_vars(spec):
    """Optional top-level ``theme`` -> extra :root CSS variables (defaults kept)."""
    vars_line = []  # always keep the full base so defaults are unchanged
    theme = spec.get("theme") or {}
    if _strip_str(theme.get("accent")):
        vars_line.append("--accent:%s;" % theme["accent"].strip())
    if _strip_str(theme.get("accent2")):
        vars_line.append("--accent2:%s;" % theme["accent2"].strip())
    if _strip_str(theme.get("font")):
        vars_line.append("--font:%s;" % theme["font"].strip())
    fs = theme.get("fontsize") if theme.get("fontsize") is not None else theme.get("font_size")
    if fs not in (None, ""):
        vars_line.append("--fontsize:%s;" % _px_number(fs, THEME_DEFAULT_FONT_SIZE))
    if _strip_str(theme.get("background")):
        vars_line.append("--bg:%s;" % theme["background"].strip())
    if _strip_str(theme.get("card")):
        vars_line.append("--card:%s;" % theme["card"].strip())
    if _strip_str(theme.get("text")):
        vars_line.append("--txt:%s;" % theme["text"].strip())
    if _strip_str(theme.get("muted")):
        vars_line.append("--muted:%s;" % theme["muted"].strip())
    radius = theme.get("radius")
    if radius not in (None, ""):
        rstr = str(radius).strip()
        if rstr.lstrip("-").replace(".", "", 1).isdigit():
            # bare number => treat as px
            vars_line.append("--radius:%spx;" % _px_number(radius, THEME_DEFAULT_RADIUS))
        else:
            vars_line.append("--radius:%s;" % rstr)
    if vars_line:
        return DEFAULT_CSS_VARS + "".join(vars_line)
    # no theme override at all -> same as baseline defaults
    return DEFAULT_CSS_VARS


def customize_html(spec):
    """Right-drawer 'Customize' section: accent/accent2/background/card/text
    color pickers, a font-family selector, a base font-size stepper, and a
    corner-radius stepper. Defaults come from spec.theme (falling back to the
    built-in CSS defaults) and are baked in at render time so the panel is
    fully populated — the live JS merely reads them. Byte-deterministic: for
    the same spec this returns identical markup."""
    theme = theme_defaults(spec.get("theme") or {})
    esc = lambda s: html_mod.escape(s, quote=True)
    # If the spec's font isn't one of the built-in stacks, add it as its own
    # selected option so the panel default always reflects spec.theme.
    has_font = any(stack == theme["font"] for _, stack in FONT_STACKS)
    opts_html = []
    if not has_font:
        opts_html.append('<option value="%s" selected>%s</option>'
                         % (esc(theme["font"]), esc(theme["font"])))
    for label, stack in FONT_STACKS:
        sel = " selected" if stack == theme["font"] else ""
        opts_html.append('<option value="%s"%s>%s</option>'
                         % (esc(stack), sel, esc(label)))
    fs = max(FONT_MIN_SIZE, min(FONT_MAX_SIZE, int(theme["fontsize"])))
    rad = max(RADIUS_MIN_SIZE, min(RADIUS_MAX_SIZE, int(theme["radius"])))
    return (
        '<div class="customize">'
        '<div class="customize-title">Customize</div>'
        '<div class="customize-row"><label for="theme-preset">Preset</label>'
        '<select id="theme-preset" aria-label="Theme preset">%s</select></div>'
        '<div class="customize-row"><label for="theme-accent">Accent</label>'
        '<input type="color" id="theme-accent" value="%s" aria-label="Accent color"></div>'
        '<div class="customize-row"><label for="theme-accent2">Accent 2</label>'
        '<input type="color" id="theme-accent2" value="%s" aria-label="Accent 2 color"></div>'
        '<div class="customize-row"><label for="theme-bg">Background</label>'
        '<input type="color" id="theme-bg" value="%s" aria-label="Background color"></div>'
        '<div class="customize-row"><label for="theme-card">Card</label>'
        '<input type="color" id="theme-card" value="%s" aria-label="Card color"></div>'
        '<div class="customize-row"><label for="theme-text">Text</label>'
        '<input type="color" id="theme-text" value="%s" aria-label="Text color"></div>'
        '<div class="customize-row"><label for="theme-font">Font</label>'
        '<select id="theme-font" aria-label="Font family">%s</select></div>'
        '<div class="customize-row"><label for="fs-value">Base font size</label>'
        '<span class="stepper">'
        '<button type="button" id="font-minus" aria-label="Decrease font size">&minus;</button>'
        '<span id="fs-value">%dpx</span>'
        '<button type="button" id="font-plus" aria-label="Increase font size">+</button>'
        '</span></div>'
        '<div class="customize-row"><label for="radius-value">Corner radius</label>'
        '<span class="stepper">'
        '<button type="button" id="radius-minus" aria-label="Decrease radius">&minus;</button>'
        '<span id="radius-value">%dpx</span>'
        '<button type="button" id="radius-plus" aria-label="Increase radius">+</button>'
        '</span></div>'
        '</div>'
    ) % (preset_options_html(), esc(theme["accent"]), esc(theme["accent2"]),
         esc(theme["background"]), esc(theme["card"]), esc(theme["text"]),
         "".join(opts_html), fs, rad)


def agent_settings(spec):
    """Optional top-level ``agent`` -> (webhook_url, display_name, timeout_ms)."""
    agent = spec.get("agent") or {}
    webhook = _strip_str(agent.get("webhook_url"))
    name = _strip_str(agent.get("name")) or "agent"
    timeout = agent.get("timeout_ms")
    if timeout in (None, ""):
        timeout = 10000
    else:
        timeout = max(1, int(timeout))
    return webhook, name, timeout


def _render_option(key, item_id, opt_body, disabled=False):
    value = opt_body.get("value")
    desc = opt_body.get("description", "")
    choices = opt_body.get("choices") or []
    field = html_mod.escape("%s--%s" % (item_id, key), quote=True)
    dis = " disabled" if disabled else ""

    label = (('<span class="opt-label" data-tip="%s">%s</span>'
              % (html_mod.escape(desc, quote=True), html_mod.escape(key)))
             if desc else
             ('<span class="opt-label">%s</span>' % html_mod.escape(key)))

    if choices:  # pill radio group
        pills = ['<div class="pills">']
        for ch in choices:
            if isinstance(ch, dict):
                chval = ch.get("value", "")
                color = ch.get("color")
            else:
                chval = ch
                color = None
            sel = " checked" if str(chval) == str(value) else ""
            sel += dis
            pill_style = (' style="--pill:%s"'
                          % html_mod.escape(str(color), quote=True)) if color else ""
            pills.append(
                '<label class="pill"><input type="radio" name="opt-%s"'
                ' value="%s"%s><span%s>%s</span></label>'
                % (field, html_mod.escape(str(chval), quote=True), sel, pill_style,
                   html_mod.escape(str(chval))))
        pills.append("</div>")
        control = "".join(pills)
    elif isinstance(value, bool):
        check = " checked" if value else ""
        check += dis
        control = ('<label class="toggle"><input type="checkbox" name="opt-%s"%s>'
                   '<span class="track"><span class="knob"></span></span></label>'
                   % (field, check))
    else:
        val = "" if value is None else str(value)
        control = ('<input class="textinput" type="text" name="opt-%s" value="%s"%s>'
                   % (field, html_mod.escape(val, quote=True), dis))

    return '<div class="opt">%s%s</div>' % (label, control)


def _render_item_html(it, disabled=False):
    notes_val = it.get("notes", "")
    dis = " disabled" if disabled else ""
    if notes_val:
        note = ('<textarea class="note" rows="1" data-role="note"%s>%s</textarea>'
                % (dis, html_mod.escape(notes_val)))
    else:
        note = ('<textarea class="note ghost" rows="1" data-role="note"%s></textarea>'
                % dis)
    opts = "".join(_render_option(k, it.get("id", ""), o, disabled)
                   for k, o in (it.get("options") or {}).items())
    return (
        '<div class="item" data-item="%s">'
        '  <label class="item-top">'
        '    <input type="checkbox" class="done" data-role="done"%s>'
        '    <span class="item-text">%s</span>'
        '  </label>'
        '  <div class="options">%s</div>'
        '  %s'
        '</div>'
    ) % (html_mod.escape(it.get("id", ""), quote=True), dis,
         html_mod.escape(it.get("text", "")), opts, note)


def _passdown_ctx(spec):
    """Return (pd, strict, skipped_ids) for a spec's embedded passdown block.

    ``pd`` is the raw ``passdown`` block (or {}), ``strict`` is True when its
    mode is ``'strict'``, and ``scope`` is the list of category ids in scope
    (empty when absent). Categories not named in ``scope`` — only meaningful
    when a non-empty scope is given — are the ones rendered as skipped.
    """
    pd = spec.get("passdown") or {}
    strict = (pd.get("mode", "") == "strict")
    scope = pd.get("scope")
    if not isinstance(scope, list):
        scope = []
    return pd, strict, scope


def _build_categories(spec):
    pd, strict, scope = _passdown_ctx(spec)
    all_ids = [c.get("id", "") for c in spec.get("categories", [])]
    skip = set()
    if scope:
        skip = {cid for cid in all_ids if cid not in scope}
    out = []
    for cat in spec.get("categories", []):
        cid = cat.get("id", "")
        skipped = cid in skip
        items_html = "".join(_render_item_html(it, skipped)
                             for it in cat.get("items", []))
        goal = cat.get("goal", "")
        goal_html = ""
        if goal:
            goal_html = ('<div class="cat-goal">%s</div>' % html_mod.escape(goal))
        collapsed = " collapsed" if (cat.get("collapsed_default", False) or skipped) else ""
        skipped_cls = " passdown-skipped" if skipped else ""
        chip = ""
        if strict:
            chip = ('<span class="completion-chip" data-chip="%s"></span>'
                    % html_mod.escape(cid, quote=True))
        out.append(
            '<section class="cat%s%s" data-cat="%s">'
            '  <button class="cat-head" type="button">'
            '    <span class="chev">▸</span>'
            '    <span class="cat-title">%s</span>'
            '    %s%s'
            '  </button>'
            '  <div class="cat-body">%s</div>'
            '</section>'
            % (collapsed, skipped_cls, html_mod.escape(cid, quote=True),
               html_mod.escape(cat.get("name", "")), chip, goal_html, items_html))
    return "\n".join(out)


def render_html(spec):
    title = spec.get("title", "Checklist")
    spec_json = _inline_js(spec)
    webhook, agent_name, timeout_ms = agent_settings(spec)
    agent_json = _inline_js({"webhook_url": webhook, "name": agent_name,
                             "timeout_ms": timeout_ms})
    if webhook:
        send_html = ('<button class="btn" id="sendbtn" type="button">'
                     'Send to %s</button>' % html_mod.escape(agent_name, quote=True))
    else:
        send_html = ""
    cats_html = _build_categories(spec)
    cust_html = customize_html(spec)

    # ---- passdown banner + strict-mode warning element (empty when no passdown)
    pd, strict, _scope = _passdown_ctx(spec)
    banner_html = ""
    if pd:
        frm = pd.get("from") if pd.get("from") not in (None, "") else "orchestrator"
        banner_html = (
            '<div class="passdown-banner">'
            '<span class="passdown-route">Passdown from %s &#8594; %s</span>'
            '<span class="passdown-sep">|</span>'
            '<span class="passdown-mission">%s</span>'
            '</div>'
            % (html_mod.escape(frm, quote=True),
               html_mod.escape(pd.get("to", ""), quote=True),
               html_mod.escape(pd.get("mission", ""), quote=True)))
    warn_html = ('<div class="passdown-warn" id="passdown-warn" hidden></div>'
                 if strict else "")

    out = HTML_TEMPLATE
    out = out.replace("__SPEC__", spec_json)
    out = out.replace("__AGENT__", agent_json)
    out = out.replace("__AGENT_SEND__", send_html)
    out = out.replace("__PRESETS__", _inline_js(
        {key: pal for key, _, pal in THEME_PRESETS}))
    out = out.replace("__ROOT_VARS__", theme_root_vars(spec))
    out = out.replace("__CUSTOMIZE__", cust_html)
    out = out.replace("__TITLE__", html_mod.escape(title, quote=True))
    out = out.replace("__BODY_CATS__", cats_html)
    out = out.replace("__PASSDOWN_BANNER__", banner_html)
    out = out.replace("__PASSDOWN_WARN__", warn_html)
    return out


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

def parse_results(results):
    """Emit canonical round-trip JSON: title, global_notes, categories[items[...]].

    Categories and items are walked in *definition order* exactly as they
    appear in the results; options are echoed in option-name order. Defaults
    are preserved as-is (build_results() already pre-fills them, so nothing is
    dropped and nothing is defaulted-out). The emitted shape is identical to
    build_results(), so ``parse(build_results(S)) == build_results(S)``.
    """
    res = {"title": results.get("title", ""),
           "global_notes": results.get("global_notes", ""),
           "categories": []}
    if results.get("theme"):
        res["theme"] = results["theme"]
    if results.get("config"):
        res["config"] = results["config"]
    if results.get("passdown"):
        res["passdown"] = results["passdown"]
    for cat in results.get("categories", []):
        items = []
        for it in cat.get("items", []):
            items.append({
                "id": it.get("id", ""),
                "text": it.get("text", ""),
                "options": dict(it.get("options", {})),
                "notes": it.get("notes", ""),
            })
        res["categories"].append({
            "id": cat.get("id", ""),
            "name": cat.get("name", ""),
            "goal": cat.get("goal", ""),
            "items": items,
        })
    return res


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_new(args):
    spec = default_spec()
    if args.path == "-":
        sys.stdout.write(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
        return
    if args.path:
        d = os.path.dirname(args.path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.path, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("wrote %s" % args.path)


def cmd_render(args):
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    sys.stdout.write(render_html(spec))


def cmd_parse(args):
    with open(args.results, encoding="utf-8") as f:
        results = json.load(f)
    canon = parse_results(results)
    sys.stdout.write(json.dumps(canon, ensure_ascii=False, indent=2) + "\n")


def cmd_passdown(args):
    """Render a spec as a pass-down for a subagent.

    The spec MUST carry ``config: {"allow_passdown": true}``; otherwise we
    refuse (exit 1) so an author can lock a checklist against delegation. The
    rendered page embeds a ``passdown`` metadata block and, when ``--scope``
    is given, collapses + disables non-scoped categories.
    """
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    cfg = spec.get("config") or {}
    if cfg.get("allow_passdown") is not True:
        sys.exit("checklst: %s is locked by its author "
                 "(config.allow_passdown must be true for passdown) "
                 "- spec locked by author" % args.spec)

    mission = (args.mission or "").strip()
    scope = []
    if args.scope:
        scope = [s.strip() for s in args.scope.split(",") if s.strip()]
    pd = {
        "from": (args.from_name or "orchestrator").strip() or "orchestrator",
        "to": (args.agent or "").strip(),
        "mission": mission,
        "scope": scope,
        "mode": "strict",
    }
    merged = dict(spec)
    merged["passdown"] = pd
    html = render_html(merged)
    if args.out:
        d = os.path.dirname(args.out)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(html)
        print("wrote %s" % args.out)
    else:
        sys.stdout.write(html)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="checklst", description="Zero-dependency checklist tool.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_new = sub.add_parser("new", help="emit a starter spec JSON file")
    s_new.add_argument("path", nargs="?", default="examples/demo.checklist.json")
    s_new.add_argument("--stdout", action="store_true", help="print to stdout")
    s_new.set_defaults(func=cmd_new)

    s_ren = sub.add_parser("render", help="render a spec to standalone HTML")
    s_ren.add_argument("spec")
    s_ren.set_defaults(func=cmd_render)

    s_par = sub.add_parser("parse", help="parse a filled results JSON")
    s_par.add_argument("results")
    s_par.set_defaults(func=cmd_parse)

    s_pass = sub.add_parser(
        "passdown", help="delegate a checklist to a subagent (config.allow_passdown must be true)")
    s_pass.add_argument("spec")
    s_pass.add_argument("--agent", required=True, help="receiving subagent name")
    s_pass.add_argument("--mission", default="", help="brief mission text for the delegate")
    s_pass.add_argument("--from", dest="from_name", default="orchestrator",
                        help="orchestrator name shown in the passdown banner")
    s_pass.add_argument("--scope", default="",
                        help="comma-separated category ids the delegate is asked to cover")
    s_pass.add_argument("-o", "--out", default=None, help="write HTML to file (default stdout)")
    s_pass.set_defaults(func=cmd_passdown)

    s_home = sub.add_parser(
        "home", help="render an agent-pipeline homepage grouping checklists by agent")
    s_home.add_argument("manifest", help="manifest JSON: {agents:[{name, lists:[spec paths]}]}")
    s_home.add_argument("-o", "--out", default=None, help="write HTML to file (default stdout)")
    s_home.set_defaults(func=cmd_home)

    args = p.parse_args(argv)
    args.func(args)




# ---------------------------------------------------------------------------
# home — agent-pipeline dashboard
# ---------------------------------------------------------------------------

def _agent_hue(name):
    """Deterministic hue 0-359 from agent name (stable across runs)."""
    h = 0
    for ch in str(name):
        h = (h * 31 + ord(ch)) % 360
    return h


def cmd_home(args):
    """Render the agent-pipeline homepage.

    Manifest shape:
      {
        "title": "optional page title",
        "agents": [
          {"name": "worker-1", "lists": ["path/a.json", "path/b.json"],
           "stage": "testing"}   # stage optional: draft|building|testing|review|done
        ]
      }
    Each spec is loaded; missing files degrade to an error card, never crash.
    Output is byte-deterministic.
    """
    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    agents_out = []
    for ag in manifest.get("agents", []):
        name = str(ag.get("name", "unnamed"))
        stage = str(ag.get("stage", "")).strip()
        lists = []
        for path in ag.get("lists", []):
            entry = {"path": path}
            try:
                with open(path, encoding="utf-8") as f:
                    spec = json.load(f)
                cats = spec.get("categories", [])
                items_n = sum(len(c.get("items", [])) for c in cats)
                entry.update({
                    "ok": True,
                    "title": spec.get("title", os.path.basename(path)),
                    "categories": len(cats),
                    "items": items_n,
                    "stage": str(spec.get("config", {}).get("stage",
                             ag.get("stage", ""))).strip(),
                })
            except Exception as e:  # missing/broken spec -> error card
                entry.update({"ok": False, "error": "%s" % e})
            lists.append(entry)
        agents_out.append({"name": name, "stage": stage, "lists": lists})

    data = {"title": manifest.get("title", "CHECKLST — Agent Pipeline"),
            "agents": agents_out}
    html = render_home(data)
    if args.out:
        d = os.path.dirname(args.out)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(html)
        print("wrote %s" % args.out)
    else:
        sys.stdout.write(html)


def render_home(data):
    title = html_mod.escape(data.get("title", "CHECKLST"), quote=True)
    favicon = ('<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/sv'
               'g\' viewBox=\'0 0 32 32\'%3E%3Crect width=\'32\' height=\'32\' fill=\'%230b0f14\'/'
               '%3E%3Cpath d=\'M9 16.5l5 5L23 11\' stroke=\'%232dd4bf\' stroke-width=\'4\' fill=\'no'
               'ne\' stroke-linecap=\'square\'/%3E%3C/svg%3E">')
    cards = []
    for a in data["agents"]:
        rows = []
        for l in a["lists"]:
            if l.get("ok"):
                stage = l.get("stage") or "draft"
                mark = {"done": "+", "testing": "~", "review": "?", "draft": "-",
                        "orchestrating": "*", "building": "*"}.get(stage, "-")
                rows.append(
                    '<div class="r">'
                    '<span class="mark m-%s">%s</span>'
                    '<span class="rt">%s</span>'
                    '<span class="meta">%d cats / %d items</span>'
                    '</div>'
                    % (html_mod.escape(stage), html_mod.escape(mark),
                       html_mod.escape(l["title"]),
                       l["categories"], l["items"]))
            else:
                rows.append(
                    '<div class="r rerr">'
                    '<span class="mark">!</span>'
                    '<span class="rt">%s</span>'
                    '<span class="meta">unreadable</span>'
                    '</div>'
                    % html_mod.escape(os.path.basename(l["path"])))
        stage = a.get("stage")
        cards.append(
            '<section class="grp">'
            '<h2>%s<span class="n">%d lists</span><em>%s</em></h2>'
            '%s'
            '</section>'
            % (html_mod.escape(a["name"]), len(a["lists"]),
               html_mod.escape(stage) if stage else "",
               "".join(rows)))
    return HOME_TEMPLATE.replace("__TITLE__", title).replace("__FAVICON__", favicon) \
        .replace("__AGENTS__", "\n".join(cards))


HOME_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
__FAVICON__
<style>
/* Terminal-ledger aesthetic: sharp corners, monospace data, hairline rules,
   ONE accent. No stat cards, no glows, no pills, no gradients. */
:root{--bg:#0c0e11;--panel:#101318;--rule:#242a33;--txt:#d8dee6;--dim:#7a8593;
  --accent:#2dd4bf;--bad:#e5534b;
  --mono:"SF Mono",ui-monospace,Menlo,Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font-family:var(--mono);
  font-size:13px;line-height:1.55;padding:56px 24px;display:flex;justify-content:center}
.wrap{width:100%;max-width:680px}
.hd{border-bottom:2px solid var(--txt);padding-bottom:14px;margin-bottom:28px}
.kicker{color:var(--dim);font-size:11px;letter-spacing:.12em;text-transform:uppercase}
h1{font-size:15px;font-weight:600;margin-top:6px;color:var(--txt)}
h1 b{color:var(--accent);font-weight:700}
.grp{margin-bottom:26px}
.grp h2{font-size:13px;font-weight:700;color:var(--txt);
  border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:0;
  display:flex;align-items:baseline;gap:10px}
.grp h2 em{margin-left:auto;font-style:normal;color:var(--dim);font-weight:400;font-size:11px}
.grp h2 .n{color:var(--dim);font-weight:400;font-size:11px}
.r{display:flex;align-items:baseline;gap:14px;padding:9px 2px;border-bottom:1px solid var(--rule)}
.r:hover{background:var(--panel)}
.mark{width:16px;text-align:center;flex:none;font-weight:700}
.m-done{color:var(--accent)}
.m-testing{color:#d8ae3c}
.m-review{color:#b58cf2}
.rerr .mark,.rerr .rt{color:var(--bad)}
.rt{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meta{color:var(--dim);font-size:11.5px;white-space:nowrap}
.ft{color:var(--dim);font-size:11px;margin-top:30px;border-top:1px solid var(--rule);padding-top:10px}
@media(max-width:560px){.meta{display:none}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hd">
    <div class="kicker">checklst &middot; pipeline</div>
    <h1><b>></b> __TITLE__</h1>
  </div>
__AGENTS__
  <div class="ft">generated by checklst &middot; zero dependencies &middot; opens from file://</div>
</div>
</body>
</html>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<!-- Favicon as an inline SVG data: URI — no external requests, deterministic bytes. -->
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%2064%2064%27%3E%3Cdefs%3E%3ClinearGradient%20id%3D%27g0%27%20x1%3D%270%27%20y1%3D%270%27%20x2%3D%271%27%20y2%3D%271%27%3E%3Cstop%20offset%3D%270%27%20stop-color%3D%27%232dd4bf%27%2F%3E%3Cstop%20offset%3D%271%27%20stop-color%3D%27%2334d399%27%2F%3E%3C%2FlinearGradient%3E%3C%2Fdefs%3E%3Crect%20width%3D%2764%27%20height%3D%2764%27%20rx%3D%2714%27%20fill%3D%27url%28%23g0%29%27%2F%3E%3Cpath%20d%3D%27M21%2033l8%208%2016-17%27%20fill%3D%27none%27%20stroke%3D%27%23ffffff%27%20stroke-width%3D%277%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%2F%3E%3C%2Fsvg%3E">
<style>
  :root{
    __ROOT_VARS__
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  :focus-visible{outline:2px solid color-mix(in srgb,var(--accent) 72%,#fff);outline-offset:2px;border-radius:6px}
  body{
    background:
      radial-gradient(1200px 640px at 14% -12%, color-mix(in srgb,var(--accent) 12%, transparent), transparent 62%),
      radial-gradient(1000px 560px at 108% -6%, color-mix(in srgb,var(--accent2) 10%, transparent), transparent 58%),
      radial-gradient(1500px 900px at 50% 118%, color-mix(in srgb,var(--bg2) 60%, var(--bg)), transparent 72%),
      var(--bg);
    background-attachment:fixed;
    color:var(--txt);
    font-family:var(--font);
    font-size:var(--fontsize,16px);
    line-height:1.55; min-height:100vh;
  }
  .wrap{max-width:920px;margin:0 auto;padding:44px 20px 88px}
  header.hero{position:relative;margin-bottom:22px;padding:26px 28px;
    background:linear-gradient(180deg,color-mix(in srgb,var(--card) 78%,transparent),transparent);
    border-radius:calc(var(--radius) + 6px)}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:12px}
  .logo{width:16px;height:16px;border-radius:5px;background:linear-gradient(135deg,var(--accent),var(--accent2));
    box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent),var(--glow)}
  .kicker{letter-spacing:.22em;text-transform:uppercase;font-size:11px;color:color-mix(in srgb,var(--muted) 82%,var(--accent));font-weight:700}
  h1{font-size:clamp(30px,5vw,40px);margin:4px 0 8px;font-weight:760;letter-spacing:-.025em;
    line-height:1.08;text-wrap:balance}
  .sub{color:var(--muted);font-size:14px;max-width:56ch}
  .chromebar{
    display:flex;justify-content:space-between;align-items:center;gap:12px;
    background:linear-gradient(180deg,var(--card),var(--bg2));
    border:1px solid var(--line);border-radius:var(--radius);
    padding:11px 15px;margin:20px 0 24px;box-shadow:var(--shadow);
  }
  .progress-label{font-size:12px;color:var(--muted);font-weight:600;white-space:nowrap}
  .progress{flex:1;height:8px;border-radius:999px;background:var(--card2);overflow:hidden;
    box-shadow:inset 0 1px 2px rgba(0,0,0,.4)}
  .progress>i{display:block;height:100%;width:0;border-radius:999px;
    background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .35s cubic-bezier(.4,0,.2,1);
    box-shadow:0 0 10px color-mix(in srgb,var(--accent) 60%,transparent)}
  .cat{background:linear-gradient(180deg,var(--card),var(--bg2));border:1px solid var(--line);
    border-radius:var(--radius);margin-bottom:16px;overflow:hidden;box-shadow:var(--shadow);
    transition:border-color .2s ease,box-shadow .25s ease}
  .cat:hover{border-color:var(--line2);box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 24px 50px -24px rgba(0,0,0,.75)}
  button.cat-head{display:block;width:100%;text-align:left;background:none;border:0;cursor:pointer;
    padding:17px 19px;font:inherit;color:inherit}
  button.cat-head:hover{background:color-mix(in srgb,var(--card2) 55%,transparent)}
  .cat-head{display:flex;align-items:center;gap:12px}
  .chev{transition:transform .35s cubic-bezier(.45,0,.25,1);color:var(--accent);font-size:13px;width:14px;flex:none}
  .cat-title{font-size:17px;font-weight:720;letter-spacing:.01em}
  .cat-goal{margin:3px 0 0 12px;font-size:13px;color:var(--muted);flex:1}
  .cat.collapsed .chev{transform:rotate(90deg)}
  .cat-body{display:block;padding:4px 20px 18px;max-height:3000px;opacity:1;overflow:hidden;
    border-top:1px solid var(--line);transition:max-height .5s cubic-bezier(.4,0,.2,1),
    opacity .3s ease,padding .3s ease,border-color .3s ease}
  .cat.collapsed .cat-body{max-height:0;opacity:0;padding-top:0;padding-bottom:0;border-top-color:transparent}
  .cat-body:empty{display:none}
  .item{padding:16px 2px;border-bottom:1px solid var(--line);border-radius:10px;
    transition:background .15s ease,box-shadow .15s ease}
  .item:last-child{border-bottom:0}
  .item:hover{background:color-mix(in srgb,var(--card2) 30%,transparent)}
  .item-top{display:flex;gap:12px;align-items:flex-start;cursor:pointer}
  input.done{width:18px;height:18px;margin-top:2px;accent-color:var(--ok);flex:none;cursor:pointer}
  .item-text{font-size:15px;font-weight:550}
  .item.doneoff .item-text{color:var(--muted);text-decoration:line-through}
  .options{display:flex;flex-wrap:wrap;gap:10px 22px;margin:14px 0 2px 32px}
  .opt-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;display:block;margin-bottom:5px}
  .opt-label[data-tip]{cursor:help;border-bottom:1px dotted var(--line)}
  .pills{display:inline-flex;gap:4px;background:var(--card2);padding:4px;border-radius:10px;border:1px solid var(--line)}
  label.pill{position:relative;cursor:pointer}
  label.pill input{position:absolute;opacity:0;inset:0;margin:0;cursor:pointer}
  label.pill span{display:block;padding:6px 12px;border-radius:7px;font-size:13px;font-weight:600;
    color:var(--muted);transition:color .18s ease,background .18s ease,transform .18s cubic-bezier(.34,1.56,.64,1)}
  label.pill span:hover{color:var(--txt)}
  label.pill input:checked+span{background:var(--pill,linear-gradient(135deg,var(--accent),var(--accent2)));
    color:#fff;box-shadow:0 4px 14px -4px color-mix(in srgb,var(--accent) 65%,transparent);
    text-shadow:0 1px 2px rgba(0,0,0,.25);transform:scale(1.02)}
  label.pill:focus-within span{outline:2px solid color-mix(in srgb,var(--accent) 65%,transparent);outline-offset:1px}
  label.toggle{display:inline-flex;cursor:pointer;vertical-align:middle}
  label.toggle input{position:absolute;opacity:0;width:0}
  .track{width:44px;height:24px;border-radius:999px;background:var(--card2);border:1px solid var(--line);
    position:relative;transition:background .22s ease,border-color .22s ease;box-shadow:inset 0 1px 2px rgba(0,0,0,.35)}
  .knob{position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:var(--muted);
    transition:left .25s cubic-bezier(.34,1.4,.5,1),background .2s ease;box-shadow:0 1px 3px rgba(0,0,0,.5)}
  label.toggle input:checked + .track{background:var(--accent);border-color:var(--accent)}
  label.toggle input:checked + .track .knob{left:22px;background:#fff}
  label.toggle:focus-visible{outline:2px solid color-mix(in srgb,var(--accent) 65%,transparent);outline-offset:2px;border-radius:999px}
  .textinput{background:var(--card2);border:1px solid var(--line);color:var(--txt);
    border-radius:8px;padding:7px 11px;font-size:13px;min-width:220px;transition:border-color .15s ease,box-shadow .15s ease}
  .textinput:hover{border-color:var(--line2)}
  .textinput:focus{outline:none;border-color:var(--accent);
    box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 22%,transparent)}
  textarea.note{display:block;width:100%;margin:10px 0 0 30px;background:var(--card2);
    border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:9px 12px;
    font-family:inherit;font-size:13px;resize:vertical;min-height:0;transition:border-color .15s ease,box-shadow .15s ease}
  textarea.note.ghost{color:var(--muted);font-style:italic;height:38px}
  textarea.note:focus{outline:none;border-color:var(--accent);
    box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 22%,transparent)}
  .readout{margin-top:28px}
  .readout .bar{display:flex;gap:10px;align-items:center;margin-bottom:8px}
  .btn{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;border:0;
    padding:9px 18px;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;
    transition:filter .15s ease,transform .1s ease,box-shadow .2s ease;
    box-shadow:0 8px 20px -8px color-mix(in srgb,var(--accent) 70%,transparent)}
  .btn:hover{filter:brightness(1.08);transform:translateY(-1px)}
  .btn:active{transform:translateY(0)}
  .btn.ghost{background:none;border:1px solid var(--line);color:var(--txt);box-shadow:none;transition:border-color .15s ease}
  .btn.ghost:hover{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 8%,transparent)}
  .drawer-toggle{white-space:nowrap}
  .drawer{position:fixed;top:0;right:0;bottom:0;width:420px;max-width:92vw;background:var(--card);
    border-left:1px solid var(--line);box-shadow:var(--shadow);z-index:60;padding:18px;
    display:flex;flex-direction:column;gap:12px;transform:translateX(105%);
    transition:transform .42s cubic-bezier(.32,.72,.24,1);overflow-y:auto}
  .drawer.open{transform:translateX(0)}
  .drawer-head{display:flex;justify-content:space-between;align-items:center;gap:10px}
  .drawer-head .progress-label{white-space:normal}
  .drawer-close{background:none;border:0;color:var(--muted);font-size:20px;line-height:1;cursor:pointer;
    border-radius:8px;padding:2px 6px;transition:color .15s ease,background .15s ease}
  .drawer-close:hover{color:var(--txt);background:color-mix(in srgb,var(--card2) 60%,transparent)}
  .drawer-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .drawer-actions .btn{white-space:nowrap}
  .sendstatus{font-size:12px;font-weight:600;color:var(--muted)}
  .sendstatus.ok{color:var(--ok)}
  .sendstatus.err{color:var(--bad)}
  .drawer-scrim{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:55;
    opacity:0;pointer-events:none;transition:opacity .4s ease;backdrop-filter:blur(3px)}
  .drawer-scrim.show{opacity:1;pointer-events:auto}
  textarea#results-json{width:100%;flex:1;min-height:200px;background:var(--card2);
    color:color-mix(in srgb,var(--accent) 45%,var(--txt));
    border:1px solid var(--line);border-radius:10px;padding:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
    font-size:12px;resize:vertical;white-space:pre}
  .customize{margin-top:14px;border-top:1px solid var(--line);padding-top:12px;
    display:flex;flex-direction:column;gap:10px}
  .customize-title{font-size:11px;color:var(--muted);text-transform:uppercase;
    letter-spacing:.05em;font-weight:700}
  .customize-row{display:flex;align-items:center;justify-content:space-between;gap:10px}
  .customize-row label{font-size:12px;color:var(--muted);font-weight:600;white-space:nowrap}
  .customize-row input[type=color]{width:46px;height:28px;padding:2px;border:1px solid var(--line);
    border-radius:6px;background:var(--card2);cursor:pointer}
  .customize-row input[type=color]:hover{border-color:var(--accent)}
  .customize-row select{background:var(--card2);border:1px solid var(--line);color:var(--txt);
    border-radius:8px;padding:6px 8px;font-size:12px;max-width:210px;cursor:pointer}
  .customize-row select:focus{outline:none;border-color:var(--accent)}
  .stepper{display:inline-flex;align-items:center;gap:4px}
  .stepper button{width:28px;height:26px;border:1px solid var(--line);background:var(--card2);
    color:var(--txt);border-radius:6px;cursor:pointer;font-size:15px;line-height:1}
  .stepper button:hover{border-color:var(--accent)}
  .stepper #fs-value{font-size:12px;min-width:40px;text-align:center;color:var(--txt);font-weight:600}
  .stepper #radius-value{font-size:12px;min-width:40px;text-align:center;color:var(--txt);font-weight:600}
  .btn:disabled{opacity:.55;cursor:not-allowed;pointer-events:none}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin-left:30px}
  .chip{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;background:var(--card2);
    color:var(--muted);border:1px solid var(--line)}
  .completion-chip{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;
    background:color-mix(in srgb,var(--accent) 14%,var(--card2));color:color-mix(in srgb,var(--accent) 55%,var(--txt));
    border:1px solid color-mix(in srgb,var(--accent) 30%,var(--line));flex:none;white-space:nowrap}
  .completion-chip.done{background:color-mix(in srgb,var(--ok) 16%,var(--card2));
    color:var(--ok);border-color:color-mix(in srgb,var(--ok) 35%,var(--line))}
  .passdown-banner{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-top:16px;
    padding:11px 15px;border:1px solid color-mix(in srgb,var(--accent) 38%,var(--line));
    border-radius:var(--radius);background:linear-gradient(180deg,
    color-mix(in srgb,var(--accent) 13%,var(--card)),transparent);box-shadow:var(--shadow)}
  .passdown-route{font-size:12px;font-weight:750;letter-spacing:.03em;
    color:color-mix(in srgb,var(--accent) 62%,var(--txt))}
  .passdown-route::before{content:"◈";margin-right:7px;color:var(--accent)}
  .passdown-sep{color:var(--line2);font-weight:400}
  .passdown-mission{font-size:13px;color:var(--muted);font-style:italic}
  .passdown-warn{display:block;margin:0 0 18px;padding:11px 16px;border-radius:var(--radius);
    border:1px solid color-mix(in srgb,var(--warn) 46%,var(--line));
    background:color-mix(in srgb,var(--warn) 12%,var(--card));color:var(--warn);
    font-size:13px;font-weight:650;box-shadow:var(--shadow)}
  .passdown-skipped{opacity:.55}
  .passdown-skipped .cat-head{pointer-events:none}
  .passdown-skipped .done,.passdown-skipped input,.passdown-skipped textarea,
  .passdown-skipped label.pill,.passdown-skipped .pills{pointer-events:none;cursor:not-allowed;opacity:.45}
  @media (max-width:560px){.options{margin-left:0}.readout .bar{flex-wrap:wrap}}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="brand"><span class="logo"></span><span class="brand">CHECKLST</span></div>
    <h1>__TITLE__</h1>
    <p class="sub">Work through every item, mark it done, and export the results.</p>
    __PASSDOWN_BANNER__
  </header>

  <div class="chromebar">
    <span class="progress-label" id="proglabel">0 done</span>
    <div class="progress"><i id="progbar"></i></div>
    <button class="btn drawer-toggle" id="drawerbtn" type="button">Results ▸</button>
  </div>

  __PASSDOWN_WARN__

  <main class="cats" id="cats">
__BODY_CATS__
  </main>

  <section class="readout">
    <div class="bar">
      <span class="progress-label">Global notes</span>
    </div>
    <textarea id="global-notes" class="note" rows="2"
      placeholder="Shared notes that apply to the whole checklist..."></textarea>
  </section>
</div>

<div class="drawer-scrim" id="scrim"></div>
<div class="drawer" id="drawer">
  <div class="drawer-head">
    <span class="progress-label">Results JSON (parse-ready)</span>
    <button class="drawer-close" id="drawerclose" type="button" aria-label="Close drawer">✕</button>
  </div>
  <textarea id="results-json" spellcheck="false"></textarea>
  <div class="drawer-actions">
    <button class="btn ghost" id="copybtn">Copy results</button>
    __AGENT_SEND__
  </div>
  <span class="sendstatus" id="send-status"></span>
  __CUSTOMIZE__
</div>

<script>
"use strict";
var SPEC = __SPEC__;
var AGENT = __AGENT__;
var PRESETS = __PRESETS__;

/* ---- Customize panel (runtime-only; does not affect render determinism) ---- */
var LS_KEY = 'checklst.theme.v1';
var FONT_MIN = 14, FONT_MAX = 18;
var RADIUS_MIN = 4, RADIUS_MAX = 40;
var THEME_DEFAULT_RADIUS = 14;
var themeDirty = false;
var THEME_MUTED = '#8fa3b8';
try{
  var __muted = getComputedStyle(document.documentElement).getPropertyValue('--muted').trim();
  if(__muted) THEME_MUTED = __muted;
}catch(e){}

function elVal(id){ return (document.getElementById(id)||{}).value; }
function readThemeControl(){
  return {
    accent:    elVal('theme-accent'),
    accent2:   elVal('theme-accent2'),
    background:elVal('theme-bg'),
    card:      elVal('theme-card'),
    text:      elVal('theme-text'),
    font:      elVal('theme-font'),
    fontsize:  parseInt((document.getElementById('fs-value').textContent||'').replace('px',''),10)||16,
    radius:    parseInt((document.getElementById('radius-value').textContent||'').replace('px',''),10)||THEME_DEFAULT_RADIUS,
    effect:    (function(){var s=document.getElementById('theme-preset');return s?s.value:'';})()
  };
}
var THEME = readThemeControl();

function applyTheme(){
  var el = document.documentElement;
  el.style.setProperty('--accent', THEME.accent);
  el.style.setProperty('--accent2', THEME.accent2);
  el.style.setProperty('--bg', THEME.background);
  el.style.setProperty('--card', THEME.card);
  el.style.setProperty('--txt', THEME.text);
  el.style.setProperty('--font', THEME.font);
  el.style.setProperty('--fontsize', THEME.fontsize + 'px');
  el.style.setProperty('--radius', THEME.radius + 'px');
  el.style.setProperty('--muted', THEME_MUTED);
}
function saveTheme(){ try{ localStorage.setItem(LS_KEY, JSON.stringify(THEME)); }catch(e){} }
function loadSavedTheme(){
  var saved = null;
  try{ saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); }catch(e){ return; }
  if(!saved || typeof saved !== 'object') return;
  function setColor(id, key){
    if(typeof saved[key] === 'string' && saved[key]){
      var el = document.getElementById(id); if(el) el.value = saved[key];
    }
  }
  setColor('theme-accent', 'accent');
  setColor('theme-accent2', 'accent2');
  setColor('theme-bg', 'background');
  setColor('theme-card', 'card');
  setColor('theme-text', 'text');
  var f = document.getElementById('theme-font');
  if(f && typeof saved.font === 'string' && saved.font){
    for(var i=0;i<f.options.length;i++){ if(f.options[i].value === saved.font){ f.value = saved.font; break; } }
  }
  var fsz = saved.fontsize; if(typeof fsz !== 'number') fsz = saved.font_size;
  var fv = document.getElementById('fs-value');
  if(typeof fsz === 'number' && fv){
    var n = Math.max(FONT_MIN, Math.min(FONT_MAX, fsz));
    fv.textContent = n + 'px';
  }
  var rv = document.getElementById('radius-value');
  if(typeof saved.radius === 'number' && rv){
    var r = Math.max(RADIUS_MIN, Math.min(RADIUS_MAX, saved.radius));
    rv.textContent = r + 'px';
  }
  THEME = readThemeControl();
  themeDirty = true;
  try{
    var m = getComputedStyle(document.documentElement).getPropertyValue('--muted').trim();
    if(m){ THEME_MUTED = m; }
  }catch(e){}
  applyTheme();
}
function themeReset(){
  THEME = readThemeControl();
  syncPresetSelect();
  themeDirty = true;
  applyTheme(); saveTheme(); refresh();
}
function syncPresetSelect(){
  var sel = document.getElementById('theme-preset');
  if(!sel) return;
  var match = '';
  outer:
  for(var key in PRESETS){
    var p = PRESETS[key], hit = true;
    for(var k in p){ if(THEME[k] !== p[k]){ hit = false; break; } }
    if(hit){ match = key; break outer; }
  }
  sel.value = match;
}
function applyPreset(key){
  var p = PRESETS[key];
  if(!p) return;
  function setC(id, v){ var el = document.getElementById(id); if(el) el.value = v; }
  if(p.accent)     setC('theme-accent', p.accent);
  if(p.accent2)    setC('theme-accent2', p.accent2);
  if(p.background) setC('theme-bg', p.background);
  if(p.card)       setC('theme-card', p.card);
  if(p.text)       setC('theme-text', p.text);
  if(p.font){
    var f = document.getElementById('theme-font');
    if(f){ f.value = p.font; }
  }
  if(typeof p.radius === 'number'){
    var rv = document.getElementById('radius-value');
    var r = Math.max(RADIUS_MIN, Math.min(RADIUS_MAX, p.radius));
    if(rv) rv.textContent = r + 'px';
  }
  THEME = readThemeControl();
  startFX(p.effect);
  themeDirty = true;
  applyTheme(); saveTheme(); refresh();
}
function bumpFontSize(delta){
  THEME.fontsize = Math.max(FONT_MIN, Math.min(FONT_MAX, THEME.fontsize + delta));
  document.getElementById('fs-value').textContent = THEME.fontsize + 'px';
  themeDirty = true;
  applyTheme(); saveTheme(); refresh();
}
function bumpRadius(delta){
  THEME.radius = Math.max(RADIUS_MIN, Math.min(RADIUS_MAX, THEME.radius + delta));
  document.getElementById('radius-value').textContent = THEME.radius + 'px';
  themeDirty = true;
  applyTheme(); saveTheme(); refresh();
}

/* ---- Theme FX: rainbow / swap / flicker + confetti blast ---- */
var FX = {raf:null, mode:null, swap:false, flip:false};
var RAINBOW = ['#ff3b30','#ff9500','#ffcc00','#34c759','#32ade6','#5e5ce6','#bf5af2'];
var rAF = window.requestAnimationFrame || function(f){ return setTimeout(f,16); };
var cAF = window.cancelAnimationFrame || function(id){ clearTimeout(id); };

function stopFX(){
  if(FX.raf){ cAF(FX.raf); FX.raf = null; }
  FX.mode = null;
  document.documentElement.classList.remove('fx-flicker');
}
function rainbowTick(ts){
  // Smooth continuous drift around the hue wheel instead of hard color steps.
  // Hue advances ~9 deg/sec; lightness breathes on a slow sine so the wheel
  // feels organic (like an aurora), not a flipping poster.
  var t = ts / 1000;
  var secondsForWheel = 10;               // full 360deg in 10s
  var h = (t * 360 / secondsForWheel) % 360;
  var breathe = 0.5 + 0.5 * Math.sin(t * 2 * Math.PI / 5.75); // ~5.75s breathing cycle (scales with wheel speed)
  var l1 = 58 + 6 * breathe;              // primary: 52..64% lightness
  var l2 = 66 + 8 * breathe;              // secondary rides slightly lighter
  var sat = 78 + 10 * breathe;
  var h2 = (h + 28) % 360;                // gentle analogous offset, not opposite
  var el = document.documentElement;
  var c1 = 'hsl(' + h.toFixed(1) + ',' + sat.toFixed(1) + '%,' + l1.toFixed(1) + '%)';
  var c2 = 'hsl(' + h2.toFixed(1) + ',' + sat.toFixed(1) + '%,' + l2.toFixed(1) + '%)';
  el.style.setProperty('--accent', c1);
  el.style.setProperty('--accent2', c2);
  el.style.setProperty('--glow',
    '0 0 0 1px ' + hsla(h, sat, l1, .4) + ',0 8px 22px -6px ' + hsla(h, sat, l1, .35));
  FX.raf = rAF(rainbowTick);
}
function hsla(h, s, l, a){
  return 'hsla(' + h.toFixed(1) + ',' + s.toFixed(1) + '%,' + l.toFixed(1) + '%,' + a + ')';
}
function hexA(hex, a){
  var n = parseInt(hex.slice(1), 16);
  return 'rgba(' + ((n>>16)&255) + ',' + ((n>>8)&255) + ',' + (n&255) + ',' + a + ')';
}
function startFX(mode){
  stopFX();
  if(!mode || mode === 'none') return;
  FX.mode = mode;
  if(mode === 'rainbow'){
    FX.raf = rAF(function loop(t){ rainbowTick(t); });
  } else if(mode === 'flicker'){
    document.documentElement.classList.add('fx-flicker');
  }
}
/* ---- Confetti: pixel-art squares on the canvas overlay ---- */
var CONFETTI_COLORS = ['#ff3b30','#ff9500','#ffcc00','#34c759','#32ade6','#5e5ce6','#bf5af2','#ff8fab'];
var cv = null, cx = null, confetti = null;
function ensureCanvas(){
  if(cv) return;
  cv = document.createElement('canvas');
  cv.id = 'confetti-canvas';
  cv.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:999';
  document.body.appendChild(cv);
  cx = cv.getContext('2d');
  confetti = [];
  function size(){ cv.width = innerWidth; cv.height = innerHeight; }
  size();
  window.addEventListener('resize', size);
}
function burstConfetti(x, y){
  try{ ensureCanvas(); }catch(e){ return; }
  for(var i=0;i<80;i++){
    confetti.push({
      x:x, y:y,
      vx:(Math.random()-0.5)*11,
      vy:-4-Math.random()*8,
      g:0.22+Math.random()*0.12,
      s:3+Math.random()*5|0,
      rot:Math.random()*Math.PI, vr:(Math.random()-.5)*.25,
      life:70+Math.random()*50|0,
      col:CONFETTI_COLORS[Math.random()*CONFETTI_COLORS.length|0]
    });
  }
  if(!confetti._running){ confetti._running = true; confettiTick(); }
}
function confettiTick(){
  cx.clearRect(0, 0, cv.width, cv.height);
  var alive = [];
  for(var i=0;i<confetti.length;i++){
    var p = confetti[i];
    p.vy += p.g; p.x += p.vx; p.y += p.vy; p.rot += p.vr; p.life--;
    if(p.life > 0 && p.y < cv.height + 20){
      cx.save();
      cx.translate(p.x, p.y);
      cx.rotate(p.rot);
      // pixel-art snap: integer coords, flat squares, no anti-alias glow
      cx.fillStyle = p.col;
      cx.globalAlpha = Math.min(1, p.life/30);
      cx.fillRect(Math.round(-p.s/2), Math.round(-p.s/2), p.s, p.s);
      cx.restore();
      alive.push(p);
    }
  }
  confetti = alive;
  if(confetti.length){ rAF(confettiTick); }
  else { confetti._running = false; cx.clearRect(0,0,cv.width,cv.height); }
}
(function(){
  ['theme-accent','theme-accent2','theme-bg','theme-card','theme-text'].forEach(function(id){
    var el = document.getElementById(id);
    if(el) el.addEventListener('input', themeReset);
  });
  var f = document.getElementById('theme-font');
  if(f) f.addEventListener('change', themeReset);
  var presetSel = document.getElementById('theme-preset');
  if(presetSel) presetSel.addEventListener('change', function(){ applyPreset(this.value); });
  var minus = document.getElementById('font-minus');
  var plus  = document.getElementById('font-plus');
  if(minus) minus.addEventListener('click', function(){ bumpFontSize(-1); });
  if(plus)  plus.addEventListener('click',  function(){ bumpFontSize(+1); });
  var rminus = document.getElementById('radius-minus');
  var rplus  = document.getElementById('radius-plus');
  if(rminus) rminus.addEventListener('click', function(){ bumpRadius(-1); });
  if(rplus)  rplus.addEventListener('click',  function(){ bumpRadius(+1); });
  try{ loadSavedTheme(); }catch(e){}
  startFX(THEME.effect || 'none');
})();

function allInputs(scope){ return Array.prototype.slice.call((scope||document).querySelectorAll('input,textarea')); }

function valueOf(ctrl){
  if(ctrl.type==='radio') return ctrl.checked ? ctrl.value : null;
  if(ctrl.type==='checkbox') return !!ctrl.checked;
  return ctrl.value;
}

function collect(){
  var res = {title:SPEC.title, global_notes:'', categories:[]};
  if(SPEC.theme || themeDirty){
    res.theme = {accent:THEME.accent, accent2:THEME.accent2,
                 font:THEME.font, fontsize:THEME.fontsize,
                 background:THEME.background, card:THEME.card,
                 text:THEME.text, muted:THEME_MUTED, radius:THEME.radius};
  }
  SPEC.categories.forEach(function(cat){
    var cj = {id:cat.id, name:cat.name, goal:(cat.goal||''), items:[]};
    (cat.items||[]).forEach(function(it){
      var item = {id:it.id, text:it.text, notes:'', options:{}};
      var holder = document.querySelector('.item[data-item="' + it.id + '"]');
      if(!holder) return;
      var note = holder.querySelector('.note');
      if(note) item.notes = note.value;
      (Object.keys(it.options||{})).forEach(function(k){
        var field = it.id + '--' + k;
        var radios = holder.querySelectorAll('input[name="opt-' + field + '"]');
        if(radios.length){
          var chosen = null;
          for(var i=0;i<radios.length;i++){ if(radios[i].checked){chosen=radios[i].value;break;} }
          item.options[k] = chosen;
        } else {
          var ctl = holder.querySelector('input[name="opt-' + field + '"]');
          if(ctl) item.options[k] = valueOf(ctl);
        }
      });
      cj.items.push(item);
    });
    res.categories.push(cj);
  });
  var glo = document.getElementById('global-notes');
  if(glo) res.global_notes = glo.value;
  if(SPEC.config) res.config = SPEC.config;
  if(SPEC.passdown) res.passdown = SPEC.passdown;
  return res;
}

function updateProgress(){
  var done = document.querySelectorAll('input.done:checked').length;
  var total = document.querySelectorAll('input.done').length;
  var lab = document.getElementById('proglabel'); var bar=document.getElementById('progbar');
  var pct = total? Math.round(done/total*100):0;
  if(lab) lab.textContent = done + ' of ' + total + ' done';
  if(bar) bar.style.width = pct + '%';
}
function updatePassdown(){
  var pd = SPEC.passdown || {};
  if(pd.mode !== 'strict'){ return; }
  var fail = 0;
  SPEC.categories.forEach(function(cat){
    var sec = document.querySelector('.cat[data-cat="' + cat.id + '"]');
    if(!sec) return;
    var els = sec.querySelectorAll('input.done');
    var done = 0, i;
    for(i=0;i<els.length;i++){ if(els[i].checked) done++; }
    var skipped = sec.classList.contains('passdown-skipped');
    var chip = sec.querySelector('.completion-chip');
    if(chip){
      if(skipped){ chip.textContent = 'skipped'; chip.classList.remove('done'); }
      else{
        chip.textContent = done + '/' + els.length;
        chip.classList.toggle('done', els.length > 0 && done === els.length);
      }
    }
    if(!skipped){ fail += (els.length - done); }
  });
  var warn = document.getElementById('passdown-warn');
  if(warn){
    if(fail > 0){
      warn.textContent = fail + ' item' + (fail > 1 ? 's' : '') +
        ' left unanswered - complete every scoped item before exporting/passing back the results.';
      warn.hidden = false;
    } else {
      warn.hidden = true;
    }
  }
}
function refresh(){
  var ta = document.getElementById('results-json');
  if(ta){ ta.value = JSON.stringify(collect(), null, 2); }
  updateProgress();
  updatePassdown();
}

document.addEventListener('input', function(e){
  var t=e.target;
  if(t && t.classList && t.classList.contains('done')){
    var lv = t.closest('.item-top');
    if(lv) lv.closest('.item').classList.toggle('doneoff', t.checked);
    if(t.checked){
      var r = t.getBoundingClientRect();
      burstConfetti(r.left + r.width/2, r.top + r.height/2);
    }
  }
  if(t && t.closest && t.closest('.cats')){
    // celebratory blast when a status pill is set to a positive choice
    if(t.type === 'radio' && /^(works|pass|done|ok|yes)$/i.test(t.value)){
      var pr = t.getBoundingClientRect();
      burstConfetti(pr.left + pr.width/2, pr.top + pr.height/2);
    }
    refresh();
  }
});
document.addEventListener('change', refresh);

document.querySelectorAll('button.cat-head').forEach(function(h){
  h.addEventListener('click', function(){
    var sec = h.closest('.cat'); sec.classList.toggle('collapsed');
  });
});

document.getElementById('copybtn').addEventListener('click', function(){
  var ta = document.getElementById('results-json');
  refresh();
  ta.select(); ta.setSelectionRange(0, ta.value.length);
  try{ document.execCommand('copy'); this.textContent='Copied ✓'; }
  catch(e){ this.textContent='Select & copy'; }
  var b=this; setTimeout(function(){ b.textContent='Copy results'; }, 1200);
});

function openDrawer(){
  document.getElementById('drawer').classList.add('open');
  document.getElementById('scrim').classList.add('show');
}
function closeDrawer(){
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('scrim').classList.remove('show');
}
document.getElementById('drawerbtn').addEventListener('click', openDrawer);
document.getElementById('drawerclose').addEventListener('click', closeDrawer);
document.getElementById('scrim').addEventListener('click', closeDrawer);

(function(){
  var sb = document.getElementById('sendbtn');
  if(!sb || !AGENT || !AGENT.webhook_url) return;
  var status = document.getElementById('send-status');
  var timeoutMs = (typeof AGENT.timeout_ms === 'number' && AGENT.timeout_ms > 0)
    ? AGENT.timeout_ms : 10000;
  function post(attempt){
    var ctrl = new AbortController();
    var timer = setTimeout(function(){ ctrl.abort(); }, timeoutMs);
    sb.disabled = true;
    status.textContent = (attempt > 1) ? 'Retrying…' : 'Sending…';
    status.className = 'sendstatus';
    /* The POST body is exactly the collected canonical results JSON
       (no timestamp field — determinism save). */
    return fetch(AGENT.webhook_url, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: document.getElementById('results-json').value,
      signal: ctrl.signal
    }).then(function(r){
      clearTimeout(timer);
      if(!r.ok) throw new Error('HTTP ' + r.status);
      sb.disabled = false;
      status.textContent = 'Sent ✓';
      status.className = 'sendstatus ok';
    }).catch(function(e){
      clearTimeout(timer);
      var aborted = !!(e && e.name === 'AbortError');
      if(attempt === 1 && !aborted){
        return post(2); /* retry once automatically on network error */
      }
      sb.disabled = false;
      var reason = aborted
        ? 'request timed out after ' + timeoutMs + 'ms'
        : (e && e.message) ? e.message : String(e);
      status.textContent = 'Failed: ' + reason;
      status.className = 'sendstatus err';
    });
  }
  sb.addEventListener('click', function(){ refresh(); post(1); });
})();

refresh();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()