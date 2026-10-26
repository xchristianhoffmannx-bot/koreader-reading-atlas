"""Draw a plot-location map: Natural Earth coastlines plus markers geocoded via OpenStreetMap Nominatim.

Coordinates never come from the language model: it only names real places/regions, Nominatim locates them.
"""
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request

from . import config as cfg
from . import prompts
from .util import atomic_json

HERE = cfg.data_home()
GEO = HERE / 'atlas-geo'
LAND_URL = ('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/'
            'ace5fed0eaf3c6c03c951e75b439ba8fffbc218e/geojson/ne_10m_land.geojson')   # pinned commit, not a moving branch
LAND_SHA256 = '1ac90796408bc6ad6911d69448485d3c4dbf2190370080368a09976e1c9f7416'
LAND_MAX = 15000000   # bytes; the file has about 10 MB
NOMINATIM = 'https://nominatim.openstreetmap.org/search'
def agent():
    contact = cfg.load()['nominatim_contact'].strip()
    if not contact:
        raise RuntimeError('Set "nominatim_contact" (your e-mail or a URL) in config.json: OpenStreetMap asks every Nominatim user to identify themselves')
    return f'koreader-reading-atlas/0.1 ({contact})'
W = 440


def land_file():
    path = GEO / 'ne_10m_land.geojson'
    if not path.exists():
        GEO.mkdir(exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(LAND_URL, headers={'User-Agent': agent()}), timeout=180) as r:
            data = r.read(LAND_MAX + 1)
        if len(data) > LAND_MAX or hashlib.sha256(data).hexdigest() != LAND_SHA256:
            raise RuntimeError('The downloaded coastline file does not match the expected checksum; it was not saved')
        tmp = path.with_suffix('.tmp')
        tmp.write_bytes(data)
        tmp.replace(path)
    return path


def nominatim(query, fetch=None):
    """Cached lookup -> {lat, lon, bbox:[s,n,w,e], name} or None. One request per second at most."""
    GEO.mkdir(exist_ok=True)
    cache_file = GEO / 'geocache.json'
    try:
        cache = json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() else {}
    except (OSError, ValueError):
        cache = {}   # unreadable cache: start again instead of losing the whole map
    if not isinstance(cache, dict):
        cache = {}
    if query not in cache:
        url = NOMINATIM + '?' + urllib.parse.urlencode({'q': query, 'format': 'jsonv2', 'limit': 1,
                                                       'accept-language': 'de'})
        if fetch:
            rows = fetch(url)
        else:
            time.sleep(1.1)
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': agent()}), timeout=30) as r:
                rows = json.load(r)
        cache[query] = ({'lat': float(rows[0]['lat']), 'lon': float(rows[0]['lon']),
                         'bbox': [float(v) for v in rows[0]['boundingbox']],
                         'name': rows[0].get('display_name', query)} if rows else None)
        atomic_json(cache_file, cache)
    return cache[query]


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(max(min(lat, 85), -85)) / 2))


def _span(lons, lats):
    mid = (min(lats) + max(lats)) / 2
    return max(max(lats) - min(lats), (max(lons) - min(lons)) * math.cos(math.radians(mid)))


def view(points, areas):
    """Pick a lon/lat window around markers and areas with modest padding. Returns (w, s, e, n)."""
    lons = [p[1] for p in points] + [b for a in areas for b in (a[2], a[3])]
    lats = [p[0] for p in points] + [b for a in areas for b in (a[0], a[1])]
    if len(points) >= 5:
        # a single far-away place would shrink everything else: leave it out of the window (it gets an edge marker)
        full = _span(lons, lats)
        best = max(range(len(points)), key=lambda i: full - _span(lons[:i] + lons[i + 1:], lats[:i] + lats[i + 1:]))
        if _span(lons[:best] + lons[best + 1:], lats[:best] + lats[best + 1:]) <= full * .7:
            lons, lats = lons[:best] + lons[best + 1:], lats[:best] + lats[best + 1:]
    west, east, south, north = min(lons), max(lons), min(lats), max(lats)
    pad_x, pad_y = max((east - west) * .25, .6), max((north - south) * .25, .5)
    return west - pad_x, south - pad_y, east + pad_x, north + pad_y


