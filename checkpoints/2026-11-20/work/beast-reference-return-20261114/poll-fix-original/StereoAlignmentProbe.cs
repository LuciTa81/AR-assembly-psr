using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;

namespace ARAssembly
{
    // Manual optical probe; optional metadata collection never activates calibration.
    public sealed class StereoAlignmentProbe : MonoBehaviour
    {
        private StereoAlignmentState state;
        private Texture2D ring;
        private GUIStyle labelStyle;
        private GUIStyle channelStyle;
        private GUIStyle detailStyle;
        private string displayName;
        private string directory;
        private bool stopped;
        private double nextPoll;
        private double seconds = 180;
        private DisplayObservationRecorder recorder;
        private string observationConfig;
        private string startPointPath;
        private CandidateProjection candidate;
        private bool candidateCorners;
        private bool trackedAlignment, diagnosticDrawn, trialDLeftUp;
        private string[] depthRecords;
        private string depthTarget;
        private TargetDepthTrial depthTrial;
        private double depthMm = double.NaN;
        private string candidateHash;
        private TrackedAlignmentDiagnostic diagnostic;
        private double[] candidateLeft, candidateRight;
        private double[][] cornerLeft, cornerRight;
        private double nextCandidateLog;

        public string CaptureStatus => state == null ? "SBS_STARTING" :
            "SBS_" + state.View.ToString().ToUpperInvariant() + "_" + state.MarkedCount;

