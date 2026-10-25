"""Portrait images for core figures, bound to the reading state and built only from verified appearance facts.

Rules: core figure (the most connected), at least `min_features` appearance features, one image per distinct feature set
(older versions stay for earlier states), a stated age is passed along, new images need your approval.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

from . import config as cfg
from . import images, prompts
from . import states as S
from .util import atomic_json

HERE = cfg.data_home()
LANG = 'en'

IMAGES = HERE / 'atlas-images'
MIN_FEATURES = 3
CORE = 12


def configure(settings):
    global MIN_FEATURES, CORE, LANG
    MIN_FEATURES, CORE, LANG = settings['min_features'], settings['core_figures'], settings['language']
AGE = re.compile(r'(\b\w+jährig\b|\b\w+(?: und \w+)? Jahre alt\b|\b[\w-]+-year-old\b|\b[\w-]+(?: and \w+)? years old\b)', re.I)
# an age tied to an event ("bei ihrer Begegnung vierzehn") is not the figure's age in general
RELATIVE = re.compile(r'\b(bei|als|damals|mit|war|wurde|zum|zur|vor|nach|at|when|as|during|since|after|before|was|became)\b', re.I)


def features(text):
    return [p.strip() for p in re.split(r',| und | and ', text) if p.strip()]


def core_ids(world):
    degree = {}
    for e in world['edges'].values():
        for i in (e['a'], e['b']):
            degree[i] = degree.get(i, 0) + 1
    for ev in world['events'].values():
        for i in ev.get('people', []):
            degree[i] = degree.get(i, 0) + 1
    ranked = sorted(world['nodes'], key=lambda i: -degree.get(i, 0))
    return ranked[:CORE]


def description(chain, upto, figure):
    """Appearance sentences (and a stated age) known up to chain[upto]."""
    looks, age = [], ''
    for state in chain[:upto + 1]:
        for f in state['facts']:
            if f['t'] == 'prof' and f['target'] == figure:
                if f['aspect'] == 'aussehen':
                    looks.append(f['text'])
                elif f['aspect'] == 'herkunft' and not age and AGE.search(f['text']) and not RELATIVE.search(f['text']):
                    age = AGE.search(f['text']).group(1)
    return looks, age


def role_of(chain, upto, figure):
    """The figure's role or status (after corrections in the text) and the setting, as known up to chain[upto]."""
    node = S.fold(chain[:upto + 1])['nodes'].get(figure) or {}
    where = (chain[upto]['state'].get('where') or '').strip()
    when = re.search(r'([A-Za-zÄÖÜäöüéèê]+\s+\d{3,4}|\b\d{3,4}\b)', where)   # the year (with month) is what matters for clothing
    return (node.get('kind') or '').strip(), when.group(1) if when else ''


def digest(looks, age, role=''):
    """Fingerprint of a version: appearance, age and status. A new status (for example a coronation) is a new version."""
    payload = [sorted(looks), age] + ([role] if role else [])
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode('utf-8')).hexdigest()[:12]


def load_index(book_id):
    path = IMAGES / book_id / 'index.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'figures': {}}


def save_index(book_id, index):
    atomic_json(IMAGES / book_id / 'index.json', index)


def plan(book_id, chain):
    """Jobs for core figures whose feature set (>= 3) is new compared with the stored index and earlier jobs."""
    world = S.fold(chain)
    index = load_index(book_id)
    jobs = []
    for figure in core_ids(world):
        known = [v['hash'] for v in index['figures'].get(figure, [])]
        for i, state in enumerate(chain):
            looks, age = description(chain, i, figure)
            role, setting = role_of(chain, i, figure)
            count = sum(len(features(t)) for t in looks) + (1 if role else 0)   # a stated status counts as one feature
            if count < MIN_FEATURES and not (looks and figure in index.get('hints', {})):
                continue   # a reader's correction hint shows that an image is wanted even with fewer features
            h = digest(looks, age, role)
            if h in known:
                continue
            known.append(h)
            jobs.append({'figure': figure, 'name': world['nodes'][figure]['name'], 'hash': h, 'from_chapter': state['chapter'],
                         'looks': looks, 'age': age, 'role': role, 'setting': setting,
                         'previous': (known[-2] if len(known) > 1 else None)})
    return jobs


