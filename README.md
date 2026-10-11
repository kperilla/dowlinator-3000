# latin-form-helper

Study Latin verb conjugations. One script scrapes full conjugation tables from
English Wiktionary into a JSON file; a second turns that file into a single HTML
page with tables you can hide, reveal cell by cell, or fill in as a graded quiz.

> **Note:** This project was written with the help of AI (Anthropic's Claude, via
> Claude Code). The code has been reviewed and run, but check the forms against a
> grammar if something looks off — and please report it.

## Setup

Requires Python 3.13+. With [uv](https://docs.astral.sh/uv/):

```sh
uv sync
```

Or with pip:

```sh
pip install requests beautifulsoup4
```

`show_conjugations.py` uses only the standard library; `requests` and
`beautifulsoup4` are needed only for scraping.

## Quick start

```sh
uv run wikt_latin_verbs.py       # scrape Wiktionary → latin_conjugations.json
uv run show_conjugations.py      # build the page   → latin_conjugations.html
```

Then open `latin_conjugations.html` in a browser. (Without uv, use `python` in
place of `uv run`.)

## 1. Scraping: `wikt_latin_verbs.py`

```sh
uv run wikt_latin_verbs.py                     # writes latin_conjugations.json
uv run wikt_latin_verbs.py -o verbs.json       # different output file
uv run wikt_latin_verbs.py --refresh           # re-download every page
uv run wikt_latin_verbs.py --cache my_cache    # different cache directory
```

| Option | Default | Meaning |
|---|---|---|
| `-o`, `--out` | `latin_conjugations.json` | Output JSON file |
| `--cache` | `wikt_cache` | Where raw page HTML is cached |
| `--refresh` | off | Ignore the cache and download again |

Pages are cached in `wikt_cache/`, so reruns don't contact Wiktionary. Downloads
are spaced one second apart.

### Which verbs

The verbs are listed in `TARGETS` near the top of the script — one per regular
conjugation plus deponents and the common irregulars:

amō, moneō, regō, capiō, audiō, hortor, sequor, sum, possum, eō, ferō, volō,
nōlō, mālō, fīō, edō, dō

To add a verb, append a line with a category label, the Wiktionary page title
(no macrons), and its infinitive *with* macrons. The infinitive picks the right
table on pages that hold more than one verb (e.g. *edō* "eat" vs *ēdō* "give out"):

```python
("2nd conjugation", "video", "vidēre"),
```

Keep `sum` in the list: its forms are used to build the compound tenses of every
other verb.

### Output format

Every slot holds a list of forms, because many slots have accepted variants
(*amāvistī* / *amāstī*). Forms keep their macrons.

```json
{
  "source": "en.wiktionary.org (CC BY-SA)",
  "retrieved": "2026-10-11",
  "verbs": {
    "amo": {
      "page": "amo",
      "category": "1st conjugation",
      "finite": {
        "indicative": {
          "active":  { "present": { "1sg": ["amō"], "2sg": ["amās"], "...": [] } },
          "passive": { "perfect": { "1sg": ["amātus sum"], "...": [] } }
        },
        "subjunctive": { "...": {} },
        "imperative":  { "...": {} }
      },
      "nonfinite": {
        "infinitive": { "active": { "present": ["amāre"] }, "passive": { "...": [] } },
        "participle": { "active": { "present": ["amāns"] }, "passive": { "...": [] } },
        "gerund": { "genitive": ["amandī"], "dative": ["amandō"], "...": [] },
        "supine": { "accusative": ["amātum"], "ablative": ["amātū"] }
      },
      "unparsed": []
    }
  }
}
```

- **Persons:** `1sg 2sg 3sg 1pl 2pl 3pl`.
- **Tenses** include the archaic *sigmatic future* (*amāssō*), *sigmatic aorist*
  subjunctive (*amāssim*) and *perfect potential* infinitive where Wiktionary lists them.
- **Compound tenses** (perfect passive, deponent perfects, …) are written out in
  full with every form of *sum*: `["audītus sim", "audītus siem", "audītus fuam"]`.
  Where the participle has two spellings, each gets its own entry
  (`["ēsus erimus", "ēssus erimus"]`).
- **`unparsed`** lists any table cells the script couldn't place. It is empty for
  all the verbs above; if you add a verb and it isn't, the labels there show why.
- Moods, voices and tenses appear in the order Wiktionary gives them.

## 2. Viewing: `show_conjugations.py`

```sh
uv run show_conjugations.py                          # writes latin_conjugations.html
uv run show_conjugations.py -i verbs.json -o verbs.html
uv run show_conjugations.py --text                   # print tables in the terminal
uv run show_conjugations.py --text --verb amō        # one verb (macrons optional: amo)
uv run show_conjugations.py --verb sum               # HTML page for one verb
```

| Option | Default | Meaning |
|---|---|---|
| `-i`, `--input` | `latin_conjugations.json` | JSON file to read |
| `-o`, `--out` | `latin_conjugations.html` | HTML file to write |
| `-t`, `--template` | `conjugations_template.html` | Page template (looked up next to the script) |
| `--text` | off | Print to the terminal instead of writing HTML |
| `--verb` | all | Only this verb (lemma or page name, macrons optional) |

### Page template

The page's layout, styles, controls and JavaScript live in
`conjugations_template.html`; edit that file to change how the page looks or
behaves. The script reads it and replaces three markers:

| Marker | Replaced with |
|---|---|
| `<!-- VERB_NAV -->` | a link to each verb, in the top bar |
| `<!-- VERBS -->` | one `<section class="verb">` per verb, holding its tables |
| `<!-- SOURCE -->` | the data source and retrieval date |

Each form cell is generated as `<td class="f" data-a='["amāvistī","amāstī"]'>`,
with its accepted answers in `data-a`, which is what the template's quiz
script grades against. Rerun `show_conjugations.py` after editing the template.

On Windows, if `--text` fails with a `UnicodeEncodeError`, set
`PYTHONIOENCODING=utf-8` (or run `chcp 65001`) so the console can print macrons.

## Using the page

The bar at the top links to each verb and holds the controls.

### Hide forms (on by default)

Every form is blanked out. Click a cell to reveal it, click again to hide it.
Untick **Hide forms** to show everything; ticking it again hides all cells anew.
Cells marked — (slots with no form, such as the 1st-person imperative) stay visible.

### Quiz mode

Tick **Quiz mode** to replace every form with a text box.

- **Grade** (next to each table heading) checks that table; **Grade All** in the
  top bar checks every table on the page.
- Correct cells turn green, wrong or empty ones red. Hover over a red cell to see
  the accepted answer(s).
- Each graded table shows a score, e.g. `14 / 18 (78%)`.
- An answer is correct if it matches **any** accepted variant. Case and extra
  spaces are ignored.
- **Ignore macrons** (on by default) accepts `amasti` for *amāstī*. Untick it to
  require exact macrons.
- **Clear** empties every box and resets colours and scores.
- Compound tenses need the whole form: `amātus sum`.

### Typing macrons

- **Shortcut:** type a vowel followed by `-`: `a-` → `ā`, so `ama-vi-` gives
  *amāvī*. Works for a e i o u y and their capitals.
- **Floating keyboard:** in quiz mode a box of ā ē ī ō ū ȳ buttons stays in the
  bottom-right corner as you scroll. Clicking one types into the text box you're
  in (or the last one you used); Shift-click for capitals.

## Known limitations

- Compound tenses use the masculine singular participle in every person, as
  Wiktionary gives it: the data has *amātus sumus*, not *amātī sumus*, and the
  quiz only accepts the former.
- Verbs are keyed by page name (`amo`) rather than lemma (`amō`), because the
  Wiktionary table has no caption to read the lemma from.
- The page's infinitive table shows present, perfect and future; the
  future-perfect and perfect-potential infinitives are in the JSON but not displayed.

## Data and licence

Conjugation data comes from [English Wiktionary](https://en.wiktionary.org/) and
is available under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
If you share the generated JSON or HTML, keep that attribution.
