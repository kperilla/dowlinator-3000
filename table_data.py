"""
Helpers for reading the tables in wikt_out/latin_conjugations.json, shared by the
terminal output (text_output.py) and the web pages (html_output.py).

Standard library only.
"""

import re

SLOTS = ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]
SLOT_LABEL = {"1sg": "1st", "2sg": "2nd", "3sg": "3rd", "1pl": "1st", "2pl": "2nd", "3pl": "3rd"}
NF_TENSES = ["present", "perfect", "future"]
CASES = ["genitive", "dative", "accusative", "ablative"]
DASH = "—"

PERIPHRASTIC = re.compile(
    r"^(?P<part>.+?)\s*\+\s*(?P<tense>[\w ]+?)\s+active\s+(?P<mood>indicative|subjunctive)\s+of\s+sum$")


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


def finite_rows(verb, mood, sum_finite):
    """[(voice, tense, {slot: [forms]})] for one mood, plus the slots actually used."""
    rows = []
    for voice, tenses in verb["finite"].get(mood, {}).items():
        for tense, slots in tenses.items():
            rows.append((voice, tense, {s: expand(slots.get(s, []), s, sum_finite) for s in SLOTS}))
    used = [s for s in SLOTS if any(r[2][s] for r in rows)]
    return rows, used
