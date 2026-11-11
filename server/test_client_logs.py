"""Exercise the client's actual multipart/zlib upload contract over HTTP."""
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
import zlib
from urllib.parse import urlencode
from pathlib import Path
from http.server import ThreadingHTTPServer

from offline_server import Config, Store, make_handler, response_for


def multipart(payload):
    return (b'--gxb-test\r\nContent-Disposition: form-data; name="payload"\r\n'
            b'\r\n' + payload + b'\r\n--gxb-test--\r\n')


class ClientLogsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'state.sqlite3'
        store = Store(self.db)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Config('127.0.0.1', 18080), store))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.tmp.cleanup()

    def post(self, compressed):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        connection.request('POST', '/client-log', multipart(compressed),
                           {'Content-Type': 'multipart/form-data; boundary=gxb-test'})
        response = connection.getresponse()
        status, data = response.status, json.loads(response.read())
        connection.close()
        return status, data

    def test_persist_before_acknowledging(self):
        entries = [{'rowid': 7, 'time': 123, 'log': 'LUA ERROR: test\nstack traceback:\n\tSummonWindow.lua'}]
        status, data = self.post(zlib.compress(json.dumps(entries).encode()))
        self.assertEqual((status, data), (200, {'received': 1}))
        with sqlite3.connect(self.db) as connection:
            saved = connection.execute('SELECT payload_json FROM client_error_log').fetchone()
        self.assertEqual(json.loads(saved[0]), entries[0])

    def test_invalid_upload_is_not_acknowledged(self):
        for data in (b'not zlib', zlib.compress(b'{}'), zlib.compress(b'[{"wrong":"field"}]'),
                     zlib.compress(b'[]') + b'trailing', zlib.compress(b' ' * (9 * 1024 * 1024))):
            with self.subTest(data_length=len(data)):
                self.assertEqual(self.post(data)[0], 400)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM client_error_log').fetchone()[0], 0)

    def test_token_enables_existing_error_uploader(self):
        config = Config('127.0.0.1', 18080)
        self.assertEqual(response_for({'mid': 1}, config)['log_url'], 'http://127.0.0.1:18080/client-log')

    def test_unimplemented_chat_is_not_a_success_with_nil_host(self):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        connection.request('POST', '/api/v1', urlencode({'payload': json.dumps({'mid': 192})}),
                           {'Content-Type': 'application/x-www-form-urlencoded'})
        response = connection.getresponse()
        self.assertEqual(response.status, 503)
        self.assertEqual(json.loads(response.read()), {'offline_unavailable': 'chat'})
        connection.close()


if __name__ == '__main__':
    unittest.main()
