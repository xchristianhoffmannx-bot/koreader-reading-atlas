"""Build the atlas pages: new chapter states up to the reading position, then one self-contained HTML page per book."""
import base64
import json
from pathlib import Path
import re
import shutil
import unicodedata

from . import books, config as cfg, epub_chapters, living, llm, portraits, progress, states
from .util import atomic_json

HERE = cfg.data_home()


def slug(title):
    ascii_title = unicodedata.normalize('NFKD', title.replace('ß', 'ss')).encode('ascii', 'ignore').decode()
    keep = ''.join(c if c.isalnum() else '-' for c in ascii_title.lower())
    return re.sub('-+', '-', keep).strip('-')[:60] or 'book'


def load_map(book_id):
    """A historical map you placed in <data home>/atlas-maps/<book_id>/ (map.png or map.jpg plus map.json)."""
    folder = cfg.data_home() / 'atlas-maps' / book_id
    meta = folder / 'map.json'
    if not meta.exists():
        return None
    m = json.loads(meta.read_text(encoding='utf-8'))
    name = m.pop('png')
    mime = 'image/jpeg' if name.endswith('.jpg') else 'image/png'
    m['src'] = f'data:{mime};base64,' + base64.b64encode((folder / name).read_bytes()).decode()
    return m


def configure(settings):
    states.LANG, states.CHUNK = settings['language'], settings['chunk_chars']
    portraits.configure(settings)


def copy_to_drive(target, settings):
    folder = settings['drive_dir'].strip()
    if not folder:
        return False
    dest = Path(folder) / settings['drive_subdir'] / target.name
    if dest.exists() and dest.read_bytes() == target.read_bytes():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, dest)
    return True


def build(settings=None, client=None, asker=None, device=None, only=None):
    """Returns (built, copied, failures). Prints one line per book."""
    settings = settings or cfg.load()
    configure(settings)
    if device:
        for book_id in progress.update_from_device(device):
            print('New reading position:', progress.get(book_id)['title'])
    out_dir = cfg.output_dir(settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    built = copied = failures = 0
    for book_id, entry in books.load().items():
        if only and book_id != only:
            continue
        try:
            position = progress.get(book_id)
            if not position:
                print(f'{entry["title"]}: no reading position yet; connect the device or run "reading-atlas position"')
                continue
            epub = books.resolve_epub(book_id, entry, device)
            if not epub:
                print(f'{entry["title"]}: EPUB not available; connect the device or set "epub" in atlas-books.json')
                continue
            book = epub_chapters.load(epub)
            if not book.front_matter_known:
                print(f'{entry["title"]}: warning: no table of contents or landmarks in the EPUB, cast lists or blurbs may be treated as story text; check the first chapters')
            client = client or llm.LazyClient(settings)
            states.advance(book_id, book, position['cutoff'], entry['title'], client, asker or llm.ask)
            where = epub_chapters.locate(book, position['cutoff'])
            chain = states.load_clean(book_id, (where[0].number, where[1]))
            if not chain:
                continue
            area_file = cfg.data_home() / 'atlas-maps' / book_id / 'geo.json'
            override = json.loads(area_file.read_text(encoding='utf-8')).get('area', '') if area_file.exists() else ''
            data = living.build_data(book_id, chain, load_map, position['updated'], override,
                                     {c.number: len(c.paragraphs) for c in book.chapters}, settings['language'], entry['title'])
            page = living.render(data)
            target = out_dir / (slug(entry['title']) + '.html')
            if not target.exists() or target.read_text(encoding='utf-8') != page:
                target.write_text(page, encoding='utf-8')
                built += 1
                print(f'Built {target.name} ({len(chain)} states)')
            copied += copy_to_drive(target, settings)
            unresolved = sum(1 for s in chain for u in s['unverified'] if u['t'] in ('node', 'place'))
            if unresolved:
                print(f'Note: {unresolved} suggested characters or places could not be verified against the text')
        except Exception as error:
            failures += 1
            print(f'{entry["title"]}: failed: {error}')
    print(f'Atlas: {built} built, {copied} copied, {failures} errors.')
    return built, copied, failures
