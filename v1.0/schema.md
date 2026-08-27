# CHECKLST v1.0 — Spec Schema Reference

This document is the canonical, human-readable reference for the CHECKLST
v1.0 specification and its round-trip results contract. It ships with the
public repo. `checklst.py` (stdlib-only) implements `new`, `render`, `parse`,
and `passdown` exactly as described here. All HTML/JS/CSS the tool emits is
vanilla and dependency-free.

---

## 1. Top-level document

A spec is a single JSON document with these fields.

| Field          | Type     | Required | Default        | Description                                        |
|----------------|----------|----------|----------------|----------------------------------------------------|
| `title`        | string   | no*      | `"Checklist"` | Checklist title shown in the page header.          |
| `categories`   | array    | yes      | `[]`           | Ordered list of category objects (see §3).        |
| `theme`        | object   | no       | built-in dark  | Optional theming block (see §5).                  |
| `agent`        | object   | no       | none           | Optional send-to-webhook block (see §6).          |
| `config`       | object   | no       | `{}`           | Optional capability gate (see §1.2).              |

\* `title` is emitted anyway when absent (`render` falls back to
`"Checklist"`, and results always carry `title`). `theme` and `agent` are
purely optional and, when absent, the built-in defaults/buttons are used.
`config` defaults to `{}` and only gates the **passdown** subcommand.

### 1.2 `config` and the `passdown` subcommand

The top-level `config` object is a capability gate = only one key today:

| Key               | Type | Required | Default | Description                                          |
|-------------------|------|----------|---------|------------------------------------------------------|
| `allow_passdown`  | bool | no       | `false` | When `true`, the spec may be handed to a subagent via the `passdown` CLI. |

```json
"config": { "allow_passdown": true }
```

If a spec does **not** set `config.allow_passdown` to `true`, the
`passdown` subcommand refuses with exit code **1** and the message
`spec locked by author`. This lets an author lock a checklist against
delegation.

**When allowed**, `passdown` renders the same HTML as `render` except it
embeds a `passdown` metadata block inside the spec JSON and shows a header
banner "Passdown from X -> Y | mission". The embedded block is:

```json
"passdown": {
  "from": "orchestrator",      // --from, else "orchestrator"
  "to": "bob",                 // --agent (required)
  "mission": "check the build",// --mission
  "scope": ["a"],              // --scope cat1,cat2
  "mode": "strict"             // strict is the only mode today
}
```

- When `--scope` is given, categories whose id is **not** in the scope render
  collapsed with class `passdown-skipped` and every one of their controls
  (radio / checkbox / text / note) is disabled.
- In `strict` mode (always), each section header carries a per-category
  completion chip (`n/m`), and an amber warning banner appears once any
  scoped item is left unanswered before the results are exported.

A spec that already carries a `passdown` key (e.g. authored directly) renders
the same way; the `--from/--agent/--mission/--scope` flags that bake into the
`passdown` block at pass-down time are what a page-runs subagent reads.

`config` and `passdown` are preserved as **metadata keys** in the canonical
results document (see §6) so the delegate's answer carries the delegation
context back to the orchestrator.

### 1.1 Results document (round-trip form)

A *filled results* document — what the rendered page collects, what
`build_results()` produces, and what `parse()` emits — is always canonical:

```json
{
  "title": "Release Acceptance Checklist",
  "global_notes": "",
  "categories": [
    { "id": "build", "name": "Build & Deployment", "goal": "",
      "items": [
        { "id": "build-clean", "text": "...", "options": {...}, "notes": "" }
      ]
    }
  ]
}
```

Fields in the results document:

| Field          | Type   | Notes                                                        |
|----------------|--------|--------------------------------------------------------------|
| `title`      | string | Copied from the spec (default `""` if absent).               |
| `global_notes`| string | Free-form checklist-wide notes captured in the page.        |
| `categories`  | array  | Categories and items in **spec order** (see §2).            |

---

## 2. Category

```json
{
  "id": "build",
  "name": "Build & Deployment",
  "goal": "The artifact builds cleanly.",
  "collapsed_default": false,
  "items": [ ... ]
}
```

| Field               | Type   | Required | Default | Description                                       |
|---------------------|--------|----------|---------|---------------------------------------------------|
| `id`              | string | yes      | —       | Stable identifier; used as the HTML `data-cat`.   |
| `name`            | string | yes      | `""`      | Display name in the category header.              |
| `goal`            | string | optional | `""`    | Optional subtitle shown under the category title. |
| `collapsed_default`| bool   | optional | `false` | Start the category collapsed (hidden items).       |
| `items`           | array | yes | `[]` | Item objects (see §3).                          |

