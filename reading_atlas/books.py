"""Which books get the living atlas, and where their EPUB comes from.

atlas-books.json: {book_id: {"title": ..., "epub": optional local path, "device_file": optional file name on the Kindle}}.
A device copy is cached once in book-cache/ so later runs work without the Kindle.
"""
import json
from pathlib import Path
import shutil

from . import config as cfg
from . import epub_chapters

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


def estimate(book, cutoff):
    """(number of states to generate, characters sent to Codex) for a book up to the reading position."""
    where = epub_chapters.locate(book, cutoff)
    if not where:
        return 0, 0
    chapter, paragraph, _ = where
    done = [c for c in book.chapters if c.number < chapter.number]
    chars = sum(sum(map(len, c.paragraphs)) for c in done) + sum(map(len, chapter.paragraphs[:paragraph + 1]))
    return len(done) + 1, chars