def prompt_for(job, has_style, has_previous):
    p = prompts.PORTRAIT[LANG]
    text = p['start'] + ' '.join(job['looks']) + ' '
    if job['age']:
        text += p['age'] + job['age'] + '. '
    if job.get('role'):
        text += p['role'] + job['role'] + '. '
        if job.get('setting'):
            text += p['setting'] + job['setting'] + '. '
        text += p['dress']
    else:
        text += p['plain']
    text += p['no_extras'] + p['style'] + ' '
    if has_style:
        text += p['style_ref']
    if has_previous:
        text += p['previous']
    if job.get('hint'):
        text += p['hint'] + job['hint'] + ' '
    return text + p['end']


def store_image(source, book_id, job):
    from PIL import Image
    folder = IMAGES / book_id / job['figure']
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert('RGB')
    image.resize((1024, 1024), Image.LANCZOS).save(folder / f"{job['hash']}.webp", quality=85)
    image.resize((384, 384), Image.LANCZOS).save(folder / f"{job['hash']}-384.webp", quality=75)
    return f"{job['figure']}/{job['hash']}"


def generate(book_id, chain, client, runner=None, limit=None):
    runner = runner or images.make_runner(cfg.load())
    limit = limit or cfg.load()['max_portraits_per_run']
    index = load_index(book_id)
    style = IMAGES / book_id / 'style.png'
    made = []
    for job in plan(book_id, chain)[:limit]:
        job['hint'] = index.get('hints', {}).get(job['figure'], '')
        previous = next((v for v in index['figures'].get(job['figure'], []) if v['hash'] == job['previous']), None)
        attachments = ([style] if style.exists() else [])
        prev_file = IMAGES / book_id / job['figure'] / f"{previous['hash']}.webp" if previous else None
        if prev_file and prev_file.exists():
            attachments.append(prev_file)
        work = HERE / 'work' / 'portrait'
        work.mkdir(parents=True, exist_ok=True)
        source = runner(prompt_for(job, style.exists(), bool(prev_file and prev_file.exists())), attachments, client, work)
        key = store_image(source, book_id, job)
        index['figures'].setdefault(job['figure'], []).append(
            {'hash': job['hash'], 'key': key, 'from_chapter': job['from_chapter'], 'looks': job['looks'], 'age': job['age'], 'role': job.get('role', ''), 'setting': job.get('setting', ''),
             'name': job['name'], 'hint': job.get('hint', ''), 'approved': False, 'created': time.strftime('%Y-%m-%dT%H:%M:%S')})
        save_index(book_id, index)
        made.append(key)
    return made


