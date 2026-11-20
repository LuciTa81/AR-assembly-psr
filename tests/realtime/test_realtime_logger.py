import json
from types import SimpleNamespace

import pytest

from server.realtime import run_realtime_server as runtime


def logger_at(tmp_path, session="one", config=None):
    from server.realtime.realtime_logger import RealtimeLogger
    return RealtimeLogger(str(tmp_path), session, config or {})


def test_existing_session_is_never_overwritten(tmp_path):
    logger = logger_at(tmp_path)
    logger.log_result({"untouched": True})
    logger.close()
    with pytest.raises(FileExistsError):
        logger_at(tmp_path)
    assert json.loads((tmp_path / "one/results.jsonl").read_text()) == {"untouched": True}


def test_exact_filter_inputs_and_overrides_are_saved(tmp_path):
    import argparse
    import yaml
    config = runtime.build_effective_config(
        {"state_filter": {"min_confidence": 0.55}},
        argparse.Namespace(dummy_auto_advance=4))
    logger = logger_at(tmp_path, config=config)
    logger.log_result({"filter_input": {"features": {"box_present_score": 0.5499996}}})
    logger.close()
    row = json.loads((tmp_path / "one/results.jsonl").read_text())
    assert row["filter_input"]["features"]["box_present_score"] == 0.5499996
    saved = yaml.safe_load((tmp_path / "one/config_used.yaml").read_text(encoding="utf-8"))
    assert saved["state_filter"]["dummy_auto_advance_frames"] == 4


def test_transition_is_durable_before_publication_and_uses_real_initial_state(tmp_path):
    import csv
    logger = logger_at(tmp_path)
    packet = SimpleNamespace(timestamp_ms=50, frame=None)
    message = {"current_state": "S3", "confidence": 0.95}
    row = {"state": "S3", "transition_event": "S2->S3",
           "filter_input": {"features": {"tool_score_a": 0.90000001}}}
    class Viewer:
        def update(self, payload, image):
            results = (tmp_path / "one/results.jsonl").read_text()
            assert json.loads(results)["filter_input"]["features"]["tool_score_a"] == 0.90000001
            with (tmp_path / "one/events.csv").open(newline="") as f:
                event = list(csv.DictReader(f))[0]
            assert event["from_state"] == "S2"
            assert event["to_state"] == "S3"
    try:
        runtime.record_and_publish(logger, Viewer(), packet, row, message, "S2")
    finally:
        logger.close()


def test_storage_failure_never_publishes_new_state(tmp_path, monkeypatch):
    from server.realtime import realtime_logger
    logger = logger_at(tmp_path)
    def disk_failure(fd):
        raise OSError("disk failure")
    monkeypatch.setattr(realtime_logger.os, "fsync", disk_failure)
    class Viewer:
        def update(self, *args):
            pytest.fail("new state published despite storage failure")
    try:
        with pytest.raises(OSError, match="disk failure"):
            runtime.record_and_publish(
                logger, Viewer(), SimpleNamespace(timestamp_ms=1, frame=None),
                {"state": "S3", "transition_event": "S2->S3"},
                {"confidence": 0.9}, "S2")
    finally:
        logger.close()
