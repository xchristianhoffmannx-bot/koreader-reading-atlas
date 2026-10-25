import json, shutil, tempfile, unittest
from pathlib import Path
from reading_atlas import living
from reading_atlas import states as S


def ev(i, after=''):
    return {'t': 'event', 'id': i, 'title': i, 'brief': '', 'text': '', 'people': [], 'strand': '', 'after': after, 'at': [1, 0]}


class OrderTest(unittest.TestCase):
    def test_follow_up_event_moves_directly_behind_its_anchor(self):
        events = {e['id']: e for e in [ev('maldon'), ev('massaker'), ev('heirat'), ev('tod', after='maldon')]}
        self.assertEqual(list(S.order_events(events)), ['maldon', 'tod', 'massaker', 'heirat'])

    def test_unknown_anchor_and_cycles_keep_insertion_order(self):
        events = {e['id']: e for e in [ev('a', after='zzz'), ev('b', after='c'), ev('c', after='b')]}
        self.assertEqual(sorted(S.order_events(events)), ['a', 'b', 'c'])

    def test_reader_override_file_sets_after_without_touching_archived_facts(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        living.HERE = tmp
        (tmp / 'atlas-maps' / 'b').mkdir(parents=True)
        (tmp / 'atlas-maps' / 'b').joinpath('order.json').write_text(json.dumps({'tod': 'maldon'}), encoding='utf-8')
        state = {'chapter': 1, 'facts': [ev('maldon'), ev('tod')]}
        out = living.apply_order_overrides('b', [state])
        self.assertEqual([f['after'] for f in out[0]['facts']], ['', 'maldon'])
        self.assertEqual(state['facts'][1]['after'], '')

if __name__ == '__main__':
    unittest.main()
