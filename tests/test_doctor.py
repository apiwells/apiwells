import contextlib
import io
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from apiwells.cli import diagnose, main, endpoint


class Handler(BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.handle_check()
    def do_POST(self):
        self.handle_check()
    def handle_check(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        Handler.calls.append((self.path, self.headers.get('Authorization'), body))
        prefix = self.path.split('/')[1]
        code = int(prefix) if prefix.isdigit() else 200
        self.send_response(code)
        if code == 302:
            self.send_header('Location', '/v1/models')
        self.end_headers()
        if prefix == 'slow':
            time.sleep(.15)
        if prefix == 'invalid':
            raw = b'<html>login</html>'
        elif prefix == 'large':
            raw = b'x' * (2 * 1024 * 1024 + 1)
        elif prefix == 'schema':
            raw = b'{"data":[{}]}'
        elif prefix == 'error':
            raw = b'{"error":{"message":"secret-test-key"}}'
        elif self.path.endswith('/chat/completions'):
            raw = b'{"choices":[{"message":{"role":"assistant","content":"OK"}}]}'
        else:
            raw = b'{"data":[{"id":"secret-test-key"}]}'
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass


class DoctorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
    def test_models_and_redaction(self):
        r = diagnose(self.base + '/v1/', 'secret-test-key')
        self.assertTrue(r['ok'])
        self.assertEqual(r['model_count'], 1)
        self.assertNotIn('secret-test-key', json.dumps(r))
        self.assertEqual(Handler.calls[-1][:2], ('/v1/models', 'Bearer secret-test-key'))
    def test_chat_payload(self):
        r = diagnose(self.base + '/v1', 'key', model='demo')
        self.assertTrue(r['ok'])
        body = json.loads(Handler.calls[-1][2])
        self.assertEqual(body['model'], 'demo')
        self.assertEqual(body['max_tokens'], 8)
        self.assertFalse(body['stream'])
    def test_http_failures_no_retry(self):
        for status, cat in [(400,'bad_request'), (401,'authentication'), (403,'forbidden'),
                            (404,'not_found'), (405,'method_not_allowed'), (429,'rate_or_quota'), (500,'server_error')]:
            with self.subTest(status=status):
                n = len(Handler.calls)
                r = diagnose(self.base + '/' + str(status))
                self.assertEqual(r['category'], cat)
                self.assertEqual(len(Handler.calls), n + 1)
    def test_redirect_not_followed(self):
        n = len(Handler.calls)
        self.assertEqual(diagnose(self.base + '/302', 'key')['category'], 'redirect')
        self.assertEqual(len(Handler.calls), n + 1)
    def test_response_validation(self):
        for path, cat in [('invalid', 'invalid_json'), ('schema', 'unexpected_schema'),
                          ('error','unexpected_schema'), ('large', 'response_too_large')]:
            self.assertEqual(diagnose(self.base + '/' + path)['category'], cat)
    def test_timeout(self):
        self.assertEqual(diagnose(self.base + '/slow', timeout=.03)['category'], 'timeout')
    def test_invalid_config(self):
        for url in ['ftp://example.com', 'https://u:p@example.com', 'https://example.com?key=x',
                    'https://example.com#x', 'https://example.com:bad', 'http://example.com',
                    'https://example.com/v1/models', 'https://exam\nple.com']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                endpoint(url)
        for timeout in [0, -1, float('nan'), float('inf'), 301]:
            with self.assertRaises(ValueError):
                diagnose(self.base, timeout=timeout)
        with self.assertRaises(ValueError):
            diagnose(self.base, 'key\r\nInjected: x')
    def test_proxy_ignored_by_default(self):
        with patch.dict(os.environ, {'http_proxy':'http://127.0.0.1:1', 'HTTP_PROXY':'http://127.0.0.1:1', 'no_proxy':'', 'NO_PROXY':''}):
            self.assertTrue(diagnose(self.base + '/v1')['ok'])
    def test_cli_json_exit_codes(self):
        for path, expected in [('v1', 0), ('401', 1)]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(['doctor','--base-url',self.base+'/'+path,'--anonymous','--json'])
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(out.getvalue())['ok'], expected == 0)
    def test_cli_usage_error(self):
        for extra in [['--chat'], ['--model','demo'], ['--timeout','nan']]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
                main(['doctor','--base-url',self.base,'--anonymous'] + extra)
            self.assertEqual(e.exception.code, 2)
    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
            main(['doctor','--base-url',self.base])
        self.assertEqual(e.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
