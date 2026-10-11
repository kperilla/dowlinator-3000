#!/usr/bin/env python3
"""
Scrape full conjugation tables for representative Latin verbs from
English Wiktionary and write them to one JSON file.

    pip install requests beautifulsoup4
    python wikt_latin_verbs.py                  # writes latin_conjugations.json
    python wikt_latin_verbs.py -o verbs.json --refresh

Raw page HTML is cached in ./wikt_cache, so reruns don't hit Wiktionary
again (use --refresh to re-download).

Output shape (all forms keep their macrons; every value is a list,
because some slots have alternates such as amāris / amāre):

{
  "source": "en.wiktionary.org", "retrieved": "2026-10-11",
  "verbs": {
    "amō": {
      "page": "amo",
      "category": "1st conjugation",
      "title": "Conjugation of amō (first conjugation)",
      "finite": {
        "indicative": {
          "active": {
            "present": {"1sg": ["amō"], "2sg": ["amās"], ... "3pl": ["amant"]},
            "imperfect": {...}, ...
          },
          "passive": {...}
        },
        "subjunctive": {...},
        "imperative": {...}
      },
      "nonfinite": {
        "infinitive": {"active": {"present": ["amāre"], ...}, "passive": {...}},
        "participle": {"active": {...}, "passive": {...}},
        "gerund":     {"genitive": [...], "dative": [...], "accusative": [...], "ablative": [...]},
        "supine":     {"accusative": [...], "ablative": [...]}
      },
      "unparsed": [ {"form": "...", "labels": [...]} ]   # cells the script couldn't classify
    },
    ...
  }
}

Order: moods, voices and tenses appear in the order Wiktionary lists
them, so a table-building script can just iterate.
"""

import argparse
import datetime
import json
import pathlib
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

API = "https://en.wiktionary.org/w/api.php"
HEADERS = {"User-Agent": "latin-paradigm-scraper/1.0 (personal study script)"}

# (category, Wiktionary page title, an infinitive that identifies the right table)
# The infinitive check picks the right verb on pages that hold two
# (volō "want" vs volō "fly", edō "eat" vs ēdō "give out").
TARGETS = [
    ("1st conjugation",     "amo",    "amāre"),
    ("2nd conjugation",     "moneo",  "monēre"),
    ("3rd conjugation",     "rego",   "regere"),
    ("3rd conjugation -iō", "capio",  "capere"),
    ("4th conjugation",     "audio",  "audīre"),
    ("deponent (1st)",      "hortor", "hortārī"),
    ("deponent (3rd)",      "sequor", "sequī"),
    ("irregular",           "sum",    "esse"),
    ("irregular",           "possum", "posse"),
    ("irregular",           "eo",     "īre"),
    ("irregular",           "fero",   "ferre"),
    ("irregular",           "volo",   "velle"),
    ("irregular",           "nolo",   "nōlle"),
    ("irregular",           "malo",   "mālle"),
    ("irregular",           "fio",    "fierī"),
    ("irregular",           "edo",    "ēsse"),
    ("irregular",           "do",     "dare"),
]

EMPTY = {"", "-", "—", "–"}

MOODS = ["indicative", "subjunctive", "imperative"]
NONFINITE = {"infinitive": "infinitive", "participle": "participle",
             "gerund": "gerund", "supine": "supine"}
VOICES = ["active", "passive"]
CASES = ["nominative", "genitive", "dative", "accusative", "ablative"]
PERSONS = {"first": "1", "second": "2", "third": "3", "1st": "1", "2nd": "2", "3rd": "3"}


# ---------------------------------------------------------------- fetching

def fetch_page(page, cache_dir, refresh):
    path = cache_dir / f"{page}.html"
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    r = requests.get(API, headers=HEADERS, timeout=30, params={
        "action": "parse", "page": page, "prop": "text",
        "format": "json", "formatversion": "2", "redirects": "1"})
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"{page}: {data['error'].get('info')}")
    html = data["parse"]["text"]
    path.write_text(html, encoding="utf-8")
    time.sleep(1)  # be polite to Wiktionary
    return html


def latin_section(html):
    """Slice the page HTML down to the Latin language section."""
    m = re.search(r'<h2[^>]*id="Latin"', html)
    if not m:
        return None
    nxt = html.find("<h2", m.end())
    return html[m.start(): nxt if nxt != -1 else len(html)]


# ---------------------------------------------------------------- table → cells

def cell_text(cell):
    for sup in cell.find_all("sup"):  # footnote markers
        sup.decompose()
    for br in cell.find_all("br"):    # <br> separates alternate forms
        br.replace_with("\n")
    lines = [" ".join(l.split()) for l in cell.get_text().split("\n")]
    return "\n".join(l for l in lines if l)


