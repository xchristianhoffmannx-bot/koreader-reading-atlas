import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from reading_atlas import books, config as cfg, i18n, living, llm, portraits, progress, states, sync
import test_epub_chapters as T

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import check_private  # noqa: E402


class ProviderTest(unittest.TestCase):
    def test_codex_is_the_default_and_api_providers_need_model_and_key(self):
        self.assertEqual(llm.load_provider({}, {}), {'provider': 'codex'})
        with self.assertRaises(ValueError):
            llm.load_provider({'ATLAS_PROVIDER': 'openai'}, {})                       # no model
        with self.assertRaises(ValueError):
            llm.load_provider({'ATLAS_PROVIDER': 'openai', 'ATLAS_MODEL': 'm'}, {})    # no key
        ok = llm.load_provider({'ATLAS_PROVIDER': 'gemini', 'ATLAS_MODEL': 'm', 'GEMINI_API_KEY': 'k'}, {})
        self.assertEqual(ok, {'provider': 'gemini', 'model': 'm', 'key': 'k'})
        with self.assertRaises(ValueError):
            llm.load_provider({'ATLAS_PROVIDER': 'nonsense'}, {})

    def test_each_api_provider_builds_its_request_and_parses_its_answer(self):
        schema = {'type': 'object'}
        cases = {
            'openai': ({'choices': [{'finish_reason': 'stop', 'message': {'content': '{"state": "x"}'}}]}, 'api.openai.com', 'Authorization'),
            'anthropic': ({'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '```json\n{"state": "x"}\n```'}]}, 'api.anthropic.com', 'x-api-key'),
            'gemini': ({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"state": "x"}'}]}}]}, 'generativelanguage.googleapis.com', 'x-goog-api-key'),
        }
        for provider, (answer, host, header) in cases.items():
            seen = {}

            def post(url, headers, body, answer=answer, seen=seen):
                seen.update(url=url, headers=headers, body=body)
                return answer
            client = llm.Client({'provider': provider, 'model': 'model-x', 'key': 'SECRET-KEY'}, post=post)
            self.assertEqual(client.ask('prompt', schema), {'state': 'x'})
            self.assertIn(host, seen['url'])
            self.assertIn(header, seen['headers'])
            self.assertNotIn('SECRET-KEY', json.dumps(seen['body']))            # the key only travels in the header
            self.assertNotIn('SECRET-KEY', seen['url'])

    def test_invalid_answer_is_retried_once_then_reported(self):
        calls = []

        def post(url, headers, body):
            calls.append(1)
            return {'choices': [{'finish_reason': 'length', 'message': {'content': '{'}}]}
        client = llm.Client({'provider': 'openai', 'model': 'm', 'key': 'k'}, post=post)
        with self.assertRaises(RuntimeError):
            client.ask('p', {})
        self.assertEqual(len(calls), 2)


class ProgressTest(unittest.TestCase):
    def test_positions_come_from_the_plugin_export_and_are_cached(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        requests = tmp / 'dev' / 'koreader' / 'settings' / 'reading_recap_requests'
        requests.mkdir(parents=True)
        (requests / ('a' * 32 + '.json')).write_text(json.dumps({'title': 'Book', 'cutoff': '/body/DocFragment[2]/body/p[1]/text().0', 'text': 'x' * 100}), encoding='utf-8')
        (requests / ('b' * 32 + '.json')).write_text(json.dumps({'title': 'Broken', 'cutoff': 'nonsense'}), encoding='utf-8')
        with mock.patch.object(cfg, 'data_home', return_value=tmp / 'home'):
            self.assertEqual(progress.update_from_device(tmp / 'dev'), ['a' * 32])
            self.assertEqual(progress.update_from_device(tmp / 'dev'), [])              # unchanged
            self.assertEqual(progress.get('a' * 32)['title'], 'Book')
            self.assertIsNone(progress.get('b' * 32))


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


class SyncTest(unittest.TestCase):
    @staticmethod
    def asker(prompt_text, schema, client, rules):
        if 'completeness' in prompt_text:
            return {'state': json.dumps({'nodes': [], 'edges': [], 'profile': []})}
        return {'state': json.dumps({'groups': [{'id': 'g', 'label': 'G'}], 'title': 'Test Book', 'kind': 'roman', 'stand': 'x',
                                     'glance': [], 'questions': [],
                                     'nodes': [{'id': 'a', 'name': 'Satz', 'group': 'g', 'kind': 'k', 'text': 't', 'anchor': 0}]})}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = self.tmp / 'home'
        self.home.mkdir()
        shutil.copy(T.make_epub(), self.tmp / 'book.epub')
        (self.home / 'atlas-books.json').write_text(json.dumps({'c' * 32: {'title': 'Test Book', 'epub': str(self.tmp / 'book.epub')}}), encoding='utf-8')
        (self.home / 'progress.json').write_text(json.dumps({'c' * 32: {'title': 'Test Book', 'updated': '01.01.2026',
                                                                         'cutoff': '/body/DocFragment[3]/body/section/p[2]/text().0'}}), encoding='utf-8')
        patches = [mock.patch.object(cfg, 'data_home', return_value=self.home), mock.patch.object(states, 'HERE', self.home),
                   mock.patch.object(books, 'CONFIG', self.home / 'atlas-books.json'), mock.patch.object(books, 'CACHE', self.home / 'cache'),
                   mock.patch.object(living, 'HERE', self.home), mock.patch.object(portraits, 'IMAGES', self.home / 'atlas-images'),
                   mock.patch.object(portraits, 'HERE', self.home), mock.patch.object(states, 'LANG', 'en'),
                   mock.patch.object(states, 'CHUNK', states.CHUNK), mock.patch.object(portraits, 'LANG', 'en'),
                   mock.patch.object(portraits, 'MIN_FEATURES', portraits.MIN_FEATURES), mock.patch.object(portraits, 'CORE', portraits.CORE)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def build(self, language='en'):
        settings = dict(cfg.DEFAULTS, language=language, drive_dir=str(self.tmp / 'drive'))
        return sync.build(settings, client=object(), asker=self.asker)

    def test_build_writes_one_page_copies_it_and_is_idempotent(self):
        self.assertEqual(self.build(), (1, 1, 0))
        page = (self.home / 'atlas' / 'test-book.html').read_text(encoding='utf-8')
        self.assertIn('Your reading position', page)
        self.assertIn('id="atlas-data"', page)
        self.assertEqual((self.tmp / 'drive' / 'Reading Atlas' / 'test-book.html').read_text(encoding='utf-8'), page)
        self.assertEqual(self.build(), (0, 0, 0))                                      # nothing changed, nothing rebuilt

    def test_german_pages_use_the_german_interface(self):
        self.build('de')
        page = (self.home / 'atlas' / 'test-book.html').read_text(encoding='utf-8')
        self.assertIn('Dein Lesestand', page)
        self.assertNotIn('Your reading position', page)

    def test_book_without_reading_position_is_skipped_not_failed(self):
        (self.home / 'progress.json').unlink()
        self.assertEqual(self.build(), (0, 0, 0))


class PrivacyTest(unittest.TestCase):
    def test_repository_contains_nothing_personal(self):
        self.assertEqual(check_private.scan(ROOT), [])

    def test_checker_catches_what_it_should(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / 'a.py').write_text('key = "sk-' + 'a' * 30 + '"\npath = "C:\\\\Users\\\\someone\\\\x"\nmail = "someone' + '@private.org"\n', encoding='utf-8')
        (tmp / 'b.txt').write_text('A Secret Book Title', encoding='utf-8')
        (tmp / 'cover.png').write_bytes(b'x')
        found = ' | '.join(why for _rel, why in check_private.scan(tmp, ['secret book']))
        for expected in ('matches sk-', 'someone' + '@private.org', 'forbidden term', 'binary or book/image file'):
            self.assertIn(expected, found)


if __name__ == '__main__':
    unittest.main()