        private void Awake()
        {
            var args = Environment.GetCommandLineArgs();
            candidateCorners = Array.IndexOf(args, "--candidate-corners") >= 0;
            trackedAlignment = Array.IndexOf(args, "--tracked-alignment") >= 0;
            trialDLeftUp = Array.IndexOf(args, "--trial-d-left-up") >= 0;
            if (trialDLeftUp && !trackedAlignment) { Stop("d_trial_requires_tracked_alignment", 2); return; }
            int startIndex = Array.IndexOf(args, "--stereo-start-point");
            if (startIndex >= 0)
            {
                if (startIndex + 1 >= args.Length) { Stop("missing_start_point", 2); return; }
                startPointPath = args[startIndex + 1];
            }
            int configIndex = Array.IndexOf(args, "--display-observation-config");
            if (configIndex >= 0)
            {
                if (configIndex + 1 >= args.Length) { Stop("missing_observation_config", 2); return; }
                observationConfig = args[configIndex + 1];
            }
            int durationIndex = Array.IndexOf(args, "--probe-seconds");
            if (durationIndex >= 0 && (durationIndex + 1 >= args.Length
                || !double.TryParse(args[durationIndex + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out seconds)
                || double.IsNaN(seconds) || seconds < 1 || seconds > (trackedAlignment ? 600 : 300)))
            {
                Stop("invalid_duration", 2);
                return;
            }
            int candidateIndex = Array.IndexOf(args, "--candidate-projection");
            if (candidateIndex >= 0)
            {
                try {
                    if (candidateIndex + 1 >= args.Length || observationConfig == null)
                        throw new ArgumentException("Candidate probe requires a local observation config");
                    string path = Path.GetFullPath(args[candidateIndex + 1]);
                    if (path.StartsWith(@"\\") || new FileInfo(path).Length > 65536)
                        throw new ArgumentException("Candidate must be a small local JSON file");
                    candidate = new CandidateProjection();
                    byte[] bytes = File.ReadAllBytes(path);
                    JsonUtility.FromJsonOverwrite(System.Text.Encoding.UTF8.GetString(bytes).TrimStart('\uFEFF'), candidate);
                    using (var sha = SHA256.Create())
                        candidateHash = BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
                } catch (Exception exc) { Stop("candidate_load_failed: " + exc.Message, 2); return; }
            }
            if (candidateCorners && candidate == null) { Stop("corners_require_candidate", 2); return; }
            if (trackedAlignment && (candidate == null || candidateCorners || startPointPath != null)) {
                Stop("tracked_diagnostic_requires_single_candidate_without_start_point", 2); return;
            }
            int cDepth = Array.IndexOf(args, "--c-depth-records");
            int dDepth = Array.IndexOf(args, "--d-depth-records");
            if (cDepth >= 0 && dDepth >= 0) { Stop("choose_one_depth_target", 2); return; }
            int depthArg = Math.Max(cDepth, dDepth);
            if (depthArg >= 0) {
                if (depthArg + 3 >= args.Length || candidate == null || candidateCorners || trackedAlignment || startPointPath != null) {
                    Stop("depth_requires_read_only_single_candidate", 2); return;
                }
                depthTarget = cDepth >= 0 ? "C" : "D";
                depthRecords = new[]{args[depthArg+1], args[depthArg+2], args[depthArg+3]};
            }
            ring = new Texture2D(128, 128, TextureFormat.RGBA32, false);
            var pixels = new Color[128 * 128];
            for (int y = 0; y < 128; y++)
                for (int x = 0; x < 128; x++)
                {
                    float distance = new Vector2(x - 63.5f, y - 63.5f).magnitude;
                    pixels[y * 128 + x] = new Color(1, 1, 1,
                        Mathf.Clamp01(2.5f - Mathf.Abs(distance - 56)));
                }
            ring.SetPixels(pixels);
            ring.Apply(false, true);
        }

        private void Update()
        {
            if (stopped) return;
            double now = Time.realtimeSinceStartupAsDouble;
            if (state == null)
            {
                var display = GetComponent<DisplayBootstrap>();
                if (display == null || !display.Ready)
                {
                    if (now > 20) Stop("display_not_ready", 2);
                    return;
                }
                if (Screen.mainWindowDisplayInfo.name.IndexOf("VITURE Beast", StringComparison.OrdinalIgnoreCase) < 0
                    || Screen.fullScreenMode != FullScreenMode.FullScreenWindow
                    || Screen.mainWindowDisplayInfo.width != Screen.width
                    || Screen.mainWindowDisplayInfo.height != Screen.height
                    || !StereoAlignmentState.SupportedSize(Screen.width, Screen.height))
                {
                    Stop("Beast_full_SBS_required_actual_" + Screen.width + "x" + Screen.height, 2);
                    return;
                }
                try
                {
                    candidate?.ValidateOutput(Screen.width, Screen.height, seconds, trackedAlignment);
                    state = new StereoAlignmentState(Screen.width, Screen.height, now, seconds, trackedAlignment);
                    displayName = Screen.mainWindowDisplayInfo.name;
                    if (startPointPath != null)
                    {
                        string path = Path.GetFullPath(startPointPath);
                        if (path.StartsWith(@"\\") || new FileInfo(path).Length > 65536)
                            throw new ArgumentException("Start point must be a small local JSON file");
                        state.RestorePositions(ParseStartPoint(File.ReadAllText(path)), now);
                        Debug.Log("[STEREO PROBE] restored_coordinates_only=true channels_confirmed=false marked=0");
                    }
                    if (observationConfig != null)
                    {
                        recorder = gameObject.AddComponent<DisplayObservationRecorder>();
                        recorder.Initialize(observationConfig, candidate, backgroundPolling: candidate != null);
                        if (depthRecords != null) {
                            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                            var rows = Array.ConvertAll(depthRecords, path => {
                                if (!DisplayCorrespondenceRules.IsLocalCollectionPath(path, local) || new FileInfo(path).Length > 65536)
                                    throw new ArgumentException("Expected a small local diagnostic record");
                                return JsonUtility.FromJson<TrackedAlignmentRecord>(File.ReadAllText(path));
                            });
                            if (recorder.TargetId != depthTarget) throw new ArgumentException("Depth trial and live target differ");
                            depthTrial = new TargetDepthTrial(candidate, candidateHash, depthTarget, rows);
                            Debug.Log("[" + depthTarget + " DEPTH TRIAL] read_only=true knots=3 extrapolation=false");
                        }
                        if (trackedAlignment) diagnostic = recorder.CreateTrackedDiagnostic(candidate, candidateHash);
                        if (trialDLeftUp) {
                            diagnostic.StartDLeftUpTrial();
                            Debug.Log("[TRACKED DIAGNOSTIC] trial_d_left_up=true");
                        }
                        if (candidate != null)
                            Debug.Log("[CANDIDATE PROBE] transport=managed_async read_only=" + !trackedAlignment
                                + " corners=" + candidateCorners + " diagnostic=" + trackedAlignment);
                    }
                    else
                    {
                        directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                            "ARAssembly", "beast-mvp", "display_probe", "stereo-" + DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ")
                            + "-" + Guid.NewGuid().ToString("N").Substring(0, 8));
                        Directory.CreateDirectory(directory);
                    }
                    Debug.Log("[STEREO PROBE] ready display=" + displayName + " framebuffer=" + Screen.width + "x"
                        + Screen.height + " seconds=" + seconds + " hardware_mode=UNVERIFIED directory=" + directory);
                }
                catch (Exception exc) { Stop("initialization_failed: " + exc.Message, 2); }
                return;
            }
            if (!Visible(now)) { Stop("deadline_or_display_changed", 0); return; }
            if (recorder != null && !recorder.Busy && now >= nextPoll)
            {
                nextPoll = now + (candidate == null ? .1 : CandidateProjection.PollIntervalSeconds);
                recorder.Poll();
            }
            if (candidate != null && !trackedAlignment && state.View != StereoProbeView.Channels && now >= nextCandidateLog)
            {
                nextCandidateLog = now + 1;
                bool projected = CandidatePixels(now);
                Debug.Log("[CANDIDATE PROBE] visible=" + projected + " pose=" + recorder.Feedback.Status(now)
                    + (depthTrial != null ? " " + depthTarget.ToLowerInvariant() + "_z_mm=" + depthMm.ToString("F1", CultureInfo.InvariantCulture) : "")
                    + " corners=" + (candidateCorners && projected ? 4 : 0)
                    + " " + recorder.Feedback.Diagnostic(now)
                    + " network_ms=" + recorder.LastNetworkMs.ToString("F1", CultureInfo.InvariantCulture)
                    + (projected ? " left=" + candidateLeft[0].ToString("F1") + "," + candidateLeft[1].ToString("F1")
                        + " right=" + candidateRight[0].ToString("F1") + "," + candidateRight[1].ToString("F1") : ""));
            }
        }

