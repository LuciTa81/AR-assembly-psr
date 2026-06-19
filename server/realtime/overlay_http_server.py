from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import cv2


class SharedOverlayState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {"system_status": "STARTING"}
        self._jpeg: Optional[bytes] = None

    def update(self, state: Dict[str, Any], frame_bgr) -> None:
        ok, encoded = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        with self._lock:
            self._state = dict(state)
            if ok:
                self._jpeg = encoded.tobytes()

    def snapshot_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def snapshot_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg


def make_handler(shared: SharedOverlayState, web_root: Path):
    class OverlayHandler(BaseHTTPRequestHandler):
        def _send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/state.json":
                data = json.dumps(shared.snapshot_state(), ensure_ascii=False).encode("utf-8")
                self._send_bytes(data, "application/json; charset=utf-8")
                return
            if path == "/frame.jpg":
                jpeg = shared.snapshot_jpeg()
                if jpeg is None:
                    self._send_bytes(b"no frame yet", "text/plain; charset=utf-8", status=503)
                else:
                    self._send_bytes(jpeg, "image/jpeg")
                return
            if path == "/":
                path = "/index.html"
            safe_name = path.lstrip("/")
            file_path = (web_root / safe_name).resolve()
            if not str(file_path).startswith(str(web_root.resolve())) or not file_path.exists():
                self._send_bytes(b"not found", "text/plain; charset=utf-8", status=404)
                return
            content_type = "text/plain; charset=utf-8"
            if file_path.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            elif file_path.suffix == ".js":
                content_type = "application/javascript; charset=utf-8"
            elif file_path.suffix == ".css":
                content_type = "text/css; charset=utf-8"
            self._send_bytes(file_path.read_bytes(), content_type)

        def log_message(self, fmt: str, *args) -> None:
            return

    return OverlayHandler


class OverlayHttpServer:
    def __init__(self, host: str, port: int, web_root: str):
        self.shared = SharedOverlayState()
        self.web_root = Path(web_root)
        handler = make_handler(self.shared, self.web_root)
        self.server = ThreadingHTTPServer((host, int(port)), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://{host}:{port}"

    def start(self) -> None:
        self.thread.start()

    def update(self, message: Dict[str, Any], frame_bgr) -> None:
        self.shared.update(message, frame_bgr)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

