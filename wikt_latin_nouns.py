#!/usr/bin/env python3
"""
Scrape declension tables for representative Latin nouns and pronouns from
English Wiktionary and write them to one JSON file.

    python wikt_latin_nouns.py                  # writes latin_declensions.json
    python wikt_latin_nouns.py -o nouns.json --refresh

Shares the page cache (./wikt_cache) and fetching code with wikt_latin_verbs.py.

Output shape (forms keep their macrons; every value is a list, because some
slots have alternates such as cīvēs / cīvīs):

{
  "source": "en.wiktionary.org (CC BY-SA)", "retrieved": "2026-10-11",
  "nouns": {
    "puella": {
      "pages": ["puella"],
      "category": "1st declension",
      "forms": {
        "singular": {"nominative": ["puella"], "genitive": ["puellae"], ...},
        "plural":   {...}
      },
      "unparsed": []
    },
    "hic": {
      "pages": ["hic"],
      "category": "demonstrative pronoun",
      "genders": ["masculine", "feminine", "neuter"],
      "forms": {
        "singular": {"masculine": {"nominative": ["hic"], ...}, "feminine": {...}, "neuter": {...}},
        "plural":   {...}
      },
      "unparsed": []
    },
    ...
  }
}

Entries without "genders" map number → case → forms; entries with it map
number → gender → case → forms. Cases appear in the order nominative,
genitive, dative, accusative, ablative, vocative, locative (locative only where
Wiktionary lists one). Pronouns have no vocative, and suī no nominative.
Some forms carry Wiktionary's anceps mark for a vowel that can be long or
short (egō̆, mihī̆, sibī̆).
"""

import argparse
import datetime
import json
import pathlib
import re
import sys

from bs4 import BeautifulSoup

from wikt_latin_verbs import EMPTY, build_grid, cell_text, fetch_page, latin_section

# (key, category, [(Wiktionary page, a form that identifies the right table), ...])
# The identifying form picks the right table on pages with several (quī has a
# relative and an interrogative table). An entry built from several pages has
# its tables merged: Wiktionary keeps ego (singular) and nōs (plural) apart.
TARGETS = [
    ("puella",   "1st declension",                [("puella", "puellārum")]),
    ("dominus",  "2nd declension",                [("dominus", "dominī")]),
    ("puer",     "2nd declension (-er)",          [("puer", "puerī")]),
    ("ager",     "2nd declension (-er)",          [("ager", "agrī")]),
    ("bellum",   "2nd declension neuter",         [("bellum", "bellī")]),
    ("rēx",      "3rd declension",                [("rex", "rēgis")]),
    ("corpus",   "3rd declension neuter",         [("corpus", "corporis")]),
    ("cīvis",    "3rd declension i-stem",         [("civis", "cīvium")]),
    ("mare",     "3rd declension neuter i-stem",  [("mare", "maribus")]),
    ("manus",    "4th declension",                [("manus", "manuum")]),
    ("cornū",    "4th declension neuter",         [("cornu", "cornibus")]),
    ("rēs",      "5th declension",                [("res", "rērum")]),
    ("diēs",     "5th declension",                [("dies", "diērum")]),
    ("deus",     "irregular noun",                [("deus", "deōrum")]),
    ("domus",    "irregular noun",                [("domus", "domuum")]),
    ("vīs",      "irregular noun",                [("vis", "vīrium")]),
    ("Iuppiter", "irregular noun",                [("Iuppiter", "Iovis")]),
    ("ego",      "personal pronoun (1st person)", [("ego", "meī"), ("nos", "nōbīs")]),
    ("tū",       "personal pronoun (2nd person)", [("tu", "tuī"), ("vos", "vōbīs")]),
    ("suī",      "reflexive pronoun",             [("sui", "sibī̆")]),
    ("is",       "demonstrative pronoun",         [("is", "eius")]),
    ("hic",      "demonstrative pronoun",         [("hic", "huius")]),
    ("ille",     "demonstrative pronoun",         [("ille", "illōrum")]),
    ("iste",     "demonstrative pronoun",         [("iste", "istōrum")]),
    ("ipse",     "intensive pronoun",             [("ipse", "ipsōrum")]),
    ("īdem",     "demonstrative pronoun",         [("idem", "eiusdem")]),
    ("quī",      "relative pronoun",              [("qui", "cuius")]),
    ("quis",     "interrogative pronoun",         [("quis", "quid")]),
]

CASES = ["nominative", "genitive", "dative", "accusative", "ablative", "vocative", "locative"]
NUMBERS = ["singular", "plural"]
GENDERS = {"masculine": "masculine", "feminine": "feminine", "neuter": "neuter",
           "m": "masculine", "f": "feminine", "n": "neuter"}


# ---------------------------------------------------------------- table → cells

def split_forms(text):
    """Alternates are separated by line breaks, commas or ' / '."""
    out = []
    for p in re.split(r"\n|,|\s/\s", text):
        p = p.strip().rstrip("/").strip()
        if p and p not in EMPTY:
            out.append(p)
    return out