        [Serializable]
        private sealed class StartPointEnvelope
        {
            public string schema_version;
            public StereoAlignmentPoint display = new StereoAlignmentPoint { scope = null };
        }

        public static StereoAlignmentPoint ParseStartPoint(string json)
        {
            if (string.IsNullOrWhiteSpace(json) || json.Length > 65536) throw new ArgumentException("Invalid start point JSON");
            var envelope = new StartPointEnvelope();
            JsonUtility.FromJsonOverwrite(json, envelope);
            if (envelope.schema_version != null)
            {
                if ((envelope.schema_version != "beast_display_correspondence_candidate_v1"
                    && envelope.schema_version != "beast_display_correspondence_pair_v2") || envelope.display == null)
                    throw new ArgumentException("Invalid start point schema");
                return envelope.display;
            }
            var point = new StereoAlignmentPoint { scope = null };
            JsonUtility.FromJsonOverwrite(json, point);
            return point;
        }

        private bool Visible(double now)
        {
            return !stopped && state != null && Screen.mainWindowDisplayInfo.name == displayName
                && Screen.fullScreenMode == FullScreenMode.FullScreenWindow
                && state.Visible(now, Screen.width, Screen.height,
                    Screen.mainWindowDisplayInfo.width, Screen.mainWindowDisplayInfo.height);
        }

        private void OnGUI()
        {
            double now = Time.realtimeSinceStartupAsDouble;
            if (!Visible(now)) return;
            HandleKey(now);
            if (stopped) return;
            if (labelStyle == null)
            {
                labelStyle = Style(22);
                channelStyle = Style(48);
                detailStyle = Style(20);
                detailStyle.wordWrap = true;
            }
            bool draw;
            if (diagnostic != null && state.View != StereoProbeView.Channels) {
                // Only Repaint commits a sample. Enter must never fetch or project a different frame.
                if (Event.current.type == EventType.Repaint)
                    diagnosticDrawn = Application.isFocused
                        && recorder.RenderDiagnostic(diagnostic, now, state.View, out candidateLeft, out candidateRight);
                draw = diagnosticDrawn;
            } else draw = candidate == null || state.View == StereoProbeView.Channels || CandidatePixels(now);
            DrawEye(false, draw);
            DrawEye(true, draw);
        }

