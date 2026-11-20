from __future__ import annotations

import copy
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

from .schemas import SPATIAL_POSE_BUDGET_MS, pose_age_ms


class SharedOverlayState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {"system_status": "STARTING"}
        self._jpeg: Optional[bytes] = None

    def update(self, state: Dict[str, Any], frame_bgr) -> None:
        import cv2
        ok, encoded = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        with self._lock:
            self._state = copy.deepcopy(state)
            self._jpeg = encoded.tobytes() if ok else None

    def snapshot_state(self) -> Dict[str, Any]:
        with self._lock:
            result = copy.deepcopy(self._state)
            current_ms = int(time.perf_counter() * 1000)
            captured_ms = result.get("timestamp_ms")
            # Recompute on every read, even when capture has stopped.
            result["frame_age_ms"] = (
                current_ms - captured_ms
                if isinstance(captured_ms, int) and captured_ms > 0 else -1
            )
            spatial = result.get("spatial")
            if isinstance(spatial, dict):
                age = pose_age_ms(spatial.get("pose_timestamp_ms"), current_ms)
                spatial["pose_age_ms"] = age
                if age < 0 or age > SPATIAL_POSE_BUDGET_MS:
                    spatial.update(target_visible=False, left_pixel=None, right_pixel=None,
                                   reason="invalid_pose" if age < 0 else "stale_pose")
            return result

    def snapshot_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg

    def snapshot_frame(self):
        # The JPEG and its identity must come from the same locked update.
        with self._lock:
            captured_ms = self._state.get("timestamp_ms")
            frame_id = self._state.get("frame_id")
            return self._jpeg, {
                "X-AR-Session": quote(str(self._state.get("session_id", "")), safe=""),
                "X-AR-Source": quote(str(self._state.get("source", "")), safe=""),
                "X-AR-Frame-Id": str(frame_id if type(frame_id) is int else 0),
                "X-AR-Timestamp-Ms": str(captured_ms if type(captured_ms) is int else -1),
                "X-AR-Frame-Age-Ms": str(pose_age_ms(captured_ms, int(time.perf_counter() * 1000))),
            }


def make_handler(shared: SharedOverlayState, web_root: Path, operator=None):
    class OverlayHandler(BaseHTTPRequestHandler):
        def _send_bytes(self, data: bytes, content_type: str, status: int = 200, headers=None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/state.json":
                data = json.dumps(shared.snapshot_state(), ensure_ascii=False).encode("utf-8")
                self._send_bytes(data, "application/json; charset=utf-8")
                return
            if path == "/frame.jpg":
                jpeg, headers = shared.snapshot_frame()
                if jpeg is None:
                    self._send_bytes(b"no frame yet", "text/plain; charset=utf-8", status=503)
                else:
                    self._send_bytes(jpeg, "image/jpeg", headers=headers)
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

        def do_POST(self) -> None:
            def reply(status, message):
                self._send_bytes(json.dumps({"message": message}).encode(), "application/json", status)
            if self.path != "/operator/confirm" or operator is None:
                reply(404, "Operator mode is not enabled")
                return
            allowed = {f"{host}:{self.server.server_port}" for host in ("127.0.0.1", "localhost")}
            host = self.headers.get("Host")
            if (host not in allowed or self.headers.get("Origin") != "http://" + host
                    or self.headers.get("X-AR-Operator") != "confirm"
                    or self.headers.get("Content-Type") != "application/json"):
                reply(403, "Same-origin operator request required")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 2048:
                    raise ValueError("Invalid body length")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {"session_id", "revision"}:
                    raise ValueError("Invalid confirmation")
            except (ValueError, UnicodeError):
                reply(400, "Invalid confirmation")
                return
            state = shared.snapshot_state()
            if (state.get("session_id") != body["session_id"]
                    or state.get("system_status") != "RUNNING"
                    or not 0 <= state["frame_age_ms"] < 500
                    or (operator.requires_tracking and state.get("marker_status") != "OK")):
                reply(409, "Fresh tracked input required")
                return
            try:
                operator.request(body["session_id"], body["revision"])
            except ValueError as exc:
                reply(409, str(exc))
                return
            reply(202, "Queued for the next fresh frame")

        def log_message(self, fmt: str, *args) -> None:
            return

    return OverlayHandler


class OverlayHttpServer:
    def __init__(self, host: str, port: int, web_root: str, *, operator=None):
        if operator is not None and host not in ("127.0.0.1", "localhost"):
            raise ValueError("Operator controls require loopback binding")
        self.shared = SharedOverlayState()
        self.web_root = Path(web_root)
        handler = make_handler(self.shared, self.web_root, operator)
        self.server = ThreadingHTTPServer((host, int(port)), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://{host}:{self.server.server_port}"

    def start(self) -> None:
        self.thread.start()

    def update(self, message: Dict[str, Any], frame_bgr) -> None:
        self.shared.update(message, frame_bgr)

    def stop(self) -> None:
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(timeout=2.0)
        self.server.server_close()

