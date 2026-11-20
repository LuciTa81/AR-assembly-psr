using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

namespace ARAssembly
{
    [RequireComponent(typeof(GuidanceReceiver), typeof(DisplayBootstrap))]
    public sealed class SbsGuidancePresenter : MonoBehaviour
    {
        private GuidanceReceiver receiver;
        private DisplayBootstrap display;
        private Texture2D ring;
        private GUIStyle heading, action, statusStyle, cueStyle;
        private double readyAt = -1;
        private string lastStatus;
        private string lastDisplayedText;
        private readonly GuidanceTextStability textStability = new GuidanceTextStability();
        private ObservedCueDelay observedCueDelay = new ObservedCueDelay(0);
        private bool delayObservedCue;
        private bool candidateMode, outputChanged, stageTargets, trialARight, instructionAboveTarget;
        private CandidateProjection candidate;
        private DisplayObservationRecorder observations;
        private string candidateError;
        private double nextPoll, nextReport;
        private int shownFrames, sampledFrames;
        private readonly Dictionary<string, int> visibilityCounts = new Dictionary<string, int>();

        public string CaptureStatus
        {
            get {
                double now = Time.realtimeSinceStartupAsDouble;
                if (receiver.State.LastSnapshot?.guidance != null) {
                    var view = receiver.State.Presentation(now, receiver.SyntheticPreview);
                    return "SBS_GUIDANCE_" + view.Status + "_" + receiver.State.LastSnapshot.target
                        + (view.Acknowledgement.Length > 0 ? "_ACK" : "");
                }
                return "SBS_" + receiver.State.Spatial.Status(now) + "_" + (receiver.State.LastSnapshot?.target ?? "none");
            }
        }

        private void Awake()
        {
            receiver = GetComponent<GuidanceReceiver>();
            display = GetComponent<DisplayBootstrap>();
            try {
                var options = SbsGuidanceOptions.Parse(Environment.GetCommandLineArgs());
                observedCueDelay = new ObservedCueDelay(options.ObservedCueDelayMs);
                delayObservedCue = options.ObservedCueDelayMs > 0;
                Debug.Log("[SBS CUE] observed_delay_ms=" + options.ObservedCueDelayMs + " presentation_only=true");
                candidateMode = options.CandidatePresentation;
                stageTargets = options.StageTargets;
                trialARight = options.TrialARight;
                if (candidateMode) {
                    string path = Path.GetFullPath(options.CandidatePath);
                    if (path.StartsWith(@"\\") || new FileInfo(path).Length > 65536)
                        throw new ArgumentException("Candidate must be a small local file");
                    candidate = new CandidateProjection();
                    byte[] bytes = File.ReadAllBytes(path);
                    JsonUtility.FromJsonOverwrite(System.Text.Encoding.UTF8.GetString(bytes).TrimStart('\uFEFF'), candidate);
                    observations = gameObject.AddComponent<DisplayObservationRecorder>();
                    observations.Initialize(options.ObservationPath, candidate, backgroundPolling: true);
                    if (options.StageDepthPath != null) {
                        StageDepthConfig.LoadAndBind(candidate, bytes,
                            JsonUtility.FromJson<DisplayCollectionConfig>(File.ReadAllText(options.ObservationPath)),
                            options.StageDepthPath, Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                            (text, type) => JsonUtility.FromJson(text, type));
                    }
                    Debug.Log("[CANDIDATE PRESENTATION] continuous=true target=" + (stageTargets ? "stage_ABCD" : "A")
                        + " trial_a_right_px=" + (trialARight ? CandidateProjection.TrialARightPx : 0)
                        + " stage_depth_cd=" + (options.StageDepthPath != null)
                        + " calibration_valid=false transport=managed_async");
                }
            } catch (Exception exc) when (exc is ArgumentException || exc is IOException || exc is UnauthorizedAccessException) {
                candidateError = "PROFILE ERROR";
                candidate = null;
                observations?.Cancel();
                Debug.LogError("[CANDIDATE PRESENTATION] Profile loading failed: " + exc.GetType().Name);
            }
            ring = new Texture2D(128, 128, TextureFormat.RGBA32, false);
            var pixels = new Color[128 * 128];
            for (int y = 0; y < 128; y++)
                for (int x = 0; x < 128; x++) {
                    float distance = new Vector2(x - 63.5f, y - 63.5f).magnitude;
                    pixels[y * 128 + x] = new Color(1, 1, 1,
                        Mathf.Clamp01(3.5f - Mathf.Abs(distance - 56)));
                }
            ring.SetPixels(pixels);
            ring.Apply(false, true);
        }

