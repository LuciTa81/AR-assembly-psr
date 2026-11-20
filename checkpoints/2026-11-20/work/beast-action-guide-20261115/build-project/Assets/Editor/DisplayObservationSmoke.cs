using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEditor;
using UnityEngine;

namespace ARAssembly
{
    // Batch-only test of the real Unity transport/parser; never opens a camera.
    public static class DisplayObservationSmoke
    {
        public static void Run()
        {
            deadline = DateTime.UtcNow.AddSeconds(30);
            routines.Push(RunChecks());
            EditorApplication.update += Tick;
        }

        private static readonly Stack<IEnumerator> routines = new Stack<IEnumerator>();
        private static AsyncOperation waiting;
        private static DateTime deadline;

        private static void Tick()
        {
            try {
                if (DateTime.UtcNow > deadline) throw new TimeoutException("Smoke test stalled");
                if (waiting != null && !waiting.isDone) return;
                waiting = null;
                while (routines.Count > 0) {
                    var routine = routines.Peek();
                    if (!routine.MoveNext()) { (routines.Pop() as IDisposable)?.Dispose(); continue; }
                    if (routine.Current is IEnumerator nested) { routines.Push(nested); continue; }
                    waiting = routine.Current as AsyncOperation;
                    return;
                }
                EditorApplication.update -= Tick;
                EditorApplication.Exit(0);
            } catch (Exception exc) {
                Debug.LogError("[CORRESPONDENCE SMOKE] FAIL " + exc);
                EditorApplication.update -= Tick;
                while (routines.Count > 0) (routines.Pop() as IDisposable)?.Dispose();
                EditorApplication.Exit(1);
            }
        }

