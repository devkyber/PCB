"""Offline inspection bench for an actual source-bound PCB review snapshot."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re

KINDS = {'machine_failure': 'Machine check', 'engineering_warning': 'Engineering advisory',
         'human_decision': 'Human decision'}
IMAGE_KINDS = {'schematic', 'assembly', 'copper'}

CSS = r'''
:root{color-scheme:light;--ink:#183044;--muted:#526779;--line:#cbd5de;--paper:#fff;--desk:#edf2f5;--blue:#126a83;--amber:#9a4c08;--tint:#fff1da;--green:#22684d}

*{box-sizing:border-box}
body{margin:0;background:var(--desk);color:var(--ink);font:15px/1.55 "Segoe UI",Arial,sans-serif}
button,input,select{font:inherit}
button,a,input,select,summary{outline-offset:4px}
button,a{touch-action:manipulation}
button{cursor:pointer}
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #007b9c}
a{color:var(--blue)}
h1,h2,h3,p{margin-top:0}
h1{font-size:clamp(25px,3vw,42px);line-height:1.15;margin-bottom:8px;letter-spacing:-.025em}
h2{font-size:23px;line-height:1.2}
h3{font-size:16px;margin-bottom:8px}
.shell{max-width:1840px;margin:auto;padding:28px clamp(16px,3vw,48px) 64px}
.masthead{display:flex;justify-content:space-between;align-items:start;gap:24px;padding-bottom:22px}
.identity{font-weight:650;color:var(--muted);margin-bottom:10px}
.snapshot{max-width:60ch;color:var(--muted);margin-bottom:0}
.state{border-left:5px solid var(--amber);background:var(--tint);padding:14px 20px;min-width:240px}
.state.clear{border-color:var(--green);background:#e8f3ed}
.state strong{display:block;font-size:20px}
.state p{margin:4px 0 0}
.notice{border-top:1px solid var(--line);padding-top:14px;margin-bottom:26px;color:var(--muted)}
.workspace{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(300px,1fr);align-items:start;gap:24px}
.panel{background:var(--paper);border:1px solid var(--line);border-radius:9px;overflow:hidden}
.panel-heading{padding:20px 24px 0}
.panel-heading p{color:var(--muted);margin-bottom:18px}
.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:end;border-block:1px solid var(--line);padding:14px 24px;background:#f5f8fa}
.toolbar label{display:grid;gap:4px;font-size:13px;color:var(--muted)}
input,select,button{border:1px solid #afbecb;border-radius:5px;background:#fff;color:var(--ink);padding:8px 11px}
input{min-width:210px}
button:hover{background:#eaf2f6}
.image-index{display:flex;gap:8px;flex-wrap:wrap;padding:14px 24px}
.image-index a{padding:5px 9px;background:#eef3f6;border-radius:4px;text-decoration:none}
.image-index a[aria-current]{background:var(--blue);color:#fff}
.artifacts{padding:0 20px 20px;background:#dce5ec;overflow:hidden}
.artifact{margin:20px 0 0;scroll-margin-top:18px}
.artifact img{display:block;width:100%;height:auto;background:white;box-shadow:0 2px 10px #213a4b17}
.artifact figcaption{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 2px 0}
.artifact strong{display:block}
.orientation{color:var(--muted);font-size:13px}
.empty{padding:20px;color:var(--muted)}
.triage{padding:22px 24px}
.triage h2{margin-bottom:8px}
.finding-group{margin-top:24px}
.finding-group h3{padding-bottom:8px;border-bottom:1px solid var(--line)}
.finding-group ul{list-style:none;padding:0;margin:0}
.finding{margin-top:16px;padding-left:12px;border-left:3px solid #d39547}
.finding.human{border-left-color:#6e6ba5}
.finding.advisory{border-left-color:#738e9d}
.finding small{display:block;color:var(--muted)}
.detail{white-space:pre-wrap;overflow-wrap:anywhere;max-width:80ch;margin-bottom:10px}
.section{margin-top:28px}
.section-intro{display:flex;align-items:baseline;justify-content:space-between;gap:16px}
.section-intro p{color:var(--muted)}
.checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:16px}
.check{padding:20px 22px;border:1px solid var(--line);border-radius:7px;background:white;min-width:0}
.check header{display:flex;justify-content:space-between;align-items:start;gap:16px}
.check h3{overflow-wrap:anywhere}
.badge{white-space:nowrap;font-size:12px;font-weight:650;padding:3px 8px;border-radius:4px;background:#e8f3ed;color:var(--green)}
.badge.fail{background:var(--tint);color:var(--amber)}
.check-meta{color:var(--muted);font-size:12px;margin-bottom:12px}
.check details{border-top:1px solid #e0e7ec;padding-top:10px}
.check summary{cursor:pointer;color:var(--blue)}
.scope{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:12px;font-size:13px}
.scope strong{display:block;margin-bottom:4px}
.scope p{margin-bottom:8px;overflow-wrap:anywhere}
.scope .limit strong{color:var(--amber)}
.advisories{padding-left:20px;font-size:13px}
.ledger{padding:20px 24px}
.ledger summary{font-size:19px;font-weight:650;cursor:pointer}
.ledger p{color:var(--muted);margin:12px 0}
.hash-table{width:100%;border-collapse:collapse;font-size:13px}
.hash-table th{text-align:left;color:var(--muted)}
.hash-table td,.hash-table th{padding:9px 8px;border-top:1px solid #e0e7ec;vertical-align:top}
.hash-table td:first-child{width:45%;overflow-wrap:anywhere}
code{font-family:Consolas,"Courier New",monospace;font-size:.92em;overflow-wrap:anywhere;white-space:normal}
.fingerprints{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
.fingerprints p{margin:0;color:var(--muted);font-size:13px}
.fingerprints code{display:block;color:var(--ink)}
.js-only{display:none}
.enhanced .js-only{display:flex}
[hidden]{display:none!important}
.count{color:var(--muted);font-size:13px}
.footer{margin-top:26px;color:var(--muted);max-width:100ch}
dialog{max-width:min(96vw,1700px);width:96vw;max-height:95vh;padding:0;border:1px solid #7d92a3;border-radius:8px;background:#e2e9ee;color:var(--ink)}
dialog::backdrop{background:#102635c9}
.dialog-bar{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:12px 18px;background:#fff;position:sticky;top:0;z-index:1}
.dialog-bar h2{font-size:17px;margin:0}
.zoom-tools{display:flex;gap:8px;align-items:center}
.zoom-tools button{min-width:40px}
.zoom-stage{height:78vh;overflow:auto;padding:24px}
.zoom-stage img{display:block;width:100%;height:auto;max-width:none;background:#fff;transform-origin:top left}
.skip{position:absolute;left:-9999px}
.skip:focus{left:16px;top:12px;background:white;padding:10px;z-index:4}
noscript p{background:white;padding:12px;border:1px solid var(--line)}

@media(max-width:1050px){.workspace{grid-template-columns:1fr}
.triage{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.triage>h2,.triage>p{grid-column:1/-1}
.finding-group{margin-top:0}
.masthead{flex-wrap:wrap}
.state{min-width:0}
.checks{grid-template-columns:1fr}
}

@media(max-width:650px){.shell{padding:20px 14px 36px}
.masthead{gap:16px}
.state{width:100%}
.toolbar,.panel-heading,.triage,.ledger{padding-left:16px;padding-right:16px}
.triage,.scope,.fingerprints{grid-template-columns:1fr}
.section-intro{display:block}
.artifacts{padding:0 10px 12px}
.artifact figcaption{align-items:start;flex-wrap:wrap}
.toolbar label{width:100%}
input,select{width:100%;min-width:0}
.dialog-bar{align-items:start;flex-wrap:wrap}
.hash-table td:first-child{width:37%}
.zoom-stage{padding:8px}
}

@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}
}

@media print{.shell{padding:0}
.workspace,.checks{display:block}
.triage,.check,.artifact{break-inside:avoid}
.js-only,.image-index,dialog{display:none!important}
.panel,.check{border-color:#aaa;box-shadow:none}
.check{margin-bottom:12px}
.artifacts{background:white}
.ledger details{display:block}
}

'''

JS = r'''
(() => {
  'use strict';
  document.documentElement.classList.add('enhanced');
  const checks = [...document.querySelectorAll('[data-check]')];
  const search = document.getElementById('check-search');
  const status = document.getElementById('check-status');
  const kind = document.getElementById('check-kind');
  const count = document.getElementById('check-count');
  function filterChecks() {
    const query = search.value.trim().toLocaleLowerCase();
    let shown = 0;
    for (const row of checks) {
      const match = (!query || row.textContent.toLocaleLowerCase().includes(query)) &&
        (status.value === 'all' || row.dataset.status === status.value) &&
        (kind.value === 'all' || row.dataset.kind === kind.value);
      row.hidden = !match;
      if (match) shown++;
    }
    count.textContent = `Showing ${shown} of ${checks.length} checks`;
    document.getElementById('no-checks').hidden = shown !== 0;
  }
  search.addEventListener('input', filterChecks);
  status.addEventListener('change', filterChecks);
  kind.addEventListener('change', filterChecks);
  filterChecks();
  document.getElementById('view-kind').addEventListener('change', event => {
    document.querySelectorAll('[data-artifact]').forEach(figure => {
      figure.hidden = event.target.value !== 'all' && figure.dataset.kind !== event.target.value;
    });
  });
  document.querySelectorAll('.image-index a').forEach(link => link.addEventListener('click', () => {
    document.getElementById('view-kind').value = 'all';
    document.querySelectorAll('[data-artifact]').forEach(item => {item.hidden = false;});
    document.querySelectorAll('.image-index a').forEach(item => item.removeAttribute('aria-current'));
    link.setAttribute('aria-current', 'true');
  }));
  const dialog = document.getElementById('image-dialog');
  const enlarged = document.getElementById('enlarged-image');
  let zoom = 1;
  function applyZoom() {
    enlarged.style.width = `${zoom * 100}%`;
    document.getElementById('zoom-value').textContent = `${Math.round(zoom * 100)}%`;
  }
  document.querySelectorAll('[data-enlarge]').forEach(button => button.addEventListener('click', () => {
    const figure = document.getElementById(button.dataset.enlarge);
    const source = figure.querySelector('img');
    enlarged.src = source.src;
    enlarged.alt = source.alt;
    document.getElementById('dialog-title').textContent = figure.querySelector('strong').textContent;
    zoom = 1;
    applyZoom();
    if (typeof dialog.showModal === 'function') dialog.showModal();
  }));
  document.getElementById('zoom-in').addEventListener('click', () => {zoom = Math.min(4, zoom + .25); applyZoom();});
  document.getElementById('zoom-out').addEventListener('click', () => {zoom = Math.max(.25, zoom - .25); applyZoom();});
  document.getElementById('zoom-fit').addEventListener('click', () => {zoom = 1; applyZoom();});
  document.getElementById('close-image').addEventListener('click', () => dialog.close());
  document.getElementById('download-json').addEventListener('click', () => {
    const payload = document.getElementById('report-data').textContent;
    const url = URL.createObjectURL(new Blob([payload], {type:'application/json'}));
    const link = document.createElement('a');
    link.href = url; link.download = 'pcb-review-snapshot.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
})();
'''


def _escape(value) -> str:
    return html.escape(str(value), quote=True)


def _safe_json(value) -> str:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False).replace('&', r'\u0026')
            .replace('<', r'\u003c').replace('>', r'\u003e')
            .replace('\u2028', r'\u2028').replace('\u2029', r'\u2029'))


def _image(image: dict, seen: set[str]) -> str:
    identifier = image['id']
    if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', identifier)
            or identifier in seen or image.get('kind') not in IMAGE_KINDS):
        raise ValueError('report images require unique safe identifiers and known native-view kinds')
    seen.add(identifier)
    uri = image.get('data_uri', '')
    if not isinstance(uri, str) or not uri.startswith('data:image/png;base64,'):
        raise ValueError('offline report accepts embedded PNG images only')
    try:
        payload = base64.b64decode(uri.removeprefix('data:image/png;base64,'), validate=True)
    except ValueError as exc:
        raise ValueError('invalid embedded PNG encoding') from exc
    if not payload.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('report image does not contain PNG bytes')
    title, orientation = _escape(image['title']), _escape(image.get('orientation', ''))
    return (f'<figure class="artifact" id="artifact-{identifier}" data-artifact data-kind="{image["kind"]}">'
            f'<img src="{uri}" alt="{title}" loading="lazy">'
            f'<figcaption><div><strong>{title}</strong><span class="orientation">{orientation}</span></div>'
            f'<button type="button" class="js-only" data-enlarge="artifact-{identifier}">Enlarge image</button>'
            '</figcaption></figure>')


def _finding_group(findings: list[dict], kind: str, title: str) -> str:
    selected = [finding for finding in findings if finding['kind'] == kind]
    items = []
    variant = 'human' if kind == 'human_decision' else 'advisory' if kind == 'engineering_warning' else ''
    for finding in selected:
        level = 'Blocking finding' if finding['blocking'] else 'Advisory'
        items.append(f'<li class="finding {variant}"><strong>{_escape(finding["check_id"])}</strong>'
                     f'<small>{level}</small><p class="detail">{_escape(finding["detail"])}</p></li>')
    content = '<ul>' + ''.join(items) + '</ul>' if items else '<p class="count">No findings of this kind recorded.</p>'
    return f'<section class="finding-group"><h3>{title} ({len(selected)})</h3>{content}</section>'


def _check(result: dict) -> str:
    passed, scope, kind = result['passed'], result['scope'], result['finding_kind']
    state, badge = ('pass', 'Passed') if passed else ('fail', 'Failed')
    advisories = ''.join(f'<li>{_escape(value)}</li>' for value in result.get('advisories', []))
    extras = f'<h4>Advisories</h4><ul class="advisories">{advisories}</ul>' if advisories else ''
    external = 'External tool required' if scope['requires_external_tool'] else 'No external tool required'
    deterministic = 'Deterministic check' if scope['deterministic'] else 'Result may vary between native runs'
    return (f'<article class="check" data-check data-status="{state}" data-kind="{kind}">'
            f'<header><h3>{_escape(result["check_id"])}</h3><span class="badge {"" if passed else "fail"}">{badge}</span></header>'
            f'<p class="check-meta">{KINDS[kind]} | {_escape(result.get("duration_ms", 0))} ms</p>'
            f'<p class="detail">{_escape(result["detail"])}</p><details open><summary>Check scope and limits</summary>'
            f'<div class="scope"><div><strong>Establishes</strong><p>{_escape(scope["proves"])}</p></div>'
            f'<div class="limit"><strong>Does not establish</strong><p>{_escape(scope["does_not_prove"])}</p></div></div>'
            f'<p class="count">{external}. {deterministic}.</p>{extras}</details></article>')


def render_report(document: dict, images: list[dict]) -> str:
    """Render actual review data; local tools never accept or record approvals."""
    review = document['review']
    if (document.get('schema_version') != 1 or document.get('source_inputs_unchanged') is not True
            or type(review.get('blocking')) is not bool):
        raise ValueError('report requires a preserved source snapshot and an actual review blocking state')
    results, findings = review['results'], review['findings']
    for result in results:
        if type(result.get('passed')) is not bool or result.get('finding_kind') not in KINDS:
            raise ValueError('report check result has an invalid status or kind')
    for finding in findings:
        if finding.get('kind') not in KINDS or type(finding.get('blocking')) is not bool:
            raise ValueError('report finding has an invalid blocking state or kind')
    seen = set()
    figures = ''.join(_image(image, seen) for image in images)
    if not figures:
        figures = '<p class="empty">No native images are included in this snapshot. Read the recorded check findings below.</p>'
    index = ''.join(f'<a href="#artifact-{image["id"]}">{_escape(image["title"])}</a>' for image in images)
    project = document['project']
    name = _escape(project['name'] if isinstance(project, dict) else project)
    pdf_link = ''
    if document.get('schematic_pdf_uri'):
        uri = document['schematic_pdf_uri']
        prefix = 'data:application/pdf;base64,'
        if not isinstance(uri, str) or not uri.startswith(prefix):
            raise ValueError('schematic download must be an embedded PDF')
        try:
            payload = base64.b64decode(uri[len(prefix):], validate=True)
        except ValueError as exc:
            raise ValueError('schematic download must be an embedded PDF') from exc
        if not payload.startswith(b'%PDF-'):
            raise ValueError('schematic download must contain PDF bytes')
        pdf_link = f'<a href="{_escape(uri)}" download="schematic.pdf">Download vector schematic PDF</a>'
    blocked = review['blocking']
    status = 'Blocked' if blocked else 'No registered blocker'
    failed = sum(not result['passed'] for result in results)
    blocking = sum(finding['blocking'] for finding in findings)
    summary = f'{len(results) - failed} passed, {failed} failed; {blocking} blocking {"finding" if blocking == 1 else "findings"}.'
    checks = ''.join(_check(result) for result in results)
    groups = ''.join(_finding_group(findings, kind, title) for kind, title in (
        ('machine_failure', 'Machine findings'), ('human_decision', 'Human decisions'),
        ('engineering_warning', 'Engineering advisories')))
    ledger = ''.join(f'<tr><td>{_escape(path)}</td><td><code>{_escape(value) if value is not None else "Not present in this snapshot"}</code></td></tr>'
                     for path, value in sorted(document['source_inputs'].items()))
    safe_data = _safe_json({'document': document, 'images': [{key: value for key, value in image.items() if key != 'data_uri'}
                                                           for image in images]})
    script_hash = base64.b64encode(hashlib.sha256(JS.encode()).digest()).decode()
    policy = (f"default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; "
              "connect-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{_escape(policy)}"><title>{name} | PCB review handover</title>
<style>{CSS}</style></head><body><a class="skip" href="#native-views">Skip to native views</a><div class="shell">
<header class="masthead"><div><p class="identity">PCB Copilot / Review handover</p><h1>{name}</h1>
<p class="snapshot">Captured {_escape(document['generated_utc'])}<br>KiCad {_escape(document['toolchain'].get('kicad_version', 'not recorded'))}. Source inputs preserved during export.</p></div>
<div class="state {'' if blocked else 'clear'}"><strong>{status}</strong><p>{summary}</p></div></header>
<p class="notice">This is an offline snapshot. Machine findings and human decisions remain separate. This report records no approval.</p>
<noscript><p>All native views, checks and source hashes are available below. Enable JavaScript for local filtering and image zoom.</p></noscript>
<main><div class="workspace"><section class="panel" id="native-views" aria-labelledby="views-title">
<div class="panel-heading"><h2 id="views-title">Inspect the saved design</h2><p>Every included sheet and board view is shown. Select a view to jump to it; enlarge for circuit detail. {pdf_link}</p></div>
<div class="toolbar js-only"><label>Native views<select id="view-kind"><option value="all">All views</option><option value="schematic">Schematics</option><option value="assembly">Assembly</option><option value="copper">Copper</option></select></label></div>
<nav class="image-index" aria-label="Native view index">{index}</nav><div class="artifacts">{figures}</div></section>
<aside class="panel triage" aria-labelledby="triage-title"><h2 id="triage-title">What needs attention</h2><p class="count">{summary}</p>{groups}</aside></div>
<section class="section" aria-labelledby="checks-title"><div class="section-intro"><h2 id="checks-title">Checks and their limits</h2><p>Read what each result establishes and what it leaves unresolved.</p></div>
<div class="toolbar js-only"><label>Search checks<input id="check-search" type="search" placeholder="Check, finding, scope…"></label>
<label>Result<select id="check-status"><option value="all">All results</option><option value="pass">Passed</option><option value="fail">Failed</option></select></label>
<label>Kind<select id="check-kind"><option value="all">All kinds</option><option value="machine_failure">Machine checks</option><option value="engineering_warning">Engineering advisories</option><option value="human_decision">Human decisions</option></select></label>
<span class="count" id="check-count" role="status" aria-live="polite">Showing {len(results)} of {len(results)} checks</span></div>
<div class="checks">{checks}</div><p class="empty" id="no-checks" hidden>No checks match these filters. Clear the search or select all results.</p></section>
<section class="panel section ledger"><details open><summary>Source hashes and evidence paths ({len(document['source_inputs'])} declared inputs)</summary>
<p>These hashes identify the captured files. They do not prove engineering suitability or that the live project still matches this snapshot.</p>
<div class="fingerprints"><p>Schematic hierarchy SHA-256<code>{_escape(review['schematic_hash'])}</code></p><p>PCB SHA-256<code>{_escape(review['pcb_hash'])}</code></p></div>
<table class="hash-table"><thead><tr><th scope="col">Declared source path</th><th scope="col">SHA-256 / absence</th></tr></thead><tbody>{ledger}</tbody></table>
<p><button class="js-only" type="button" id="download-json">Download snapshot JSON</button></p></details></section>
</main><footer class="footer">{_escape(document['scope'])}</footer></div>
<dialog id="image-dialog" aria-labelledby="dialog-title"><div class="dialog-bar"><h2 id="dialog-title">Native image</h2><div class="zoom-tools">
<button id="zoom-out" type="button" aria-label="Zoom out">−</button><span id="zoom-value">100%</span><button id="zoom-in" type="button" aria-label="Zoom in">+</button>
<button id="zoom-fit" type="button">Fit width</button><button id="close-image" type="button">Close image</button></div></div><div class="zoom-stage"><img id="enlarged-image" alt=""></div></dialog>
<script type="application/json" id="report-data">{safe_data}</script><script>{JS}</script></body></html>'''
