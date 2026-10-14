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
uv run wikt_latin_nouns.py       # (optional) nouns & pronouns → latin_declensions.json
uv run show_conjugations.py      # build the pages  → docs/conjugations.html, docs/declensions.html
```

Then open `docs/index.html`, the homepage, in a browser and pick
**Declensions** or **Conjugations**. The title on each table page links back
home, and the links under it switch between the two. The homepage is a static
file in `docs/`; only the two table pages are generated. (Without uv, use
`python` in place of `uv run`.)

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

### Nouns and pronouns: `wikt_latin_nouns.py`

```sh
uv run wikt_latin_nouns.py                     # writes latin_declensions.json
uv run wikt_latin_nouns.py -o nouns.json --refresh
```

Same options as the verb scraper (`-o`, `--cache`, `--refresh`), sharing the same
page cache. It covers:

| Group | Words |
|---|---|
| 1st declension | puella |
| 2nd declension | dominus, puer, ager, bellum |
| 3rd declension | rēx, corpus, cīvis (i-stem), mare (neuter i-stem) |
| 4th declension | manus, cornū |
| 5th declension | rēs, diēs |
| Irregular nouns | deus, domus, vīs, Iuppiter |
| Pronouns | ego / nōs, tū / vōs, suī, is, hic, ille, iste, ipse, īdem, quī, quis |

Nouns map number → case → forms; pronouns that vary by gender also have a
`genders` list and map number → gender → case → forms:

```json
"cīvis": {"pages": ["civis"], "category": "3rd declension i-stem",
          "forms": {"singular": {"nominative": ["cīvis"], "ablative": ["cīve", "cīvī"], "...": []},
                    "plural":   {"genitive": ["cīvium"], "...": []}},
          "unparsed": []},
"hic":   {"pages": ["hic"], "category": "demonstrative pronoun",
          "genders": ["masculine", "feminine", "neuter"],
          "forms": {"singular": {"masculine": {"nominative": ["hic"], "...": []}, "...": {}}},
          "unparsed": []}
```

- Cases run nominative, genitive, dative, accusative, ablative, vocative, plus
  locative where Wiktionary gives one (*domī*, *bellī*, *diē*). Pronouns have no
  vocative, and *suī* no nominative.
- Wiktionary lists *ego* and *nōs* (and *tū* / *vōs*) on separate pages; each is
  merged into one entry, so `TARGETS` takes a list of `(page, identifying form)`
  pairs. To add a word, append an entry with a form that appears only in the
  table you want, e.g. `("lupus", "2nd declension", [("lupus", "lupōrum")])`.
- A few forms carry Wiktionary's anceps mark for a vowel that may be long or
  short: *egō̆*, *mihī̆*, *sibī̆*.

## 2. Viewing: `show_conjugations.py`

```sh
uv run show_conjugations.py                          # writes docs/conjugations.html + docs/declensions.html
uv run show_conjugations.py -i verbs.json -o verbs.html
uv run show_conjugations.py --text                   # print tables in the terminal
uv run show_conjugations.py --text --verb amō        # one verb (macrons optional: amo)
uv run show_conjugations.py --verb sum               # HTML page for one verb
```

| Option | Default | Meaning |
|---|---|---|
| `-i`, `--input` | `latin_conjugations.json` | JSON file to read |
| `-o`, `--out` | `docs/conjugations.html` | Conjugation page to write |
| `-t`, `--template` | `conjugations_template.html` | Conjugation page template (looked up next to the script) |
| `--nouns-input` | `latin_declensions.json` | Declensions JSON; the declension page is skipped if it's missing |
| `--nouns-out` | `docs/declensions.html` | Declension page to write |
| `--nouns-template` | `declensions_template.html` | Declension page template |
| `--text` | off | Print verbs to the terminal instead of writing HTML |
| `--verb` | all | Only this verb (lemma or page name, macrons optional); skips the declension page |

The declension page groups words by declension (1st–5th, irregular nouns,
pronouns), with one table per word: cases down the side, singular and plural
across, split by gender for pronouns such as *hic* and *quī*. Hide forms, Quiz
mode, grading and the macron shortcuts all work the same as on the conjugation
page.

The pages link to each other by file name (`index.html`, `conjugations.html`,
`declensions.html`), so keep them together in `docs/`; if you rename one with
`-o` / `--nouns-out`, update the links in `docs/index.html` and under `<h1>` in
both templates.

### Page templates

Each page's layout and controls live in its template:
`conjugations_template.html` and `declensions_template.html`. The script reads
them and replaces these markers:

| Template | Marker | Replaced with |
|---|---|---|
| conjugations | `<!-- VERB_NAV -->` | a link to each verb, in the top bar |
| conjugations | `<!-- VERBS -->` | one `<section class="verb">` per verb, holding its tables |
| declensions | `<!-- NOUN_NAV -->` | a link to each group (1st declension, …, pronouns) |
| declensions | `<!-- NOUNS -->` | one `<section class="group">` per group, a table per word |
| both | `<!-- SOURCE -->` | the data source and retrieval date |

Styles and scripts live in `docs/` next to the pages, and are edited there
directly (no rerun needed):

| File | Used by | Holds |
|---|---|---|
| `tables.css` | both table pages | shared layout, table, hide and quiz styles |
| `conjugations.css` | conjugations | conjugation-only rules |
| `declensions.css` | declensions | declension-only rules (side-by-side noun tables) |
| `tables.js` | both table pages | the hide, quiz and macron-input logic |
| `index.css` | `index.html` | landing page styles |

Each form cell is generated as `<td class="f" data-a='["amāvistī","amāstī"]'>`,
with its accepted answers in `data-a`, which is what the template's quiz
script grades against. Rerun `show_conjugations.py` after editing a template.

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