        private static IEnumerator RunChecks()
        {
            int checks = 0;
            string directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "ARAssembly", "beast-mvp", "display_correspondence", "smoke-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var host = new GameObject("Correspondence smoke");
            try {
                using (var fixture = new Fixture()) {
                    var config = new DisplayCollectionConfig {
                        schema_version = "beast_display_collection_config_v1", session_id = "smoke",
                        camera_profile_id = "camera", workspace_profile_id = "workspace",
                        camera_profile_sha256 = new string('a', 64), workspace_profile_sha256 = new string('b', 64),
                        observation_url = "http://127.0.0.1:" + fixture.Port + "/observation", token = "smoke-token",
                        directory = directory, image_size = new[] {1280, 720}, target_id = "A", setup_id = "smoke-unchanged"
                    };
                    string configPath = Path.Combine(directory, "client-config.json");
                    File.WriteAllText(configPath, JsonUtility.ToJson(config));
                    var recorder = host.AddComponent<DisplayObservationRecorder>();
                    recorder.Initialize(configPath);
                    // Exclude Editor startup/import stalls from the first timed save assertion.
                    fixture.Body = "{}";
                    yield return recorder.PollRoutine();
                    var state = new StereoAlignmentState(3840, 1080, 0, 300);
                    state.ConfirmChannels(1);
                    var point = state.PreviewMark(2);
                    int saved = 0;
                    string valid = "{\"schema_version\":\"beast_display_observation_v1\",\"session_id\":\"smoke\","
                        + "\"camera_profile_id\":\"camera\",\"workspace_profile_id\":\"workspace\","
                        + "\"camera_profile_sha256\":\"" + new string('a', 64) + "\",\"workspace_profile_sha256\":\"" + new string('b', 64) + "\","
                        + "\"image_size\":[1280,720],\"target_id\":\"A\",\"frame_id\":1,\"status\":\"tracking\",\"reason\":\"\","
                        + "\"age_ms\":0,\"rvec\":[1,0,0],\"tvec_mm\":[0,0,400],\"world_xyz_mm\":[150,150,60],"
                        + "\"camera_xyz_mm\":[1,2,500],\"target_pixel\":[600,300],\"marker_ids\":[0,2,3,5],\"rms_px\":0.2,\"max_error_px\":0.3}";
                    fixture.Body = valid;
                    yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(saved == 0 && recorder.Status == "HOLD STILL"
                        && Directory.GetFiles(directory, "point-*.json").Length == 0,
                        "single eye cannot save without stable history"); checks++;
                    yield return StablePolls(recorder, fixture, valid, 2);
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":5");
                    yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(saved == 1 && recorder.Status == "SAVED", "valid real HTTP save"); checks++;
                    var savedPoint = JsonUtility.FromJson<DisplayCorrespondenceCandidate>(File.ReadAllText(Path.Combine(directory, "point-001.json")));
                    Check(savedPoint.observation.frame_id == 5 && savedPoint.eye == "left"
                        && savedPoint.conservative_age_ms <= 150 && savedPoint.stability.distinct_frames >= 3
                        && savedPoint.stability.last_frame_id == 5 && !savedPoint.binocular_confirmed_by_user,
                        "stable single-eye contract is not binocular confirmation"); checks++;
                    yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(saved == 1, "duplicate"); checks++;
                    int unusedFrameId = 10;
                    foreach (var bad in new[] {
                        ("{broken", "INVALID OBSERVATION"), ("{}", "INVALID OBSERVATION"),
                        (valid.Replace("\"age_ms\":0,", ""), "STALE"),
                        (valid.Replace("\"age_ms\":0", "\"age_ms\":151"), "STALE"),
                        (valid.Replace("\"frame_id\":1,", ""), "NO POSE"),
                        (valid.Replace("\"rms_px\":0.2,", ""), "INVALID OBSERVATION"),
                        (valid.Replace("\"rvec\":[1,0,0],", ""), "INVALID OBSERVATION"),
                        (valid.Replace("\"tracking\"", "\"pose_rejected\""), "NO POSE"),
                        (valid.Replace("\"age_ms\":0", "\"age_ms\":NaN"), "STALE"),
                        (valid.Replace("beast_display_observation_v1", "wrong-schema"), "INVALID OBSERVATION"),
                        (new string('x', 70000), "CONNECTION ERROR")}) {
                        fixture.Body = bad.Item1.Replace("\"frame_id\":1", "\"frame_id\":" + unusedFrameId++);
                        yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                        Check(saved == 1 && recorder.Status == bad.Item2,
                            "reject malformed/stale/missing/large: expected " + bad.Item2 + " actual " + recorder.Status); checks++;
                    }
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":2");
                    foreach (int code in new[] {401, 302}) {
                        fixture.Code = code;
                        yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                        Check(saved == 1, "reject HTTP " + code); checks++;
                    }
                    fixture.Code = 200;
                    int gateCalls = 0;
                    yield return recorder.CollectRoutine(point, () => ++gateCalls == 1, _ => saved++);
                    Check(saved == 1, "display changed during request"); checks++;
                    fixture.DelayMs = 80;
                    var routine = recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(routine.MoveNext() && recorder.Pending, "pending request"); checks++;
                    var actualRequest = (IEnumerator)routine.Current;
                    Check(actualRequest.MoveNext() && actualRequest.Current is AsyncOperation, "HTTP actually sent before cancel"); checks++;
                    while (!fixture.Serving) yield return null;
                    Check(!recorder.CollectRoutine(point, () => true, _ => saved++).MoveNext(), "duplicate Enter blocked"); checks++;
                    recorder.Cancel();
                    yield return actualRequest;
                    yield return routine;
                    Check(saved == 1 && !recorder.Pending, "cancel rejects late response"); checks++;
                    while (fixture.Serving) yield return null;
                    fixture.DelayMs = 250;
                    yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(saved == 1 && recorder.Status != "SAVED", "RTT makes observation stale"); checks++;
                    fixture.DelayMs = 1500;
                    yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(saved == 1 && !recorder.Pending, "timeout ends request"); checks++;
                    Check(Directory.GetFiles(directory, "point-*.json").Length == 1, "only one valid candidate on disk"); checks++;
                    while (fixture.Serving) yield return null;
                    fixture.DelayMs = 0;
                    yield return StablePolls(recorder, fixture, valid, 87);
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":90");
                    yield return recorder.PollRoutine();
                    Check(saved == 1 && Directory.GetFiles(directory, "point-*.json").Length == 1,
                        "poll never saves"); checks++;
                    Check(recorder.Feedback.Detail(Time.realtimeSinceStartupAsDouble).Contains("Markers 4"),
                        "poll feedback: " + recorder.Feedback.Status(Time.realtimeSinceStartupAsDouble)); checks++;
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":91");
                    yield return recorder.CollectRoutine(point, () => true, _ => saved++);
                    var freshPoint = JsonUtility.FromJson<DisplayCorrespondenceCandidate>(File.ReadAllText(Path.Combine(directory, "point-002.json")));
                    Check(saved == 2 && freshPoint.observation.frame_id == 91, "Enter obtains fresh observation instead of poll cache"); checks++;

