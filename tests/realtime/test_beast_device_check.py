from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from server.realtime.beast_device_check import inspect_devices, read_windows_devices


def device(device_id, *, status="OK", error_code=0, name="Camera"):
    return {
        "Name": name,
        "PNPClass": "Camera",
        "DeviceID": device_id,
        "Status": status,
        "ConfigManagerErrorCode": error_code,
    }


class BeastDeviceCheckTests(unittest.TestCase):
    def test_no_devices_does_not_report_hardware_success(self):
        report = inspect_devices([])
        self.assertEqual(report["camera_status"], "missing")
        self.assertFalse(report["ready_for_capture_probe"])
        self.assertEqual(report["scope"], "device_enumeration_only")

    def test_known_camera_id_is_only_a_capture_candidate(self):
        report = inspect_devices([device(r"USB\VID_0c45&PID_6368&MI_00\instance")])
        self.assertEqual(report["camera_status"], "candidate_found")
        self.assertTrue(report["ready_for_capture_probe"])
        self.assertFalse(report["capture_verified"])
        self.assertFalse(report["display_alignment_verified"])

    def test_luma_camera_and_similar_pid_are_not_beast(self):
        for value in (r"USB\VID_0C45&PID_636B\x", r"USB\VID_0C45&PID_63680\x"):
            with self.subTest(value=value):
                self.assertEqual(inspect_devices([device(value)])["camera_status"], "missing")

    def test_friendly_name_is_not_device_identity(self):
        report = inspect_devices([device(r"ROOT\CAMERA\0000", name="VITURE Beast")])
        self.assertFalse(report["ready_for_capture_probe"])

    def test_faulted_camera_is_not_ready(self):
        for changes in ({"status": "Error"}, {"error_code": 43}, {"status": None}):
            with self.subTest(changes=changes):
                report = inspect_devices([device(r"USB\VID_0C45&PID_6368\x", **changes)])
                self.assertEqual(report["camera_status"], "device_error")
                self.assertFalse(report["ready_for_capture_probe"])

    def test_malformed_inventory_is_rejected(self):
        for value in (None, "not json", {}, [None], [1]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inspect_devices(value)

    def test_powershell_single_object_is_normalized_and_unicode_is_preserved(self):
        payload = device(r"USB\VID_0C45&PID_6368\x", name="\uCE74\uBA54\uB77C")
        with patch("server.realtime.beast_device_check.subprocess.run") as run:
            run.return_value.stdout = "\ufeff" + json.dumps(payload, ensure_ascii=False)
            self.assertEqual(read_windows_devices(), [payload])
            self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
            self.assertTrue(run.call_args.kwargs["check"])

    def test_query_failure_is_not_reported_as_device_absence(self):
        from subprocess import CalledProcessError

        with patch("server.realtime.beast_device_check.subprocess.run", side_effect=CalledProcessError(1, "powershell")):
            with self.assertRaises(CalledProcessError):
                read_windows_devices()


if __name__ == "__main__":
    unittest.main()