        private void Update()
        {
            double now = Time.realtimeSinceStartupAsDouble;
            if (!display.Ready) {
                if (now > 20) Application.Quit(2);
                return;
            }
            if (readyAt < 0) readyAt = now;
            if (candidateMode && candidate != null) {
                var physical = Screen.mainWindowDisplayInfo;
                if (!CandidateProjection.IsPresentationOutput(Screen.width, Screen.height,
                    physical.width, physical.height, physical.name, Screen.fullScreenMode == FullScreenMode.FullScreenWindow)) {
                    outputChanged = true;
                    observations.Cancel();
                }
                if (!outputChanged && stageTargets) {
                    observations.PollStage(now, CandidateProjection.StageTarget(receiver.State.LastSnapshot) != null);
                } else if (!outputChanged && now >= nextPoll && !observations.Busy) {
                    nextPoll = now + CandidateProjection.PollIntervalSeconds;
                    observations.Poll();
                }
                sampledFrames++;
                string cause = CandidateStatus(now, out _, out _);
                if (cause == "VISIBLE") shownFrames++;
                visibilityCounts.TryGetValue(cause, out int count);
                visibilityCounts[cause] = count + 1;
                if (now >= nextReport) {
                    nextReport = now + 5;
                    var counts = new List<string>();
                    foreach (var entry in visibilityCounts) counts.Add(entry.Key + ":" + entry.Value);
                    Debug.Log("[CANDIDATE PRESENTATION] state=" + receiver.State.LastSnapshot?.current_state
                        + " state_frame=" + receiver.State.LastSnapshot?.frame_id
                        + " gate=" + cause + " shown=" + shownFrames + "/" + sampledFrames
                        + " counts=[" + string.Join(", ", counts) + "] " + observations.Feedback.Diagnostic(now)
                        + " network_ms=" + observations.LastNetworkMs.ToString("F1", System.Globalization.CultureInfo.InvariantCulture)
                        + " detail=" + observations.Feedback.Detail(now));
                    shownFrames = sampledFrames = 0;
                    visibilityCounts.Clear();
                }
            }
            receiver.State.Spatial.ObserveOutput(Screen.mainWindowDisplayInfo.name,
                Screen.width, Screen.height, Screen.fullScreenMode == FullScreenMode.Windowed);
            if (receiver.SyntheticPreview && now - readyAt >= receiver.PreviewDuration) Application.Quit();
            string status = CaptureStatus;
            if (status != lastStatus) {
                Debug.Log("[SBS GUIDANCE] " + status + " rtt_ms=" + receiver.LastRoundTripMs.ToString("F1")
                    + " pose_age_ms=" + (receiver.State.LastSnapshot?.spatial?.pose_age_ms ?? -1));
                lastStatus = status;
            }
        }

