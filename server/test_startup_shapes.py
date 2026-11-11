"""Contracts for the missing fields identified by the device Lua tracebacks."""
import unittest
from offline_server import Config, response_for


class StartupShapesTest(unittest.TestCase):
    def response(self, mid):
        return response_for({'mid': mid}, Config('127.0.0.1', 18080))

    def test_library_iteration_and_background_clock(self):
        data = self.response(836)
        self.assertIsInstance(data['library_talk_infos'], dict)
        self.assertIsInstance(data['library_infos'], dict)
        self.assertIsInstance(data['library_bg_infos']['server_time'], int)

    def test_illusion_status_comparison(self):
        data = self.response(1344)
        self.assertLess(data['paradise_info']['count'], 1)
        self.assertGreater(data['paradise_info']['paradise_id'], 0)

    def test_social_lists_are_iterable(self):
        data = self.response(176)
        for key in ('blacklist', 'friend_list', 'notice_list', 'request_list', 'offline_msg_list'):
            self.assertIsInstance(data[key], list)

    def test_achievement_iteration(self):
        data = self.response(1302)
        self.assertIsInstance(data['achieve_list'], list)
        self.assertIsInstance(data['base_info']['award_status'], list)
