"""Loopback lifecycle console. Opening this page never opens a camera."""
from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote


class Controller:
    def __init__(self, backend, runs: Path):
        self.backend, self.runs = backend, runs
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.worker = None
        self.closed = False
        self.data = dict(status='idle', run_id=None, session_id=None,
                         preflight=None, error='', log_folder=None)
        self.upstream = None

    def snapshot(self):
        with self.lock:
            return dict(self.data, schema_version='beast_console_v1')

    def target(self):
        with self.lock:
            return self.upstream if self.data['status'] == 'running' else None

    def command(self, action):
        with self.lock:
            if self.closed:
                return False
            busy = self.worker is not None and self.worker.is_alive()
            if action == 'stop':
                if not busy:
                    return False
                self.data['status'] = 'stopping'
                self.upstream = None
                self.cancel.set()
                return True
            if action not in ('start', 'check') or busy:
                return False
            self.cancel.clear()
            self.data.update(status='checking', error='', session_id=None)
            self.worker = threading.Thread(target=self._run, args=(action,), daemon=True)
            self.worker.start()
            return True

    def _run(self, action):
        job, error = None, ''
        try:
            report = self.backend.check(self.cancel)
            with self.lock:
                self.data['preflight'] = report
            if self.cancel.is_set():
                return
            if not report['ready']:
                raise RuntimeError('연결 확인 항목을 확인해 주세요. 카메라는 시작하지 않았습니다.')
            if action == 'check':
                return
            with self.lock:
                if self.cancel.is_set():
                    return
                run_id = uuid.uuid4().hex
                folder = self.runs / run_id
                folder.mkdir(parents=True)
                self.data.update(status='starting', run_id=run_id, log_folder=str(folder))
            job = self.backend.launch(folder)
            deadline = time.monotonic() + 120
            while not self.cancel.wait(.2):
                code = job.poll()
                if code is not None:
                    if code:
                        raise RuntimeError('실행이 중단됐습니다. 연결 상태와 실행 로그를 확인해 주세요.')
                    return
                ready = job.ready()
                if ready:
                    parsed = urlsplit(ready['url'])
                    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
                            or not parsed.port or parsed.path or parsed.query or parsed.fragment
                            or parsed.username or parsed.password or not ready.get('session')):
                        raise RuntimeError('실행 세션의 연결 정보가 올바르지 않습니다.')
                    with self.lock:
                        if self.cancel.is_set():
                            return
                        self.upstream = (ready['url'], ready['session'])
                        self.data.update(status='running', session_id=ready['session'])
                elif time.monotonic() >= deadline:
                    raise RuntimeError('시작 시간이 초과됐습니다. 장치 연결을 확인해 주세요.')
        except Exception as exc:
            error = str(exc)
        finally:
            with self.lock:
                self.upstream = None
            if job:
                try:
                    job.stop()
                except Exception as exc:
                    error = '실행 종료를 확인하지 못했습니다: ' + str(exc)
            with self.lock:
                self.data.update(status='error' if error else 'idle', error=error, session_id=None)

    def close(self):
        with self.lock:
            self.closed = True
            self.cancel.set()
            worker = self.worker
            self.upstream = None
        if worker:
            worker.join(150)


def make_server(controller, web_root, port=8764):
    web_root = Path(web_root).resolve()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *_):
            pass

        def send(self, status, body=b'', content_type='application/json', headers=None):
            if isinstance(body, dict):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            return self.headers.get('Host') in (
                '127.0.0.1:' + str(self.server.server_port),
                'localhost:' + str(self.server.server_port))

        def do_GET(self):
            if not self.valid_host():
                return self.send(403)
            path = urlsplit(self.path).path
            if path == '/console/status':
                return self.send(200, controller.snapshot())
            if path in ('/state.json', '/frame.jpg'):
                return self.proxy(path)
            name = 'supervisor_demo.html' if path == '/' else unquote(path).lstrip('/')
            candidate = (web_root / name).resolve()
            if (not candidate.is_relative_to(web_root) or '\\' in name
                    or not (name.startswith('supervisor') and '/' not in name
                            or name.startswith('fonts/'))
                    or candidate.suffix not in ('.html', '.js', '.css', '.woff2')
                    or not candidate.is_file()):
                return self.send(404)
            body = candidate.read_bytes()
            if name == 'supervisor_demo.html':
                body = body.replace(b'</head>', b'<link rel="stylesheet" href="/supervisor_console.css">'
                                    b'<script defer src="/supervisor_console.js"></script></head>')
            return self.send(200, body, mimetypes.guess_type(name)[0] or 'application/octet-stream')

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2048 or self.headers.get('Transfer-Encoding'):
                    raise ValueError()
                raw = self.rfile.read(length)
                body = json.loads(raw)
            except (ValueError, OSError):
                return self.send(400)
            if (not self.valid_host() or self.headers.get('Origin') != 'http://' + self.headers.get('Host', '')
                    or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'
                    or self.headers.get('Transfer-Encoding')):
                return self.send(403)
            path = urlsplit(self.path).path
            header = 'X-AR-Operator' if path == '/operator/confirm' else 'X-AR-Console'
            expected = 'confirm' if path == '/operator/confirm' else 'control'
            if self.headers.get(header) != expected:
                return self.send(403)
            if path == '/operator/confirm':
                if not isinstance(body, dict) or set(body) != {'session_id', 'revision'}:
                    return self.send(400)
                target = controller.target()
                if not target or body['session_id'] != target[1]:
                    return self.send(409)
                return self.proxy(path, raw)
            if path not in ('/console/check', '/console/start', '/console/stop'):
                return self.send(404)
            if body != {}:
                return self.send(400)
            accepted = controller.command(path.rsplit('/', 1)[1])
            return self.send(202 if accepted else 409, {'accepted': accepted})

        def proxy(self, path, raw=None):
            target = controller.target()
            if not target:
                return self.send(503, {'error': 'session_not_running'})
            parsed = urlsplit(target[0])
            conn = http.client.HTTPConnection('127.0.0.1', parsed.port, timeout=1.5)
            try:
                headers = {} if raw is None else {'Content-Type': 'application/json',
                    'Origin': target[0], 'X-AR-Operator': 'confirm'}
                conn.request('GET' if raw is None else 'POST', path, body=raw, headers=headers)
                response = conn.getresponse()
                limit = 4_194_304 if path == '/frame.jpg' else 65536
                payload = response.read(limit + 1)
                if len(payload) > limit or controller.target() != target:
                    return self.send(503)
                if response.status == 200:
                    if path == '/state.json':
                        state = json.loads(payload)
                        if not isinstance(state, dict) or state.get('session_id') != target[1]:
                            return self.send(503)
                    if path == '/frame.jpg' and response.getheader('X-AR-Session') != target[1]:
                        return self.send(503)
                passthrough = {k: v for k, v in response.getheaders() if k.lower().startswith('x-ar-')}
                return self.send(response.status, payload, response.getheader('Content-Type', 'application/json'), passthrough)
            except (OSError, ValueError, http.client.HTTPException):
                return self.send(503, {'error': 'live_session_unavailable'})
            finally:
                conn.close()

    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    return LocalServer(('127.0.0.1', port), Handler)


def main():
    from console_process import Backend
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8764)
    args = parser.parse_args()
    backend = Backend(args.profile)
    controller = Controller(backend, args.profile.parent / 'runs')
    server = make_server(controller, backend.root / 'web_overlay', args.port)
    print('http://127.0.0.1:' + str(server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.close()
        server.server_close()


if __name__ == '__main__':
    main()
