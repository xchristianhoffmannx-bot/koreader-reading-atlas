import unittest
from types import SimpleNamespace

from reading_atlas import enrich_profiles, states as S

PARAS = ['He needed help.', 'Ed came at noon.', 'Rolfs horse was lost.', 'The prisoners were quiet.']
CHAPTER = SimpleNamespace(number=1, title='One', paragraphs=PARAS)


def known():
    k = S.empty_known()
    k['groups'].append({'id': 'g', 'label': 'G'})
    return k


class WholeWordTest(unittest.TestCase):
    def test_a_name_inside_another_word_is_no_evidence(self):
        self.assertFalse(S.supported(PARAS, 0, ['Ed'], 0))          # "needed"
        self.assertTrue(S.supported(PARAS, 1, ['Ed'], 0))
        self.assertFalse(S.supported(['The malice grew.'], 0, ['Alice'], 0))

    def test_inflected_names_still_count(self):
        self.assertTrue(S.supported(PARAS, 2, ['Rolf'], 0))       # genitive -s
        self.assertFalse(S.supported(['Rolfo came.'], 0, ['Rolf'], 0))

    def test_one_and_two_letter_names_need_the_exact_capitalised_word(self):
        self.assertFalse(S.supported(['It was an odd day.'], 0, ['An'], 0))
        self.assertTrue(S.supported(['An came home.'], 0, ['An'], 0))

    def test_nameless_figures_match_at_the_start_of_a_word(self):
        self.assertTrue(S.supported(PARAS, 3, ['Der Prisoners'], 0, fuzzy=True))
        self.assertFalse(S.supported(['An imprisonment.'], 0, ['Der Prisoners'], 0, fuzzy=True))


class ModelOutputTest(unittest.TestCase):
    def test_garbage_does_not_crash_and_good_items_survive(self):
        delta = {'groups': ['x', {'id': 'g2', 'label': 7}, {'id': ['l']}],
                 'nodes': ['x', 5, {'id': ['list'], 'name': 'Ed', 'group': 'g', 'anchor': 1},
                          {'id': 'ed', 'name': 'Ed', 'aliases': 'Eddie', 'group': 'g', 'kind': None, 'text': 3, 'anchor': 1},
                          {'id': 'x2', 'name': 'Rolf', 'group': 'g', 'anchor': '2'}],
                 'edges': [{'a': ['x'], 'b': 'ed'}, 'oops'],
                 'events': {'not': 'a list'}, 'places': 'nope', 'profile': 'text', 'revisions': [None, {'target': ['t']}],
                 'glance': ['x', {'label': 'L', 'text': 'T'}], 'questions': 'q', 'title': 5}
        log = {'unverified': []}
        facts = S.apply_delta(known(), delta, CHAPTER, 3, log)
        self.assertEqual([f['id'] for f in facts if f['t'] == 'node'], ['ed'])
        self.assertEqual(facts[0]['aliases'], ['Eddie'])
        self.assertEqual((facts[0]['kind'], facts[0]['text']), ('', '3'))
        self.assertGreaterEqual(len(log['unverified']), 5)         # the rubbish is logged, not shown

    def test_state_fields_have_the_right_shape(self):
        k = known()
        S.apply_delta(k, {'glance': ['x', {'label': 'L', 'text': 'T'}], 'questions': 'q'}, CHAPTER, 3, {'unverified': []})
        self.assertEqual(k['state']['glance'], [{'label': 'L', 'text': 'T'}])
        self.assertNotIn('questions', k['state'])                 # not a list: ignored


class NoBookTitleTest(unittest.TestCase):
    def test_the_book_title_never_reaches_a_prompt(self):
        k, lines = known(), [(0, 'Some text.')]
        for text in (S.prompt('Secret Title', CHAPTER, k, lines, True), S.audit_prompt('Secret Title', CHAPTER, k, lines),
                     enrich_profiles.prompt('Secret Title', CHAPTER, k, lines)):
            self.assertNotIn('Secret Title', text)


if __name__ == '__main__':
    unittest.main()
