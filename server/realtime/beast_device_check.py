from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Match the documented Beast UVC ID, not its mutable camera index.
BEAST_CAMERA_ID = re.compile(r"(?:^|\\)VID_0C45&PID_6368(?:&|\\|$)", re.IGNORECASE)
VITURE_CONTROL_ID = re.compile(r"(?:^|\\)VID_35CA&", re.IGNORECASE)
SDK_SOURCE = "https://www.viture.com/developer/glasses-sdk/glasses"


def inspect_devices(devices: list[dict]) -> dict:
    if not isinstance(devices, list) or any(not isinstance(d, dict) for d in devices):
        raise ValueError("Expected a list of Windows PnP device objects.")

    cameras = [d for d in devices if BEAST_CAMERA_ID.search(str(d.get("DeviceID", "")))]
    healthy = [
        d for d in cameras
        if str(d.get("Status", "")).upper() == "OK"
        and d.get("ConfigManagerErrorCode") == 0
    ]
    return {
        "schema_version": "beast_device_inventory_v1",
        "scope": "device_enumeration_only",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "device_id_source": SDK_SOURCE,
        "camera_status": "candidate_found" if healthy else "device_error" if cameras else "missing",
        "ready_for_capture_probe": bool(healthy),
        "beast_camera_candidates": cameras,
        "viture_control_candidates": [
            d for d in devices if VITURE_CONTROL_ID.search(str(d.get("DeviceID", "")))
        ],
        "monitor_candidates": [d for d in devices if d.get("PNPClass") == "Monitor"],
        "capture_verified": False,
        "display_alignment_verified": False,
        "next_check": (
            "Match the camera preview to Beast; then measure capture with display output."
            if healthy else
            "Connect Beast with a data/display-capable connection and inspect Windows devices."
        ),
    }


def read_windows_devices() -> list[dict]:
    command = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$devices = @(Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.PNPClass -in @('Camera', 'Monitor') -or
    $_.DeviceID -match 'VID_35CA&|VID_0C45&PID_6368(?:&|\\|$)'
} | Select-Object Name, PNPClass, Status, DeviceID, ConfigManagerErrorCode)
ConvertTo-Json -InputObject $devices -Depth 3 -Compress
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=30,
    )
    data = json.loads(result.stdout.lstrip("\ufeff").strip())
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or any(not isinstance(d, dict) for d in data):
        raise ValueError("Windows device query returned an invalid JSON inventory.")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Beast USB identity without opening any camera.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    if sys.platform != "win32":
        print("[ERROR] Windows device enumeration is required.", file=sys.stderr)
        return 2

    try:
        report = inspect_devices(read_windows_devices())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"[ERROR] Device query failed: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    # Absence is a valid diagnostic result; it is not successful hardware validation.
    return 0 if report["ready_for_capture_probe"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
