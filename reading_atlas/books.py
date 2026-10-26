"""Which books get the living atlas, and where their EPUB comes from.

atlas-books.json: {book_id: {"title": ..., "epub": optional local path, "device_file": optional file name on the Kindle}}.
A device copy is cached once in book-cache/ so later runs work without the Kindle.
"""
import json
from pathlib import Path
import shutil

from . import config as cfg
from . import epub_chapters, states

HERE = cfg.data_home()
CONFIG = HERE / 'atlas-books.json'
CACHE = HERE / 'book-cache'


def load():
    return json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}


def save(config):
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')


def resolve_epub(book_id, cfg, device=None):
    """Local EPUB path for a configured book, copying it from the device once; None if unavailable."""
    cached = CACHE / f'{book_id}.epub'
    if cfg.get('epub') and Path(cfg['epub']).exists():
        return Path(cfg['epub'])
    if cached.exists():
        return cached
    if device and cfg.get('device_file'):
        source = Path(device) / 'documents' / cfg['device_file']
        if source.exists():
            CACHE.mkdir(exist_ok=True)
            shutil.copy2(source, cached)
            return cached
    return None


def scan_device(device):
    """{book_id: path} for every EPUB in the Kindle's documents folder (book_id = KOReader partial MD5)."""
    found = {}
    for path in sorted((Path(device) / 'documents').rglob('*.epub')):
        if 'Wiki-Lesestoff' in path.parts:
            continue
        found[epub_chapters.partial_md5(path)] = path
    return found


REQUEST_OVERHEAD = 3500   # characters of instructions in every request
WORLD_PER_STATE = 150     # the known-world JSON grows by about this much with every finished state


def estimate(book, cutoff):
    """(states, requests, characters sent) to build a book up to the reading position. A rough guide, not a quote.

    Every state sends its text twice (main request and audit request, each per CHUNK characters), plus instructions and
    the known characters and events. Reading on inside a chapter makes a new partial state: the chapter up to the new
    position is sent again (the finished chapters before it are not)."""
    where = epub_chapters.locate(book, cutoff)
    if not where:
        return 0, 0, 0
    chapter, paragraph, _ = where
    jobs = [(c, len(c.paragraphs) - 1) for c in book.chapters if c.number < chapter.number] + [(chapter, paragraph)]
    requests = chars = 0
    for index, (c, last) in enumerate(jobs):
        lines = epub_chapters.text_upto(c, last)
        n = 2 * len(states.audit_chunks(lines))
        requests += n
        chars += 2 * sum(len(t) for _, t in lines) + n * (REQUEST_OVERHEAD + WORLD_PER_STATE * index)
    return len(jobs), requests, chars