def split_forms(text):
    parts = [p.strip() for p in text.split("\n")]
    out = []
    for p in parts:
        # Periphrastic cells ("amātus, -a, -um + sum") must not be comma-split.
        pieces = [p] if "+" in p else p.split(",")
        out += [x.strip() for x in pieces if x.strip() not in EMPTY]
    return out


def own_rows(table):
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def is_compound(cell):
    return "roa-compound-row" in (cell.get("class") or [])


def build_grid(table):
    """Expand rowspan/colspan into a rectangular grid of (cell, is_header)."""
    grid, pending = [], {}  # pending[(r, c)] = (cell, is_th)
    for r, tr in enumerate(own_rows(table)):
        row, c = [], 0
        cells = tr.find_all(["th", "td"], recursive=False)
        it = iter(cells)
        while True:
            if (r, c) in pending:
                row.append(pending.pop((r, c)))
                c += 1
                continue
            cell = next(it, None)
            if cell is None:
                break
            rs = int(cell.get("rowspan", 1) or 1)
            cs = int(cell.get("colspan", 1) or 1)
            # Periphrastic rows ("amātus + present active indicative of sum")
            # are <th> cells but hold content, not headers.
            entry = (cell, cell.name == "th" and not is_compound(cell))
            for dr in range(rs):
                for dc in range(cs):
                    if dr == 0:
                        row.append(entry)
                    else:
                        pending[(r + dr, c + dc)] = entry
            c += cs
        # leftover spanned cells at row end
        while (r, c) in pending:
            row.append(pending.pop((r, c)))
            c += 1
        grid.append(row)
    return grid


def labeled_cells(table):
    """Yield (forms, [header labels]) for each data cell slot."""
    grid = build_grid(table)
    width = max((len(r) for r in grid), default=0)
    texts = {}

    def txt(cell):
        k = id(cell)
        if k not in texts:
            texts[k] = cell_text(cell)
        return texts[k]

    def is_header_row(row):
        return all(is_th for _, is_th in row)

    def is_title(cell):
        return int(cell.get("colspan", 1) or 1) >= width - 1 and width > 3

    seen = set()
    for r, row in enumerate(grid):
        if is_header_row(row):
            continue
        tds = [i for i, (_, is_th) in enumerate(row) if not is_th]
        first_td = tds[0]
        # A single cell spanning the full row is a notes/footer row.
        if len({id(row[i][0]) for i in tds}) == 1 and len(tds) >= width - 1 \
                and not is_compound(row[first_td][0]):
            continue
        # Nearest block of header rows above this row.
        block, k = [], r - 1
        while k >= 0 and not is_header_row(grid[k]):
            k -= 1
        while k >= 0 and is_header_row(grid[k]):
            block.insert(0, grid[k])
            k -= 1
        for c in tds:
            cell = row[c][0]
            compound = is_compound(cell)
            key = id(cell) if compound else (id(cell), c)
            if key in seen:
                continue
            seen.add(key)
            labels = ["compound"] if compound else []

            def add(cell_):
                if is_title(cell_):
                    return
                t = txt(cell_)
                if t and t not in labels:
                    labels.append(t)

            for hrow in block:                     # block label, e.g. "indicative"
                for i in range(min(first_td, len(hrow))):
                    add(hrow[i][0])
            for hrow in block:                     # column labels, e.g. "singular", "first"
                if c < len(hrow) and not compound:  # a compound cell spans all persons
                    add(hrow[c][0])
            for i in range(c):                     # row labels, e.g. "active", "present"
                if row[i][1]:
                    add(row[i][0])
            forms = split_forms(txt(cell))
            if forms:
                yield forms, labels


def table_title(table):
    cell = table.find("caption") or table.find("th")
    return " ".join(cell.get_text(" ").split()) if cell else ""


# ---------------------------------------------------------------- labels → slots

def classify(labels):
    words = [l.lower() for l in labels]
    joined = " | ".join(words)
    info = {}
    for m in MOODS:
        if m in joined:
            info["mood"] = m
    for key, val in NONFINITE.items():
        if re.search(rf"\b{key}s?\b", joined):
            info["nonfinite"] = val
    for v in VOICES:
        if re.search(rf"\b{v}\b", joined):
            info["voice"] = v
    joined_t = joined.replace("future-perfect", "future perfect")
    # Multi-word tenses first, so "sigmatic future" isn't read as "future".
    for t in ("future perfect", "sigmatic future", "sigmatic aorist", "perfect potential",
              "pluperfect", "imperfect", "perfect", "future", "present"):
        if re.search(rf"\b{t}\b", joined_t):
            info["tense"] = t
            break
    if "compound" in words:
        info["compound"] = True
    for w in words:
        for p, n in PERSONS.items():
            if re.fullmatch(rf"{p}( person)?", w):
                info["person"] = n
    if re.search(r"\bsingular\b", joined):
        info["number"] = "sg"
    elif re.search(r"\bplural\b", joined):
        info["number"] = "pl"
    for case in CASES:
        if re.search(rf"\b{case}\b", joined):
            info["case"] = case
    return info


