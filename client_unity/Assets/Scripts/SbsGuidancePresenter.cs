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
        private Texture2D ring, contextRing;
        private GUIStyle heading, action, statusStyle, cueStyle;
        private GUIStyle actionHeading, actionLine;
        private Font actionFont;
        private bool actionKorean;
        private double readyAt = -1;
        private string lastStatus;
        private string lastDisplayedText;
        private readonly GuidanceTextStability textStability = new GuidanceTextStability();
        private readonly ActionGuidanceDisplay actionDisplay = new ActionGuidanceDisplay();
        private ObservedCueDelay observedCueDelay = new ObservedCueDelay(0);
        private bool delayObservedCue;
        private bool candidateMode, outputChanged, stageTargets, stageContext, trialARight, instructionAboveTarget;
        private CandidateProjection candidate;
        private BoxOutlineProfile boxOutline;
        private bool boxOutlineRequested;
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
                actionKorean = options.ActionKorean;
                if (actionKorean) {
                    actionFont = Resources.Load<Font>("Fonts/NotoSansKR-Bold");
                    if (actionFont == null) {
                        Debug.LogError("[SBS ACTION] Korean font missing; keeping original guidance");
                        actionKorean = false;
                    }
                }
                Debug.Log("[SBS ACTION] korean=" + actionKorean + " presentation_only=true");
                observedCueDelay = new ObservedCueDelay(options.ObservedCueDelayMs);
                delayObservedCue = options.ObservedCueDelayMs > 0;
                Debug.Log("[SBS CUE] observed_delay_ms=" + options.ObservedCueDelayMs + " presentation_only=true");
                candidateMode = options.CandidatePresentation;
                stageTargets = options.StageTargets;
                stageContext = options.StageContext;
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
                    boxOutlineRequested = options.BoxOutlinePath != null;
                    if (boxOutlineRequested) {
                        try {
                            string boxPath = Path.GetFullPath(options.BoxOutlinePath);
                            if (boxPath.StartsWith(@"\\") || new FileInfo(boxPath).Length > 65536)
                                throw new ArgumentException("Box outline must be a small local file");
                            var outline = JsonUtility.FromJson<BoxOutlineProfile>(File.ReadAllText(boxPath));
                            if (outline == null) throw new ArgumentException("Missing box outline");
                            outline.Validate(candidate);
                            boxOutline = outline;
                        } catch (Exception exc) when (exc is ArgumentException || exc is IOException || exc is UnauthorizedAccessException) {
                            Debug.LogError("[BOX OUTLINE] Disabled; active screw retained: " + exc.GetType().Name);
                        }
                    }
                    Debug.Log("[CANDIDATE PRESENTATION] continuous=true target=" + (stageTargets ? "stage_ABCD" : "A")
                        + " trial_a_right_px=" + (trialARight ? CandidateProjection.TrialARightPx : 0)
                        + " stage_depth_cd=" + (options.StageDepthPath != null)
                        + " stage_context=" + stageContext
                        + " box_outline=" + (boxOutline != null)
                        + " calibration_valid=false transport=managed_async");
                }
            } catch (Exception exc) when (exc is ArgumentException || exc is IOException || exc is UnauthorizedAccessException) {
                candidateError = "PROFILE ERROR";
                candidate = null;
                observations?.Cancel();
                Debug.LogError("[CANDIDATE PRESENTATION] Profile loading failed: " + exc.GetType().Name);
            }
            ring = CreateRing(3.5f);
            if (stageContext) contextRing = CreateRing(4.5f);
        }

        private static Texture2D CreateRing(float halfThickness)
        {
            var texture = new Texture2D(128, 128, TextureFormat.RGBA32, false);
            var pixels = new Color[128 * 128];
            for (int y = 0; y < 128; y++)
                for (int x = 0; x < 128; x++) {
                    float distance = new Vector2(x - 63.5f, y - 63.5f).magnitude;
                    pixels[y * 128 + x] = new Color(1, 1, 1,
                        Mathf.Clamp01(halfThickness - Mathf.Abs(distance - 56)));
                }
            texture.SetPixels(pixels);
            texture.Apply(false, true);
            return texture;
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
                    observations.PollStage(now, CandidateProjection.StageTarget(receiver.State.LastSnapshot) != null
                        || boxOutline != null && boxOutline.WantsObservation(receiver.State, now));
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
            if (Event.current.type != EventType.Repaint) return;
            if (!display.Ready) return;
            if (heading == null) {
                heading = Style(40, Color.white);
                action = Style(48, Color.white);
                statusStyle = Style(28, new Color(1, .78f, .35f));
                cueStyle = Style(56, Color.white);
                if (actionKorean) {
                    actionHeading = Style(40, Color.white);
                    actionLine = Style(64, Color.white);
                    actionHeading.font = actionLine.font = actionFont;
                    actionHeading.wordWrap = actionLine.wordWrap = false;
                }
            }
            double now = Time.realtimeSinceStartupAsDouble;
            var state = receiver.State;
            var snapshot = state.LastSnapshot;
            var rawView = state.Presentation(now, receiver.SyntheticPreview, keepOperatorActionOnLoss: stageTargets);
            bool visible = state.Spatial.TryGetPixels(now, out var pair) && rawView.ShowTarget;
            double[] left = null, right = null;
            string gate = candidateMode ? CandidateStatus(now, out left, out right) : null;
            if (candidateMode) visible = gate == "VISIBLE";
            double[][] contextLeft = null, contextRight = null;
            double[][] boxLeft = null, boxRight = null;
            BoxOutlineProfile.Stroke[] boxStrokesLeft = null, boxStrokesRight = null;
            bool boxVisible = !outputChanged && candidateError == null && boxOutline != null
                && (boxOutline.RoundedStaged
                    ? boxOutline.TryProjectStrokes(candidate, observations?.Feedback, state, observations?.SessionId,
                        now, out boxStrokesLeft, out boxStrokesRight)
                    : boxOutline.TryProject(candidate, observations?.Feedback, state, observations?.SessionId,
                        now, out boxLeft, out boxRight));
            bool contextVisible = boxOutlineRequested ? boxVisible
                && (!boxOutline.RoundedStaged || CandidateProjection.StageTarget(snapshot) != null || snapshot?.current_state == "S6")
                && candidate.TryProjectCorners(observations.Feedback, now, out contextLeft, out contextRight)
                : visible && stageContext
                && candidate.TryProjectStageContext(observations.Feedback, state, observations.SessionId,
                    now, out contextLeft, out contextRight);
            string targetLabel = stageTargets ? CandidateProjection.StageTarget(snapshot) : "A REF";
            string context = snapshot?.session_id + "|" + snapshot?.current_state + "|" + snapshot?.target;
            var displayView = observedCueDelay.Apply(rawView, context, now);
            var view = textStability.Apply(displayView, context, now);
            string colorStatus = delayObservedCue ? view.Status : rawView.Status;
            Color ringColor = colorStatus == "OBSERVED" || colorStatus == "COMPLETED" ? new Color(.35f, 1f, .55f)
                : colorStatus == "GUIDING" || colorStatus == "LIVE" || delayObservedCue && colorStatus == "OBSERVING"
                    ? new Color(.35f, .85f, 1f)
                : new Color(1f, .78f, .35f);
            string hint = candidateMode
                ? textStability.Hint(boxVisible && snapshot?.current_state == "S6" ? "Assembly outline"
                    : boxVisible && (snapshot?.current_state == "S0" || snapshot?.current_state == "S1") ? "Box placement reference"
                    : CandidateHint(gate, now), gate, context, now) : view.Status.Replace('_', ' ');
            Color cueColor = view.Status == "PAUSED" ? new Color(1f, .78f, .35f) : ringColor;
            cueStyle.normal.textColor = cueColor;
            var compact = actionKorean ? actionDisplay.Apply(view, snapshot, gate,
                candidateMode && gate != "VISIBLE" ? hint : null, now) : default(ActionGuidanceText);
            if (actionKorean) {
                ringColor = compact.Tone == ActionGuidanceTone.Working ? new Color(.35f, .85f, 1f)
                    : compact.Tone == ActionGuidanceTone.Release || compact.Tone == ActionGuidanceTone.Complete
                        ? new Color(.35f, 1f, .55f) : new Color(1f, .78f, .35f);
                actionLine.normal.textColor = ringColor;
                actionLine.fontSize = 64;
                float textWidth = actionLine.CalcSize(new GUIContent(compact.Action)).x;
                if (textWidth > 1760) actionLine.fontSize = Mathf.FloorToInt(64 * 1760 / textWidth);
            }
            string shownText = "state=" + snapshot?.current_state + " cue=" + view.Cue
                + " instruction=" + view.Instruction + " hint=" + hint
                + (actionKorean ? " action_ko=" + compact.Action + " tone=" + compact.Tone
                    + " text_retained=" + compact.Retained : "");
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
                if (boxVisible) {
                    if (boxOutline.RoundedStaged) DrawBoxStrokes(eye == 0 ? boxStrokesLeft : boxStrokesRight);
                    else DrawBoxOutline(eye == 0 ? boxLeft : boxRight);
                }
                if (contextVisible) DrawStageContext(eye == 0 ? contextLeft : contextRight, targetLabel,
                    connectScrews: !boxOutlineRequested);
                string title = view.StepTitle;
                if (snapshot != null && view.IsReference) title = "Last: " + title;
                GUI.Label(new Rect(80, 40, 1760, 64), actionKorean ? compact.Title : title,
                    actionKorean ? actionHeading : heading);
                if (visible) {
                    float x = (float)(candidateMode ? (eye == 0 ? left[0] : right[0]) : (eye == 0 ? pair.LeftX : pair.RightX));
                    float y = (float)(candidateMode ? (eye == 0 ? left[1] : right[1]) : (eye == 0 ? pair.LeftY : pair.RightY));
                    Color previousColor = GUI.color;
                    GUI.color = ringColor;
                    GUI.DrawTexture(new Rect(x - 24, y - 24, 48, 48), ring);
                    GUI.color = previousColor;
                    if (candidateMode && !actionKorean) GUI.Label(new Rect(x - 60, y + 28, 120, 38), targetLabel, statusStyle);
                }
                if (actionKorean) {
                    GUI.Label(new Rect(80, cueY + 38, 1760, 100), compact.Action, actionLine);
                    if (receiver.SyntheticPreview || !candidateMode)
                        GUI.Label(new Rect(80, 1000, 1760, 45), "PREVIEW | NOT A LIVE ALIGNMENT", statusStyle);
                } else {
                    GUI.Label(new Rect(80, cueY, 1760, 64), view.Cue, cueStyle);
                    GUI.Label(new Rect(80, cueY + 76, 1760, 100), view.Instruction, action);
                    GUI.Label(new Rect(80, cueY + 176, 1760, 50), view.Acknowledgement, statusStyle);
                    GUI.Label(new Rect(80, 1000, 1760, 45),
                        candidateMode ? (stageTargets ? "STAGE GUIDE" : "A REF") + "  |  UNVERIFIED  |  " + hint
                            : (receiver.SyntheticPreview ? "SYNTHETIC  |  NOT CALIBRATED  |  " : "NOT CALIBRATED  |  ")
                                + hint, statusStyle);
                }
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

        private void DrawStageContext(double[][] points, string activeTarget, bool connectScrews)
        {
            Color previousColor = GUI.color;
            GUI.color = new Color(.45f, .85f, .8f, .45f);
            // Screw-center outline, not the physical outer lid boundary.
            string order = CandidateProjection.LidPerimeter;
            for (int i = 0; connectScrews && i < order.Length - 1; i++) {
                var a = points[order[i] - 'A']; var b = points[order[i + 1] - 'A'];
                DrawLine(a, b, 3);
            }
            GUI.color = new Color(.55f, .9f, .85f, .60f);
            for (int i = 0; i < points.Length; i++) {
                if (activeTarget != null && activeTarget[0] - 'A' == i) continue;
                GUI.DrawTexture(new Rect((float)points[i][0] - 18, (float)points[i][1] - 18, 36, 36), contextRing);
            }
            GUI.color = previousColor;
        }

        private static void DrawBoxOutline(double[][] points)
        {
            Color previousColor = GUI.color;
            // Wireframe reference: dim lower edges remain visible through the physical box.
            for (int i = 0; i < 4; i++) {
                int next = (i + 1) % 4;
                GUI.color = new Color(.45f, .85f, .8f, .25f);
                DrawLine(points[i + 4], points[next + 4], 2);
                GUI.color = new Color(.45f, .85f, .8f, .32f);
                DrawLine(points[i], points[i + 4], 2);
                GUI.color = new Color(.45f, .85f, .8f, .50f);
                DrawLine(points[i], points[next], 3);
            }
            GUI.color = previousColor;
        }

        private static void DrawBoxStrokes(BoxOutlineProfile.Stroke[] strokes)
        {
            Color previousColor = GUI.color;
            foreach (var stroke in strokes) {
                float light = stroke.Level == 3 ? .8f : .55f;
                float width = stroke.Level == 3 ? 4f : 3f;
                // Opaque dim RGB avoids brighter alpha-overlap spots along rounded joins.
                GUI.color = new Color(.55f * light, .95f * light, .85f * light, 1f);
                for (int i = 1; i < stroke.Points.Length; i++) DrawLine(stroke.Points[i - 1], stroke.Points[i], width);
            }
            GUI.color = previousColor;
        }

        private static void DrawLine(double[] a, double[] b, float width)
        {
            // IMGUI clips the source rectangle before rotation inside the eye group.
            if (b[0] < a[0]) { var swap = a; a = b; b = swap; }
            Matrix4x4 previous = GUI.matrix;
            var start = new Vector2((float)a[0], (float)a[1]);
            var delta = new Vector2((float)(b[0] - a[0]), (float)(b[1] - a[1]));
            GUIUtility.RotateAroundPivot(Mathf.Atan2(delta.y, delta.x) * Mathf.Rad2Deg, start);
            GUI.DrawTexture(new Rect(start.x, start.y - width / 2, delta.magnitude, width), Texture2D.whiteTexture);
            GUI.matrix = previous;
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

        private void OnDestroy()
        {
            observations?.Cancel();
            if (ring != null) Destroy(ring);
            if (contextRing != null) Destroy(contextRing);
        }
    }
}
