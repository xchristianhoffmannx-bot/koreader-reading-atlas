import json, unittest
from reading_atlas import living
from reading_atlas import states as S

def fact(t, id, name, **kw):
    return dict({'t': t, 'id': id, 'name': name, 'short': '', 'aliases': [], 'group': 'g', 'kind': '', 'text': name + ' text', 'at': [1, 0]}, **kw)

STATES = [
    {'chapter': 1, 'paragraph': 9, 'complete': True, 'label': 'Eins', 'place': '', 'when': '', 'groups': [{'id': 'g', 'label': 'G'}],
     'state': {'title': 'T', 'area': ''}, 'facts': [fact('node', 'a', 'Anna')]},
    {'chapter': 2, 'paragraph': 5, 'complete': False, 'label': 'Zwei', 'place': '', 'when': '', 'groups': [{'id': 'g', 'label': 'G'}],
     'state': {'title': 'T', 'area': ''}, 'facts': [fact('node', 'b', 'Ben'), {'t': 'rev', 'target': 'a', 'field': 'text', 'text': 'neu', 'at': [2, 1]}]},
]

class LivingTest(unittest.TestCase):
    def test_fold_grows_and_keeps_old_wording_in_old_state(self):
        self.assertEqual(list(S.fold(STATES[:1])['nodes']), ['a'])
        self.assertEqual(S.fold(STATES[:1])['nodes']['a']['text'], 'Anna text')
        self.assertEqual(list(S.fold(STATES)['nodes']), ['a', 'b'])
        self.assertEqual(S.fold(STATES)['nodes']['a']['text'], 'neu')

    def test_render_embeds_data_safely(self):
        data = living.build_data('x' * 32, STATES, lambda _id: None, '25.10.2026')
        data['states'][0]['state']['stand'] = '</script><b>'
        page = living.render(data)
        self.assertNotIn('</script><b>', page)
        self.assertIn('Anna', page)

if __name__ == '__main__':
    unittest.main()