def put(tree, keys, forms):
    for k in keys[:-1]:
        tree = tree.setdefault(k, {})
    slot = tree.setdefault(keys[-1], [])
    for f in forms:
        if f not in slot:
            slot.append(f)


def parse_verb(table):
    finite, nonfinite, unparsed = {}, {}, []
    for forms, labels in labeled_cells(table):
        i = classify(labels)
        nf = i.get("nonfinite")
        if nf in ("gerund", "supine") and "case" in i:
            put(nonfinite, [nf, i["case"]], forms)
        elif nf in ("infinitive", "participle") and "voice" in i and "tense" in i:
            put(nonfinite, [nf, i["voice"], i["tense"]], forms)
        elif i.get("compound") and "mood" in i and "voice" in i and "tense" in i:
            # Periphrastic tense: one description covers all six persons.
            for slot in ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl"):
                put(finite, [i["mood"], i["voice"], i["tense"], slot], forms)
        elif "mood" in i and "voice" in i and "tense" in i and "person" in i and "number" in i:
            put(finite, [i["mood"], i["voice"], i["tense"], i["person"] + i["number"]], forms)
        else:
            unparsed.append({"form": " / ".join(forms), "labels": labels})
    return finite, nonfinite, unparsed


PERIPHRASTIC = re.compile(
    r"^(?P<part>.+?)\s*\+\s*(?P<tense>[\w ]+?)\s+active\s+(?P<mood>indicative|subjunctive)\s+of\s+sum$")


def expand_periphrastic(finite, sum_finite):
    """Replace 'amātus + present active indicative of sum' with 'amātus sum' etc.,
    using the scraped forms of sum (one entry per alternate, e.g. sim/siem/fuam)."""
    for tenses in (v for voices in finite.values() for v in voices.values()):
        for slots in tenses.values():
            for slot, forms in slots.items():
                out = []
                for f in forms:
                    m = PERIPHRASTIC.match(f)
                    aux = m and (sum_finite.get(m["mood"], {}).get("active", {})
                                 .get(m["tense"].strip(), {}).get(slot))
                    # "ēsus or ēssus" → one full form per participle spelling.
                    parts = re.split(r"\s+or\s+", m["part"]) if aux else []
                    for x in ([f"{p} {a}" for p in parts for a in aux] if aux else [f]):
                        if x not in out:
                            out.append(x)
                slots[slot] = out


def find_table(section_html, infinitive):
    soup = BeautifulSoup(section_html, "html.parser")
    for table in soup.find_all("table"):
        text = table.get_text(" ").lower()
        if "indicative" not in text:
            continue
        for td in table.find_all("td"):
            if infinitive in split_forms(cell_text(td)):
                return table
    return None


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default="latin_conjugations.json")
    ap.add_argument("--cache", default="wikt_cache")
    ap.add_argument("--refresh", action="store_true", help="re-download pages")
    args = ap.parse_args()
    cache = pathlib.Path(args.cache)
    cache.mkdir(exist_ok=True)

    out = {"source": "en.wiktionary.org (CC BY-SA)",
           "retrieved": datetime.date.today().isoformat(), "verbs": {}}
    for category, page, infinitive in TARGETS:
        try:
            html = fetch_page(page, cache, args.refresh)
        except Exception as e:
            print(f"{page:8} FETCH FAILED: {e}", file=sys.stderr)
            continue
        section = latin_section(html)
        table = find_table(section, infinitive) if section else None
        if table is None:
            print(f"{page:8} no conjugation table with '{infinitive}' found", file=sys.stderr)
            continue
        title = table_title(table)
        m = re.search(r"Conjugation of (\S+)", title)
        lemma = m.group(1) if m else page
        finite, nonfinite, unparsed = parse_verb(table)
        out["verbs"][lemma] = {"page": page, "category": category, "title": title,
                               "finite": finite, "nonfinite": nonfinite,
                               "unparsed": unparsed}
        n = sum(len(v) for m_ in finite.values() for vo in m_.values() for v in vo.values())
        print(f"{lemma:8} {category:20} {n:3} finite slots, "
              f"{len(unparsed)} unparsed", file=sys.stderr)

    sum_verb = next((v for v in out["verbs"].values() if v["page"] == "sum"), None)
    if sum_verb:
        for v in out["verbs"].values():
            expand_periphrastic(v["finite"], sum_verb["finite"])
    else:
        print("sum not scraped; periphrastic forms left unexpanded", file=sys.stderr)

    pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
