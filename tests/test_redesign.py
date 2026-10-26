"""The explore-first redesign of the page: structure, translation and the rules that must not regress."""
import re
import unittest
from pathlib import Path

from reading_atlas import i18n, living

PAGE = (Path(__file__).resolve().parent.parent / 'reading_atlas' / 'templates' / 'atlas.html').read_text(encoding='utf-8')
NEW_TEXTS = [
    ('All open riddles', 'Alle offenen Rätsel'), ('What is documented so far', 'Was bisher belegt ist'),
    ('Next riddle →', 'Nächstes Rätsel →'), ('Who is close to whom?', 'Wer steht wem nah?'),
    ('Spoiler-free: only what you have read up to your reading position is shown here.',
     'Spoilerfrei: Hier steht nur, was du bis zu deiner Lesestelle gelesen hast.'),
    ('Riddle ${qi+1} of ${qs.length}', 'Rätsel ${qi+1} von ${qs.length}'), ('Open in the story · ', 'Offen in der Geschichte · '),
]


class StructureTest(unittest.TestCase):
    def test_riddles_come_right_after_the_overview_and_the_nav_follows(self):
        order = re.findall(r'<section id="(\w+)"', PAGE)
        self.assertLess(order.index('blick'), order.index('offen'))
        self.assertLess(order.index('offen'), order.index('karte'))
        self.assertIn("[['blick','Start'],['offen','Riddles'],['figuren',L.nav],['verlauf','Timeline']", PAGE)

    def test_entry_elements_and_sheet_parts_exist_once(self):
        for ident in ('safe', 'entry', 'teaser', 't-show', 't-next', 'rnd', 'recap-btn', 'sheet-x', 'backdrop', 'stats'):
            self.assertEqual(PAGE.count(f'id="{ident}"'), 1, ident)
        self.assertEqual(PAGE.count('<script>'), 1)           # the Content-Security-Policy hashes exactly one inline script

    def test_nothing_from_the_review_draft_is_left(self):
        for leftover in ('data-new', 'NEU', 'Entwurf', 'Beispielseite'):
            self.assertNotIn(leftover, PAGE)

    def test_the_sheet_does_not_open_while_the_page_draws(self):
        select = re.search(r'function selectPerson\(id\)\{.*?\n \}', PAGE, re.S).group(0)
        self.assertNotIn('openSheet', select)                  # the first figure is selected on load, the sheet stays closed

    def test_new_state_is_additive_and_exported(self):
        self.assertIn("visited:store.visited||{}", PAGE)
        self.assertIn("store.laterN", PAGE)
        self.assertIn("const KEY='atlas:v1:'+", PAGE)           # the storage key is unchanged

    def test_motion_and_focus_rules_survive(self):
        self.assertIn('prefers-reduced-motion', PAGE)
        self.assertIn("lastFocus", PAGE)
        self.assertIn("aria-label=\"Close\"", PAGE)

    def test_leading_articles_are_skipped_in_both_languages(self):
        art = re.search(r'const ART=/\^\((.*?)\)\$/i', PAGE).group(1).split('|')
        for word in ('the', 'a', 'an', 'der', 'die', 'das', 'both', 'beiden'):
            self.assertIn(word, art)

    def test_group_shapes_and_colour_roles(self):
        self.assertIn('--riddle:', PAGE)
        self.assertIn('shape(gi(n.group),', PAGE)
        self.assertRegex(PAGE, r'\.pin \.dot\{fill:var\(--dust\)')    # red is reserved for "you are here"


class TranslationTest(unittest.TestCase):
    def test_german_page_has_the_new_texts_and_no_english_leftovers(self):
        german = i18n.translate(PAGE, 'de')
        for english, translated in NEW_TEXTS:
            self.assertIn(translated, german, translated)
            self.assertNotIn(english, german, english)

    def test_english_page_keeps_the_english_texts(self):
        for english, _ in NEW_TEXTS:
            self.assertIn(english, PAGE, english)

    def test_rendered_page_keeps_a_valid_policy_hash(self):
        import base64, hashlib
        page = living.render({'lang': 'de', 'title': 'x'})
        script = re.search(r'<script>(.*?)</script>', page, re.S).group(1)
        digest = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode()
        self.assertIn(f"'sha256-{digest}'", page)


if __name__ == '__main__':
    unittest.main()