        private void OnGUI()
        {
            if (Event.current.type == EventType.KeyDown && (Event.current.keyCode == KeyCode.Escape
                || (candidateMode && Event.current.keyCode == KeyCode.Q))) Application.Quit();
            if (!display.Ready) return;
            if (heading == null) {
                heading = Style(40, Color.white);
                action = Style(48, Color.white);
                statusStyle = Style(28, new Color(1, .78f, .35f));
                cueStyle = Style(56, Color.white);
            }
            double now = Time.realtimeSinceStartupAsDouble;
            var state = receiver.State;
            var snapshot = state.LastSnapshot;
            var rawView = state.Presentation(now, receiver.SyntheticPreview, keepOperatorActionOnLoss: stageTargets);
            bool visible = state.Spatial.TryGetPixels(now, out var pair) && rawView.ShowTarget;
            double[] left = null, right = null;
            string gate = candidateMode ? CandidateStatus(now, out left, out right) : null;
            if (candidateMode) visible = gate == "VISIBLE";
            string targetLabel = stageTargets ? CandidateProjection.StageTarget(snapshot) : "A REF";
            string context = snapshot?.session_id + "|" + snapshot?.current_state + "|" + snapshot?.target;
            var displayView = observedCueDelay.Apply(rawView, context, now);
            var view = textStability.Apply(displayView, context, now);
            string colorStatus = delayObservedCue ? view.Status : rawView.Status;
            Color ringColor = colorStatus == "OBSERVED" ? new Color(.35f, 1f, .55f)
                : colorStatus == "GUIDING" || colorStatus == "LIVE" || delayObservedCue && colorStatus == "OBSERVING"
                    ? new Color(.35f, .85f, 1f)
                : new Color(1f, .78f, .35f);
            string hint = candidateMode
                ? textStability.Hint(CandidateHint(gate, now), gate, context, now) : view.Status.Replace('_', ' ');
            Color cueColor = view.Status == "PAUSED" ? new Color(1f, .78f, .35f) : ringColor;
            cueStyle.normal.textColor = cueColor;
            string shownText = "state=" + snapshot?.current_state + " cue=" + view.Cue
                + " instruction=" + view.Instruction + " hint=" + hint;
            if (shownText != lastDisplayedText) {
                Debug.Log("[SBS TEXT] " + shownText);
                lastDisplayedText = shownText;
            }
            // Keep both eyes' instruction band stable during pose loss and small target jitter.
            if (visible) {
                double targetY = candidateMode ? Math.Max(left[1], right[1]) : Math.Max(pair.LeftY, pair.RightY);
                if (targetY > 650) instructionAboveTarget = true;
                else if (targetY < 550) instructionAboveTarget = false;
            }
            float cueY = instructionAboveTarget ? 140 : 760;
            Matrix4x4 previous = GUI.matrix;
            float scale = Mathf.Min(Screen.width / 3840f, Screen.height / 1080f);
            GUI.matrix = Matrix4x4.TRS(new Vector3((Screen.width - 3840 * scale) / 2,
                (Screen.height - 1080 * scale) / 2, 0), Quaternion.identity, Vector3.one * scale);
            for (int eye = 0; eye < 2; eye++) {
                // IMGUI already uses top-left coordinates; clipping keeps each ring in its eye.
                GUI.BeginGroup(new Rect(eye * 1920, 0, 1920, 1080));
                string title = view.StepTitle;
                if (snapshot != null && view.IsReference) title = "Last: " + title;
                GUI.Label(new Rect(80, 40, 1760, 64), title, heading);
                if (visible) {
                    float x = (float)(candidateMode ? (eye == 0 ? left[0] : right[0]) : (eye == 0 ? pair.LeftX : pair.RightX));
                    float y = (float)(candidateMode ? (eye == 0 ? left[1] : right[1]) : (eye == 0 ? pair.LeftY : pair.RightY));
                    Color previousColor = GUI.color;
                    GUI.color = ringColor;
                    GUI.DrawTexture(new Rect(x - 24, y - 24, 48, 48), ring);
                    GUI.color = previousColor;
                    if (candidateMode) GUI.Label(new Rect(x - 60, y + 28, 120, 38), targetLabel, statusStyle);
                }
                GUI.Label(new Rect(80, cueY, 1760, 64), view.Cue, cueStyle);
                GUI.Label(new Rect(80, cueY + 76, 1760, 100), view.Instruction, action);
                GUI.Label(new Rect(80, cueY + 176, 1760, 50), view.Acknowledgement, statusStyle);
                GUI.Label(new Rect(80, 1000, 1760, 45),
                    candidateMode ? (stageTargets ? "STAGE GUIDE" : "A REF") + "  |  UNVERIFIED  |  " + hint
                        : (receiver.SyntheticPreview ? "SYNTHETIC  |  NOT CALIBRATED  |  " : "NOT CALIBRATED  |  ")
                            + hint, statusStyle);
                GUI.EndGroup();
            }
            GUI.matrix = previous;
        }

        private string CandidateHint(string gate, double now)
        {
            if (stageTargets && gate == "VISIBLE") return "Target visible";
            if (gate == "NO STAGE TARGET") return "Text guidance only";
            if (gate == "STAGE TARGET UNAVAILABLE") return "Target position unavailable";
            if (gate == "OUTSIDE TARGET DEPTH") return "Return to the tested working distance";
            if (gate == "STATE TRACKING_LOST") return "Bring the workspace markers into view";
            if (gate == "DISPLAY CHANGED") return "Display changed. Position guide paused";
            if (gate == "PROFILE ERROR") return "Profile unavailable. Position guide paused";
            return observations == null ? "Waiting for position" : observations.Feedback.PresentationHint(gate, now);
        }

        private string CandidateStatus(double now, out double[] left, out double[] right)
        {
            left = right = null;
            if (outputChanged) return "DISPLAY CHANGED";
            if (candidateError != null) return candidateError;
            if (observations == null || candidate == null) return "WAITING";
            return candidate.PresentationStatus(observations.Feedback, receiver.State,
                observations.SessionId, now, out left, out right, stageTargets, trialARight);
        }

        private static GUIStyle Style(int size, Color color)
        {
            var style = new GUIStyle(GUI.skin.label) { fontSize = size,
                alignment = TextAnchor.MiddleCenter, wordWrap = true, richText = false };
            style.normal.textColor = color;
            return style;
        }

        private void OnDestroy() { observations?.Cancel(); if (ring != null) Destroy(ring); }
    }
}
