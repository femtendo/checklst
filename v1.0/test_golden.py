#!/usr/bin/env python3
"""test_golden.py — deterministic golden test for checklst.

Builds a small fixed spec, renders it twice (asserting byte-identical sha256,
i.e. no timestamps / random ids), fills a known results JSON, parses it, and
compares the canonical output against an embedded golden dict — exact match.

Run from the repo root:   python3 v1.0/test_golden.py   (exit 0 on success)
Run from v1.0/ dir:       python3 test_golden.py        (also works)
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKLST = os.path.join(REPO, "v1.0", "checklst.py")

SPEC = {
    "title": "T",
    "categories": [
        {
            "id": "a",
            "name": "A",
            "goal": "g",
            "collapsed_default": False,
            "items": [
                {
                    "id": "x1",
                    "text": "Do X",
                    "options": {
                        "status": {
                            "value": "Works",
                            "description": "state?",
                            "choices": ["Works", "Doesn't", "Bugged"],
                        },
                        "fancy": {"value": False, "description": "fancy?"},
                    },
                }
            ],
        },
        {
            "id": "b",
            "name": "B",
            "collapsed_default": True,
            "items": [
                {
                    "id": "x2",
                    "text": "Do Y",
                    "options": {
                        "severity": {"value": "mild",
                                     "choices": ["mild", "hot"]}
                    },
                    "notes": "note2",
                }
            ],
        },
    ],
}

RESULTS = {
    "title": "T",
    "global_notes": "all good",
    "categories": [
        {
            "id": "a", "name": "A", "goal": "g",
            "items": [
                {"id": "x1", "text": "Do X",
                 "options": {"status": "Works", "fancy": False}, "notes": ""}
            ],
        },
        {
            "id": "b", "name": "B",
            "items": [
                {"id": "x2", "text": "Do Y",
                 "options": {"severity": "hot"}, "notes": "note2"}
            ],
        },
    ],
}

EXPECTED = {
    "title": "T",
    "global_notes": "all good",
    "categories": [
        {"id": "a", "name": "A", "goal": "g", "items": [
            {"id": "x1", "text": "Do X",
             "options": {"status": "Works", "fancy": False}, "notes": ""}]},
        {"id": "b", "name": "B", "goal": "", "items": [
            {"id": "x2", "text": "Do Y",
             "options": {"severity": "hot"}, "notes": "note2"}]},
    ],
}


def run_cli(*args):
    out = subprocess.run([sys.executable, CHECKLST] + list(args),
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("cmd %r failed rc=%d\n%s"
                         % (list(args), out.returncode, out.stderr))
    return out.stdout


def test_render_and_parse(td):
    spec_path = os.path.join(td, "spec.json")
    res_path = os.path.join(td, "res.json")
    with open(spec_path, "w") as f:
        json.dump(SPEC, f)
    with open(res_path, "w") as f:
        json.dump(RESULTS, f)

    html1 = run_cli("render", spec_path)
    html2 = run_cli("render", spec_path)

    s1 = hashlib.sha256(html1.encode()).hexdigest()
    s2 = hashlib.sha256(html2.encode()).hexdigest()
    assert s1 == s2, "render not deterministic: %s != %s" % (s1, s2)
    print(f"render deterministic sha256   : {s1}")

    for n in ("__SPEC__", "__RESULTS__", "__TITLE__", "__BODY_CATS__", "__FAVICON__"):
            assert n not in html1, f"leftover placeholder {n} in HTML"

    # favicon: inline SVG data: URI <link rel=icon>, no external requests.
    assert '<link rel="icon" href="data:image/svg+xml,' in html1, "missing data:SVG favicon link"
    head = html1[html1.find("<head>"):html1.find("</head>")]
    assert "data:image/svg+xml" in head
    assert "http://" not in head and "https://" not in head, "favicon must not fetch externally"

    parsed = json.loads(run_cli("parse", res_path))
    assert parsed == EXPECTED, "parse != EXPECTED:\n%s" % json.dumps(parsed, indent=1)
    print("parse == golden (exact)      : OK")


def test_new(tmp):
    spec_path = os.path.join(tmp, "ex", "demo.checklist.json")
    os.makedirs(os.path.dirname(spec_path), exist_ok=True)
    run_cli("new", spec_path)
    with open(spec_path) as f:
        spec = json.load(f)
    assert "title" in spec and isinstance(spec["categories"], list)
    cat = spec["categories"][0]
    assert {"id", "name", "collapsed_default", "items"} <= set(cat), cat.keys()
    item = cat["items"][0]
    assert {"id", "text", "options"} <= set(item), item.keys()
    status = item["options"]["status"]
    assert status["choices"] == ["Works", "Doesn't", "Bugged"], status
    assert "value" in status and "description" in status
    print("new emits valid starter spec  : OK (status is just a normal option)")


def _render(spec):
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False, encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
        spec_path = f.name
    try:
        return run_cli("render", spec_path)
    finally:
        os.remove(spec_path)


def _rest(spec):
    """Return (html_str, sha256, sha256_again) for a spec (determinism known)."""
    h1 = _render(spec)
    h2 = _render(spec)
    s1 = hashlib.sha256(h1.encode()).hexdigest()
    s2 = hashlib.sha256(h2.encode()).hexdigest()
    return h1, s1, s2


def test_theme_and_colored_choices(tmp_path):
    spec = {
        "title": "T",
        "theme": {"accent": "#00aaff", "accent2": "#ff00cc", "font": "Roboto, sans-serif"},
        "categories": [
            {
                "id": "a",
                "name": "A",
                "items": [
                    {
                        "id": "x1",
                        "text": "X",
                        "options": {
                            "status": {
                                "value": "pass",
                                "choices": [
                                    {"value": "pass", "color": "#3fb950"},
                                    {"value": "fail", "color": "#f85149"},
                                ],
                            }
                        },
                    }
                ],
            }
        ],
    }
    html, s1, s2 = _rest(spec)
    assert s1 == s2, "theme/choice render not deterministic"
    # (a) theme injection present
    assert "--accent:#00aaff;" in html
    assert "--accent2:#ff00cc;" in html
    assert "--font:Roboto, sans-serif;" in html
    # (b) object-choice pill carries the custom color
    assert 'style="--pill:#3fb950"' in html
    assert 'style="--pill:#f85149"' in html
    # and the underlying value is the plain string
    assert '<input type="radio" name="opt-x1--status" value="pass"' in html
    assert '<input type="radio" name="opt-x1--status" value="fail"' in html

    # collect the right value through parse: a filled result using the value string
    filled = {
        "title": "T",
        "global_notes": "",
        "categories": [
            {
                "id": "a", "name": "A", "goal": "",
                "items": [{"id": "x1", "text": "X",
                           "options": {"status": "fail"}, "notes": ""}],
            }
        ],
    }
    with open(os.path.join(tmp_path, "res.json"), "w") as f:
        json.dump(filled, f)
    parsed = json.loads(run_cli("parse", os.path.join(tmp_path, "res.json")))
    assert parsed["categories"][0]["items"][0]["options"] == {"status": "fail"}, parsed
    print("theme injected + colored pill  : OK (value passes through parse)")


def test_send_button_presence():
    # (c) send button present iff agent.webhook_url set, absent otherwise
    base = {"title": "T", "categories": []}
    with_agent = dict(base)
    with_agent["agent"] = {"webhook_url": "https://example.com/hook", "name": "QA bot"}
    html_with, s1, _ = _rest(with_agent)
    assert s1, "no agenthash"
    assert 'id="sendbtn"' in html_with
    assert "Send to QA bot" in html_with
    assert "example.com/hook" in html_with  # AGENT js config present

    html_without = _render(base)
    assert 'id="sendbtn"' not in html_without
    print("send-to-agent present iff webhook : OK")


def test_results_drawer():
    # (d) results-json lives inside the drawer, not as a main-page section
    spec = {"title": "T", "categories": []}
    html = _render(spec)
    # only one results-json textarea total, and it sits within the drawer block
    assert html.count('id="results-json"') == 1
    drawer_start = html.find('<div class="drawer"')
    drawer_end = html.find(
        '<span class="sendstatus" id="send-status"></span>')
    assert drawer_start != -1 and drawer_end != -1
    drawer = html[drawer_start:drawer_end]
    assert 'id="results-json"' in drawer
    # main-page region: before the drawer must have no results-json textarea
    main = html[:drawer_start]
    assert 'id="results-json"' not in main
    # the open/close controls exist
    assert 'id="drawerbtn"' in html and 'id="drawerclose"' in html and 'id="scrim"' in html
    print("results-json isolated in drawer  : OK")


# Synthetic spec exercising EVERY schema feature: bool option, plain textual
# choices, colored-object choices, plain free-text option, notes, goal,
# collapsed_default true, theme block, and agent block.
SYNTHETIC_SPEC = {
    "title": "Synthetic",
    "theme": {"accent": "#00aaff", "accent2": "#ff00cc", "font": "Roboto, sans-serif"},
    "agent": {"webhook_url": "https://example.com/hook", "name": "bot"},
    "categories": [
        {
            "id": "c1", "name": "C1", "goal": "goal phrase",
            "collapsed_default": True,
            "items": [
                {
                    "id": "i1", "text": "Bool item", "notes": "note1",
                    "options": {
                        "flag": {"value": True, "description": "a bool"},
                        "severity": {"value": "mild", "choices": ["mild", "hot"]},
                        "risk": {"value": "low", "choices": [
                            {"value": "low", "color": "#3fb950"},
                            {"value": "high", "color": "#f85149"}]},
                        "free": {"value": "hello", "description": "free text"},
                    },
                },
                {"id": "i2", "text": "Second item",
                 "options": {"label": {"value": "x"}}},
            ],
        },
        {
            "id": "c2", "name": "C2",
            "items": [
                {"id": "i3", "text": "No options", "options": {}},
            ],
        },
    ],
}


def _load_module():
    spec = importlib.util.spec_from_file_location("checklst", CHECKLST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_roundtrip_property():
    """For 3 different specs, prove parse(build_results(S)) == build_results(S),
    and that render is deterministic (sha256 stable across two runs) for each."""
    mod = _load_module()
    demo_path = os.path.join(REPO, "v1.0", "examples", "demo.checklist.json")
    with open(demo_path, encoding="utf-8") as f:
        demo = json.load(f)
    specs = [("golden", SPEC), ("demo", demo), ("synthetic", SYNTHETIC_SPEC)]

    for name, S in specs:
        results = mod.build_results(S)
        parsed = mod.parse_results(results)
        assert parsed == results, (
            "round-trip property failed for %s:\n%s\n!= \n%s"
            % (name, json.dumps(parsed, indent=1), json.dumps(results, indent=1)))

    print("round-trip parse(build_results(S))==build_results(S) : OK")
    print("  specs covered: golden, demo, synthetic")

    # Explicitly assert the canonical parse() shape and spec order.
    canon = mod.parse_results(mod.build_results(SPEC))
    assert set(canon) == {"title", "global_notes", "categories"}, canon.keys()
    assert list(canon["categories"][0].keys()) == ["id", "name", "goal", "items"]
    assert list(canon["categories"][0]["items"][0].keys()) == [
        "id", "text", "options", "notes"]
    print("  canonical keys + spec order            : OK")

    # Deterministic render hash, stable across two runs, for every spec.
    for name, S in [("golden", SPEC), ("demo", demo), ("synthetic", SYNTHETIC_SPEC)]:
        s1 = hashlib.sha256(_render(S).encode()).hexdigest()
        s2 = hashlib.sha256(_render(S).encode()).hexdigest()
        assert s1 == s2, "render not deterministic for %s" % name
        print("  render deterministic sha256 [%s]     : %s" % (name, s1))


def test_customize_panel():
    # (e) the Customize panel lives inside the drawer and its control defaults
    # mirror spec.theme (accent, accent2, font, fontsize, background, card,
    # text, radius).
    spec = {
        "title": "T",
        "theme": {"accent": "#00aaff", "accent2": "#ff00cc",
                  "font": "Roboto, sans-serif", "fontsize": 17,
                  "background": "#10141c", "card": "#1c2431",
                  "text": "#f0f6fc", "muted": "#9aa7b4", "radius": 18},
        "categories": [],
    }
    html, s1, s2 = _rest(spec)
    assert s1 == s2, "customize render not deterministic"
    # panel controls present (existing + new background/card/text/radius)
    for cid in ("theme-accent", "theme-accent2", "theme-bg", "theme-card",
               "theme-text", "theme-font", "fs-value", "font-minus", "font-plus",
               "radius-value", "radius-minus", "radius-plus"):
        assert 'id="%s"' % cid in html, "missing control %s" % cid
    # the panel sits inside the drawer, not the main page
    drawer_start = html.find('<div class="drawer"')
    assert drawer_start != -1
    assert html.find('id="theme-accent"') > drawer_start
    main = html[:drawer_start]
    assert 'theme-accent' not in main
    # spec.theme values appear as the panel defaults (render-time baked)
    assert 'value="#00aaff"' in html
    assert 'value="#ff00cc"' in html
    assert 'value="#10141c"' in html
    assert 'value="#1c2431"' in html
    assert 'value="#f0f6fc"' in html
    assert '<option value="Roboto, sans-serif" selected>' in html
    assert 'id="fs-value">17px' in html
    assert 'id="radius-value">18px' in html
    # live-applied font/color/radius vars reference the CSS custom properties
    for prop in ("--accent", "--accent2", "--bg", "--card", "--txt",
                 "--font", "--fontsize", "--radius", "--muted"):
        assert "setProperty('%s'" % prop in html, "missing setProperty %s" % prop
    # localStorage persist/restore is guarded (file:// origin-null tolerant)
    assert "localStorage" in html
    # timeout/abort/retry wiring present with the agent default timeout
    assert "AbortController" in html
    assert "timeout_ms" in html
    assert "Retrying" in html
    print("customize panel in drawer + theme defaults : OK")


def test_theme_expansion_vars():
    # (a') full theme block injects every new CSS variable deterministically.
    spec = {
        "title": "T",
        "theme": {"accent": "#00aaff", "accent2": "#ff00cc",
                  "font": "Roboto, sans-serif", "fontsize": 17,
                  "background": "#000000", "card": "#111111",
                  "text": "#ffffff", "muted": "#888888", "radius": "20px"},
        "categories": [],
    }
    html, s1, s2 = _rest(spec)
    assert s1 == s2, "theme expansion render not deterministic"
    for var in ("--accent:#00aaff;", "--accent2:#ff00cc;",
                "--font:Roboto, sans-serif;", "--fontsize:17;",
                "--bg:#000000;", "--card:#111111;", "--txt:#ffffff;",
                "--muted:#888888;", "--radius:20px;"):
        assert var in html, "missing injected var %s" % var
    # absent keys fall back to built-in defaults (no injected override:
    # a partial theme adds ONE override line for its key, leaving others at
    # their built-in default occurrence count)
    sub = {"title": "T", "theme": {"background": "#123456"}, "categories": []}
    sh, _x, _y = _rest(sub)
    assert "--bg:#123456;" in sh
    assert sh.count("--card:") == 1, "absent card key must keep default, not override"
    # legacy font_size alias still honoured
    legacy = {"title": "T", "theme": {"font_size": 15}, "categories": []}
    lh, l1, l2 = _rest(legacy)
    assert l1 == l2
    assert "--fontsize:15;" in lh
    # a bare numeric radius is injected as px
    numr = {"title": "T", "theme": {"radius": 20}, "categories": []}
    rh, _p, _q = _rest(numr)
    assert "--radius:20px;" in rh, "bare numeric radius should inject as px"
    print("theme expansion (all 9 vars + legacy alias) : OK")


def test_send_contract_timeout_and_retry():
    # (c') Send wiring: POST canonical results (no sent_at), timeout, retry,
    # AbortController, disabled-while-in-flight, and default timeout of 10000.
    base = {"title": "T", "theme": {"accent": "#00aaff", "accent2": "#ff00cc"},
            "categories": []}
    spec = dict(base)
    spec["agent"] = {"webhook_url": "https://example.com/hook",
                     "name": "QA bot", "timeout_ms": 3000}
    html, s1, s2 = _rest(spec)
    assert s1 == s2, "agent send render not deterministic"
    assert 'id="sendbtn"' in html
    assert 'name": "QA bot"' in html or "QA bot" in html
    assert "example.com/hook" in html
    # webhook_url + timeout_ms ride in AGENT config json
    assert '"timeout_ms": 3000' in html
    # POST uses exactly the collected results body, application/json, abort
    assert "method:'POST'" in html
    assert "'Content-Type':'application/json'" in html
    assert "new AbortController()" in html
    assert "ctrl.abort()" in html
    assert "signal: ctrl.signal" in html
    assert "sb.disabled = true" in html
    assert "sb.disabled = false" in html
    assert "post(2)" in html      # retry once on network error
    assert "Sent \u2713" in html  # success status text
    assert "Failed: " in html
    # determinism: NO timestamps / sent_at anywhere in the payload path
    assert "sent_at" not in html
    assert "Date.now" not in html
    assert "toISOString" not in html
    # default timeout is 10000 when agent.timeout_ms is absent
    nod = {"title": "T", "agent": {"webhook_url": "https://h.example.com/x"},
           "categories": []}
    h2, _a, _b = _rest(nod)
    assert '"timeout_ms": 10000' in h2, "default timeout should be 10000"
    print("send contract: timeout + abort + retry once  : OK")


def test_theme_roundtrip():
    # (f) theme round-trips through build_results/parse_results: present theme
    # survives, absent theme yields an OMITTED key (never null).
    mod = _load_module()
    s_theme = {
        "title": "T",
        "theme": {"accent": "#00aaff", "accent2": "#ff00cc",
                  "font": "Roboto, sans-serif", "fontsize": 17,
                  "background": "#000000", "card": "#111111",
                  "text": "#ffffff", "muted": "#888888", "radius": 20},
        "categories": [],
    }
    r = mod.build_results(s_theme)
    assert r.get("theme") == s_theme["theme"], r
    p = mod.parse_results(r)
    assert p == r, "theme round-trip failed"
    assert p["theme"]["accent"] == "#00aaff"
    assert p["theme"]["fontsize"] == 17
    assert p["theme"]["radius"] == 20

    s_none = {"title": "T", "categories": []}
    r2 = mod.build_results(s_none)
    assert "theme" not in r2, "theme should be omitted when spec lacks it"
    p2 = mod.parse_results(r2)
    assert "theme" not in p2, "theme should be omitted when results lack it"
    print("theme build/parse round-trip (omitted, not null) : OK")


def _run_cli_rc(*args):
    """Run the CLI and return (returncode, stdout, stderr)."""
    out = subprocess.run([sys.executable, CHECKLST] + list(args),
                         capture_output=True, text=True)
    return out.returncode, out.stdout, out.stderr


def _section(html, cid):
    import re
    m = re.search(r'<section class="cat[^"]*" data-cat="%s">.*?</section>' % cid, html, re.S)
    return m.group(0)


def _pass_spec():
    # a spec that OPT-IN to passdown (config.allow_passdown). Two categories so
    # a --scope can skip one (a == in scope, b == skipped).
    spec = {
        "title": "T",
        "config": {"allow_passdown": True},
        "categories": [
            {
                "id": "a", "name": "A", "goal": "ga",
                "items": [
                    {"id": "x1", "text": "Do X", "notes": "n1",
                     "options": {
                         "status": {"value": "Works",
                                    "choices": ["Works", "Doesn't", "Bugged"]}}},
                ],
            },
            {
                "id": "b", "name": "B", "goal": "gb",
                "collapsed_default": False,
                "items": [
                    {"id": "x2", "text": "Do Y",
                     "options": {"flag": {"value": False},
                                 "sev": {"value": "mild", "choices": ["mild", "hot"]}}},
                ],
            },
        ],
    }
    return spec


def test_passdown_render(tmp_path):
    spec_path = os.path.join(tmp_path, "pass.json")
    with open(spec_path, "w") as f:
        json.dump(_pass_spec(), f)

    # success path: --agent, --mission, --scope, --from; banner + embeds block
    html1 = run_cli("passdown", spec_path, "--agent", "bob",
                    "--mission", "check the build", "--scope", "a", "--from", "ox-alpha")
    html2 = run_cli("passdown", spec_path, "--agent", "bob",
                    "--mission", "check the build", "--scope", "a", "--from", "ox-alpha")
    s1 = hashlib.sha256(html1.encode()).hexdigest()
    s2 = hashlib.sha256(html2.encode()).hexdigest()
    assert s1 == s2, "passdown render not deterministic"
    print("passdown render deterministic sha256   : %s" % s1)

    # (a) idempotent header banner "Passdown from X -> Y | mission"
    assert "passdown-banner" in html1
    assert "Passdown from" in html1
    assert "ox-alpha" in html1 and "bob" in html1
    assert "check the build" in html1
    assert "|" in html1
    assert html1.count("passdown-banner") == html1.count("passdown-banner")
    # banner appears exactly once (idempotent, not duplicated)
    assert html1.count("Passdown from") == 1, "banner must be idempotent"
    print("passdown banner present + idempotent          : OK")

    # SPEC embeds the passdown metadata block
    i = html1.find("var SPEC = ")
    spec_json = html1[i + len("var SPEC = "):html1.find(";", i)]
    emb = json.loads(spec_json)
    assert emb["config"] == {"allow_passdown": True}
    assert emb["passdown"] == {
        "from": "ox-alpha", "to": "bob", "mission": "check the build",
        "scope": ["a"], "mode": "strict"}
    print("SPEC embeds config.allow_passdown + passdown block : OK")

    # (c) scope disables non-scoped category: b skipped+collapsed+disabled, a live
    ra = _section(html1, "a"); rb = _section(html1, "b")
    assert "passdown-skipped" not in ra and "disabled" not in ra
    assert "passdown-skipped" in rb and "collapsed" in rb and "disabled" in rb
    print("scope: non-scoped category skipped+disabled  : OK")

    # (d) strict chips exist in every section header (strict mode)
    assert html1.count('class="completion-chip"') >= 2
    assert 'id="passdown-warn"' in html1
    print("strict completion-chips + warn element        : OK")
    print("passdown render feature tests                 : all OK")


def test_passdown_locked(tmp_path):
    # (b) spec without / with false allow_passdown -> exit 1, clear message
    for allow in (False, None):
        spec = _pass_spec()
        if allow is False:
            spec["config"] = {"allow_passdown": False}
        elif allow is None:
            del spec["config"]
        p = os.path.join(tmp_path, "locked.json")
        with open(p, "w") as f:
            json.dump(spec, f)
        rc, out, err = _run_cli_rc("passdown", p, "--agent", "bob")
        assert rc == 1, "expected exit 1 for locked spec, got %s" % rc
        assert "locked by author" in err, err
    print("allow_passdown false/absent -> exit 1          : OK")


def test_passdown_metadata_roundtrip():
    # round-trip property keeps holding; config/passdown preserved as metadata
    mod = _load_module()
    spec = _pass_spec()
    spec["passdown"] = {"from": "orchestrator", "to": "bob",
                        "mission": "m", "scope": ["a"], "mode": "strict"}
    results = mod.build_results(spec)
    assert results["config"] == {"allow_passdown": True}
    assert results["passdown"]["to"] == "bob"
    parsed = mod.parse_results(results)
    assert parsed == results, "round-trip with config/passdown failed"
    print("build/parse preserve config+passdown metadta   : OK")

    # specs WITHOUT config/passdown stay clean (omitted, not null)
    plain = {"title": "T", "categories": []}
    rp = mod.build_results(plain)
    assert "config" not in rp and "passdown" not in rp
    pp = mod.parse_results(rp)
    assert "config" not in pp and "passdown" not in pp
    print("config/passdown omitted when absent            : OK")
    print("passdown metadata round-trip                   : PASS OK")


def main():
    with tempfile.TemporaryDirectory() as td:
        test_render_and_parse(td)
        test_theme_and_colored_choices(td)
        test_send_button_presence()
        test_results_drawer()
        test_customize_panel()
        test_theme_expansion_vars()
        test_theme_roundtrip()
        test_send_contract_timeout_and_retry()
        test_new(td)
        test_roundtrip_property()
        test_passdown_render(td)
        test_passdown_locked(td)
        test_passdown_metadata_roundtrip()
    print("\nALL GOLDEN CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()