def clip(points, left, top, right, bottom):
    """Sutherland-Hodgman clip of a polygon to a rectangle (border artefacts stay outside the viewBox)."""
    def run(pts, inside, cross):
        out = []
        for i, cur in enumerate(pts):
            prev = pts[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
        return out
    def at_x(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
    def at_y(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), y)
    for inside, cross in ((lambda p: p[0] >= left, at_x(left)), (lambda p: p[0] <= right, at_x(right)),
                          (lambda p: p[1] >= top, at_y(top)), (lambda p: p[1] <= bottom, at_y(bottom))):
        if not points:
            break
        points = run(points, inside, cross)
    return points


def build(places, areas, land_path=None, credit=''):
    """places: [{n, name, lat, lon, current}], areas: [{name, bbox:[s,n,w,e]}] -> template dict or None."""
    if not places and not areas:
        return None
    west, south, east, north = view([(p['lat'], p['lon']) for p in places], [a['bbox'] for a in areas])
    dy = merc_y(north) - merc_y(south)
    need = math.degrees(dy * W / 640)  # widen tall windows so the picture stays phone-sized
    if east - west < need:
        mid = (east + west) / 2
        west, east = mid - need / 2, mid + need / 2
    scale = W / math.radians(east - west)
    top = merc_y(north)
    h = dy * scale
    px = lambda lon: (lon - west) / (east - west) * W
    py = lambda lat: (top - merc_y(lat)) * scale
    land = []
    data = json.loads((land_path or land_file()).read_text(encoding='utf-8'))
    for feature in data['features']:
        geometry = feature['geometry']
        polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        for polygon in polygons:
            for ring in polygon:
                lons = [c[0] for c in ring]
                lats = [c[1] for c in ring]
                if max(lons) < west or min(lons) > east or max(lats) < south or min(lats) > north:
                    continue
                pts, last = [], None
                for lon, lat in ring:
                    x, y = round(px(lon), 1), round(py(lat), 1)
                    if last is None or abs(x - last[0]) + abs(y - last[1]) >= 0.5:
                        pts.append((x, y))
                        last = (x, y)
                pts = clip(pts, -30, -30, W + 30, h + 30)
                if len(pts) > 2:
                    land.append('M' + 'L'.join(f'{x} {y}' for x, y in pts) + 'Z')
    markers = []  # places on (nearly) the same spot share one pin so numbers do not hide each other
    for p in places:
        x, y = round(px(p['lon']), 1), round(py(p['lat']), 1)
        edge = None
        if not (14 <= x <= W - 14 and 14 <= y <= h - 14):   # outside the window: pin sits on the border, arrow points to the place
            edge = round(math.degrees(math.atan2(y - h / 2, x - W / 2)))
            x, y = round(min(max(x, 26), W - 26), 1), round(min(max(y, 26), h - 26), 1)
        same = next((m for m in markers if abs(m['x'] - x) < 8 and abs(m['y'] - y) < 8 and m.get('edge') == edge), None)
        item = {'n': p['n'], 'name': p['name'], 'id': p.get('id', ''), 'from': p.get('from', 0)}
        if same:
            same['n'] += '·' + str(p['n'])
            same['name'] += ' / ' + p['name']
            same['current'] = same['current'] or bool(p.get('current'))
            same['items'].append(item)
        else:
            markers.append({'n': str(p['n']), 'name': p['name'], 'x': x, 'y': y, 'current': bool(p.get('current')),
                            'items': [item], **({'edge': edge} if edge is not None else {})})
    out = {'w': W, 'h': round(h), 'land': land, 'markers': markers,
           'areas': [], 'credit': credit}
    for a in areas:
        s, n, w_, e = a['bbox']
        out['areas'].append({'name': a['name'], 'cx': round(px((w_ + e) / 2), 1), 'cy': round(py((s + n) / 2), 1),
                             'rx': round(max(abs(px(e) - px(w_)) / 2, 14), 1),
                             'ry': round(max(abs(py(s) - py(n)) / 2, 14), 1), 'current': bool(a.get('current')),
                             'from': a.get('from', 0)})
    return out
