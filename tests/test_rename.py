import unittest
from types import SimpleNamespace
from reading_atlas import states as S

PARAS = ['Der Gefangene schwieg.', 'Wie heißt du?', 'Rolf Berg, sagte er.', 'Ein anderer Absatz ohne Namen.']


def known():
    k = S.empty_known()
    k['groups'].append({'id': 'g', 'label': 'G'})
    k['nodes']['gef'] = {'t': 'node', 'id': 'gef', 'name': 'Der Gefangene', 'aliases': ['der Däne'], 'kind': 'Gefangener', 'text': 'x', 'group': 'g'}
    return k


class RenameTest(unittest.TestCase):
    def apply(self, text, anchor):
        chapter, log = SimpleNamespace(number=3, paragraphs=PARAS), {'unverified': []}
        k = known()
        facts = S.apply_delta(k, {'revisions': [{'target': 'gef', 'field': 'name', 'text': text, 'reason': 'r', 'anchor': anchor}]}, chapter, 3, log)
        return k, facts, log

    def test_name_stated_at_anchor_renames_and_keeps_old_name_as_alias(self):
        k, facts, log = self.apply('Rolf Berg', 2)
        self.assertEqual(k['nodes']['gef']['name'], 'Rolf Berg')
        self.assertIn('Der Gefangene', k['nodes']['gef']['aliases'])
        self.assertEqual([f['field'] for f in facts], ['name'])
        folded = S.fold([{'facts': [dict(known()['nodes']['gef'])] + facts, 'state': {}, 'groups': []}])
        self.assertEqual(folded['nodes']['gef']['name'], 'Rolf Berg')
        self.assertIn('Der Gefangene', folded['nodes']['gef']['aliases'])

    def test_name_not_at_anchor_is_rejected(self):
        k2, facts2, log2 = self.apply('Tom Falk', 2)         # invented name
        self.assertEqual(facts2, [])
        self.assertEqual(k2['nodes']['gef']['name'], 'Der Gefangene')
        self.assertEqual(len(log2['unverified']), 1)


if __name__ == '__main__':
    unittest.main()
