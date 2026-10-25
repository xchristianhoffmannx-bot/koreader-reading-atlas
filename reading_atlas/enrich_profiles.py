"""One-off pass: add character-sheet facts to chapter states created before the profile feature.

Non-destructive: the original state file is copied to before-profile/<book_id>/ first, existing facts stay
unchanged, and a state is only processed once (flag profile_pass).
"""
import json
from pathlib import Path
import shutil

from . import config as cfg
from . import epub_chapters, prompts, states
from .util import atomic_json

HERE = cfg.data_home()


def prompt(title, chapter, known, lines):
    world = [{'id': n['id'], 'name': n['name'], 'aliases': n.get('aliases', [])} for n in known['nodes'].values()]
    profile = {i: [f"{p['aspect']}: {p['text'][:70]}" for p in ps] for i, ps in known['profile'].items()}
    return (prompts.build(prompts.ENRICH, states.LANG, PROFILE=prompts.PROFILE_RULES[states.LANG])
            + prompts.dumps({'book': title, 'chapter': chapter.title, 'known_world': {'nodes': world, 'profile': profile},
                             'text': '\n'.join(f'[{i}] {t}' for i, t in lines)}))


def enrich(book_id, book, title, client, asker):
    folder = HERE / 'atlas-history' / book_id / 'states'
    backup = HERE / 'before-profile' / book_id
    done = []
    for s in states.load_states(book_id):
        name = f"{s['chapter']:03d}-{s['paragraph']:05d}-{'c' if s['complete'] else 'p'}.json"
        path = folder / name
        if s.get('profile_pass'):
            continue
        chapter = next(c for c in book.chapters if c.number == s['chapter'])
        earlier = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))]
        earlier = [x for x in earlier if x['complete'] and x['chapter'] < s['chapter']]
        known = states.fold(earlier + [s])
        offset = 0 if s['complete'] else (epub_chapters.locate(book, s['cutoff']) or (None, 0, 0))[2]
        lines = epub_chapters.text_upto(chapter, s['paragraph'], offset)
        log, facts = {'unverified': []}, []
        chunks, size = [[]], 0
        for line in lines:
            if size + len(line[1]) > states.CHUNK and chunks[-1]:
                chunks.append([])
                size = 0
            chunks[-1].append(line)
            size += len(line[1])
        for chunk in chunks:
            raw = asker(prompt(title, chapter, known, chunk), states.SCHEMA, client, states.RULES)
            facts += states.apply_profile(known, states.parse(raw).get('profile'), chapter, s['paragraph'], log)
        backup.mkdir(parents=True, exist_ok=True)
        if not (backup / name).exists():
            shutil.copy2(path, backup / name)
        s['facts'] = s['facts'] + facts
        s['unverified'] = s['unverified'] + log['unverified']
        s['profile_pass'] = True
        atomic_json(path, s)
        done.append((name, len(facts), len(log['unverified'])))
    return done
