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

    def _build(self, places):
        path = Path(tempfile.mkdtemp()) / 'land.json'
        path.write_text(json.dumps(LAND), encoding='utf-8')
        return G.build([{'n': i + 1, 'name': f'P{i + 1}', 'lat': la, 'lon': lo} for i, (la, lo) in enumerate(places)], [], path)

    def test_far_place_gets_edge_marker_and_nothing_is_dropped(self):
        near = [(52.0, 0.0), (51.5, 0.3), (51.8, -0.4), (52.4, 0.8), (51.2, -0.9)]
        r = self._build(near + [(47.0, 3.0)])                     # one place far to the south
        self.assertEqual(len(r['markers']), 6)                    # every place keeps a pin
        edges = [m for m in r['markers'] if 'edge' in m]
        self.assertEqual([m['name'] for m in edges], ['P6'])
        self.assertTrue(25 <= edges[0]['y'] <= r['h'] - 25)       # sits inside the picture, arrow points outwards
        self.assertTrue(all('edge' not in m for m in r['markers'] if m['name'] != 'P6'))

    def test_evenly_spread_places_have_no_edge_marker(self):
        r = self._build([(50, 0), (51, 1), (52, 0), (53, 1), (54, 0)])
        self.assertTrue(all('edge' not in m for m in r['markers']))

    def test_nothing_to_place(self):
        self.assertIsNone(G.build([], []))

if __name__ == '__main__':
    unittest.main()
