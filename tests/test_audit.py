import json, shutil, tempfile, unittest
from pathlib import Path
from reading_atlas import states as S
import test_epub_chapters as T
from reading_atlas import epub_chapters as E


class FakeChapter:
    number = 1
    def __init__(self, paragraphs):
        self.paragraphs = paragraphs


def known_with_group():
    known = S.empty_known()
    known['groups'].append({'id': 'g', 'label': 'G'})
    return known


class AuditTest(unittest.TestCase):
    def test_nameless_figure_is_accepted_via_key_word_in_anchor_window(self):
        chapter = FakeChapter(['Der junge Mann wurde gefesselt.', 'Alle sahen den Gefangenen an.'])
        known, log = known_with_group(), {'unverified': []}
        node = {'id': 'gefangener', 'name': 'Der dänische Gefangene', 'group': 'g', 'text': 't', 'anchor': 1}
        facts = S.apply_delta(known, {'nodes': [node]}, chapter, 1, log)
        self.assertEqual([f['id'] for f in facts], ['gefangener'])     # was rejected before: label not literally in the text

    def test_invented_figure_is_still_rejected(self):
        chapter = FakeChapter(['Es regnete in Strömen.', 'Niemand sprach.'])
        known, log = known_with_group(), {'unverified': []}
        node = {'id': 'x', 'name': 'Der geheimnisvolle Zauberer', 'group': 'g', 'text': 't', 'anchor': 1}
        self.assertEqual(S.apply_delta(known, {'nodes': [node]}, chapter, 1, log), [])
        self.assertEqual(len(log['unverified']), 1)

    def test_same_figure_under_another_id_is_not_added_twice(self):
        chapter = FakeChapter(['Der Gefangene schwieg.'])
        known, log = known_with_group(), {'unverified': []}
        one = {'id': 'a', 'name': 'Der Gefangene', 'group': 'g', 'text': 't', 'anchor': 0}
        two = {'id': 'b', 'name': 'der gefangene', 'aliases': ['Pferdedieb'], 'group': 'g', 'text': 't', 'anchor': 0}
        S.apply_delta(known, {'nodes': [one]}, chapter, 0, log)
        S.apply_delta(known, {'nodes': [two]}, chapter, 0, log)
        self.assertEqual(list(known['nodes']), ['a'])
        self.assertIn('Pferdedieb', known['nodes']['a']['aliases'])

    def test_audit_adds_a_forgotten_figure_and_repairs_old_states(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        S.HERE = tmp
        book = E.load(T.make_epub())
        calls = []

        def asker(prompt_text, schema, codex, rules):
            calls.append(prompt_text)
            if 'completeness' in prompt_text:
                return {'state': json.dumps({'nodes': [{'id': 'wort', 'name': 'Der Satz-Mann', 'aliases': ['Satz'], 'group': 'g', 'text': 't', 'anchor': 0}]})}
            return {'state': json.dumps({'groups': [{'id': 'g', 'label': 'G'}], 'title': 'T', 'kind': 'roman', 'stand': 'x',
                                         'glance': [], 'questions': [], 'nodes': []})}
        S.advance('d' * 32, book, '/body/DocFragment[2]/body/section/p[3]/text().0', 'Buch', 'x', asker)
        states = S.load_states('d' * 32)
        self.assertIn('wort', S.fold(states)['nodes'])                  # audit ran as part of advance
        path = next((tmp / 'atlas-history' / ('d' * 32) / 'states').glob('*.json'))
        old = json.loads(path.read_text(encoding='utf-8'))
        old['audit_pass'] = False
        old['facts'] = [f for f in old['facts'] if f.get('id') != 'wort']
        path.write_text(json.dumps(old), encoding='utf-8')
        done = S.audit_states('d' * 32, book, 'Buch', 'x', asker)
        self.assertEqual(done[0][1], ['Der Satz-Mann'])
        self.assertTrue((tmp / 'before-audit' / ('d' * 32) / path.name).exists())
        self.assertEqual(S.audit_states('d' * 32, book, 'Buch', 'x', asker), [])   # once only

if __name__ == '__main__':
    unittest.main()
