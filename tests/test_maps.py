import unittest
from reading_atlas import maps as M

def page(title, lic):
    return {'title': title, 'imageinfo': [{'thumburl': 'u/' + title, 'thumbwidth': 800, 'thumbheight': 600, 'descriptionurl': 'p/' + title,
            'extmetadata': {'LicenseShortName': {'value': lic}, 'Artist': {'value': '<b>A</b> &amp; B'}, 'LicenseUrl': {'value': 'l'}}}]}

class MapTest(unittest.TestCase):
    def fetch(self, params):
        return {'query': {'pages': {'1': page('File:Free.png', 'CC BY-SA 4.0'), '2': page('File:Nonfree.png', 'Fair use'),
                                    '3': page('File:Pd.png', 'Public domain')}}}

    def run_find(self, index, mime='image/png'):
        answers = iter([{'queries': ['q']}, {'index': index}])
        return M.find_map('England 1013', 'Buch', 'x', asker=lambda *a: next(answers), fetch=self.fetch,
                          download=lambda url: (b'img', mime))

    def test_only_free_licences_are_offered_and_credit_is_from_api(self):
        titles = [c['title'] for c in M.candidates(['q'], self.fetch)]
        self.assertEqual(sorted(titles), ['File:Free.png', 'File:Pd.png'])
        meta, data, ext = self.run_find(0)
        self.assertIn('CC BY-SA 4.0', meta['credit'])
        self.assertIn('A & B', meta['credit'])
        self.assertEqual((data, ext), (b'img', 'png'))

    def test_no_pick_or_bad_mime_means_no_map(self):
        self.assertIsNone(self.run_find(-1))
        self.assertIsNone(self.run_find(0, 'image/gif'))

if __name__ == '__main__':
    unittest.main()
