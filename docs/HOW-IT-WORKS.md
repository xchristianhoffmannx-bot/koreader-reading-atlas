# How it works

## Goal

An atlas that can never spoil you. Two ideas make that hold:

1. **The data contains only what you have read.** The page is built from chapter states up to your reading position. A later chapter is not hidden by the interface, it is not in the file.
2. **Knowledge only grows.** Characters, relationships, places and events that became known are never dropped. A statement changes only through an explicit correction in the text (`revision`), and the earlier state keeps its earlier wording.

## Pipeline

```
reader (KOReader + koreader-reading-recap)  ->  position (XPointer)
EPUB  ->  story chapters (front/back matter excluded)
            |
            v   per chapter, up to the position
        AI request: new facts, each with a source paragraph [n]
            |
            v   Python checks every fact against the text
        verified facts  -> atlas-history/<book>/states/NNN-PPPPP-c|p.json   (c = complete chapter, p = up to the position)
            |
            v   second pass: audit for forgotten characters (also nameless ones)
            v
        states -> one HTML page with embedded data -> output_dir (+ optional synced folder)
```

## Chapters and positions

`epub_chapters.py` reads the spine and the table of contents. Titles such as cover, contents, blurb, cast list, map, epigraph, acknowledgements and "Part One" are **never** a source: a cast list or a later chapter title would reveal the plot. KOReader positions (`/body/DocFragment[10]/body/section/p[57]/text().0`) are resolved to chapter and paragraph. Chapter titles of the form "Place, Month Year" give place and time for the page.

## Facts and verification

A state is a list of facts: `node` (character or concept), `edge` (relationship), `event`, `place`, `prof` (profile sentence about appearance, traits or origin) and `rev` (correction). Every fact carries `at: [chapter, paragraph]`.

`states.py` verifies before a fact is accepted:

- **Anchor:** the cited paragraph must exist and be inside what you have read.
- **Names:** a character's name, short name or alias must occur at the anchor or up to three paragraphs before it, as whole words (a plain genitive or plural ending is fine, "Ed" is not found in "needed"; names of one or two letters must match exactly, case included). For nameless characters a capitalised key word of the label ("prisoner", "mother") is enough.
- **Relationships and events:** one of the involved characters must be named near the anchor.
- **Profile sentences:** the figure must be named near the anchor, repeated or reworded sentences are dropped, at most four new ones per figure and state.
- **Duplicates:** the same character under two ids stays one character; the extra names become aliases.

What is **not** checked: the descriptive text of a fact (`text`, `detail`, `brief`, the summaries and open questions of a state) is the model's own wording. Only the source is verified, not every sentence. The book title is not sent to the model, so it cannot lean on outside knowledge of the plot by title; the page uses the title from `atlas-books.json`.

The model's answer is treated as untrusted: items that are not objects, fields of the wrong type and non-lists are dropped and logged in `unverified`, they never stop a run.

Rejected items are kept in `unverified` inside the state file for inspection. They never reach the page.

The **audit pass** asks the AI once more which important characters are missing from the list and sends the answers through the same checks. `reading-atlas audit <book>` repairs states created before the audit existed.

## Ordering

Events are ordered as extracted; an event may carry `after: <earlier event id>` ("a few days after the battle") and then stands directly behind it. Corrections you want to keep go into `atlas-maps/<book id>/order.json` as `{"event_id": "earlier_event_id"}` and are applied when the page is built.

## The page

`reading_atlas/templates/atlas.html` is one file with an embedded JSON blob, no external scripts, fonts or images. A Content Security Policy in the page (script allowed only by its hash, no network access, images only as embedded data) limits what a page could do even if text from a book contained markup. The browser folds the states up to the chosen slider position into the visible world; every view (network, list, timeline, map, search, journal, recap) uses that same fold. Your personal state (seen/skipped discoveries, bookmarks, notes, animation setting) lives in the browser's local storage, keyed by book id, and can be exported and imported as JSON.

## Maps

- **Location map:** places with a real-world name are looked up with Nominatim (OpenStreetMap), cached in `atlas-geo/geocache.json`, and drawn on Natural Earth land polygons (downloaded once). Invented places are shown as an approximate region if the text names one.
- **Historical map (optional):** put `map.png` or `map.jpg` and `map.json` into `atlas-maps/<book id>/` (see `sync.load_map` for the fields). It is shown as a second view. `maps.py` can search freely licensed maps on Wikimedia Commons; licence and author come from the Commons API, never from the model.

## Portraits

`portraits.py` plans a portrait for a core figure when the verified appearance sentences contain at least `min_features` features (parts separated by comma or "and"). The prompt contains only those sentences, a stated age (not an age tied to an event), an optional reader hint, a style reference and, for a new version, the earlier image. Images are stored in `atlas-images/<book id>/<figure>/<hash>.webp` (1024 px) and `-384.webp` (embedded); `index.json` records features, age, hint and approval. Only approved images are embedded, and a version is shown only from the chapter it was created for.

## Data home layout

```
config.json  atlas-books.json  progress.json
atlas-history/<book>/states/      chapter states (the facts)
atlas-images/<book>/              portraits + index.json
atlas-maps/<book>/                optional map.png|jpg, map.json, order.json, geo.json
atlas-geo/                        Natural Earth download, geocoding cache
book-cache/                       copies of EPUB files taken from the reader
atlas/                            the finished pages
```

`geo.json` (`{"area": "Region, Country"}`) can name the region of invented places if the text only implied it.
