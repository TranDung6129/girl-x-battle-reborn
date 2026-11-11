import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
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
        with patch('offline_server.random.choice', return_value=10001001):
            one, ten = self.draw(1, 1), self.draw(1, 3)
        self.assertEqual(len(one['result']), 1)
        self.assertEqual(len(ten['result']), 10)
        self.assertTrue(one['result'][0]['is_partner'])
        self.assertTrue(all(not hero['is_partner'] and hero['to_stone'] for hero in ten['result']))
        self.assertTrue(all(hero['table_id'] == 40001001 for hero in ten['result']))
        restarted = Store(self.path)
        login = response_for({'mid': 1}, self.config, restarted)
        self.assertEqual(len(login['detail']['49']['heros']), 1)
        self.assertEqual(login['detail']['81']['list'][0]['item_num'], 10)
        self.assertEqual(login['detail']['17']['guide_id'], 100197)
        self.assertEqual([hero['partner_id'] for hero in login['detail']['49']['heros']],
                         [one['result'][0]['partner_id']])

    def test_crystal_ten_and_invalid_request(self):
        self.assertEqual(len(self.draw(2, 2)['result']), 10)
        with self.assertRaises(ValueError):
            self.draw(1, 999)
        self.assertEqual(len(self.store.heroes()) + sum(x['item_num'] for x in self.store.items()), 10)

    def test_concurrent_draws_keep_unique_ids(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.draw(1, 3), range(4)))
        ids = [hero['partner_id'] for answer in results for hero in answer['result'] if hero['is_partner']]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertLessEqual(len(self.store.heroes()), 5)
        self.assertEqual(len(self.store.heroes()) + sum(x['item_num'] for x in self.store.items()), 40)

    def test_existing_duplicates_preserved(self):
        with self.store.connect() as con:
            con.executemany('INSERT INTO offline_heroes(table_id) VALUES(?)', [(10001001,), (10001001,)])
        with patch('offline_server.random.choice', return_value=10001001):
            self.assertTrue(self.draw(1, 1)['result'][0]['to_stone'])
        self.assertEqual(len(Store(self.path).heroes()), 2)

    def test_max_account_and_world_map(self):
        player = response_for({'mid': 17}, self.config, self.store)
        self.assertEqual((player['lev'], player['vip'], player['max_energy']), (100, 15, 160))
        self.assertLess(player['exp'], 613615)
        world = response_for({'mid': 112}, self.config, self.store)
        self.assertEqual([len(world[k]) for k in ('normal', 'super', 'challenge')], [11, 6, 18])
        for kind in ('normal', 'super', 'challenge'):
            for stage in world[kind]:
                self.assertEqual(stage['star'], 0)
                self.assertIn('reset_count', stage)
        self.assertEqual(world['chapter_info']['normal_campaign_id'], 100001)
        login = response_for({'mid': 1}, self.config, self.store)
        self.assertEqual(login['detail']['112'], world['chapter_info'])

    def test_old_tutorial_upload_cannot_reenable_blocking_guide(self):
        response_for({'mid': 26, 'story_id': 1, 'story_state': 0, 'guide_id': 100104}, self.config, self.store)
        self.assertEqual(Store(self.path).profile()['guide_id'], 100197)
