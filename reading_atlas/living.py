"""Assemble the data blob and the page of the living atlas from chapter states."""
import json
from pathlib import Path

from . import config as cfg
from . import geo_map, i18n, prompts
from . import states as S

HERE = cfg.data_home()
TEMPLATE = Path(__file__).resolve().parent / 'templates' / 'atlas.html'


def make_geo(states, book_id, area_override='', locate=geo_map.nominatim, lang='en'):
    """Markers carry the state index they first appear in, so the page can reveal them with the reading position."""
    world = S.fold(states)
    first = {}
    for index, state in enumerate(states):
        for fact in state['facts']:
            if fact['t'] == 'place':
                first.setdefault(fact['id'], index)
    places = []
    for number, (pid, place) in enumerate(world['places'].items(), 1):
        hit = locate(place['geo']) if place.get('geo') else None
        if hit:
            places.append({'n': number, 'id': pid, 'name': place['name'], 'lat': hit['lat'], 'lon': hit['lon'], 'from': first[pid]})
    areas, last = [], None
    for index, state in enumerate(states):
        name = state['state'].get('area') or (area_override if index == 0 else '')
        if name and name != last:
            hit = locate(name)
            if hit:
                areas.append({'name': name.split(',')[0], 'bbox': hit['bbox'], 'from': index})
            last = name
    return geo_map.build(places, areas, credit=prompts.py(lang, 'geo_credit'))


def apply_order_overrides(book_id, states):
    """atlas-maps/<book_id>/order.json: {event_id: earlier_event_id} corrections of the chronology (e.g. from the text)."""
    path = HERE / 'atlas-maps' / book_id / 'order.json'
    if not path.exists():
        return states
    rules = json.loads(path.read_text(encoding='utf-8'))
    out = []
    for s in states:
        facts = [dict(f, after=rules[f['id']]) if f['t'] == 'event' and f['id'] in rules else f for f in s['facts']]
        out.append(dict(s, facts=facts))
    return out


def build_data(book_id, states, load_map, asof, area_override='', sizes=None, lang='en', title=''):
    states = apply_order_overrides(book_id, states)
    if title:   # the configured title wins: the model is not told the book title and only guesses one
        states = [dict(s, state=dict(s['state'], title=title)) for s in states]
    last = states[-1]['state']
    data = {'title': title or last.get('title', ''), 'book_id': book_id, 'asof': asof, 'lang': lang,
            'states': [{'label': s['label'], 'place': s['place'], 'when': s['when'], 'complete': s['complete'],
                        'groups': s['groups'], 'state': s['state'], 'facts': s['facts'],
                        'chapter': s['chapter'], 'size': (sizes or {}).get(s['chapter'], 0)} for s in states]}
    try:
        data['geo'] = make_geo(states, book_id, area_override, lang=lang)
    except Exception as error:  # place lookup is optional decoration
        print(f'Location map skipped: {error}')
        data['geo'] = None
    try:
        from . import portraits
        data['images'] = portraits.embed_data(book_id)
    except Exception as error:  # portraits are optional decoration
        print(f'Portraits skipped: {error}')
        data['images'] = {}
    historic = load_map(book_id)
    data['map'] = dict(historic, **{'from': 0}) if historic else None
    return data


def render(data):
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    page = TEMPLATE.read_text(encoding='utf-8')
    page = i18n.translate(page, data.get('lang', 'en'))
    return page.replace('{{DATA}}', payload)
