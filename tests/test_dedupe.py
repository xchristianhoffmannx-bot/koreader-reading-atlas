import unittest
from reading_atlas import states as S


def prof(target, text):
    return {'t': 'prof', 'id': 'p:' + text[:8], 'target': target, 'aspect': 'aussehen', 'text': text, 'at': [1, 0]}


class DedupeTest(unittest.TestCase):
    def test_reworded_repeat_is_dropped_but_new_information_stays(self):
        chain = [{'facts': [prof('a', 'Garrick hat dunkle Augen, ein tief zerfurchtes Gesicht und vorzeitig weißes, schütteres Haar.')]},
                 {'facts': [prof('a', 'Er hat dunkle Augen, ein tief zerfurchtes Gesicht und vorzeitig weißes, schütteres Haar.'),
                            prof('a', 'Er trägt einen langen grauen Mantel mit Fuchspelz.'),
                            prof('b', 'Er hat dunkle Augen, ein tief zerfurchtes Gesicht und vorzeitig weißes, schütteres Haar.')]}]
        out = S.dedupe_profile(chain)
        self.assertEqual([f['text'][:10] for f in out[1]['facts']], ['Er trägt e', 'Er hat dun'])   # a: repeat gone, b: other figure keeps it
        self.assertEqual(len(chain[1]['facts']), 3)                                                 # input untouched

    def test_short_different_statements_are_not_confused(self):
        self.assertFalse(S.similar('Marlow ist groß, breitschultrig und bärtig.', 'Marlow hat ein breites Kreuz und überragt die meisten Männer.'))

if __name__ == '__main__':
    unittest.main()
