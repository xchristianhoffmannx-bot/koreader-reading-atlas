"""Regression tests for the low audit findings N1 to N8."""
import base64
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from reading_atlas import books, cli, config as cfg, enrich_profiles, geo_map, living, llm, portraits, progress, states, sync


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)


class DataHomeTest(TempCase):
    def test_n1_home_set_after_import_is_used_by_every_module(self):
        keep = [mock.patch.object(m, 'HERE', m.HERE) for m in (enrich_profiles, geo_map, living, portraits, states, books)]
        keep += [mock.patch.object(books, 'CONFIG', books.CONFIG), mock.patch.object(books, 'CACHE', books.CACHE),
                 mock.patch.object(geo_map, 'GEO', geo_map.GEO), mock.patch.object(portraits, 'IMAGES', portraits.IMAGES),
                 mock.patch.object(states, 'LANG', 'en'), mock.patch.object(states, 'CHUNK', states.CHUNK),
                 mock.patch.object(portraits, 'LANG', 'en'), mock.patch.object(portraits, 'MIN_FEATURES', portraits.MIN_FEATURES),
                 mock.patch.object(portraits, 'CORE', portraits.CORE)]
        for p in keep:
            p.start()
            self.addCleanup(p.stop)
        with mock.patch.dict(os.environ, {'READING_ATLAS_HOME': str(self.tmp)}):
            sync.configure(dict(cfg.DEFAULTS))
        for module in (enrich_profiles, geo_map, living, portraits, states, books):
            self.assertEqual(module.HERE, self.tmp, module.__name__)
        self.assertEqual(books.CONFIG, self.tmp / 'atlas-books.json')
        self.assertEqual(geo_map.GEO, self.tmp / 'atlas-geo')
        self.assertEqual(portraits.IMAGES, self.tmp / 'atlas-images')


class PageTest(unittest.TestCase):
    def test_n2_html_comment_opener_in_the_data_cannot_break_the_page(self):
        data = {'lang': 'en', 'title': 'x', 'note': '<!--<script> and </script> and <!-- again'}
        page = living.render(data)
        blob = re.search(r'id="atlas-data"[^>]*>(.*?)</script>', page, re.S).group(1)
        self.assertNotIn('<!--', blob)
        self.assertNotIn('</', blob)
        self.assertEqual(json.loads(blob), data)

    def test_n2_content_security_policy_names_the_hash_of_the_page_script(self):
        page = living.render({'lang': 'de', 'title': 'x'})
        csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
        script = re.search(r'<script>(.*?)</script>', page, re.S).group(1)
        digest = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode()
        self.assertIn(f"script-src 'sha256-{digest}'", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertEqual(page.count('<script>'), 1)               # no other inline script that the policy would block


class LandFileTest(TempCase):
    def fetch(self, payload):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n=-1): return payload[:n] if n >= 0 else payload
        return mock.patch.object(geo_map.urllib.request, 'urlopen', return_value=Response())

    def test_n3_download_must_match_the_pinned_checksum(self):
        good = b'{"features": []}'
        with mock.patch.object(geo_map, 'GEO', self.tmp), mock.patch.object(geo_map, 'agent', return_value='t'), \
                mock.patch.object(geo_map, 'LAND_SHA256', hashlib.sha256(good).hexdigest()):
            with self.fetch(b'{"features": ["tampered"]}'):
                with self.assertRaises(RuntimeError):
                    geo_map.land_file()
            self.assertFalse((self.tmp / 'ne_10m_land.geojson').exists())      # nothing wrong is kept
            with self.fetch(good):
                self.assertEqual(geo_map.land_file().read_bytes(), good)

    def test_n3_url_is_pinned_to_a_commit_not_a_branch(self):
        self.assertRegex(geo_map.LAND_URL, r'/[0-9a-f]{40}/')
        self.assertNotIn('/master/', geo_map.LAND_URL)


class DeviceTest(TempCase):
    def test_n4_only_koreader_book_ids_are_accepted(self):
        folder = self.tmp / 'koreader' / 'settings' / 'reading_recap_requests'
        folder.mkdir(parents=True)
        good = 'a1' * 16
        for name in (good, '.', '..', 'not-a-hash', 'A1' * 16):
            (folder / (name + '.json')).write_text(json.dumps({'cutoff': '/body/DocFragment[1]', 'title': 'T'}), encoding='utf-8')
        home = self.tmp / 'home'
        home.mkdir()
        with mock.patch.object(cfg, 'data_home', return_value=home):
            self.assertEqual(progress.update_from_device(self.tmp), [good])


