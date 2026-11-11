import hashlib
import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from asset_server import AssetIndex
from offline_server import Config, Store, make_handler, response_for


class AssetsTest(unittest.TestCase):
    def test_client_download_and_wrong_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'res' / 'web'
            (root / 'images').mkdir(parents=True)
            content = b'preserved image bytes'
            (root / 'images' / '10002001.png').write_bytes(content)
            config = Config('127.0.0.1', 18080, root)
            self.assertEqual(response_for({'mid': 20480}, config)['res_download_url'],
                             'http://127.0.0.1:18080/assets/')
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(config, Store(Path(directory) / 'state.db')))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                for digest, status in ((hashlib.md5(content).hexdigest(), 200), ('0' * 32, 404)):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
                    connection.request('GET', '/assets/10002001.png.' + digest)
                    response = connection.getresponse()
                    data = response.read()
                    self.assertEqual(response.status, status)
                    if status == 200:
                        self.assertEqual(data, content)
                    connection.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
            index = AssetIndex(root)
            self.assertIsNone(index.find('../state.db.' + '0' * 32))

    def test_same_basename_is_disambiguated_by_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (('first', b'a'), ('second', b'b')):
                (root / name).mkdir()
                (root / name / 'icon.png').write_bytes(value)
            index = AssetIndex(root)
            path = index.find('icon.png.' + hashlib.md5(b'b').hexdigest())
            self.assertEqual(path.read_bytes(), b'b')
