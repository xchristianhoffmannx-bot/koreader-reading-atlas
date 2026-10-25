"""Reading position per book, taken from the koreader-reading-recap plugin's export on the connected device.

The plugin writes <device>/koreader/settings/reading_recap_requests/<book_id>.json with the KOReader position (`cutoff`),
the title and the text read so far. Only position and title are used here; the exported text is ignored. The position is
cached in the data home so a build also works while the device is not connected.
"""
import datetime
import json
from pathlib import Path

from . import config as cfg
from .util import atomic_json


def file():
    return cfg.data_home() / 'progress.json'


def load():
    return json.loads(file().read_text(encoding='utf-8')) if file().exists() else {}


def update_from_device(device):
    """Refresh the cache from the device; returns the book ids whose position changed."""
    folder = Path(device) / 'koreader' / 'settings' / 'reading_recap_requests'
    if not folder.is_dir():
        return []
    known, changed = load(), []
    for path in sorted(folder.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        book_id, cutoff = path.stem, data.get('cutoff')
        if not (isinstance(cutoff, str) and cutoff.startswith('/body/') and isinstance(data.get('title'), str)):
            continue
        if known.get(book_id, {}).get('cutoff') != cutoff:
            known[book_id] = {'title': data['title'], 'cutoff': cutoff,
                              'updated': datetime.datetime.now().astimezone().strftime('%d.%m.%Y %H:%M')}
            changed.append(book_id)
    if changed:
        atomic_json(file(), known)
    return changed


def get(book_id):
    return load().get(book_id)
