import json, tempfile, unittest
from pathlib import Path
from reading_atlas import geo_map as G

LAND = {'features': [{'geometry': {'type': 'Polygon', 'coordinates': [[[-10, 40], [10, 40], [10, 60], [-10, 60], [-10, 40]]]}},
                     {'geometry': {'type': 'Polygon', 'coordinates': [[[100, 0], [101, 0], [101, 1], [100, 1], [100, 0]]]}}]}


class GeoTest(unittest.TestCase):
    def test_marker_inside_view_far_land_dropped_and_clipped(self):
        path = Path(tempfile.mkdtemp()) / 'land.json'
        path.write_text(json.dumps(LAND), encoding='utf-8')
        r = G.build([{'n': 1, 'name': 'X', 'lat': 50, 'lon': 0, 'current': True}], [], path)
        self.assertEqual(len(r['land']), 1)                       # distant polygon skipped
        m = r['markers'][0]
        self.assertTrue(0 < m['x'] < r['w'] and 0 < m['y'] < r['h'])
        self.assertLessEqual(r['h'], 640)

    def test_north_is_up(self):
        path = Path(tempfile.mkdtemp()) / 'land.json'
        path.write_text(json.dumps(LAND), encoding='utf-8')
        r = G.build([{'n': 1, 'name': 'S', 'lat': 45, 'lon': 0}, {'n': 2, 'name': 'N', 'lat': 55, 'lon': 0}], [], path)
        self.assertLess(r['markers'][1]['y'], r['markers'][0]['y'])

    def test_nothing_to_place(self):
        self.assertIsNone(G.build([], []))

if __name__ == '__main__':
    unittest.main()
