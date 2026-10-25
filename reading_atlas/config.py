"""Settings and the data home.

The code contains nothing personal. Everything that belongs to you (books, chapter states, images, maps, progress,
credentials) lives under the data home, which is never part of this repository:

    READING_ATLAS_HOME  (environment variable)  or  ~/ReadingAtlas
"""
import json
import os
from pathlib import Path

DEFAULTS = {
    'language': 'en',               # language of the atlas page and of the generated texts: 'en' or 'de'
    'output_dir': 'atlas',          # finished HTML pages, relative to the data home or absolute
    'drive_dir': '',                # optional sync folder (for example Google Drive for desktop); the page is copied there
    'drive_subdir': 'Reading Atlas',
    'nominatim_contact': '',        # e-mail or URL identifying you to OpenStreetMap's Nominatim (required for place lookups)
    'chunk_chars': 30000,           # book text sent per AI request
    'max_output_tokens': 16000,     # upper bound for one answer from an API provider
    'core_figures': 12,             # the most connected figures form the relationship network and may get portraits
    'portraits': False,             # portraits are opt-in: image generation costs money
    'image_provider': 'codex',      # 'codex' (signed-in Codex CLI) or 'openai' (Images API)
    'image_model': '',              # exact model ID for the OpenAI Images API
    'min_features': 3,              # appearance features a figure needs before a portrait is drawn
    'max_portraits_per_run': 3,
}


def data_home():
    return Path(os.environ.get('READING_ATLAS_HOME') or Path.home() / 'ReadingAtlas')


def load():
    path = data_home() / 'config.json'
    config = dict(DEFAULTS)
    if path.exists():
        config.update(json.loads(path.read_text(encoding='utf-8-sig')))
    if config['language'] not in ('en', 'de'):
        raise ValueError("language must be 'en' or 'de'")
    return config


def output_dir(config=None):
    config = config or load()
    path = Path(config['output_dir'])
    return path if path.is_absolute() else data_home() / path
