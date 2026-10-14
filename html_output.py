"""
Build the web pages, docs/conjugations.html and docs/declensions.html, for
show_conjugations.py.

The pages' layout lives in templates/ (conjugations_template.html and
declensions_template.html, found relative to this file), which link the styles
and scripts in docs/ (tables.css, tables.js, conjugations.css, declensions.css);
this module only fills in the words.

Standard library only.
"""

import html
import json
import re
import sys
from pathlib import Path

from table_data import CASES, DASH, NF_TENSES, SLOT_LABEL, finite_rows

TEMPLATES = Path(__file__).with_name("templates")
TEMPLATE = TEMPLATES / "conjugations_template.html"


def h(s):
    return html.escape(str(s))


def td(forms):
    if not forms:
        return f'<td class="empty">{DASH}</td>'
    # data-a holds the accepted answers for quiz mode.
    return (f"<td class='f' data-a='{h(json.dumps(forms, ensure_ascii=False))}'>"
            f"<span class='t'>{'<br>'.join(h(f) for f in forms)}</span></td>")


def block(title, table, h3_class="", note="", wide=False):
    """A heading + table, with the quiz-mode Grade button and score beside the heading."""
    cls = f" class='{h3_class}'" if h3_class else ""
    return (f"<div class='block{' wide' if wide else ''}'><div class='bhead'><h3{cls}>{title}</h3>{note}"
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
        head = ["<thead><tr><th rowspan=2></th>"]
        if sg:
            head.append(f"<th colspan={len(sg)}>singular</th>")
        if pl:
            head.append(f"<th colspan={len(pl)}>plural</th>")
        head.append("</tr><tr>" + "".join(f"<th>{SLOT_LABEL[s]}</th>" for s in used) + "</tr></thead>")
        # One table (and Grade button) per voice.
        for voice in dict.fromkeys(v for v, *_ in rows):
            # Archaic sigmatic tenses (amāssō, amāssim) are hidden unless "Include sigmatic" is on.
            body = "".join(f"<tr{' class=sigmatic' if tense.startswith('sigmatic') else ''}><th>{h(tense)}</th>"
                           + "".join(td(slots[s]) for s in used) + "</tr>"
                           for v, tense, slots in rows if v == voice)
            out.append(block(f"{h(mood)} {h(voice)}", "".join(head) + f"<tbody>{body}</tbody>"))

    nf = verb.get("nonfinite", {})
    kinds = [k for k in ("infinitive", "participle") if k in nf]
    for v in ("active", "passive"):
        if not any(nf[k].get(v) for k in kinds):
            continue
        t = ["<thead><tr><th></th>" + "".join(f"<th>{t}</th>" for t in NF_TENSES) + "</tr></thead><tbody>"]
        for k in kinds:
            t.append(f"<tr><th>{k}s</th>" + "".join(td(nf[k].get(v, {}).get(t, [])) for t in NF_TENSES) + "</tr>")
        t.append("</tbody>")
        out.append(block(f"{v} infinitives &amp; participles", "".join(t)))
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


def source_line(data):
    return f"Source: {h(data.get('source', ''))}, retrieved {h(data.get('retrieved', ''))}"


def fill_template(template, fill, path):
    """Replace each <!-- NAME --> marker in the template with fill[NAME] and write the page."""
    page = Path(template).read_text(encoding="utf-8")
    for name, content in fill.items():
        marker = f"<!-- {name} -->"
        if marker not in page:
            sys.exit(f"{template} has no {marker} marker")
        page = page.replace(marker, content)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(page, encoding="utf-8")


def write_html(data, verbs, sum_finite, path, template=TEMPLATE):
    """Fill the conjugation template's VERB_NAV, VERBS and SOURCE markers."""
    anchors = {lemma: f"v{i}" for i, lemma in enumerate(verbs)}
    fill_template(template, {
        "VERB_NAV": "".join(f'<a href="#{anchors[l]}">{h(l)}</a>' for l in verbs),
        "VERBS": "".join(html_verb(l, verbs[l], sum_finite, anchors[l]) for l in verbs),
        "SOURCE": source_line(data),
    }, path)


# ---------------------------------------------------------------- declension page

DECL_TEMPLATE = TEMPLATES / "declensions_template.html"
NOUN_CASES = ["nominative", "genitive", "dative", "accusative", "ablative", "vocative", "locative"]
GENDER_LABEL = {"masculine": "masc.", "feminine": "fem.", "neuter": "neut."}


def group_of(category):
    """'3rd declension i-stem' → '3rd declension'; pronouns and irregular nouns get their own groups."""
    m = re.match(r"\d\w\w declension", category)
    if m:
        return m.group(0)
    return "pronouns" if "pronoun" in category else "irregular nouns"


def html_noun(key, noun):
    """One table for a noun or pronoun: cases down the side, number (and gender) across."""
    forms, genders = noun["forms"], noun.get("genders")
    numbers = [n for n in ("singular", "plural") if n in forms]
    if genders:
        cols = [(n, g) for n in numbers for g in genders]
        get = lambda n, g, c: forms[n].get(g, {}).get(c, [])
        head = ("<thead><tr><th rowspan=2></th>"
                + "".join(f"<th colspan={len(genders)}>{n}</th>" for n in numbers) + "</tr><tr>"
                + "".join(f"<th>{GENDER_LABEL.get(g, h(g))}</th>" for _, g in cols) + "</tr></thead>")
    else:
        cols = [(n, None) for n in numbers]
        get = lambda n, g, c: forms[n].get(c, [])
        head = "<thead><tr><th></th>" + "".join(f"<th>{n}</th>" for n in numbers) + "</tr></thead>"
    cases = [c for c in NOUN_CASES if any(get(n, g, c) for n, g in cols)]
    body = "".join(f"<tr><th>{c}</th>" + "".join(td(get(n, g, c)) for n, g in cols) + "</tr>"
                   for c in cases)
    out = block(h(key), head + f"<tbody>{body}</tbody>", h3_class="word",
                note=f"<span class='cat'>{h(noun['category'])}</span>", wide=bool(genders))
    if noun.get("unparsed"):
        out += "<ul class='unparsed'>" + "".join(
            f"<li>{h(u['form'])} ← {h(' | '.join(u['labels']))}</li>" for u in noun["unparsed"]) + "</ul>"
    return out


def write_declensions(data, path, template=DECL_TEMPLATE):
    """Fill the declension template's NOUN_NAV, NOUNS and SOURCE markers."""
    groups = {}
    for key, noun in data["nouns"].items():
        groups.setdefault(group_of(noun["category"]), []).append((key, noun))
    anchors = {g: f"g{i}" for i, g in enumerate(groups)}
    fill_template(template, {
        "NOUN_NAV": "".join(f'<a href="#{anchors[g]}">{h(g)}</a>' for g in groups),
        "NOUNS": "".join(f'<section class="group" id="{anchors[g]}"><h2>{h(g)}</h2><div class="words">'
                         + "".join(html_noun(k, n) for k, n in words) + "</div></section>"
                         for g, words in groups.items()),
        "SOURCE": source_line(data),
    }, path)