        private bool CandidatePixels(double now)
        {
            candidateLeft = candidateRight = null;
            cornerLeft = cornerRight = null;
            if (candidateCorners) {
                if (recorder == null || !candidate.TryProjectCorners(recorder.Feedback, now, out cornerLeft, out cornerRight))
                    return false;
                candidateLeft = cornerLeft[0]; candidateRight = cornerRight[0];
                return true;
            }
            depthMm = double.NaN;
            if (recorder == null || !recorder.Feedback.TryGetCameraPoint(now, out var xyz)) return false;
            depthMm = xyz[2];
            return depthTrial != null ? depthTrial.TryProject(xyz, out candidateLeft, out candidateRight)
                : candidate.TryProject(xyz, out candidateLeft, out candidateRight);
        }

        private void HandleKey(double now)
        {
            Event key = Event.current;
            if (key.type != EventType.KeyDown) return;
            if (recorder != null && recorder.Pending && key.keyCode != KeyCode.Q && key.keyCode != KeyCode.Escape)
            {
                key.Use();
                return;
            }
            double step = key.shift ? 20 : 2;
            if (candidate != null && !trackedAlignment && (key.keyCode == KeyCode.Return || key.keyCode == KeyCode.KeypadEnter
                || key.keyCode == KeyCode.R || key.keyCode == KeyCode.LeftArrow || key.keyCode == KeyCode.RightArrow
                || key.keyCode == KeyCode.UpArrow || key.keyCode == KeyCode.DownArrow))
            {
                key.Use();
                return;
            }
            switch (key.keyCode)
            {
                case KeyCode.Space:
                    if (state.View == StereoProbeView.Channels)
                    {
                        state.ConfirmChannels(now);
                        if (candidate != null) SelectView(StereoProbeView.Both, now);
                        Debug.Log("[STEREO PROBE] channels_confirmed_by_user=true");
                    }
                    break;
                case KeyCode.Alpha1: case KeyCode.Keypad1: SelectView(StereoProbeView.Left, now); break;
                case KeyCode.Alpha2: case KeyCode.Keypad2: SelectView(StereoProbeView.Right, now); break;
                case KeyCode.Alpha3: case KeyCode.Keypad3: SelectView(StereoProbeView.Both, now); break;
                case KeyCode.C: SelectView(StereoProbeView.Channels, now); break;
                case KeyCode.R:
                    if (diagnostic != null) { diagnostic.Reset(state.View); diagnosticDrawn = false; }
                    else state.ResetSelected(now);
                    break;
                case KeyCode.LeftArrow: MoveSelected(-step, 0, now); break;
                case KeyCode.RightArrow: MoveSelected(step, 0, now); break;
                case KeyCode.UpArrow: MoveSelected(0, -step, now); break;
                case KeyCode.DownArrow: MoveSelected(0, step, now); break;
                case KeyCode.Return: case KeyCode.KeypadEnter: SavePoint(now); break;
                case KeyCode.Q: case KeyCode.Escape: Stop("user_exit", 0); break;
                default: return;
            }
            if (diagnostic != null) Debug.Log("[TRACKED DIAGNOSTIC] view=" + state.View + " status=" + diagnostic.Status);
            else Debug.Log("[STEREO PROBE] view=" + state.View + " left=" + state.LeftX + "," + state.LeftY
                + " right=" + state.RightX + "," + state.RightY);
            if (key.keyCode != KeyCode.Return && key.keyCode != KeyCode.KeypadEnter) recorder?.ClearOutcome();
            key.Use();
        }

        private void MoveSelected(double dx, double dy, double now)
        {
            if (diagnostic != null) { diagnostic.Move(state.View, dx, dy); diagnosticDrawn = false; }
            else state.Move(dx, dy, now);
        }

        private void SelectView(StereoProbeView view, double now)
        {
            state.Select(view, now);
            diagnostic?.Invalidate();
            diagnosticDrawn = false;
        }

        private void OnApplicationFocus(bool focused)
        {
            if (!focused) { diagnostic?.Invalidate(); diagnosticDrawn = false; }
        }