class CodexPathTest(TempCase):
    def make(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        for name in ('codex', 'codex.exe'):
            (folder / name).write_text('x')
            (folder / name).chmod(0o755)

    def test_n5_a_codex_in_the_current_folder_or_a_relative_path_entry_is_never_used(self):
        planted = self.tmp / 'planted'
        self.make(planted)
        cwd = os.getcwd()
        os.chdir(planted)
        self.addCleanup(os.chdir, cwd)
        env = {'PATH': os.pathsep.join(['', '.', 'bin']), 'PATHEXT': '.EXE'}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop('LOCALAPPDATA', None)
            self.assertIsNone(llm.find_codex())

    def test_n5_an_absolute_path_entry_is_found(self):
        real = self.tmp / 'real'
        self.make(real)
        with mock.patch.dict(os.environ, {'PATH': str(real), 'PATHEXT': '.EXE'}, clear=False):
            os.environ.pop('LOCALAPPDATA', None)
            self.assertEqual(Path(llm.find_codex()).parent, real)


class OrderTest(unittest.TestCase):
    def test_n6_very_long_after_chains_do_not_hit_the_recursion_limit(self):
        events = {f'e{i}': {'id': f'e{i}', 'after': f'e{i - 1}' if i else ''} for i in range(5000)}
        ordered = list(states.order_events(dict(reversed(list(events.items())))))
        self.assertEqual(ordered, [f'e{i}' for i in range(5000)])

    def test_n6_order_and_cycles_behave_as_before(self):
        events = {'a': {'id': 'a', 'after': ''}, 'b': {'id': 'b', 'after': 'c'}, 'c': {'id': 'c', 'after': ''}, 'd': {'id': 'd', 'after': 'c'}}
        self.assertEqual(list(states.order_events(events)), ['a', 'c', 'b', 'd'])
        cyclic = {'x': {'id': 'x', 'after': 'y'}, 'y': {'id': 'y', 'after': 'x'}}
        self.assertEqual(sorted(states.order_events(cyclic)), ['x', 'y'])


class RobustFilesTest(TempCase):
    def test_n7_book_list_is_written_atomically(self):
        with mock.patch.object(books, 'CONFIG', self.tmp / 'atlas-books.json'):
            books.save({'a': {'title': 'Ä'}})
            self.assertEqual(books.load(), {'a': {'title': 'Ä'}})
        self.assertEqual([p.name for p in self.tmp.iterdir()], ['atlas-books.json'])      # no leftover temp file

    def test_n7_broken_geocache_is_rebuilt_not_fatal(self):
        (self.tmp / 'geocache.json').write_text('{"half', encoding='utf-8')
        rows = [{'lat': '1', 'lon': '2', 'boundingbox': ['0', '1', '2', '3'], 'display_name': 'X'}]
        with mock.patch.object(geo_map, 'GEO', self.tmp):
            self.assertEqual(geo_map.nominatim('X', fetch=lambda url: rows)['lat'], 1.0)
            self.assertIn('X', json.loads((self.tmp / 'geocache.json').read_text(encoding='utf-8')))

    def test_n7_one_failing_place_lookup_is_skipped(self):
        def locate(query):
            if query == 'bad':
                raise OSError('down')
            return {'lat': 1, 'lon': 2}
        with mock.patch('builtins.print'):
            self.assertIsNone(living.lookup(locate, 'bad'))
        self.assertEqual(living.lookup(locate, 'ok'), {'lat': 1, 'lon': 2})


class CliTest(TempCase):
    def test_n8_approve_without_figures_is_a_clear_message_not_a_traceback(self):
        with mock.patch.dict(os.environ, {'READING_ATLAS_HOME': str(self.tmp)}), \
                mock.patch.object(sync, 'configure'), mock.patch.object(states, 'load_clean', return_value=[]):
            for action in ('approve', 'reject'):
                with self.assertRaises(SystemExit) as stop:
                    cli.main(['portraits', action, 'b' * 32])
                self.assertIn('needs figure ids', str(stop.exception))

    def test_n8_error_messages_in_the_code_are_english(self):
        source = (Path(__file__).resolve().parent.parent / 'reading_atlas' / 'states.py').read_text(encoding='utf-8')
        self.assertNotIn('Lesestelle liegt', source)


if __name__ == '__main__':
    unittest.main()