---

## 3. Item

```json
{
  "id": "qa-login",
  "text": "Login flow works for a valid user",
  "notes": "Record the account used.",
  "options": { ... }
}
```

| Field     | Type   | Required | Default | Description                                      |
|-----------|--------|----------|---------|--------------------------------------------------|
| `id`      | string | yes | —       | Stable identifier; used in option input `name=`s. |
| `text`    | string | yes | `""`    | The checkable statement shown to the user.        |
| `notes`   | string | no | `""`    | Free-form note captured per item.                 |
| `options` | object | yes*    | `{}`      | `option-name -> option-body` map (see §3.1).    |

\* `options` may be `{}` (no knobs); when absent it is treated as empty.

### 3.1 Option

An item's `options` is an **arbitrary** dict whose keys are option names and
whose values are option bodies:

```json
"options": {
  "status": {
    "value": "Works",
    "description": "Does this item work, fail, or is it broken?",
    "choices": ["Works", "Doesn't", "Bugged"]
  },
  "deploy_risk": {
    "value": "low",
    "choices": [
      { "value": "low",    "color": "#3fb950" },
      { "value": "medium", "color": "#d29922" },
      { "value": "high",   "color": "#f85149" }
    ]
  }
}
```

| Option key   | Type                    | Required | Description                                        |
|--------------|-------------------------|----------|----------------------------------------------------|
| `value`      | bool \| string (any)   | yes | The option's default value. Pre-filled in results. |
| `description`| string                 | no      | Tooltip on the rendered label.                      |
| `choices`    | array of string \| object | no      | If present => segmented "pill" radio; else see below. |

**Choice entries** may each be either:

- a plain **string** — the radio value and label; or
- an **object** `{ "value": str, "color": "#hex" }` — a colored pill. The
  stored value is the plain `value` string; `color` is only a rendering hint
  that recolors the selected pill.

**Widget selection (no hardcoded semantics anywhere):**

| option shape                    | control         |
|---------------------------------|-----------------|
| `choices` list present          | segmented pill (radio) group |
| `value` is a Python `bool`      | checkbox toggle |
| anything else                   | free-text input |