def is_person_table(table):
    """The 'Latin personal and reflexive pronouns' overview shown on many pronoun pages."""
    return any(th.get_text(strip=True) in ("first", "second") for th in table.find_all("th"))


def find_table(section_html, form):
    soup = BeautifulSoup(section_html, "html.parser")
    for table in soup.find_all("table"):
        if "nominative" not in table.get_text(" ").lower() or is_person_table(table):
            continue
        for td in table.find_all("td"):
            if form in split_forms(cell_text(td)):
                return table
    return None


def labeled_cells(table):
    """Yield (forms, [labels]) per data cell: column headers above it, row headers left of it."""
    grid = build_grid(table)
    texts = {}

    def txt(cell):
        if id(cell) not in texts:
            texts[id(cell)] = cell_text(cell)
        return texts[id(cell)]

    # Data rows start with a case name; header rows are everything above the first one.
    first_data = next(r for r, row in enumerate(grid)
                      if row and any(txt(c).lower() in CASES for c, is_th in row if is_th))
    headers = grid[:first_data]
    for row in grid[first_data:]:
        # A cell spanning several columns (huius for all three genders) is
        # yielded once per column, so each gender gets the form.
        for c, (cell, is_th) in enumerate(row):
            if is_th:
                continue
            forms = split_forms(txt(cell))
            if not forms:
                continue
            labels = []
            for i in range(c):                       # row labels: case
                if row[i][1] and txt(row[i][0]) not in labels:
                    labels.append(txt(row[i][0]))
            for hrow in headers:                     # column labels: number, gender
                if c < len(hrow) and hrow[c][1] and txt(hrow[c][0]) not in labels:
                    labels.append(txt(hrow[c][0]))
            yield forms, labels


# ---------------------------------------------------------------- labels → slots

def classify(labels):
    words = [l.lower() for l in labels]
    info = {}
    for w in words:
        if w in CASES:
            info["case"] = w
        elif w in NUMBERS:
            info["number"] = w
        elif w in GENDERS:
            info["gender"] = GENDERS[w]
    return info


def put(tree, keys, forms):
    for k in keys[:-1]:
        tree = tree.setdefault(k, {})
    slot = tree.setdefault(keys[-1], [])
    for f in forms:
        if f not in slot:
            slot.append(f)


def sort_tree(tree):
    """Put numbers, genders and cases in canonical order, whatever order the tables came in."""
    def order(d, keys):
        return {k: d[k] for k in sorted(d, key=keys)}
    out = {}
    for number in sorted(tree, key=NUMBERS.index):
        sub = tree[number]
        if any(k in CASES for k in sub):
            out[number] = order(sub, CASES.index)
        else:
            gorder = list(dict.fromkeys(GENDERS.values()))
            out[number] = {g: order(sub[g], CASES.index) for g in sorted(sub, key=gorder.index)}
    return out


def parse_table(table, forms_tree, unparsed):
    for forms, labels in labeled_cells(table):
        i = classify(labels)
        if "case" in i and "number" in i:
            keys = [i["number"]] + ([i["gender"]] if "gender" in i else []) + [i["case"]]
            put(forms_tree, keys, forms)
        else:
            unparsed.append({"form": " / ".join(forms), "labels": labels})


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default="latin_declensions.json")
    ap.add_argument("--cache", default="wikt_cache")
    ap.add_argument("--refresh", action="store_true", help="re-download pages")
    args = ap.parse_args()
    cache = pathlib.Path(args.cache)
    cache.mkdir(exist_ok=True)

    out = {"source": "en.wiktionary.org (CC BY-SA)",
           "retrieved": datetime.date.today().isoformat(), "nouns": {}}
    for key, category, sources in TARGETS:
        forms, unparsed, pages = {}, [], []
        for page, ident in sources:
            try:
                html = fetch_page(page, cache, args.refresh)
            except Exception as e:
                print(f"{page:9} FETCH FAILED: {e}", file=sys.stderr)
                continue
            section = latin_section(html)
            table = find_table(section, ident) if section else None
            if table is None:
                print(f"{page:9} no declension table with '{ident}' found", file=sys.stderr)
                continue
            parse_table(table, forms, unparsed)
            pages.append(page)
        if not forms:
            continue
        entry = {"pages": pages, "category": category}
        if any(k not in CASES for n in forms.values() for k in n):
            entry["genders"] = [g for g in dict.fromkeys(GENDERS.values())
                                if any(g in n for n in forms.values())]
        entry["forms"] = sort_tree(forms)
        entry["unparsed"] = unparsed
        out["nouns"][key] = entry
        n = sum(1 for _ in _slots(entry["forms"]))
        print(f"{key:9} {category:30} {n:3} slots, {len(unparsed)} unparsed", file=sys.stderr)

    pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {args.out}", file=sys.stderr)


def _slots(tree):
    for v in tree.values():
        if isinstance(v, list):
            yield v
        else:
            yield from _slots(v)


if __name__ == "__main__":
    main()
