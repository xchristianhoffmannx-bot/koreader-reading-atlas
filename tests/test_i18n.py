import re
import unittest
from pathlib import Path

from reading_atlas import i18n

ROOT = Path(__file__).resolve().parent.parent


class I18nTest(unittest.TestCase):
    page = (ROOT / 'reading_atlas' / 'templates' / 'atlas.html').read_text(encoding='utf-8')

    def test_table_is_a_bijection_and_every_entry_is_used(self):
        english = [row[0] for row in i18n.TABLE]
        german = [row[1] for row in i18n.TABLE]
        self.assertEqual(len(set(english)), len(english))
        self.assertEqual(len(set(german)), len(german))
        for en, de, raw in i18n.TABLE:
            self.assertIn(en, self.page, en)                                          # no stale entries

    def test_no_german_vocabulary_is_left_in_the_english_page(self):
        words = lambda text: set(re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", text))
        german = set().union(*(words(de) for _en, de, _raw in i18n.TABLE)) - set().union(*(words(en) for en, _de, _raw in i18n.TABLE))
        english = {w.lower() for w in set().union(*(words(en) for en, _de, _raw in i18n.TABLE))}
        german = {w for w in german if w[0].isupper() and w.lower() not in english}   # visible German starts with a capital
        visible = re.sub(r'<style>.*?</style>', '', self.page, flags=re.S)
        left = sorted({w for w in words(visible) if w in german})
        self.assertEqual(left, [])

    def test_english_page_has_no_german_and_german_page_has_no_english_leftovers(self):
        visible = re.sub(r'<style>.*?</style>', '', self.page, flags=re.S)
        self.assertEqual(re.findall(r'[äöüÄÖÜß]', re.sub(r'\[A-Za-zÄÖÜäöüÆæ0-9\]', '', visible)), [])
        german = i18n.translate(self.page, 'de')
        self.assertIn('Dein Lesestand', german)
        self.assertNotIn('Your reading position', german)
        self.assertIn('<html lang="de">', german)
        self.assertIn('{{DATA}}', german)


if __name__ == '__main__':
    unittest.main()
