#!/usr/bin/env python3
"""
Display the conjugation tables in wikt_out/latin_conjugations.json, and the declension
tables in wikt_out/latin_declensions.json when it exists.

    python show_conjugations.py                     # writes docs/conjugations.html + docs/declensions.html
    python show_conjugations.py --text              # prints the tables in the terminal
    python show_conjugations.py --text --verb amō   # just one verb (macrons optional: amo)
    python show_conjugations.py -i other.json -o other.html

Periphrastic cells such as "amātus + present active indicative of sum"
are expanded into real forms (amātus sum, amātus es, …) using the sum
table from the same file, when it is there.

The web pages are built by html_output.py, from the templates in templates/
(found relative to this script, or pass -t / --nouns-template); the terminal
tables by text_output.py.

Standard library only.
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from html_output import DECL_TEMPLATE, TEMPLATE, write_declensions, write_html
from text_output import print_verb


def strip_macrons(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", default="wikt_out/latin_conjugations.json")
    ap.add_argument("-o", "--out", default="docs/conjugations.html")
    ap.add_argument("-t", "--template", default=TEMPLATE, help="HTML page template")
    ap.add_argument("--nouns-input", default="wikt_out/latin_declensions.json",
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
