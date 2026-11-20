import http.client
import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def api():
    path = ROOT / 'server/realtime/console_controller.py'
    assert path.exists(), 'Self-service controller is not implemented yet'
    spec = importlib.util.spec_from_file_location('console_controller_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Backend:
    def __init__(self):
        self.launches = 0
        self.stops = 0
        self.ok = True
        self.block = None
        self.entered = threading.Event()
        self.dead = False

    def check(self, cancel=None):
        self.entered.set()
        if self.block:
            self.block.wait(3)
        return {'ready': self.ok, 'checks': [{'name': 'files', 'ok': self.ok}]}

    def launch(self, folder):
        self.launches += 1
        return self

    def poll(self):
        return 1 if self.dead else None

    def ready(self):
        return {'url': 'http://127.0.0.1:19874', 'session': 'session-' + str(self.launches)}

    def stop(self):
        self.stops += 1


def wait_status(controller, status):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        result = controller.snapshot()
        if result['status'] == status:
            return result
        time.sleep(.01)
    pytest.fail(str(controller.snapshot()))


def test_duplicate_start_reload_and_fresh_restart(tmp_path):
    m, backend = api(), Backend()
    controller = m.Controller(backend, tmp_path)
    try:
        assert controller.command('start')
        assert not controller.command('start')
        first = wait_status(controller, 'running')
        for _ in range(4):
            assert controller.snapshot()['session_id'] == first['session_id']
        assert controller.command('stop')
        wait_status(controller, 'idle')
        assert backend.stops == 1
        assert controller.command('start')
        second = wait_status(controller, 'running')
        assert second['session_id'] != first['session_id']
        assert second['run_id'] != first['run_id']
    finally:
        controller.close()
    assert backend.stops == 2


def test_failed_check_never_starts_camera(tmp_path):
    m, backend = api(), Backend()
    backend.ok = False
    controller = m.Controller(backend, tmp_path)
    try:
        controller.command('start')
        wait_status(controller, 'error')
        assert backend.launches == 0
        assert controller.target() is None
    finally:
        controller.close()


def test_stop_during_check_cancels_late_launch(tmp_path):
    m, backend = api(), Backend()
    backend.block = threading.Event()
    controller = m.Controller(backend, tmp_path)
    try:
        controller.command('start')
        assert backend.entered.wait(1)
        assert controller.command('stop')
        assert not controller.command('start')
        backend.block.set()
        wait_status(controller, 'idle')
        assert backend.launches == 0
    finally:
        controller.close()


def test_child_exit_clears_proxy_and_cleans_owned_job(tmp_path):
    m, backend = api(), Backend()
    controller = m.Controller(backend, tmp_path)
    try:
        controller.command('start')
        wait_status(controller, 'running')
        backend.dead = True
        wait_status(controller, 'error')
        assert controller.target() is None
        assert backend.stops == 1
    finally:
        controller.close()


def test_check_only_never_launches_and_unknown_command_rejected(tmp_path):
    m, backend = api(), Backend()
    controller = m.Controller(backend, tmp_path)
    try:
        assert not controller.command('shell')
        assert controller.command('check')
        wait_status(controller, 'idle')
        assert controller.snapshot()['preflight']['ready']
        assert backend.launches == 0
    finally:
        controller.close()


def test_http_origin_guard_allowlist_and_idle_state(tmp_path):
    m, backend = api(), Backend()
    controller = m.Controller(backend, tmp_path)
    server = m.make_server(controller, ROOT / 'web_overlay', port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = '127.0.0.1:' + str(server.server_port)

    def request(path, method='GET', headers=None, body=None):
        conn = http.client.HTTPConnection(host, timeout=2)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        result = response.status, response.read(), dict(response.headers)
        conn.close()
        return result

    valid = {'Origin': 'http://' + host, 'Content-Type': 'application/json', 'X-AR-Console': 'control'}
    try:
        assert request('/')[0] == 200
        assert request('/state.json')[0] == 503
        assert request('/console/status')[0] == 200
        assert request('/console/status', headers={'Host': 'evil.test'})[0] == 403
        assert request('/console/start', 'POST', body='{}')[0] == 403
        assert request('/console/start', 'POST', {**valid, 'Origin': 'https://evil.test'}, '{}')[0] == 403
        assert request('/console/start', 'POST', valid, '{"command":"calc"}')[0] == 400
        assert request('/console/shell', 'POST', valid, '{}')[0] == 404
        assert request('/../configs/realtime_viture_beast_aruco.yaml')[0] == 404
        assert request('/observation')[0] == 404
        assert request('/console/check', 'POST', valid, '{}')[0] == 202
        wait_status(controller, 'idle')
        assert backend.launches == 0
    finally:
        server.shutdown()
        server.server_close()
        controller.close()


def test_proxy_checks_session_and_forwards_confirmation(tmp_path):
    m, backend = api(), Backend()
    controller = m.Controller(backend, tmp_path)
    state = {'session_id': 'owned'}
    received = []

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            payload = json.dumps(state).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('X-AR-Session', state.get('session_id', '') if isinstance(state, dict) else '')
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            received.append((self.headers.get('Origin'), self.headers.get('X-AR-Operator'),
                             json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(202)
            self.send_header('Content-Length', '0')
            self.end_headers()

    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    url = 'http://127.0.0.1:' + str(upstream.server_port)
    controller.data['status'] = 'running'
    controller.upstream = (url, 'owned')
    server = m.make_server(controller, ROOT / 'web_overlay', port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = '127.0.0.1:' + str(server.server_port)

    def request(path, body=None):
        conn = http.client.HTTPConnection(host, timeout=2)
        conn.request('POST' if body else 'GET', path, json.dumps(body) if body else None,
                     {'Origin': 'http://' + host, 'Content-Type': 'application/json',
                      'X-AR-Operator': 'confirm'})
        response = conn.getresponse()
        result = response.status
        response.read()
        conn.close()
        return result

    try:
        assert request('/state.json') == 200
        assert request('/frame.jpg') == 200
        assert request('/operator/confirm', {'session_id': 'old', 'revision': 0}) == 409
        assert received == []
        assert request('/operator/confirm', {'session_id': 'owned', 'revision': 1}) == 202
        assert received == [(url, 'confirm', {'session_id': 'owned', 'revision': 1})]
        state = {'session_id': 'old'}
        assert request('/state.json') == 503
        assert request('/frame.jpg') == 503
        state = []
        assert request('/state.json') == 503
    finally:
        server.shutdown()
        server.server_close()
        upstream.shutdown()
        upstream.server_close()
        controller.close()