def sheet(book_id, only_pending=True):
    """Contact sheet PNG of the images that wait for approval; returns its path or None."""
    from PIL import Image, ImageDraw, ImageFont
    index = load_index(book_id)
    items = [(f, v) for f, vs in index['figures'].items() for v in vs if not (only_pending and v['approved'])]
    if not items:
        return None
    try:
        font = ImageFont.truetype('arial.ttf', 18)
    except OSError:
        try:
            font = ImageFont.truetype('DejaVuSans.ttf', 18)
        except OSError:
            font = ImageFont.load_default()
    cell, cols = 300, 4
    rows = (len(items) + cols - 1) // cols
    sheet_img = Image.new('RGB', (cols * cell, rows * (cell + 50)), (17, 20, 28))
    draw = ImageDraw.Draw(sheet_img)
    for n, (figure, v) in enumerate(items):
        x, y = (n % cols) * cell, (n // cols) * (cell + 50)
        thumb = Image.open(IMAGES / book_id / (v['key'] + '-384.webp')).resize((cell - 10, cell - 10))
        sheet_img.paste(thumb, (x + 5, y + 5))
        draw.text((x + 8, y + cell), f"{v['name']}  ({figure}:{v['hash'][:6]})", fill=(233, 226, 208), font=font)
        draw.text((x + 8, y + cell + 24), f"from chapter {v['from_chapter']}, {sum(len(features(t)) for t in v['looks'])} features", fill=(170, 165, 149), font=font)
    out = IMAGES / book_id / 'kontaktbogen.png'
    sheet_img.save(out)
    return out


def rekey(book_id, chain):
    """After cleaning duplicate sentences: unapproved versions whose real feature set equals an approved one are dropped;
    the others get the clean hash and feature list (the picture itself stays, it was drawn from the same information)."""
    index = load_index(book_id)
    changed = []
    for figure, versions in index['figures'].items():
        for v in list(versions):
            if v['approved']:
                continue
            at = next((i for i, s in enumerate(chain) if s['chapter'] >= v['from_chapter']), len(chain) - 1)
            looks, age = description(chain, at, figure)
            role, _setting = role_of(chain, at, figure)
            clean = digest(looks, age, role)
            twin = next((o for o in versions if o is not v and o['approved'] and o['hash'] == clean), None)
            folder = IMAGES / book_id / figure
            if twin:
                for suffix in ('.webp', '-384.webp'):
                    p = IMAGES / book_id / (v['key'] + suffix)
                    if p.exists():
                        p.unlink()
                versions.remove(v)
                changed.append((v['name'], 'dropped: unchanged compared with the approved version'))
                continue
            for suffix in ('.webp', '-384.webp'):
                old = folder / (v['hash'] + suffix)
                if old.exists() and clean != v['hash']:
                    old.rename(folder / (clean + suffix))
            v['hash'], v['key'], v['looks'], v['age'], v['role'] = clean, f'{figure}/{clean}', looks, age, role
            changed.append((v['name'], 're-filed'))
    save_index(book_id, index)
    return changed


def set_approval(book_id, ids, value):
    index = load_index(book_id)
    hit = 0
    for figure, versions in index['figures'].items():
        for v in versions:
            if ids == ['all'] or figure in ids or v['hash'] in ids:
                v['approved'] = value
                hit += 1
    save_index(book_id, index)
    return hit


def reject(book_id, figure):
    """Delete the unapproved versions of a figure so they are generated again."""
    index = load_index(book_id)
    keep = [v for v in index['figures'].get(figure, []) if v['approved']]
    for v in index['figures'].get(figure, []):
        if not v['approved']:
            for suffix in ('.webp', '-384.webp'):
                p = IMAGES / book_id / (v['key'] + suffix)
                if p.exists():
                    p.unlink()
    index['figures'][figure] = keep
    save_index(book_id, index)


def embed_data(book_id):
    """{figure: [{from, src, looks}]} for approved images, small versions as data URIs."""
    import base64
    out = {}
    for figure, versions in load_index(book_id)['figures'].items():
        rows, latest = [], {}
        for v in versions:   # one picture per figure and chapter: the newest approved version wins
            if v['approved']:
                latest[v['from_chapter']] = v
        for v in (latest[c] for c in sorted(latest)):
            small = IMAGES / book_id / (v['key'] + '-384.webp')
            if small.exists():
                rows.append({'from': v['from_chapter'], 'looks': v['looks'], 'age': v['age'], 'role': v.get('role', ''), 'hint': v.get('hint', ''),
                             'src': 'data:image/webp;base64,' + base64.b64encode(small.read_bytes()).decode()})
        if rows:
            out[figure] = rows
    return out


def preview(book_id, chain, figures=None):
    """[(name, prompt text, attachments)] for the planned images; nothing is generated or sent."""
    index = load_index(book_id)
    style = IMAGES / book_id / 'style.png'
    out = []
    for job in plan(book_id, chain):
        if figures and job['figure'] not in figures:
            continue
        job['hint'] = index.get('hints', {}).get(job['figure'], '')
        has_previous = any(v['hash'] == job['previous'] for v in index['figures'].get(job['figure'], []))
        out.append((job['name'], prompt_for(job, style.exists(), has_previous),
                    (['style reference'] if style.exists() else []) + (['earlier version'] if has_previous else [])))
    return out
