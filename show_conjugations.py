#!/usr/bin/env python3
"""
Display the conjugation tables in latin_conjugations.json, and the declension
tables in latin_declensions.json when it exists.

    python show_conjugations.py                     # writes docs/conjugations.html + docs/declensions.html
    python show_conjugations.py --text              # prints the tables in the terminal
    python show_conjugations.py --text --verb amō   # just one verb (macrons optional: amo)
    python show_conjugations.py -i other.json -o other.html

Periphrastic cells such as "amātus + present active indicative of sum"
are expanded into real forms (amātus sum, amātus es, …) using the sum
table from the same file, when it is there.

The pages' layout, styles and scripts live in conjugations_template.html and
declensions_template.html (next to this script, or pass -t / --nouns-template);
this script only fills in the words.

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

TEMPLATE = Path(__file__).with_name("conjugations_template.html")


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
            body = "".join(f"<tr><th>{h(tense)}</th>" + "".join(td(slots[s]) for s in used) + "</tr>"
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

DECL_TEMPLATE = Path(__file__).with_name("declensions_template.html")
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


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", default="latin_conjugations.json")
    ap.add_argument("-o", "--out", default="docs/conjugations.html")
    ap.add_argument("-t", "--template", default=TEMPLATE, help="HTML page template")
    ap.add_argument("--nouns-input", default="latin_declensions.json",
                    help="declensions JSON from wikt_latin_nouns.py (skipped if missing)")
    ap.add_argument("--nouns-out", default="docs/declensions.html")
    ap.add_argument("--nouns-template", default=DECL_TEMPLATE, help="declension page template")
    ap.add_argument("--text", action="store_true", help="print to the terminal instead of writing HTML")
    ap.add_argument("--verb", help="show only this verb (macrons optional); skips the declension page")
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
        write_html(data, verbs, sum_finite, args.out, args.template)
        print(f"Wrote {args.out}", file=sys.stderr)
        if args.verb:
            return
        nouns = Path(args.nouns_input)
        if nouns.exists():
            write_declensions(json.loads(nouns.read_text(encoding="utf-8")), args.nouns_out, args.nouns_template)
            print(f"Wrote {args.nouns_out}", file=sys.stderr)
        else:
            print(f"{nouns} not found; skipping the declension page "
                  f"(run wikt_latin_nouns.py to create it)", file=sys.stderr)


if __name__ == "__main__":
    main()