                    var poll = recorder.PollRoutine();
                    Check(poll.MoveNext() && recorder.Busy, "poll owns transport"); checks++;
                    var pendingSave = recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(pendingSave.MoveNext() && recorder.Pending && pendingSave.Current == null, "save waits behind poll"); checks++;
                    yield return poll.Current;
                    yield return poll;
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":92");
                    yield return pendingSave;
                    Check(saved == 3 && !recorder.Busy, "serialized save completes"); checks++;

                    fixture.DelayMs = 220;
                    poll = recorder.PollRoutine();
                    Check(poll.MoveNext(), "slow diagnostic starts"); checks++;
                    pendingSave = recorder.CollectRoutine(point, () => true, _ => saved++);
                    Check(pendingSave.MoveNext() && pendingSave.Current == null, "Enter waits for slow diagnostic"); checks++;
                    yield return poll.Current;
                    yield return poll;
                    fixture.DelayMs = 0;
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":93");
                    yield return pendingSave;
                    Check(saved == 3 && recorder.Status == "STALE", "Enter queue wait is included in capture age"); checks++;

                    foreach (string source in new[] {JsonUtility.ToJson(point), JsonUtility.ToJson(savedPoint)}) {
                        var restored = new StereoAlignmentState(3840, 1080, 0, 300);
                        restored.RestorePositions(StereoAlignmentProbe.ParseStartPoint(source), 1);
                        Check(restored.LeftX == point.left_x && restored.MarkedCount == 0
                            && restored.View == StereoProbeView.Channels, "JSON restore coordinates only"); checks++;
                    }
                    string missingCoordinate = JsonUtility.ToJson(point).Replace("\"right_x\":960.0,", "").Replace("\"right_x\":960,", "");
                    Check(!missingCoordinate.Contains("\"right_x\""), "missing-coordinate fixture"); checks++;
                    bool rejected = false;
                    try {
                        var restored = new StereoAlignmentState(3840, 1080, 0, 300);
                        restored.RestorePositions(StereoAlignmentProbe.ParseStartPoint(missingCoordinate), 1);
                    } catch (ArgumentException) { rejected = true; }
                    Check(rejected, "missing restore coordinate rejected"); checks++;

                    var pairState = new StereoAlignmentState(3840, 1080, 0, 300);
                    pairState.ConfirmChannels(1); pairState.Mark(2);
                    pairState.Select(StereoProbeView.Right, 2); pairState.Mark(2);
                    pairState.Select(StereoProbeView.Both, 2);
                    var pairPoint = pairState.PreviewMark(2);
                    recorder.Feedback.Fail("RESET");
                    var pairObservation = JsonUtility.FromJson<DisplayObservation>(valid);
                    pairObservation.marker_count = 4;
                    pairObservation.frame_id = 100;
                    fixture.Body = JsonUtility.ToJson(pairObservation);
                    yield return recorder.CollectRoutine(pairPoint, () => true, _ => saved++);
                    Check(saved == 3 && recorder.Status == "HOLD STILL", "pair cannot save without stable history"); checks++;
                    for (int i = 1; i <= 3; i++) {
                        double waitUntil = Time.realtimeSinceStartupAsDouble + .1;
                        while (Time.realtimeSinceStartupAsDouble < waitUntil) yield return null;
                        pairObservation.frame_id = 100 + i;
                        fixture.Body = JsonUtility.ToJson(pairObservation);
                        yield return recorder.PollRoutine();
                    }
                    pairObservation.frame_id = 104;
                    fixture.Body = JsonUtility.ToJson(pairObservation);
                    yield return recorder.CollectRoutine(pairPoint, () => true, _ => saved++);
                    Check(saved == 4 && recorder.Status == "SAVED", "stable binocular pair uses real HTTP save"); checks++;
                    var pairRecord = JsonUtility.FromJson<DisplayCorrespondenceCandidate>(
                        File.ReadAllText(Path.Combine(directory, "point-004.json")));
                    Check(pairRecord.schema_version == "beast_display_correspondence_pair_v2"
                        && pairRecord.eye == "both" && pairRecord.binocular_confirmed_by_user
                        && pairRecord.setup_id == "smoke-unchanged"
                        && pairRecord.stability.distinct_frames >= 3
                        && pairRecord.stability.last_frame_id == 104
                        && !pairRecord.calibration_valid && !pairRecord.display_alignment_verified,
                        "pair contract survives Unity JSON serialization"); checks++;
                    var pairRestored = new StereoAlignmentState(3840, 1080, 0, 300);
                    pairRestored.RestorePositions(StereoAlignmentProbe.ParseStartPoint(JsonUtility.ToJson(pairRecord)), 1);
                    Check(pairRestored.MarkedCount == 0, "pair restore does not restore confirmation"); checks++;
                    yield return recorder.CollectRoutine(pairPoint, () => true, _ => saved++);
                    Check(saved == 4, "duplicate pair rejected"); checks++;
                    pairObservation.frame_id = 105; pairObservation.camera_xyz_mm[0] += 10;
                    fixture.Body = JsonUtility.ToJson(pairObservation);
                    yield return recorder.CollectRoutine(pairPoint, () => true, _ => saved++);
                    Check(saved == 4 && recorder.Status == "HOLD STILL", "moving target cannot become stable pair"); checks++;

                    state.Select(StereoProbeView.Right, 2);
                    var rightPoint = state.PreviewMark(2);
                    string moved = valid.Replace("[1,2,500]", "[11,2,500]");
                    fixture.Body = moved.Replace("\"frame_id\":1", "\"frame_id\":106");
                    yield return recorder.CollectRoutine(rightPoint, () => true, _ => saved++);
                    Check(saved == 4 && recorder.Status == "HOLD STILL",
                        "right eye also needs its own stable capture"); checks++;
                    yield return StablePolls(recorder, fixture, moved, 107);
                    fixture.Body = moved.Replace("\"frame_id\":1", "\"frame_id\":110");
                    yield return recorder.CollectRoutine(rightPoint, () => true, _ => saved++);
                    var rightRecord = JsonUtility.FromJson<DisplayCorrespondenceCandidate>(
                        File.ReadAllText(Path.Combine(directory, "point-005.json")));
                    Check(saved == 5 && rightRecord.eye == "right"
                        && rightRecord.observation.camera_xyz_mm[0] == 11
                        && savedPoint.observation.camera_xyz_mm[0] == 1
                        && rightRecord.stability.last_frame_id == 110
                        && !rightRecord.binocular_confirmed_by_user && !rightRecord.calibration_valid
                        && !rightRecord.display_alignment_verified,
                        "independent eyes retain their own poses without becoming a pair"); checks++;

                    recorder.Initialize(configPath, backgroundPolling: true);
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":200");
                    yield return recorder.PollRoutine();
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":201");
                    yield return recorder.PollRoutine();
                    double receivedAt = Time.realtimeSinceStartupAsDouble;
                    Check(recorder.Feedback.DiagnosticFrameId == 201 && recorder.Feedback.Status(receivedAt) == "POSE READY",
                        "background transport real HTTP/parser"); checks++;
                    Debug.Log("[BACKGROUND POLL SMOKE] network_ms=" + recorder.LastNetworkMs
                        + " " + recorder.Feedback.Diagnostic(receivedAt));
                    Check(Directory.GetFiles(directory, "point-*.json").Length == 5, "background poll never saves"); checks++;
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":202")
                        .Replace("\"status\":\"tracking\"", "\"status\":\"pose_rejected\",\"reason_code\":\"marker_geometry\"");
                    yield return recorder.PollRoutine();
                    receivedAt = Time.realtimeSinceStartupAsDouble;
                    Check(recorder.Feedback.PresentationHint("POSE NO POSE", receivedAt).Contains("marker layout")
                        && !recorder.Feedback.TryGetCameraPoint(receivedAt, out _),
                        "structured pose reason survives HTTP and Unity JSON parsing"); checks++;
                    Check(recorder.Feedback.PresentationHint("POSE NO POSE", receivedAt + .2).Contains("delayed"),
                        "expired reason is no longer current"); checks++;
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":203");
                    yield return recorder.PollRoutine();
                    Check(recorder.Feedback.PresentationHint("VISIBLE", Time.realtimeSinceStartupAsDouble) == "Reference visible",
                        "new valid observation clears hold reason"); checks++;
                    fixture.Body = "{broken";
                    yield return recorder.PollRoutine();
                    Check(recorder.Feedback.Status(Time.realtimeSinceStartupAsDouble) == "INVALID OBSERVATION",
                        "background malformed JSON clears pose"); checks++;
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":202").Replace("\"age_ms\":0", "\"age_ms\":151");
                    yield return recorder.PollRoutine();
                    Check(recorder.Feedback.Status(Time.realtimeSinceStartupAsDouble) == "STALE",
                        "background cannot extend pose lifetime"); checks++;
                    fixture.Body = valid.Replace("\"frame_id\":1", "\"frame_id\":204");
                    fixture.DelayMs = 80;
                    poll = recorder.PollRoutine();
                    Check(poll.MoveNext() && recorder.Busy, "background starts without waiting on Unity HTTP"); checks++;
                    while (!fixture.Serving) yield return null;
                    recorder.Cancel();
                    yield return poll;
                    Check(!recorder.Busy && recorder.Feedback.Status(Time.realtimeSinceStartupAsDouble) == "CANCELLED",
                        "background late reply cannot revive pose"); checks++;
                }
                Debug.Log("[CORRESPONDENCE SMOKE] PASS checks=" + checks);
            } finally {
                UnityEngine.Object.DestroyImmediate(host);
                // Keep only this run's local metadata as evidence; no images or camera access.
            }
        }

        private static IEnumerator StablePolls(DisplayObservationRecorder recorder, Fixture fixture, string body, int firstFrame)
        {
            for (int i = 0; i < 3; i++) {
                double until = Time.realtimeSinceStartupAsDouble + .1;
                while (Time.realtimeSinceStartupAsDouble < until) yield return null;
                fixture.Body = body.Replace("\"frame_id\":1", "\"frame_id\":" + (firstFrame + i));
                yield return recorder.PollRoutine();
            }
        }

        private static void Check(bool condition, string test)
        {
            if (!condition) throw new Exception(test);
        }

        private sealed class Fixture : IDisposable
        {
            private readonly TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
            private readonly Thread thread;
            private volatile bool stopped;
            public volatile string Body = "{}";
            public volatile int Code = 200, DelayMs;
            public volatile bool Serving;
            public int Port => ((IPEndPoint)listener.LocalEndpoint).Port;
            public Fixture()
            {
                listener.Start();
                thread = new Thread(Serve) { IsBackground = true }; thread.Start();
            }
            private void Serve()
            {
                while (!stopped) {
                    try {
                        using (var client = listener.AcceptTcpClient()) {
                            Serving = true;
                            client.ReceiveTimeout = client.SendTimeout = 2000;
                            using (var stream = client.GetStream()) {
                                var reader = new StreamReader(stream, Encoding.ASCII, false, 1024, true);
                                string first = reader.ReadLine();
                                bool authorized = false;
                                for (string line = reader.ReadLine(); !string.IsNullOrEmpty(line); line = reader.ReadLine())
                                    if (line.Equals("Authorization: Bearer smoke-token", StringComparison.OrdinalIgnoreCase)) authorized = true;
                                int code = authorized && first.StartsWith("GET /observation ") ? Code : 401;
                                byte[] body = Encoding.UTF8.GetBytes(Body);
                                if (DelayMs > 0) Thread.Sleep(DelayMs);
                                byte[] header = Encoding.ASCII.GetBytes("HTTP/1.1 " + code + " Test\r\nContent-Type: application/json\r\nContent-Length: "
                                    + body.Length + "\r\nLocation: http://127.0.0.1:" + Port + "/forbidden\r\nConnection: close\r\n\r\n");
                                stream.Write(header, 0, header.Length); stream.Write(body, 0, body.Length);
                            }
                        }
                    } catch (Exception) { if (stopped) return; }
                      finally { Serving = false; }
                }
            }
            public void Dispose() { stopped = true; listener.Stop(); thread.Join(2500); }
        }
    }
}