The built-in `status` preset (Works / Doesn't / Bugged) is **nothing special**:
it is just an ordinary option with a plain-string `choices` list. Any user can
define their own status option with custom colored choices using the object
form above. There is no `status`-aware code in the renderer — the name is only
a convention and is fully arbitrary.

---

## 4. theme (optional)

```json
"theme": {
  "accent":     "#2dd4bf",
  "accent2":    "#34d399",
  "font":       "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif",
  "fontsize":   16,
  "background": "#0b0f14",
  "card":       "#151d28",
  "text":       "#e7eef4",
  "muted":      "#8fa3b8",
  "radius":     "14px"
}
```

The default renderer ships a deep, layered ember-ink dark palette with a
characterful **warm-teal → spring-emerald** accent pair
(`--accent:#2dd4bf` / `--accent2:#34d399`). All fields below override those
defaults; the ambient background glow, focus rings, and shadows are all
derived from `--accent`/`--accent2`/`--bg2` via `color-mix()`, so a user theme
override restyles the whole page (not just the buttons).

| Field        | Type        | Default        | CSS variable  | Description                                  |
|--------------|-------------|----------------|---------------|----------------------------------------------|
| `accent`     | `#hex`      | `#2dd4bf`      | `--accent`    | Primary accent (gradient start).             |
| `accent2`    | `#hex`      | `#34d399`      | `--accent2`   | Secondary accent (gradient end).             |
| `font`       | `css font-family` | system UI stack | `--font` | Page font stack.                             |
| `fontsize`   | px number   | `16`           | `--fontsize`  | Base root font size in px.                   |
| `background` | `#hex`      | `#0b0f14`      | `--bg`        | Page background color.                       |
| `card`       | `#hex`      | `#151d28`      | `--card`      | Card / panel background color.               |
| `text`       | `#hex`      | `#e7eef4`      | `--txt`        | Primary text color.                          |
| `muted`      | `#hex`      | `#8fa3b8`      | `--muted`     | Secondary/muted text color.                  |
| `radius`     | css length  | `14px`         | `--radius`    | Corner radius of cards/panels (a bare number is treated as px). |

All fields are optional and are injected as CSS variables on `:root` — an
absent theme (or any absent subfield) leaves the built-in dark defaults
unchanged. `fontsize` and `radius` drive the corresponding controls in the
Customize panel. The legacy `font_size` alias is still accepted for
`fontsize`. Every customized value is persisted to `localStorage` and rides
along in the results document (`res.theme`) on export and send.

---

## 5. agent (optional) and the CORS note

```json
"agent": {
  "webhook_url": "https://example.com/hook",
  "name": "QA bot",
  "timeout_ms": 10000
}
```

| Field         | Type   | Required | Default | Description                                                              |
|---------------|--------|----------|---------|--------------------------------------------------------------------------|
| `webhook_url` | string | yes      | —       | Endpoint receiving the results JSON. When empty/absent, no send button renders. |
| `name`        | string | no       | `agent` | Button label: **Send to `<name>`**.                                      |
| `timeout_ms`  | int    | no       | `10000` | Max request time in ms; the POST aborts past this and is reported as a timeout. |

When `agent.webhook_url` is present, a **Send to <name>** button appears in
the results drawer. Clicking it `POST`s the **collected canonical results
JSON** (the same payload shown in the drawer — and the same object
`build_results()`/`parse()` produce — including `theme` when customized) via
`fetch` with `Content-Type: application/json` and shows an inline status line.

**Send contract.** The *agent* listens on `webhook_url`: it receives the
results JSON as the POST request body and should respond with any **2xx**
status. There is **no `sent_at` / timestamp field** — the renderer is
byte-deterministic and never stamps the payload (the sha256 of the rendered
HTML — and the collected JSON — is stable across runs).

**Reliability.** The request runs through an `AbortController`; if it does not
complete within `timeout_ms` it is aborted and reported as `Failed: request
timed out after <n>ms`. A transient network error is **retried once**
automatically before a failure is shown. The button is disabled while the
request is in flight; the final status reads `Sent ✓` on success or
`Failed: <reason>` otherwise.

**CORS note.** Opened from `file://`, the browser origin is `null`, so the
webhook server must respond with permissive CORS headers (e.g.
`Access-Control-Allow-Origin: *`) or the POST is blocked and the drawer shows
an error. This is a browser security constraint, not a bug.

---

## 6. Round-trip contract (locked)

1. **Deterministic render.** `render(spec)` always produces **byte-identical**
   HTML for the same spec — no timestamps, random ids, or date strings. The
   `sha256` of the output is stable across runs.
2. **Canonical `parse`.** `parse(results)` emits:
   `{ title, global_notes, categories: [ {id, name, goal, items:
   [ {id, text, options: {…}, notes} ] } ] }` — keys in **spec order**
   (categories then items in definition order; options in option-name order).
   `theme`, and — when present — `config` and `passdown`, are echoed as
   metadata keys; any other unexpected top-level key is ignored.
3. **Defaults included consistently.** `build_results()` pre-fills every option
   with its spec default; `parse()` preserves whatever the results contain —
   nothing is dropped, nothing is defaulted-out.
4. **Round-trip property.** For any valid spec `S`:

   ```
   parse(build_results(S))  deep-equals  build_results(S)
   ```

   This is asserted in `v1.0/test_golden.py` over three specs: the fixed golden
   spec, `examples/demo.checklist.json`, and a synthetic spec exercising bool /
   text / colored choice options, notes, goal, collapsed-default and theme+agent
   blocks.

---

## 7. Preset — the `status` option

The starter spec (`checklst new`) includes this option on every item. It is a
plain preset, documented here for convenience — nothing in the renderer treats
it specially.

```json
"status": {
  "value": "Works",
  "description": "Does this item work, fail, or is it broken/bugged?",
  "choices": [
    "Works",
    "Doesn't",
    "Bugged"
  ]
}
```

For colored pills, use the object form:

```json
"status": {
  "value": "pass",
  "choices": [
    { "value": "pass", "color": "#3fb950" },
    { "value": "fail", "color": "#f85149" }
  ]
}
```

---

## 8. CLI

```
checklst new    <path>         emit a starter spec JSON file (default: examples/demo.checklist.json)
checklst render <spec>          render a spec to standalone dark HTML (stdout)
checklst parse  <results>       normalize filled results to canonical round-trip JSON (stdout)
checklst passdown <spec> --agent NAME [--mission TEXT] [--scope c1,c2] [-o out.html] [--from NAME]
                                render a spec as a subagent pass-down (needs config.allow_passdown=true; exits 1 if locked)
```