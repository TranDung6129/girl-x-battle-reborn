import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from offline_server import Config, Store, response_for


class SummonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'state.sqlite3'
        self.store = Store(self.path)
        self.config = Config('127.0.0.1', 18080)

    def tearDown(self):
        self.tmp.cleanup()

    def draw(self, kind, index):
        return response_for({'mid': 50, 'summon_type': kind, 'summon_index': index}, self.config, self.store)

    def test_buy_one_ten_and_restart(self):
        one, ten = self.draw(1, 1), self.draw(1, 3)
        self.assertEqual(len(one['result']), 1)
        self.assertEqual(len(ten['result']), 10)
        granted = one['result'] + ten['result']
        self.assertEqual(len({hero['partner_id'] for hero in granted}), 11)
        self.assertTrue(all(hero['is_partner'] is True for hero in granted))
        restarted = Store(self.path)
        login = response_for({'mid': 1}, self.config, restarted)
        self.assertEqual(len(login['detail']['49']['heros']), 11)
        self.assertEqual(login['detail']['17']['guide_id'], 100197)
        self.assertEqual([hero['partner_id'] for hero in login['detail']['49']['heros']],
                         [hero['partner_id'] for hero in granted])

    def test_crystal_ten_and_invalid_request(self):
        self.assertEqual(len(self.draw(2, 2)['result']), 10)
        with self.assertRaises(ValueError):
            self.draw(1, 999)
        self.assertEqual(len(self.store.heroes()), 10)

    def test_concurrent_draws_keep_unique_ids(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.draw(1, 3), range(4)))
        ids = [hero['partner_id'] for answer in results for hero in answer['result']]
        self.assertEqual(len(set(ids)), 40)
        self.assertEqual(len(self.store.heroes()), 40)

    def test_old_tutorial_upload_cannot_reenable_blocking_guide(self):
        response_for({'mid': 26, 'story_id': 1, 'story_state': 0, 'guide_id': 100104}, self.config, self.store)
        self.assertEqual(Store(self.path).profile()['guide_id'], 100197)
