import json, shutil, tempfile, unittest
from pathlib import Path
from reading_atlas import states as S
import test_epub_chapters as T
from reading_atlas import epub_chapters as E

def fake(prompt_text, schema, codex, rules):
    data = json.loads(prompt_text.split('{"state":"..."}.\n', 1)[1])
    known = {n['id'] for n in data['known_world']['nodes']}
    if 'completeness' in prompt_text:   # audit pass: nothing forgotten
        return {'state': json.dumps({'nodes': [], 'edges': [], 'profile': []})}
    delta = {'groups': [{'id': 'g', 'label': 'Gruppe'}], 'title': 'T', 'kind': 'roman', 'stand': 'x', 'glance': [], 'questions': [],
             'nodes': [], 'edges': [], 'events': [], 'places': [], 'revisions': []}
    if 'a' not in known:
        delta['nodes'] = [{'id': 'a', 'name': 'Satz', 'short': '', 'aliases': [], 'group': 'g', 'kind': 'k', 'text': 'alt', 'anchor': 0},
                          {'id': 'x', 'name': 'Erfunden', 'group': 'g', 'text': 'nie im Text', 'anchor': 1}]
    else:
        delta['nodes'] = [{'id': 'a', 'name': 'Satz', 'group': 'g', 'text': 'DOPPELT', 'anchor': 0}]  # known id must be ignored
        delta['revisions'] = [{'target': 'a', 'field': 'text', 'text': 'neu', 'reason': 'Korrektur', 'anchor': 0}]
    return {'state': json.dumps(delta)}


class StatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        S.HERE = self.tmp
        self.book = E.load(T.make_epub())

    def run_advance(self, cutoff):
        return S.advance('b' * 32, self.book, cutoff, 'Buch', 'x', fake)

    def test_growth_verification_and_resume(self):
        made = self.run_advance('/body/DocFragment[3]/body/section/p[2]/text().0')
        self.assertEqual(len(made), 2)                                  # chapter 1 complete + chapter 2 partial
        first = json.loads((self.tmp / 'atlas-history' / ('b' * 32) / 'states' / made[0]).read_text(encoding='utf-8'))
        self.assertEqual([f['id'] for f in first['facts'] if f['t'] == 'node'], ['a'])   # fabricated node rejected
        self.assertEqual(len(first['unverified']), 1)
        self.assertEqual(self.run_advance('/body/DocFragment[3]/body/section/p[2]/text().0'), [])   # idempotent
        states = S.load_states('b' * 32)
        world = S.fold(states)
        self.assertEqual(world['nodes']['a']['text'], 'neu')            # explicit revision applied, duplicate ignored
        self.assertEqual(S.fold(states[:1])['nodes']['a']['text'], 'alt')   # earlier state keeps old wording

    def test_partial_is_superseded_when_chapter_completes(self):
        self.run_advance('/body/DocFragment[2]/body/section/p[3]/text().0')
        self.run_advance('/body/DocFragment[3]/body/section/p[2]/text().0')
        labels = [(s['chapter'], s['complete']) for s in S.load_states('b' * 32)]
        self.assertEqual(labels, [(1, True), (2, False)])

if __name__ == '__main__':
    unittest.main()
