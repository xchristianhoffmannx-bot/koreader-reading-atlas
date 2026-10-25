import shutil, tempfile, unittest
from pathlib import Path
from PIL import Image
from reading_atlas import portraits as P


def prof(target, aspect, text, chapter=1):
    return {'t': 'prof', 'id': f'prof:{target}:{text[:5]}', 'target': target, 'aspect': aspect, 'text': text, 'at': [chapter, 0]}


def node(i):
    return {'t': 'node', 'id': i, 'name': i.title(), 'short': '', 'aliases': [], 'group': 'g', 'kind': '', 'text': '', 'at': [1, 0]}


def chain():
    s1 = {'chapter': 1, 'paragraph': 9, 'complete': True, 'label': 'Eins', 'groups': [{'id': 'g', 'label': 'G'}], 'state': {},
          'facts': [node('anna'), node('ben'), {'t': 'edge', 'id': 'e', 'a': 'anna', 'b': 'ben', 'label': 'x', 'detail': '', 'at': [1, 0]},
                    prof('anna', 'aussehen', 'Anna ist groß, breitschultrig und bärtig.'),
                    prof('anna', 'herkunft', 'Anna ist einundzwanzig Jahre alt.'),
                    prof('ben', 'aussehen', 'Ben hat große Augen.')]}
    s2 = {'chapter': 2, 'paragraph': 5, 'complete': False, 'label': 'Zwei', 'groups': [], 'state': {},
          'facts': [prof('anna', 'aussehen', 'Anna hat eine Narbe am Kinn.', 2),
                    prof('ben', 'aussehen', 'Ben hat rotes Haar, trägt einen Mantel und hat Sommersprossen.', 2)]}
    return [s1, s2]


class PortraitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        P.IMAGES = self.tmp / 'images'
        P.HERE = self.tmp
        self.calls = []

    def runner(self, prompt, attachments, codex, work):
        self.calls.append((prompt, [Path(a).name for a in attachments]))
        path = self.tmp / f'src{len(self.calls)}.png'
        Image.new('RGB', (64, 64), (80, 60, 40)).save(path)
        return path

    def test_features_are_counted_by_comma_and_und(self):
        self.assertEqual(len(P.features('Anna ist groß, breitschultrig und bärtig.')), 3)

    def test_threshold_age_and_versions(self):
        jobs = P.plan('b' * 32, chain())
        names = [(j['name'], j['from_chapter']) for j in jobs]
        self.assertIn(('Anna', 1), names)                 # 3 features in one sentence qualify
        self.assertIn(('Anna', 2), names)                 # new feature set -> new version
        self.assertIn(('Ben', 2), names)                  # only from chapter 2 (1 feature before)
        self.assertNotIn(('Ben', 1), names)
        self.assertEqual(jobs[0]['age'], 'einundzwanzig Jahre alt')

    def test_event_bound_age_is_not_used(self):
        c = chain()
        c[0]['facts'][4] = prof('anna', 'herkunft', 'Anna war bei der Hochzeit vierzehn Jahre alt.')
        self.assertEqual(P.plan('b' * 32, c)[0]['age'], '')

    def test_generation_is_idempotent_and_chains_previous_version(self):
        made = P.generate('b' * 32, chain(), 'x', runner=self.runner, limit=5)
        self.assertEqual(len(made), 3)
        self.assertEqual(P.generate('b' * 32, chain(), 'x', runner=self.runner, limit=5), [])   # nothing to do twice
        second = next(c for c in self.calls if 'eine Narbe am Kinn' in c[0])
        self.assertIn('same person', second[0])       # reference to the earlier version
        self.assertEqual(len(second[1]), 1)               # the earlier image is attached

    def test_only_approved_images_are_embedded_and_limit_is_respected(self):
        P.generate('b' * 32, chain(), 'x', runner=self.runner, limit=1)
        self.assertEqual(P.embed_data('b' * 32), {})
        P.set_approval('b' * 32, ['all'], True)
        data = P.embed_data('b' * 32)
        self.assertEqual(list(data), ['anna'])
        self.assertTrue(data['anna'][0]['src'].startswith('data:image/webp;base64,'))
        self.assertEqual(len(P.generate('b' * 32, chain(), 'x', runner=self.runner, limit=1)), 1)   # next one only


