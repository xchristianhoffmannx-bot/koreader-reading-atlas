# Demo with a public-domain book

The repository ships no book, no data and no generated atlas. To see what the page looks like without using your own
books, build a demo from a public-domain novel (for example a DRM-free EPUB from [Project Gutenberg](https://www.gutenberg.org/)).

1. Estimate the work first, nothing is sent:

   ```bash
   python tools/demo_estimate.py path/to/novel.epub --chapters 5
   ```

2. Register the book and a reading position, for example the end of chapter 5, without any reader:

   ```bash
   reading-atlas init
   # edit config.json in your data home: "language", "nominatim_contact"
   # then add the book to atlas-books.json in the data home:
   #   { "demo": { "title": "My Demo Novel", "epub": "path/to/novel.epub" } }
   reading-atlas position demo --chapter 5 --title "My Demo Novel"
   reading-atlas build
   ```

   The book id (`demo` above) can be any name without spaces. States are built chapter by chapter up to the position;
   build again after `reading-atlas position demo --chapter 8` to watch the atlas grow.

3. Open `atlas/my-demo-novel.html` from your data home. Try the time slider, the discovery journal, the map and the notes.

A ready-made demo page is not included yet: generating one costs AI requests, so it is done only after the estimate
from step 1 has been accepted by whoever pays for them.
