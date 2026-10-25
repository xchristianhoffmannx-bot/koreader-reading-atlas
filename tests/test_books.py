import shutil, tempfile, unittest
from pathlib import Path
from reading_atlas import books
from reading_atlas import epub_chapters as E
import test_epub_chapters as T


class BooksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        books.CACHE = self.tmp / 'cache'
        docs = self.tmp / 'kindle' / 'documents'
        (docs / 'Wiki-Lesestoff').mkdir(parents=True)
        shutil.copy(T.make_epub(), docs / 'Buch.epub')
        shutil.copy(T.make_epub(), docs / 'Wiki-Lesestoff' / 'Artikel.epub')
        self.device = self.tmp / 'kindle'

    def test_scan_skips_wiki_reading_material_and_ids_match_koreader_hash(self):
        found = books.scan_device(self.device)
        self.assertEqual(len(found), 1)
        (book_id, path), = found.items()
        self.assertEqual(book_id, E.partial_md5(path))

    def test_device_copy_is_cached_so_later_runs_work_without_kindle(self):
        cfg = {'title': 'Buch', 'device_file': 'Buch.epub'}
        first = books.resolve_epub('a' * 32, cfg, self.device)
        self.assertTrue(first.exists())
        self.assertEqual(books.resolve_epub('a' * 32, cfg, None), first)       # no device: cache is used
        self.assertIsNone(books.resolve_epub('b' * 32, cfg, None))             # unknown book, no device

    def test_estimate_counts_states_and_characters(self):
        book = E.load(T.make_epub())
        count, chars = books.estimate(book, '/body/DocFragment[3]/body/section/p[2]/text().0')
        self.assertEqual(count, 2)
        self.assertGreater(chars, 0)
        self.assertEqual(books.estimate(book, '/body/DocFragment[1]/body/section/p[1]/text().0'), (0, 0))

if __name__ == '__main__':
    unittest.main()
