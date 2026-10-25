"""Find a freely licensed map for a novel's real setting on Wikimedia Commons.

Codex only proposes search terms and picks among candidates (text only, no browsing).
Licence, author and source come from the Commons API, never from the model.
"""
import html
import json
from pathlib import Path
import re

from . import config as cfg
from . import llm, prompts
import urllib.parse
import urllib.request

API = 'https://commons.wikimedia.org/w/api.php'


def agent():
    from .geo_map import agent as geo_agent
    return geo_agent()

LICENSE_OK = re.compile(r'^(CC0|CC[ -]BY([ -]SA)?[ -][0-9.]+|CC[ -]BY([ -]SA)?|Public domain|PD[ -].*)$', re.I)
MAX_BYTES = 4_000_000
MIME = {'image/png': 'png', 'image/jpeg': 'jpg'}


def http_json(params):
    url = API + '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': agent()}), timeout=30) as r:
        return json.load(r)


def http_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': agent()}), timeout=60) as r:
        data = r.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Map image too large')
        return data, r.headers.get_content_type()


def plain(value):
    return html.unescape(re.sub(r'<[^>]+>', '', value or '')).strip()


def candidates(queries, fetch=http_json):
    found = {}
    for query in queries[:3]:
        data = fetch({'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6,
                      'gsrsearch': query + ' map', 'gsrlimit': 8, 'prop': 'imageinfo',
                      'iiprop': 'url|size|mime|extmetadata', 'iiurlwidth': 1200})
        for page in (data.get('query') or {}).get('pages', {}).values():
            info = (page.get('imageinfo') or [{}])[0]
            meta = info.get('extmetadata') or {}
            licence = plain((meta.get('LicenseShortName') or {}).get('value'))
            if not licence or not LICENSE_OK.match(licence) or not info.get('thumburl'):
                continue
            found[page['title']] = {
                'title': page['title'], 'url': info['thumburl'], 'page': info.get('descriptionurl', ''),
                'w': info.get('thumbwidth') or info.get('width'), 'h': info.get('thumbheight') or info.get('height'),
                'licence': licence, 'licence_url': plain((meta.get('LicenseUrl') or {}).get('value')),
                'author': plain((meta.get('Artist') or {}).get('value'))[:120],
                'description': plain((meta.get('ImageDescription') or {}).get('value'))[:240]}
    return list(found.values())[:15]


def find_map(real_setting, title, client, asker=llm.ask, fetch=http_json, download=http_bytes, lang='en'):
    """Return (map_meta, image_bytes, extension) or None."""
    terms = asker(prompts.MAP_QUERIES[lang] + prompts.dumps({'setting': real_setting, 'book': title}),
                  {'type': 'object', 'properties': {'queries': {'type': 'array', 'items': {'type': 'string'}}},
                   'required': ['queries'], 'additionalProperties': False}, client)
    queries = [q for q in terms.get('queries', []) if isinstance(q, str) and q.strip()]
    options = candidates(queries, fetch) if queries else []
    if not options:
        return None
    listing = [{'index': i, 'title': c['title'], 'description': c['description'], 'size': f"{c['w']}x{c['h']}"}
               for i, c in enumerate(options)]
    pick = asker(prompts.MAP_PICK[lang] + prompts.dumps({'setting': real_setting, 'candidates': listing}),
                 {'type': 'object', 'properties': {'index': {'type': 'integer'}}, 'required': ['index'],
                  'additionalProperties': False}, client)
    index = pick.get('index')
    if not isinstance(index, int) or not 0 <= index < len(options):
        return None
    chosen = options[index]
    data, mime = download(chosen['url'])
    if mime not in MIME or not chosen['w'] or not chosen['h']:
        return None
    name = chosen['title'].removeprefix('File:')
    meta = {'w': chosen['w'], 'h': chosen['h'], 'light': True, 'auto': True,
            'alt': prompts.py(lang, 'map_alt', title=name), 'intro': prompts.py(lang, 'map_intro'), 'key': '',
            'note': prompts.py(lang, 'map_note'),
            'credit': prompts.py(lang, 'map_credit', title=name, author=(', ' + chosen['author']) if chosen['author'] else '',
                                 licence=chosen['licence'], licence_url=(' (' + chosen['licence_url'] + ')') if chosen['licence_url'] else '',
                                 page=chosen['page'])}
    return meta, data, MIME[mime]
