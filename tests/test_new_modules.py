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


class NetworkTest(unittest.TestCase):
    """Client._post against a fake opener: retries, error details, size limit."""
    KEY = 'sk-secret-key'

    def client(self):
        return llm.Client({'provider': 'openai', 'model': 'm', 'key': self.KEY})

    def run_post(self, steps, **patches):
        """steps: HTTPError or bytes per attempt; returns (result or exception, sleeps)."""
        sleeps, queue = [], list(steps)
        patches.setdefault('MAX_ANSWER', llm.MAX_ANSWER)

        class Response:
            def __init__(self, raw): self.raw = raw
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n=-1): return self.raw[:n] if n >= 0 else self.raw

        class Opener:
            def open(self, request, timeout=None):
                step = queue.pop(0)
                if isinstance(step, BaseException):
                    raise step
                return Response(step)
        with mock.patch.object(llm.urllib.request, 'build_opener', return_value=Opener()),                 mock.patch.object(llm, 'sleep', sleeps.append), mock.patch.multiple(llm, **patches):
            try:
                return self.client()._post('https://x', {}, {}), sleeps
            except RuntimeError as error:
                return error, sleeps

    @staticmethod
    def http(code, body=b'', headers=None):
        import email.message, io, urllib.error
        message = email.message.Message()
        for k, v in (headers or {}).items():
            message[k] = v
        return urllib.error.HTTPError('https://x', code, 'err', message, io.BytesIO(body))

    def test_rate_limits_and_server_errors_are_retried_with_backoff(self):
        result, sleeps = self.run_post([self.http(429), self.http(503), b'{"ok": 1}'])
        self.assertEqual(result, {'ok': 1})
        self.assertEqual(sleeps, [2, 8])

    def test_retry_after_header_is_honoured_and_capped(self):
        _, sleeps = self.run_post([self.http(429, headers={'Retry-After': '5'}), self.http(429, headers={'Retry-After': '9999'}), b'{}'])
        self.assertEqual(sleeps, [5, 120])

    def test_gives_up_after_four_attempts(self):
        result, sleeps = self.run_post([self.http(500)] * 4)
        self.assertIsInstance(result, RuntimeError)
        self.assertIn('gave up after 4 attempts', str(result))
        self.assertEqual(sleeps, [2, 8, 30])

    def test_connection_errors_and_garbled_json_are_retried(self):
        import urllib.error
        result, sleeps = self.run_post([urllib.error.URLError('down'), b'{"cut', b'{"a": 2}'])
        self.assertEqual(result, {'a': 2})
        self.assertEqual(len(sleeps), 2)

    def test_client_errors_are_not_retried_and_show_the_providers_message_without_the_key(self):
        body = ('{"error": {"message": "Incorrect API key provided: ' + self.KEY + '"}}').encode()
        result, sleeps = self.run_post([self.http(401, body)])
        self.assertIsInstance(result, RuntimeError)
        self.assertIn('HTTP 401: Incorrect API key provided', str(result))
        self.assertNotIn(self.KEY, str(result))
        self.assertEqual(sleeps, [])

    def test_an_oversized_answer_is_an_error_not_a_silent_cut(self):
        result, _ = self.run_post([b'{"a": "' + b'x' * 50 + b'"}'], MAX_ANSWER=20)
        self.assertIsInstance(result, RuntimeError)
        self.assertIn('larger than', str(result))


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

    def test_position_moving_back_removes_later_chapters_from_the_page(self):
        def states_in_page():
            page = (self.home / 'atlas' / 'test-book.html').read_text(encoding='utf-8')
            blob = re.search(r'id="atlas-data"[^>]*>(.*?)</script>', page, re.S).group(1)
            return json.loads(blob)['states']
        self.build()
        self.assertEqual(len(states_in_page()), 2)                                      # read into chapter 2
        progress = json.loads((self.home / 'progress.json').read_text(encoding='utf-8'))
        progress['c' * 32]['cutoff'] = '/body/DocFragment[2]/body/section/p[3]/text().0'  # back to chapter 1
        (self.home / 'progress.json').write_text(json.dumps(progress), encoding='utf-8')
        self.build()
        shown = states_in_page()
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]['label'], 'Oakfield, October 1013')

    def test_page_title_is_the_configured_title_not_the_models_guess(self):
        def asker(prompt_text, schema, client, rules):
            answer = json.loads(self.asker(prompt_text, schema, client, rules)['state'])
            answer['title'] = 'Wrong Title'
            return {'state': json.dumps(answer)}
        settings = dict(cfg.DEFAULTS, language='en', drive_dir=str(self.tmp / 'drive'))
        sync.build(settings, client=object(), asker=asker)
        page = (self.home / 'atlas' / 'test-book.html').read_text(encoding='utf-8')
        data = json.loads(re.search(r'id="atlas-data"[^>]*>(.*?)</script>', page, re.S).group(1))
        self.assertEqual(data['title'], 'Test Book')
        self.assertEqual({s['state']['title'] for s in data['states']}, {'Test Book'})

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
