"""Opt-in, local presentation of one camera stream; never activates calibration."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import secrets
import time
import uuid

from .display_observation_server import ObservationStore, start_server, _write_json, pose_reason_code
from .workspace_live_preview import load_profiles, analyze_frame, render_preview


def guided_target(estimate, marker_ok):
    targets = dict(zip(('S2', 'S3', 'S4', 'S5'), 'ABCD'))
    target = targets.get(estimate.state)
    phase = getattr(estimate.guidance, 'phase', None)
    tool_wait = phase == 'PAUSED' and getattr(estimate.guidance, 'reason', None) in (
        'tool_not_visible', 'tool_position_unknown', 'invalid_observation', 'observation_gap')
    return (target if marker_ok and target and estimate.target == 'screw_' + target.lower()
            and (phase in ('GUIDING', 'OBSERVING', 'OBSERVED') or tool_wait) else None)


def metric_marker(observation, now):
    from .aruco_tracker import ArUcoResult
    analysis = observation['analysis']
    age = (now - observation['received_at']) * 1000
    ok = analysis['status'] == 'tracking' and 0 <= age <= 150
    return ArUcoResult(enabled=True, marker_ok=ok,
                       marker_count=len(analysis.get('marker_ids') or []),
                       marker_status='OK' if ok else 'LOST', warp_quality=0.)


class PresentationBridge:
    def __init__(self, config_path: Path, session_id: str, *, root: Path | None = None):
        path = Path(config_path)
        if str(path).startswith('\\\\') or path.stat().st_size > 65536:
            raise ValueError('Presentation config must be a small local file')
        data = json.loads(path.read_text(encoding='utf-8'))
        self.pose_max_rms_px = data.get('pose_max_rms_px', 3.)
        if (isinstance(self.pose_max_rms_px, bool)
                or not isinstance(self.pose_max_rms_px, (int, float))
                or not math.isfinite(self.pose_max_rms_px)
                or not 0 < self.pose_max_rms_px <= 3.5):
            raise ValueError('pose_max_rms_px must be a finite number in (0, 3.5]')
        self.camera, self.workspace, metadata = load_profiles(
            Path(data['camera_profile']), Path(data['workspace_profile']))
        session = dict(session_id=session_id, camera_profile_id=self.camera.profile_id,
                       timestamp_clock='time.perf_counter',
                       workspace_profile_id=self.workspace.profile_id,
                       camera_profile_sha256=metadata['camera_profile_sha256'],
                       workspace_profile_sha256=metadata['workspace_profile_sha256'])
        self.store = ObservationStore(session, self.camera, self.workspace)
        self.previous_timestamp_ms = None
        root = root or Path(os.environ['LOCALAPPDATA']) / 'ARAssembly/beast-mvp/display_correspondence'
        self.directory = Path(root).resolve() / uuid.uuid4().hex
        self.directory.mkdir(parents=True, exist_ok=False)
        token = secrets.token_urlsafe(32)
        self.server, self.thread = start_server(self.store, token)
        self.config_path = self.directory / 'client-config.json'
        try:
            _write_json(self.config_path, dict(session, schema_version='beast_display_collection_config_v1',
                token=token, observation_url=f'http://127.0.0.1:{self.server.server_port}/observation',
                image_size=list(self.camera.image_size), target_id='A', directory=str(self.directory)))
        except BaseException:
            self.close()
            raise

    def observe(self, packet):
        started = time.perf_counter()
        # FrameSource and observation consumers share the same precise monotonic clock.
        received = packet.timestamp_ms / 1000.
        options = {} if self.pose_max_rms_px == 3. else {'max_rms_px': self.pose_max_rms_px}
        analysis = analyze_frame(packet.frame, self.camera, self.workspace, **options)
        analyzed = time.perf_counter()
        current = dict(frame_id=packet.frame_id, received_at=received, analysis=analysis, image=packet.frame)
        self.store.update(current)
        current.update(started=started, analyzed=analyzed)
        return current

    def update(self, packet, *, target_id=None, observation=None):
        current = self.observe(packet) if observation is None else observation
        if current['frame_id'] != packet.frame_id or current['received_at'] != packet.timestamp_ms / 1000.:
            raise ValueError('Presentation observation must match the source frame')
        analysis, started, analyzed = current['analysis'], current['started'], current['analyzed']
        visual, status = render_preview(current, time.perf_counter(), self.camera.image_size,
                                       assembly_profiles=(self.camera, self.workspace), target_id=target_id,
                                       selection_mode='stage', diagnostic_banner=False)
        finished = time.perf_counter()
        ids = analysis.get('marker_ids')
        status['diagnostics'] = {
            'frame_id': packet.frame_id,
            'analysis_status': analysis['status'], 'analysis_reason': analysis.get('reason', ''),
            'reason_code': pose_reason_code(analysis['status'], analysis.get('reason', '')),
            'marker_count': len(ids) if isinstance(ids, list) else None,
            'marker_ids': ids,
            'detected_corners_px': analysis.get('detected_corners_px', {}),
            'image_size': list(self.camera.image_size),
            'camera_profile_sha256': self.store.session['camera_profile_sha256'],
            'workspace_profile_sha256': self.store.session['workspace_profile_sha256'],
            'rms_px': analysis.get('rms_px'),
            'pose_max_rms_px': self.pose_max_rms_px,
            'pose_max_point_error_px': 5.,
            'source_interval_ms': None if self.previous_timestamp_ms is None else packet.timestamp_ms - self.previous_timestamp_ms,
            'input_age_ms': round(started * 1000 - packet.timestamp_ms, 3),
            'analysis_ms': round((analyzed - started) * 1000, 3),
            'preview_ms': round((finished - analyzed) * 1000, 3),
            'publish_age_ms': round(finished * 1000 - packet.timestamp_ms, 3),
        }
        self.previous_timestamp_ms = packet.timestamp_ms
        return visual, status

    def close(self):
        self.store.invalidate('Presentation ended')
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2.)
