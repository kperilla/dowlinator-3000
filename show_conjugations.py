#!/usr/bin/env python3
"""
Display the conjugation tables in latin_conjugations.json.

    python show_conjugations.py                     # writes latin_conjugations.html
    python show_conjugations.py --text              # prints the tables in the terminal
    python show_conjugations.py --text --verb amō   # just one verb (macrons optional: amo)
    python show_conjugations.py -i other.json -o other.html

Periphrastic cells such as "amātus + present active indicative of sum"
are expanded into real forms (amātus sum, amātus es, …) using the sum
table from the same file, when it is there.

Standard library only.
"""

import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

SLOTS = ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]
SLOT_LABEL = {"1sg": "1st", "2sg": "2nd", "3sg": "3rd", "1pl": "1st", "2pl": "2nd", "3pl": "3rd"}
NF_TENSES = ["present", "perfect", "future"]
CASES = ["genitive", "dative", "accusative", "ablative"]
DASH = "—"

PERIPHRASTIC = re.compile(
    r"^(?P<part>.+?)\s*\+\s*(?P<tense>[\w ]+?)\s+active\s+(?P<mood>indicative|subjunctive)\s+of\s+sum$")


# ---------------------------------------------------------------- data helpers

def strip_macrons(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def expand(forms, slot, sum_finite):
    """Turn 'amātus + present active indicative of sum' into 'amātus sum'."""
    out = []
    for f in forms:
        m = PERIPHRASTIC.match(f)
        aux = None
        if m and sum_finite:
            aux = (sum_finite.get(m["mood"], {}).get("active", {})
                   .get(m["tense"].strip(), {}).get(slot))
        if aux:
            out += [f"{m['part']} {a}" for a in aux]
        else:
            out.append(f)
    return out


def cell(forms):
    return ", ".join(forms) if forms else DASH


def finite_rows(verb, mood, sum_finite):
    """[(voice, tense, {slot: [forms]})] for one mood, plus the slots actually used."""
    rows = []
    for voice, tenses in verb["finite"].get(mood, {}).items():
        for tense, slots in tenses.items():
            rows.append((voice, tense, {s: expand(slots.get(s, []), s, sum_finite) for s in SLOTS}))
    used = [s for s in SLOTS if any(r[2][s] for r in rows)]
    return rows, used


# ---------------------------------------------------------------- terminal output

def text_table(header, rows):
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    line = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip()
    rule = "  ".join("─" * w for w in widths)
    return "\n".join([line(header), rule] + [line(r) for r in rows])


def print_verb(lemma, verb, sum_finite):
    print(f"\n{'═' * 70}\n{lemma}  ·  {verb['category']}\n{verb.get('title', '')}\n{'═' * 70}")
    for mood in verb["finite"]:
        rows, used = finite_rows(verb, mood, sum_finite)
        if not rows:
            continue
        header = ["", ""] + [f"{SLOT_LABEL[s]} {s[1:]}" for s in used]
        body, last_voice = [], None
        for voice, tense, slots in rows:
            body.append([voice if voice != last_voice else "", tense] + [cell(slots[s]) for s in used])
            last_voice = voice
        print(f"\n{mood.upper()}\n" + text_table(header, body))

    nf = verb.get("nonfinite", {})
    vt = [(v, t) for v in ("active", "passive") for t in NF_TENSES]
    body = [[kind + "s"] + [cell(nf.get(kind, {}).get(v, {}).get(t, [])) for v, t in vt]
            for kind in ("infinitive", "participle") if kind in nf]
    if body:
        print("\nNON-FINITE\n" + text_table([""] + [f"{v[:3]}. {t}" for v, t in vt], body))
    for kind in ("gerund", "supine"):
        if kind in nf:
            cases = [c for c in CASES if c in nf[kind]]
            print(f"\n{kind.upper()}\n" + text_table(cases, [[cell(nf[kind][c]) for c in cases]]))
    if verb.get("unparsed"):
        print("\nUNPARSED CELLS")
        for u in verb["unparsed"]:
            print(f"  {u['form']}   ← {' | '.join(u['labels'])}")


# ---------------------------------------------------------------- HTML output

CSS = """
:root{--bg:#fbfaf7;--fg:#22201c;--muted:#6f6a60;--line:#e2ded5;--head:#f1eee7;--accent:#8a3324;--chip:#efe7dc;--ok:#d6efd6;--bad:#f6d3cf}
@media (prefers-color-scheme:dark){:root{--bg:#1a1917;--fg:#ebe7df;--muted:#a19b90;--line:#36332e;--head:#24221f;--accent:#e08a6f;--chip:#2c2925;--ok:#1f3b24;--bad:#4a2420}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 Georgia,"Iowan Old Style",serif}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;
    display:flex;flex-wrap:wrap;gap:6px;z-index:2}
nav a{color:var(--fg);text-decoration:none;background:var(--chip);padding:2px 10px;border-radius:999px;font-size:14px}
nav a:hover{color:var(--accent)}
main{max-width:1100px;margin:0 auto;padding:16px}
section.verb{margin:32px 0 48px;scroll-margin-top:70px}
h2{font-size:28px;margin:0;color:var(--accent)}
.meta{color:var(--muted);font:13px/1.4 system-ui,sans-serif;margin:2px 0 14px}
h3{font:600 12px/1 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:22px 0 6px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;min-width:100%;font-size:15px}
th,td{border:1px solid var(--line);padding:5px 9px;text-align:left;vertical-align:top}
thead th{background:var(--head);font:600 12px/1.3 system-ui,sans-serif;color:var(--muted)}
tbody th{font:600 13px/1.3 system-ui,sans-serif;color:var(--muted);background:var(--head);white-space:nowrap}
td.empty{color:var(--muted);text-align:center}
.unparsed{font-size:13px;color:var(--muted)}
.controls{margin-left:auto;display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;font:14px system-ui,sans-serif}
.controls label{display:flex;align-items:center;gap:6px;cursor:pointer}
button{font:13px system-ui,sans-serif;padding:2px 10px;border:1px solid var(--line);border-radius:6px;
       background:var(--chip);color:var(--fg);cursor:pointer}
button:hover{color:var(--accent)}
.quiz-only{display:none}
body.quiz .quiz-only{display:flex}
/* hide mode (ignored while quizzing) */
body.hide:not(.quiz) td.f{cursor:pointer}
body.hide:not(.quiz) td.f:not(.shown){color:transparent;background:var(--chip)}
body.hide:not(.quiz) td.f:not(.shown):hover{background:var(--line)}
/* quiz mode */
.bhead{display:flex;align-items:baseline;gap:12px;margin:22px 0 6px}
.bhead h3{margin:0}
.grader{display:none;align-items:baseline;gap:10px}
body.quiz .grader{display:flex}
.score{font:600 13px system-ui,sans-serif;color:var(--muted)}
td.f input{display:none;width:100%;min-width:7em;font:inherit;color:var(--fg);background:transparent;
           border:1px solid var(--line);border-radius:4px;padding:2px 5px}
body.quiz td.f input{display:block}
body.quiz td.f .t{display:none}
body.quiz td.f.ok{background:var(--ok)}
body.quiz td.f.bad{background:var(--bad)}
#macrons{position:fixed;right:16px;bottom:16px;z-index:3;display:none;gap:4px;padding:6px;
         background:var(--head);border:1px solid var(--line);border-radius:10px;box-shadow:0 2px 10px #0003}
body.quiz #macrons{display:flex}
#macrons button{font:18px/1 Georgia,serif;width:2em;height:2em;padding:0}
"""

JS = """
const body = document.body;
const $ = id => document.getElementById(id);

// hide mode: click a blanked cell to reveal it
$('hide').addEventListener('change', e => {
  body.classList.toggle('hide', e.target.checked);
  document.querySelectorAll('td.f.shown').forEach(c => c.classList.remove('shown'));
});
document.addEventListener('click', e => {
  const c = e.target.closest('td.f');
  if (c && body.classList.contains('hide') && !body.classList.contains('quiz')) c.classList.toggle('shown');
});

// quiz mode: a text box in every form cell
document.querySelectorAll('td.f').forEach(c => {
  const i = document.createElement('input');
  i.type = 'text'; i.autocomplete = 'off'; i.spellcheck = false;
  i.setAttribute('autocapitalize', 'off');
  c.appendChild(i);
});
$('quiz').addEventListener('change', e => body.classList.toggle('quiz', e.target.checked));

// floating macron keyboard: types into the focused (or last focused) quiz box
let lastInput = null;
document.addEventListener('focusin', e => { if (e.target.matches('td.f input')) lastInput = e.target; });
$('macrons').addEventListener('mousedown', e => e.preventDefault());  // keep focus in the text box
$('macrons').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b || !lastInput) return;
  const ch = e.shiftKey ? b.textContent.toUpperCase() : b.textContent;
  lastInput.focus();
  lastInput.setRangeText(ch, lastInput.selectionStart, lastInput.selectionEnd, 'end');
  lastInput.dispatchEvent(new Event('input', {bubbles: true}));
});

const norm = s => {
  s = s.trim().replace(/\\s+/g, ' ').toLowerCase();
  if ($('nomacrons').checked) s = s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  return s;
};

function grade(block) {
  const cells = block.querySelectorAll('td.f');
  let right = 0;
  cells.forEach(c => {
    const answers = JSON.parse(c.dataset.a);
    const ok = answers.some(a => norm(a) === norm(c.querySelector('input').value));
    c.classList.toggle('ok', ok);
    c.classList.toggle('bad', !ok);
    c.title = ok ? '' : answers.join(', ');  // hover a red cell to see the answer
    right += ok;
  });
  const pct = cells.length ? Math.round(100 * right / cells.length) : 0;
  block.querySelector('.score').textContent = `${right} / ${cells.length} (${pct}%)`;
}

document.querySelectorAll('.block').forEach(b =>
  b.querySelector('.grade').addEventListener('click', () => grade(b)));
$('gradeall').addEventListener('click', () => document.querySelectorAll('.block').forEach(grade));
$('reset').addEventListener('click', () => {
  document.querySelectorAll('td.f').forEach(c => {
    c.querySelector('input').value = ''; c.classList.remove('ok', 'bad'); c.title = '';
  });
  document.querySelectorAll('.score').forEach(s => s.textContent = '');
});
"""


def h(s):
    return html.escape(str(s))


def td(forms):
    if not forms:
        return f'<td class="empty">{DASH}</td>'
    # data-a holds the accepted answers for quiz mode.
    return (f"<td class='f' data-a='{h(json.dumps(forms, ensure_ascii=False))}'>"
            f"<span class='t'>{'<br>'.join(h(f) for f in forms)}</span></td>")


def block(title, table):
    """A heading + table, with the quiz-mode Grade button and score beside the heading."""
    return (f"<div class='block'><div class='bhead'><h3>{title}</h3>"
            f"<span class='grader'><button type='button' class='grade'>Grade</button>"
            f"<span class='score'></span></span></div>"
            f"<div class='scroll'><table>{table}</table></div></div>")


def html_verb(lemma, verb, sum_finite, anchor):
    out = [f'<section class="verb" id="{anchor}"><h2>{h(lemma)}</h2>',
           f'<div class="meta">{h(verb["category"])} · {h(verb.get("title", ""))}</div>']
    for mood in verb["finite"]:
        rows, used = finite_rows(verb, mood, sum_finite)
        if not rows:
            continue
        sg = [s for s in used if s.endswith("sg")]
        pl = [s for s in used if s.endswith("pl")]
        t = ["<thead><tr><th colspan=2 rowspan=2></th>"]
        if sg:
            t.append(f"<th colspan={len(sg)}>singular</th>")
        if pl:
            t.append(f"<th colspan={len(pl)}>plural</th>")
        t.append("</tr><tr>" + "".join(f"<th>{SLOT_LABEL[s]}</th>" for s in used) + "</tr></thead><tbody>")
        voices = {}
        for voice, *_ in rows:
            voices[voice] = voices.get(voice, 0) + 1
        last = None
        for voice, tense, slots in rows:
            t.append("<tr>")
            if voice != last:
                t.append(f"<th rowspan={voices[voice]}>{h(voice)}</th>")
                last = voice
            t.append(f"<th>{h(tense)}</th>" + "".join(td(slots[s]) for s in used) + "</tr>")
        t.append("</tbody>")
        out.append(block(h(mood), "".join(t)))

    nf = verb.get("nonfinite", {})
    kinds = [k for k in ("infinitive", "participle") if k in nf]
    if kinds:
        t = ["<thead><tr><th rowspan=2></th><th colspan=3>active</th><th colspan=3>passive</th></tr><tr>"
             + "".join(f"<th>{t}</th>" for t in NF_TENSES * 2) + "</tr></thead><tbody>"]
        for k in kinds:
            t.append(f"<tr><th>{k}s</th>" + "".join(
                td(nf[k].get(v, {}).get(t, [])) for v in ("active", "passive") for t in NF_TENSES) + "</tr>")
        t.append("</tbody>")
        out.append(block("infinitives &amp; participles", "".join(t)))
    for k in ("gerund", "supine"):
        if k in nf:
            cases = [c for c in CASES if c in nf[k]]
            out.append(block(k, "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cases)
                             + "</tr></thead><tbody><tr>" + "".join(td(nf[k][c]) for c in cases)
                             + "</tr></tbody>"))
    if verb.get("unparsed"):
        out.append("<h3>unparsed cells</h3><ul class='unparsed'>" + "".join(
            f"<li>{h(u['form'])} ← {h(' | '.join(u['labels']))}</li>" for u in verb["unparsed"]) + "</ul>")
    out.append("</section>")
    return "".join(out)


def write_html(data, verbs, sum_finite, path):
    anchors = {lemma: f"v{i}" for i, lemma in enumerate(verbs)}
    nav = "".join(f'<a href="#{anchors[l]}">{h(l)}</a>' for l in verbs)
    body = "".join(html_verb(l, verbs[l], sum_finite, anchors[l]) for l in verbs)
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Latin Conjugations</title><style>{CSS}</style></head><body>"
            f"<nav>{nav}<div class='controls'>"
            f"<label><input type='checkbox' id='hide'> Hide forms</label>"
            f"<label><input type='checkbox' id='quiz'> Quiz mode</label>"
            f"<span class='quiz-only' style='gap:8px;align-items:center'>"
            f"<label><input type='checkbox' id='nomacrons' checked> Ignore macrons</label>"
            f"<button type='button' id='gradeall'>Grade All</button>"
            f"<button type='button' id='reset'>Clear</button></span>"
            f"</div></nav>"
            f"<div id='macrons' title='Shift-click for capitals'>"
            + "".join(f"<button type='button'>{v}</button>" for v in "āēīōūȳ")
            + f"</div><main>{body}"
            f"<p class='meta'>Source: {h(data.get('source', ''))}, retrieved {h(data.get('retrieved', ''))}</p>"
            f"</main><script>{JS}</script></body></html>")
    Path(path).write_text(page, encoding="utf-8")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", default="latin_conjugations.json")
    ap.add_argument("-o", "--out", default="latin_conjugations.html")
    ap.add_argument("--text", action="store_true", help="print to the terminal instead of writing HTML")
    ap.add_argument("--verb", help="show only this verb (macrons optional)")
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    verbs = data["verbs"]
    sum_finite = verbs.get("sum", {}).get("finite")

    if args.verb:
        want = strip_macrons(args.verb).lower()
        verbs = {l: v for l, v in verbs.items()
                 if strip_macrons(l).lower() == want or v.get("page") == want}
        if not verbs:
            sys.exit(f"No verb matching '{args.verb}' in {args.input}")

    if args.text:
        for lemma, verb in verbs.items():
            print_verb(lemma, verb, sum_finite)
    else:
        write_html(data, verbs, sum_finite, args.out)
        print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
