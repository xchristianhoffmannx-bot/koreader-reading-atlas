# KOReader Reading Atlas

A **spoiler-free atlas of the books you read**. For every book it builds one self-contained web page with the characters, their relationships, a timeline, the places on a map and a discovery journal. The page **grows with your reading position**: you only ever see what the text you have actually read tells you, and a slider lets you look at the world as it was after any earlier chapter.

It is the companion to [koreader-reading-recap](https://github.com/xchristianhoffmannx-bot/koreader-reading-recap): the recap plugin tells this tool how far you have read; this tool turns the text up to that point into an atlas. You use **your own AI account** (a Codex CLI login or your own OpenAI, Anthropic or Google Gemini API key).

## What you get

- **Characters and relationships** as a list with search, and a relationship network of the most connected characters. Each character has a growing profile (appearance, traits, origin) and a note where every detail came from ("chapter, about 45 % in").
- **Timeline** of events in story order, filterable by plot line.
- **Places** on a present-day map (Natural Earth coastlines, positions from OpenStreetMap) with small numbered pins that appear as the story reaches them. The map is cropped to the places; one far-away place sits at the edge with an arrow instead of shrinking the rest. Names show for the current place and on a first tap, a second tap jumps to the location entry.
- **Time slider**: "The world at this point". Every view, search and note respects it.
- **Discovery journal**: what became known and when, a short animated reveal when your world has grown, bookmarks and your own notes (clearly marked as guesses, never turned into book facts). Backup and restore as a JSON file.
- **Optional portraits** of main characters, drawn only from appearance details the text states, labelled as AI interpretation. Off by default, because image generation costs money.
- German and English interface and texts. Books can be in any language.

The page is a single HTML file: it works offline on a phone, you can keep it in a synced folder (for example Google Drive) and open it from there.

## Status

Early release. The pipeline was developed on a jailbroken Kindle running KOReader and Windows, with the Codex CLI. The API-provider code paths (OpenAI, Anthropic, Gemini, and the OpenAI Images API for portraits) are covered by tests with simulated answers but have **not been tried against the live services yet**. Model names are not hard-coded; you set the exact model ID of your account.

The reading position comes from the koreader-reading-recap plugin (Windows companion). The Python code itself is platform-neutral; the device pipeline is tested on Windows only. Supported books: **DRM-free EPUB**. This project contains no books, no way to remove DRM and no data.

## How it works

1. The recap plugin on your reader exports the position (KOReader XPointer) you have reached. `reading-atlas build --device <drive>` reads it.
2. The EPUB is split into story chapters (cover, contents, cast list, map, blurb and other front/back matter are never used: they would reveal the plot). For each chapter, up to your position, an AI request extracts **new** facts with a source paragraph for each.
3. Python checks the source of every fact: the cited paragraph must lie inside what you have read and name the character or place involved (as whole words). Facts that fail are discarded, not shown. The descriptive sentences of a fact are the AI's paraphrase; they are not compared with the text. A second pass asks for forgotten characters, including nameless ones such as "the prisoner".
4. Knowledge only grows: a known character is never dropped; wording changes only through an explicit correction in the text.
5. One HTML page per book is written. It contains only states up to your reading position, so a later chapter cannot leak even if someone reads the page source.

Details: [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md). What is sent where, what is stored, copyright: [docs/PRIVACY-AND-COPYRIGHT.md](docs/PRIVACY-AND-COPYRIGHT.md).

## Requirements

- Python **3.11 or newer**. No other packages are needed (Pillow only for portraits).
- koreader-reading-recap installed on the reader if you want positions from the device. Without it you can set a position by hand.
- Your own AI access: the [Codex CLI](https://developers.openai.com/codex/cli/) signed in with your account, **or** an API key for OpenAI, Anthropic or Google Gemini.
- Internet access and allowance/billing with your provider. A first read of a long book makes many requests, one per roughly 30,000 characters of text. `reading-atlas add-book` shows an estimate before anything is sent.

## Install and first run

```bash
git clone <this repository>
cd koreader-reading-atlas
python -m pip install .          # add ".[portraits]" for portraits
reading-atlas init               # creates your data home and config.json
reading-atlas doctor             # checks provider, tools, settings
```

Your data home is `~/ReadingAtlas` (or the folder in the environment variable `READING_ATLAS_HOME`). Everything personal lives there, never in this repository.

**AI provider.** If you already ran `configure.ps1` of koreader-reading-recap, the same provider and key are used. Otherwise set environment variables:

| Provider | Variables |
|---|---|
| Codex CLI (default) | none, run `codex login` once |
| OpenAI | `ATLAS_PROVIDER=openai`, `ATLAS_MODEL=<exact model id>`, `OPENAI_API_KEY` |
| Anthropic | `ATLAS_PROVIDER=anthropic`, `ATLAS_MODEL=<exact model id>`, `ANTHROPIC_API_KEY` |
| Google Gemini | `ATLAS_PROVIDER=gemini`, `ATLAS_MODEL=<exact model id>`, `GEMINI_API_KEY` |

**Settings** (`config.json` in the data home):

| Key | Meaning |
|---|---|
| `language` | `en` or `de`: interface and generated texts |
| `nominatim_contact` | **required for the location map**: your e-mail or a URL; OpenStreetMap asks Nominatim users to identify themselves |
| `output_dir` | where the HTML pages are written (default `atlas`) |
| `drive_dir`, `drive_subdir` | optional synced folder; every changed page is copied to `<drive_dir>/<drive_subdir>/` |
| `chunk_chars`, `max_output_tokens` | size of one AI request and its answer; lower them if your model rejects long answers |
| `portraits`, `image_provider`, `image_model` | portraits are off by default; provider `codex` or `openai` |
| `core_figures`, `min_features`, `max_portraits_per_run` | portrait rules |

## Use

```bash
reading-atlas add-book --device F:\          # list books with a reading position and the estimated work
reading-atlas add-book --device F:\ --yes    # add them and build their chapter states
reading-atlas build --device F:\             # after more reading: new states, new pages
```

Open the page from `atlas/` (or your synced folder). Run `build` whenever you have read more; unchanged books cost nothing.

Other commands: `position` (set a reading position by hand), `audit` and `enrich` (repair older states), `portraits plan|generate|sheet|approve|reject|rekey`.

## Portraits

Turn them on with `"portraits": true`. A character gets a portrait once the text states at least three appearance features (and only for the most connected characters). The stated rank or status (for example "king", "priest", "child") counts as one feature and shapes the clothing: a king is drawn with a crown or circlet, a priest in a plain robe, and an unclear status stays plain. The prompt also names the time stated in the text (month and year only). Personal marks such as scars, weapons or jewellery are never invented. A new version is drawn only when that set of facts changes (a new status is a change); older versions stay for earlier states. New images are **not shown until you approve them** (`portraits sheet` writes a contact sheet, `portraits approve <ids>` releases them). You can add a correction hint per character in `atlas-images/<book id>/index.json` under `hints`; it is shown in the page next to the image.

## Limitations

- The AI can miss characters or mis-order events. The checks catch invented names and wrong sources, not every wrong or missing statement (descriptions are not verified against the text, and a book the model knows well can colour them even though the title is not sent); a chronology correction can be put into `atlas-maps/<book id>/order.json`.
- Chapters can be long, so states are chapter-sized.
- Place lookups need a real-world place name; invented places are shown as an approximate region at most.
- Portraits are an AI reading of a short description. They will differ from your own mental picture.
- One reader and one device family have been tested.

## Development

```bash
python -m unittest discover -s tests      # all tests, no network, no AI access needed
python tools/check_private.py             # fails if keys, personal paths, book or image files slipped in
```

The privacy check also accepts `--terms <file>` with names and book titles you never want to publish (keep that file outside the repository).

## Related

[koreader-reading-recap](https://github.com/xchristianhoffmannx-bot/koreader-reading-recap): the KOReader plugin and Windows companion that write the reading recaps and the position.

## Licence

AGPL-3.0-or-later, see [COPYING](COPYING) and [NOTICE](NOTICE).
