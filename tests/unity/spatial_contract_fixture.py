"""Generate metadata-only Python outputs for the real Unity JSON contract smoke."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.realtime.display_calibration import SyntheticDisplayProfile, project_display


def build_fixture():
    fixture = json.loads((ROOT / "tests/fixtures/spatial_guidance_v1.json").read_text(encoding="utf-8"))
    profile = SyntheticDisplayProfile.from_dict(fixture["profile"])
    fresh = dict(fixture["expected"], spatial=asdict(project_display(profile, fixture["input"], 1025)))
    stale = dict(fresh, spatial=asdict(project_display(profile, fixture["input"], 1200)))
    legacy = {key: value for key, value in fresh.items() if key != "spatial"}
    result = dict(fresh=fresh, stale=stale, legacy=legacy)
    result.update({name + "_json": json.dumps(value, allow_nan=False) for name, value in list(result.items())})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_fixture(), indent=2, allow_nan=False), encoding="utf-8")
    print(output)