        private void DrawEye(bool rightEye, bool draw)
        {
            if (!state.ShowEye(rightEye)) return;
            // Keep every primitive within its own half of the full-SBS framebuffer.
            GUI.BeginGroup(new Rect(rightEye ? state.EyeWidth : 0, 0, state.EyeWidth, state.Height));
            float x = (float)(rightEye ? state.RightX : state.LeftX);
            float y = (float)(rightEye ? state.RightY : state.LeftY);
            bool channels = state.View == StereoProbeView.Channels;
            if (candidate != null && !channels && draw)
            {
                var pixel = rightEye ? candidateRight : candidateLeft;
                x = (float)pixel[0]; y = (float)pixel[1];
            }
            Color previous = GUI.color;
            GUI.color = channels && rightEye ? new Color(.2f, .8f, 1) : new Color(.35f, 1, .75f);
            if (draw && candidateCorners && !channels)
            {
                DrawLid(rightEye ? cornerRight : cornerLeft);
            }
            else if (draw)
            {
                GUI.DrawTexture(new Rect(x - 24, y - 24, 48, 48), ring);
                GUI.DrawTexture(new Rect(x - 5, y - 1, 10, 2), Texture2D.whiteTexture);
                GUI.DrawTexture(new Rect(x - 1, y - 5, 2, 10), Texture2D.whiteTexture);
            }
            GUI.color = previous;
            if (channels)
                GUI.Label(new Rect(Mathf.Clamp(x - 40, 0, state.EyeWidth - 80), Mathf.Max(0, y - 90), 80, 60),
                    rightEye ? "R" : "L", channelStyle);
            string manualStatus = state.View.ToString().ToUpperInvariant() + "  |  " + state.MarkStatus;
            if (recorder != null && !channels)
                manualStatus = state.View == StereoProbeView.Both
                    ? "MANUAL COMPARISON  |  " + (state.MarkStatus == "PAIR SAVED" ? "PAIR SAVED" : "BINOCULAR UNVERIFIED")
                    : state.View.ToString().ToUpperInvariant() + " SAMPLE  |  " + state.MarkStatus;
            GUI.Label(new Rect(24, state.Height - 126, state.EyeWidth - 48, 34),
                diagnostic != null && !channels ? recorder.TargetId + "  |  " + state.View.ToString().ToUpperInvariant()
                    + "  |  " + diagnostic.Status + "  |  DIAGNOSTIC"
                : candidate == null ? manualStatus + "  |  NOT CALIBRATED"
                    : (candidateCorners ? "A-D" : recorder.TargetId) + "  |  CANDIDATE "
                        + (channels ? "CHANNEL CHECK" : draw ? "TRACKING" : "PAUSED") + "  |  UNVERIFIED", labelStyle);
            if (recorder != null)
            {
                double now = Time.realtimeSinceStartupAsDouble;
                string outcome = recorder.Status == "READY" || recorder.Status == "SAVED" ? "" : "  |  SAVE: " + recorder.Status;
                string captureStatus = recorder.Feedback.Status(now);
                if (depthTrial != null && !channels && !double.IsNaN(depthMm))
                    captureStatus = depthTarget + "  " + (depthMm/10).ToString("F1", CultureInfo.InvariantCulture)
                        + " cm  |  " + (draw ? (depthTarget == "C" ? "TEST AT 40 cm" : "TEST AT 46 cm") : "OUTSIDE TRIAL RANGE OR VIEW");
                if (candidateCorners && !channels && !draw && captureStatus == "POSE READY")
                    captureStatus = "FOUR TARGETS UNAVAILABLE OR OUTSIDE VIEW";
                if (candidate == null && !channels && captureStatus == "POSE READY")
                    captureStatus = recorder.Feedback.PairEvidence(now) == null ? "HOLD STILL" : "CAPTURE READY";
                GUI.Label(new Rect(24, state.Height - 92, state.EyeWidth - 48, 34), captureStatus + outcome, labelStyle);
                GUI.Label(new Rect(24, state.Height - 58, state.EyeWidth - 48, 54), recorder.Feedback.Detail(now), detailStyle);
            }
            GUI.EndGroup();
        }

