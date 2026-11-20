import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_fixture():
    spec = importlib.util.spec_from_file_location("guidance_fixture", ROOT / "tests/unity/guidance_fixture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_filter_and_message_pipeline_matches_hand_checked_milestones():
    fixture = load_fixture().build_fixture()
    for expected in fixture["expected"]:
        message = fixture["snapshots"][expected["index"]]
        assert message["current_state"] == expected["state"]
        assert message["target"] == expected["target"]
        assert message["guidance"]["phase"] == expected["phase"]
        assert expected["instruction_contains"] in message["next_action"]
    events = [(row["elapsed_ms"], row["transition_event"]) for row in fixture["rows"] if row["transition_event"]]
    assert events == [(1100, "S0->S1"), (1450, "S1->S2"), (6900, "S2->S3"),
                      (9600, "S3->S4"), (14100, "S4->S5"), (16400, "S5->S6")]


def test_same_recorded_inputs_reproduce_states_instructions_and_acknowledgements():
    from server.realtime.realtime_replay import replay_filter_inputs
    fixture = load_fixture().build_fixture()
    predictions = replay_filter_inputs(fixture["rows"], fixture["config"])
    for row, result in zip(fixture["rows"], predictions):
        assert {key: row[key] for key in result} == result
