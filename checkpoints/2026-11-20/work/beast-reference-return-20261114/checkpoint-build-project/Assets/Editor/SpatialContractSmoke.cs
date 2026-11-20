using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace ARAssembly
{
    // Reads Python-produced synthetic metadata; does not start a scene or camera.
    public static class SpatialContractSmoke
    {
        [Serializable]
        private sealed class Fixture
        {
            public string fresh_json, stale_json, legacy_json;
        }

        public static void Run()
        {
            try {
                string[] args = Environment.GetCommandLineArgs();
                int index = Array.IndexOf(args, "--spatial-fixture");
                Check(index >= 0 && index + 1 < args.Length, "fixture argument");
                var fixture = JsonUtility.FromJson<Fixture>(File.ReadAllText(args[index + 1]));
                var fresh = GuidanceReceiver.ParseSnapshot(fixture.fresh_json);
                var spatial = fresh.spatial;
                Check(spatial != null && spatial.schema_version == "beast_spatial_guidance_v1", "nested schema");
                Check(spatial.target_visible && !spatial.display_alignment_verified
                    && spatial.calibration_status == "synthetic", "synthetic provenance");
                Check(spatial.coordinate_convention == "eye_local_pixels_top_left"
                    && spatial.channel_order == "left_half_left_eye_right_half_right_eye"
                    && spatial.display_mode == "full_sbs", "coordinate conventions");
                Check(spatial.eye_width == 1920 && spatial.eye_height == 1080, "per-eye size");
                Check(spatial.left_pixel.Length == 2 && spatial.right_pixel.Length == 2
                    && Near(spatial.left_pixel[0], 1008) && Near(spatial.left_pixel[1], 540)
                    && Near(spatial.right_pixel[0], 908.8) && Near(spatial.right_pixel[1], 539.62), "independent projections");
                Check(spatial.pose_frame_id == 7 && fresh.frame_id == 8
                    && spatial.pose_timestamp_ms == 1000 && spatial.pose_age_ms == 25, "original pose identity and age");
                Check(spatial.camera_profile_id == "synthetic-camera"
                    && spatial.workspace_profile_id == "synthetic-workspace"
                    && spatial.display_profile_id == "synthetic-display-r2"
                    && spatial.camera_profile_sha256 == new string('a', 64)
                    && spatial.workspace_profile_sha256 == new string('b', 64), "profile binding");
                var stale = GuidanceReceiver.ParseSnapshot(fixture.stale_json).spatial;
                Check(!stale.target_visible && stale.reason == "stale_pose" && stale.pose_age_ms == 200,
                    "stale hidden");
                Check((stale.left_pixel == null || stale.left_pixel.Length == 0)
                    && (stale.right_pixel == null || stale.right_pixel.Length == 0), "stale coordinates cleared");
                var state = new GuidanceState();
                Check(state.Apply(fresh, 1, 1.01) && state.LastSnapshot.current_state == "S2"
                    && !state.ShowTestRing(1.02, false), "no renderer opt-in or state inference");
                Check(new GuidanceState().Apply(GuidanceReceiver.ParseSnapshot(fixture.legacy_json), 1, 1.01), "legacy state accepted");
                // FromJsonOverwrite is the receiver's actual parsing path.
                var missing = new GuidanceSnapshot();
                JsonUtility.FromJsonOverwrite("{\"spatial\":{}}", missing);
                Check(!missing.spatial.target_visible && !missing.spatial.display_alignment_verified,
                    "missing fields do not become visible/verified");
                var config = new SpatialPreviewConfig {
                    schema_version = "beast_spatial_preview_config_v1", session_id = "synthetic-r2",
                    state_url = "http://127.0.0.1:12345/state.json", duration_seconds = 30,
                    display_profile_id = spatial.display_profile_id, camera_profile_id = spatial.camera_profile_id,
                    workspace_profile_id = spatial.workspace_profile_id,
                    camera_profile_sha256 = spatial.camera_profile_sha256, workspace_profile_sha256 = spatial.workspace_profile_sha256
                };
                string json = fixture.fresh_json.Replace(": ", ":");
                var parsed = GuidanceReceiver.ParseSnapshot(json);
                var spatialState = new GuidanceState(config);
                spatialState.Spatial.ObserveOutput("Laptop", 1536, 432, true);
                spatialState.Apply(parsed, 1, 1.01);
                Check(spatialState.Spatial.TryGetPixels(1.02, out var pair) && Near(pair.RightX, 908.8), "consumer projection");
                Check(!spatialState.Spatial.TryGetPixels(1.126, out _), "consumer expiry");
                foreach (string field in new[] {"pose_age_ms", "pose_frame_id", "pose_timestamp_ms"}) {
                    long number = field == "pose_age_ms" ? 25 : field == "pose_frame_id" ? 7 : 1000;
                    string incomplete = json.Replace("\"" + field + "\":" + number + ",", "");
                    Check(incomplete != json, "missing-field fixture " + field);
                    var consumer = new GuidanceState(config);
                    consumer.Spatial.ObserveOutput("Laptop", 1536, 432, true);
                    consumer.Apply(GuidanceReceiver.ParseSnapshot(incomplete), 1, 1.01);
                    Check(!consumer.Spatial.TryGetPixels(1.02, out _), "missing " + field + " rejected");
                    if (field != "pose_frame_id") {
                        consumer.Apply(GuidanceReceiver.ParseSnapshot(json), 1.03, 1.04);
                        Check(!consumer.Spatial.TryGetPixels(1.041, out _), "repaired duplicate remains hidden: " + field);
                        var newer = GuidanceReceiver.ParseSnapshot(json);
                        newer.frame_id++; newer.timestamp_ms += 100;
                        newer.spatial.pose_frame_id++; newer.spatial.pose_timestamp_ms += 100;
                        consumer.Apply(newer, 1.05, 1.06);
                        Check(consumer.Spatial.TryGetPixels(1.061, out _), "newer pose recovers: " + field);
                    }
                }
                var absent = GuidanceReceiver.ParseSnapshot(fixture.legacy_json);
                Check(absent.spatial == null || !absent.spatial.target_visible, "legacy cannot inherit pose");
                Debug.Log("[SPATIAL CONTRACT SMOKE] PASS " + checks + " checks");
                EditorApplication.Exit(0);
            } catch (Exception exc) {
                Debug.LogError("[SPATIAL CONTRACT SMOKE] FAIL " + exc);
                EditorApplication.Exit(1);
            }
        }

        private static int checks;
        private static bool Near(double actual, double expected) => Math.Abs(actual - expected) < 1e-8;
        private static void Check(bool condition, string name)
        {
            if (!condition) throw new InvalidOperationException(name);
            checks++;
        }
    }
}