        private void DrawLid(double[][] points)
        {
            GUI.color = new Color(.45f, .8f, 1f, .55f);
            string order = CandidateProjection.LidPerimeter;
            for (int i = 0; i < order.Length - 1; i++) {
                var a = points[order[i] - 'A']; var b = points[order[i + 1] - 'A'];
                var start = new Vector2((float)a[0], (float)a[1]);
                var delta = new Vector2((float)(b[0] - a[0]), (float)(b[1] - a[1]));
                Matrix4x4 matrix = GUI.matrix;
                GUIUtility.RotateAroundPivot(Mathf.Atan2(delta.y, delta.x) * Mathf.Rad2Deg, start);
                GUI.DrawTexture(new Rect(start.x, start.y - 1, delta.magnitude, 2), Texture2D.whiteTexture);
                GUI.matrix = matrix;
            }
            for (int i = 0; i < points.Length; i++) {
                float x = (float)points[i][0], y = (float)points[i][1];
                float size = i == 0 ? 48 : 36;
                GUI.color = i == 0 ? new Color(.35f, 1f, .75f) : new Color(.65f, .85f, 1f, .7f);
                GUI.DrawTexture(new Rect(x - size / 2, y - size / 2, size, size), ring);
                if (i == 0) {
                    GUI.DrawTexture(new Rect(x - 5, y - 1, 10, 2), Texture2D.whiteTexture);
                    GUI.DrawTexture(new Rect(x - 1, y - 5, 2, 10), Texture2D.whiteTexture);
                }
                GUI.Label(new Rect(Mathf.Clamp(x + size / 2 + 4, 0, state.EyeWidth - 32),
                    Mathf.Clamp(y - 16, 0, state.Height - 32), 32, 32), ((char)('A' + i)).ToString(), labelStyle);
            }
        }

        private void SavePoint(double now)
        {
            if (diagnostic != null) {
                if (!Application.isFocused || !diagnosticDrawn || state.View == StereoProbeView.Channels
                    || !recorder.Feedback.TryGetCameraPoint(now, out _)) {
                    recorder.RejectBeforeCapture("WAIT FOR TRACKING"); return;
                }
                if (state.View == StereoProbeView.Both) recorder.SaveDiagnostic(diagnostic, now);
                else {
                    try { diagnostic.ConfirmEye(state.View); recorder.ClearOutcome(); }
                    catch (InvalidOperationException exc) { recorder.RejectBeforeCapture(exc.Message); }
                }
                return;
            }
            if (recorder != null)
            {
                StereoAlignmentPoint pendingPoint;
                try
                {
                    pendingPoint = state.PreviewMark(now);
                }
                catch (InvalidOperationException exc)
                {
                    recorder.RejectBeforeCapture(exc.Message);
                    return;
                }
                double responseValidatedAt = now;
                recorder.Collect(pendingPoint, () => {
                    responseValidatedAt = Time.realtimeSinceStartupAsDouble;
                    return Visible(responseValidatedAt);
                }, saved => state.CommitMark(saved, responseValidatedAt));
                return;
            }
            StereoAlignmentPoint point;
            try { point = state.Mark(now); }
            catch (InvalidOperationException exc)
            {
                Debug.Log("[STEREO PROBE] mark_ignored: " + exc.Message);
                return;
            }
            try
            {
                string path = Path.Combine(directory, "point-" + point.point_index.ToString("D3") + ".json");
                using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
                using (var writer = new StreamWriter(stream)) writer.Write(JsonUtility.ToJson(point, true));
                Debug.Log("[STEREO PROBE] saved view=" + point.selected_view + " path=" + path
                    + " calibration_valid=false display_alignment_verified=false");
            }
            catch (Exception exc) { Stop("save_failed: " + exc.Message, 2); }
        }

        private void Stop(string reason, int exitCode)
        {
            if (stopped) return;
            stopped = true;
            recorder?.Cancel();
            string message = "[STEREO PROBE] stopped reason=" + reason + " marked=" + (state?.MarkedCount ?? 0);
            if (exitCode == 0) Debug.Log(message);
            else Debug.LogError(message);
            Application.Quit(exitCode);
        }

        private static GUIStyle Style(int size)
        {
            var style = new GUIStyle(GUI.skin.label) {
                fontSize = size, alignment = TextAnchor.MiddleCenter, richText = false, wordWrap = false
            };
            style.normal.textColor = Color.white;
            return style;
        }

        private void OnDestroy()
        {
            if (ring != null) Destroy(ring);
        }
    }
}
