import json, shutil, tempfile, unittest
from pathlib import Path
from reading_atlas import states as S
from reading_atlas import enrich_profiles as P
import test_epub_chapters as T
from reading_atlas import epub_chapters as E


def delta_node():
    return {'groups': [{'id': 'g', 'label': 'G'}], 'title': 'T', 'kind': 'roman', 'stand': 'x', 'glance': [], 'questions': [],
            'nodes': [{'id': 'a', 'name': 'Satz', 'group': 'g', 'kind': 'k', 'text': 't', 'anchor': 0}]}


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        S.HERE = self.tmp
        P.HERE = self.tmp
        self.book = E.load(T.make_epub())
        self.chapter = self.book.chapters[0]

    def known_with_node(self):
        known = S.empty_known()
        log = {'unverified': []}
        S.apply_delta(known, delta_node(), self.chapter, 5, log)
        return known

    def test_only_verified_unique_capped_profile_facts_are_kept(self):
        known, log = self.known_with_node(), {'unverified': []}
        items = [{'target': 'a', 'aspect': 'aussehen', 'text': 'Groß und hager.', 'anchor': 0},
                 {'target': 'a', 'aspect': 'aussehen', 'text': 'groß und hager', 'anchor': 0},        # repeat
                 {'target': 'zzz', 'aspect': 'aussehen', 'text': 'Unbekannte Figur.', 'anchor': 0},   # unknown figure
                 {'target': 'a', 'aspect': 'laune', 'text': 'Falscher Aspekt.', 'anchor': 0},         # invalid aspect
                 {'target': 'a', 'aspect': 'herkunft', 'text': 'Nicht belegt.', 'anchor': 99}]        # anchor missing
        kept = S.apply_profile(known, items, self.chapter, 5, log)
        self.assertEqual([k['text'] for k in kept], ['Groß und hager.'])
        self.assertEqual(len(log['unverified']), 1)
        sentences = ['Der Mann trägt einen roten Mantel.', 'Seine Stiefel sind weiß verschmutzt.', 'Über dem Auge sitzt eine große Narbe.',
                     'Ein silberner Ring steckt am Finger.', 'Die Haut wirkt von der Sonne gebräunt.', 'Sein Gang ist auffällig hinkend.']
        more = [{'target': 'a', 'aspect': 'eigenschaft', 'text': s, 'anchor': 0} for s in sentences]
        self.assertEqual(len(S.apply_profile(known, more, self.chapter, 5, log)), 3)   # 4 per figure and state

    def test_fold_collects_profile_by_figure(self):
        known = self.known_with_node()
        facts = S.apply_profile(known, [{'target': 'a', 'aspect': 'herkunft', 'text': 'Bauer.', 'anchor': 0}], self.chapter, 5, {'unverified': []})
        state = {'chapter': 1, 'paragraph': 5, 'complete': True, 'groups': known['groups'], 'state': {},
                 'facts': [dict(known['nodes']['a'])] + facts}
        self.assertEqual([p['text'] for p in S.fold([state])['profile']['a']], ['Bauer.'])

    def test_enrich_is_non_destructive_and_runs_once(self):
        def asker(prompt_text, schema, codex, rules):
            if 'only the field profile' in prompt_text:
                return {'state': json.dumps({'profile': [{'target': 'a', 'aspect': 'aussehen', 'text': 'Neu.', 'anchor': 0}]})}
            return {'state': json.dumps(delta_node())}
        S.advance('c' * 32, self.book, '/body/DocFragment[2]/body/section/p[3]/text().0', 'Buch', 'x', asker)
        folder = self.tmp / 'atlas-history' / ('c' * 32) / 'states'
        path = next(folder.glob('*.json'))
        data = json.loads(path.read_text(encoding='utf-8'))
        data['profile_pass'] = False                       # simulate a state created before the feature
        data['facts'] = [f for f in data['facts'] if f['t'] != 'prof']
        path.write_text(json.dumps(data), encoding='utf-8')
        done = P.enrich('c' * 32, self.book, 'Buch', 'x', asker)
        self.assertEqual(len(done), 1)
        self.assertTrue((self.tmp / 'before-profile' / ('c' * 32) / path.name).exists())   # original saved
        self.assertEqual(P.enrich('c' * 32, self.book, 'Buch', 'x', asker), [])            # second run does nothing

if __name__ == '__main__':
    unittest.main()
