using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace ARAssembly
{
    public static class AssemblyGuidanceSmoke
    {
        [Serializable] private sealed class Expected
        {
            public int index;
            public string state, target, phase, instruction_contains;
        }
        [Serializable] private sealed class Fixture
        {
            public GuidanceSnapshot[] snapshots;
            public Expected[] expected;
        }
        private static int checks;
        public static void Run()
        {
            try {
                var args = Environment.GetCommandLineArgs();
                int index = Array.IndexOf(args, "--guidance-fixture");
                Check(index >= 0 && index + 1 < args.Length, "fixture argument");
                var fixture = JsonUtility.FromJson<Fixture>(File.ReadAllText(args[index + 1]));
                const string legacy = "{\"schema_version\":\"realtime_v1\",\"session_id\":\"legacy\",\"frame_id\":1,\"timestamp_ms\":1000,\"frame_age_ms\":0,\"system_status\":\"RUNNING\",\"marker_status\":\"OK\",\"current_state\":\"S2\",\"current_label\":\"Lid closed\",\"target\":\"screw_a\",\"next_action\":\"Fasten screw A\"}";
                var legacyFrame = GuidanceReceiver.ParseSnapshot(legacy);
                Check(new GuidanceState().Apply(legacyFrame, 1, 1.01), "absent guidance remains compatible");
                var emptyGuidance = GuidanceReceiver.ParseSnapshot(legacy.TrimEnd('}') + ",\"guidance\":{}}");
                Check(!new GuidanceState().Apply(emptyGuidance, 1, 1.01), "explicit empty guidance is invalid");
                foreach (string extra in new[] { ",\"guidance\":null", ",\"extra\":{\"guidance\":{}}" })
                    Check(new GuidanceState().Apply(GuidanceReceiver.ParseSnapshot(legacy.TrimEnd('}') + extra + "}"),
                        1, 1.01), "null/irrelevant guidance remains compatible");
                bool rejected = false;
                try { GuidanceReceiver.ParseSnapshot(legacy.TrimEnd('}') + ",\"guidance\":true}"); }
                catch (ArgumentException) { rejected = true; }
                Check(rejected, "non-object guidance rejected");
                var state = new GuidanceState(new SpatialPreviewConfig {
                    schema_version = "beast_spatial_preview_config_v1", session_id = "synthetic-r4",
                    state_url = "http://127.0.0.1:12345/state.json", duration_seconds = 30,
                    display_profile_id = "synthetic-display-r2", camera_profile_id = "synthetic-camera",
                    workspace_profile_id = "synthetic-workspace",
                    camera_profile_sha256 = new string('a', 64), workspace_profile_sha256 = new string('b', 64)
                });
                state.Spatial.ObserveOutput("Laptop", 1536, 432, true);
                int expectedIndex = 0;
                for (int i = 0; i < fixture.snapshots.Length; i++) {
                    var frame = GuidanceReceiver.ParseSnapshot(JsonUtility.ToJson(fixture.snapshots[i]));
                    double now = 1 + i * .05;
                    Check(state.Apply(frame, now, now + .002), "frame accepted " + i);
                    var view = state.Presentation(now + .003, true);
                    if (expectedIndex < fixture.expected.Length && fixture.expected[expectedIndex].index == i) {
                        var expected = fixture.expected[expectedIndex++];
                        Check(state.LastSnapshot.current_state == expected.state && state.LastSnapshot.target == expected.target,
                            "step/target milestone " + i);
                        Check(view.Status == (frame.marker_status == "LOST" ? "TRACKING_LOST" : expected.phase),
                            "display phase " + i + ": " + view.Status);
                        if (frame.marker_status == "OK")
                            Check(view.Instruction.Contains(expected.instruction_contains), "instruction milestone " + i);
                        Check(!view.ShowTarget || expected.target.StartsWith("screw_"), "no non-screw ring " + i);
                        if (expected.phase == "PAUSED") Check(!view.ShowTarget, "pause hides target " + i);
                    }
                    if (frame.current_state == "S3")
                        Check(view.Instruction.Contains("screw B"), "A acknowledgement never replaces B instruction");
                }
                Check(expectedIndex == fixture.expected.Length, "all milestones consumed");
                string first = JsonUtility.ToJson(fixture.snapshots[0]);
                string incomplete = first.Replace("\"acknowledgement_remaining_ms\":0", "\"ignored\":0");
                Check(incomplete != first, "missing acknowledgement age fixture");
                var malformed = GuidanceReceiver.ParseSnapshot(incomplete);
                Check(!new GuidanceState().Apply(malformed, 1, 1.01), "missing nested age rejected by actual parser");
                Debug.Log("[ASSEMBLY GUIDANCE SMOKE] PASS " + checks + " checks");
                EditorApplication.Exit(0);
            } catch (Exception exc) {
                Debug.LogError("[ASSEMBLY GUIDANCE SMOKE] FAIL " + exc);
                EditorApplication.Exit(1);
            }
        }
        private static void Check(bool condition, string message)
        {
            if (!condition) throw new InvalidOperationException(message);
            checks++;
        }
    }
}