def rank_chain(role='King', later_role=None):
    def n(kind):
        return {'t': 'node', 'id': 'k', 'name': 'Kay', 'short': '', 'aliases': [], 'group': 'g', 'kind': kind, 'text': '', 'at': [1, 0]}
    s1 = {'chapter': 1, 'paragraph': 9, 'complete': True, 'label': 'One', 'groups': [{'id': 'g', 'label': 'G'}],
          'state': {'where': 'Oakfield · October 1013'},
          'facts': [n(role), {'t': 'node', 'id': 'q', 'name': 'Quin', 'short': '', 'aliases': [], 'group': 'g', 'kind': '', 'text': '', 'at': [1, 0]},
                    {'t': 'edge', 'id': 'e', 'a': 'k', 'b': 'q', 'label': 'x', 'detail': '', 'at': [1, 0]},
                    prof('k', 'aussehen', 'Kay is tall and grey-haired.'), prof('q', 'aussehen', 'Quin is tall and grey-haired.')]}
    states = [s1]
    if later_role:
        states.append({'chapter': 2, 'paragraph': 4, 'complete': False, 'label': 'Two', 'groups': [], 'state': {'where': 'Harbourtown'},
                       'facts': [{'t': 'rev', 'target': 'k', 'field': 'kind', 'text': later_role, 'reason': '', 'at': [2, 1]}]})
    return states


class RankTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        P.IMAGES = self.tmp / 'images'
        P.HERE = self.tmp
        P.LANG = 'en'

    def test_a_stated_status_counts_as_a_feature(self):
        names = [j['name'] for j in P.plan('b' * 32, rank_chain())]
        self.assertEqual(names, ['Kay'])        # two features + the role reach three; Quin has the same looks but no role

    def test_a_new_status_is_a_new_version_from_that_chapter(self):
        jobs = [(j['name'], j['from_chapter'], j['role']) for j in P.plan('b' * 32, rank_chain('Prince', 'King'))]
        self.assertEqual(jobs, [('Kay', 1, 'Prince'), ('Kay', 2, 'King')])

    def test_prompt_carries_status_setting_and_clothing_rule_only_when_a_status_is_known(self):
        job = P.plan('b' * 32, rank_chain())[0]
        text = P.prompt_for(job, True, False)
        self.assertIn('Status or role according to the text: King', text)
        self.assertIn('Time according to the text: October 1013', text)
        self.assertIn('crown', text)
        self.assertIn('neither mentioned nor part of the stated status', text)       # personal marks stay forbidden
        plain = P.prompt_for(dict(job, role='', setting=''), True, False)
        self.assertNotIn('crown', plain)
        self.assertIn('Plain, timeless clothing', plain)

    def test_only_the_newest_approved_version_per_chapter_is_embedded_with_its_status(self):
        for h, role in (('aaa', 'Prince'), ('bbb', 'King')):
            folder = P.IMAGES / ('b' * 32) / 'k'
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (h + '-384.webp')).write_bytes(b'x')
        P.save_index('b' * 32, {'figures': {'k': [
            {'hash': 'aaa', 'key': 'k/aaa', 'from_chapter': 1, 'looks': [], 'age': '', 'role': 'Prince', 'approved': True},
            {'hash': 'bbb', 'key': 'k/bbb', 'from_chapter': 1, 'looks': [], 'age': '', 'role': 'King', 'approved': True}]}})
        rows = P.embed_data('b' * 32)['k']
        self.assertEqual([r['role'] for r in rows], ['King'])


if __name__ == '__main__':
    unittest.main()
