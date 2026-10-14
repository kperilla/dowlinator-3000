"""
Print conjugation tables in the terminal, for show_conjugations.py --text.

Standard library only.
"""

from table_data import CASES, DASH, NF_TENSES, SLOT_LABEL, finite_rows


def cell(forms):
    return ", ".join(forms) if forms else DASH


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
