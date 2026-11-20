using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace ARAssembly
{
    public sealed class DisplayObservationRecorder : MonoBehaviour
    {
        private DisplayCollectionConfig config;
        private DisplayCorrespondenceStore store;
        private UnityWebRequest active;
        private ObservationHttpTransport background;
        private StageObservationPoll stagePoll;
        private int generation;
        private bool polling;
        private DisplayObservation renderedSource;
        private double sourceStarted, sourceReceived;
        private long sourceFrame = -1;
        public bool Pending { get; private set; }
        public bool Busy => Pending || polling || active != null;
        public string Status { get; private set; } = "READY";
        public DisplayObservationFeedback Feedback { get; } = new DisplayObservationFeedback();
        public string SessionId => config?.session_id;
        public string TargetId => config?.target_id;
        public double LastNetworkMs { get; private set; } = -1;

        public void Initialize(string configPath, CandidateProjection candidate = null, bool backgroundPolling = false)
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string path = Path.GetFullPath(configPath);
            if (!DisplayCorrespondenceRules.IsLocalCollectionPath(path, local) || new FileInfo(path).Length > 65536)
                throw new ArgumentException("Config must be a small local collection file");
            config = new DisplayCollectionConfig();
            JsonUtility.FromJsonOverwrite(File.ReadAllText(path), config);
            DisplayCorrespondenceRules.ValidateConfig(config);
            candidate?.Validate(config);
            config.directory = Path.GetFullPath(config.directory);
            if (!DisplayCorrespondenceRules.IsLocalCollectionPath(config.directory, local)
                || !string.Equals(Path.GetDirectoryName(path), config.directory, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("Config and records must share a local session directory");
            store = new DisplayCorrespondenceStore(config);
            background?.Dispose();
            background = backgroundPolling ? new ObservationHttpTransport(config) : null;
            stagePoll = null;
        }

        public void Collect(StereoAlignmentPoint point, Func<bool> stillValid, Action<StereoAlignmentPoint> onSaved)
        {
            if (!Pending) StartCoroutine(CollectRoutine(point, stillValid, onSaved));
        }

        public void Poll() { if (!Busy) StartCoroutine(PollRoutine()); }
        public void PollStage(double now, bool screwStage, bool keepDiagnosticSource = false)
        {
            if (background == null) return;
            if (stagePoll == null) stagePoll = new StageObservationPoll(background.FetchAsync);
            var reply = stagePoll.Tick(now, screwStage, out double started);
            if (reply != null) ApplyReply(reply, started, now, keepDiagnosticSource);
        }
        public void ClearOutcome() { if (!Pending) Status = "READY"; }

        public void RejectBeforeCapture(string reason)
        {
            if (Pending) return;
            Status = reason;
            Debug.Log("[CORRESPONDENCE] rejected stage=alignment reason=" + reason);
        }

        public IEnumerator PollRoutine()
        {
            if (Busy) yield break;
            polling = true;
            int attempt = generation;
            try {
                if (background == null) {
                    yield return RequestRoutine(attempt, (_, __, ___) => { }, _ => { });
                } else {
                    double started = Time.realtimeSinceStartupAsDouble;
                    var request = background.FetchAsync();
                    while (!request.IsCompleted && attempt == generation) yield return null;
                    if (attempt != generation) yield break;
                    ApplyReply(request.GetAwaiter().GetResult(), started, Time.realtimeSinceStartupAsDouble, true);
                }
            }
            finally { if (attempt == generation) polling = false; }
        }

        private void ApplyReply(ObservationHttpTransport.Reply reply, double started, double finished, bool keepDiagnosticSource)
        {
            LastNetworkMs = reply.NetworkMs;
            if (reply.Error != null) { Feedback.Fail(reply.Error); renderedSource = null; return; }
            try {
                var observation = new DisplayObservation();
                JsonUtility.FromJsonOverwrite(reply.Text, observation);
                // Include render-thread queue wait; a delayed reply does not renew the pose.
                Feedback.Apply(config, observation, started, finished);
                if (!keepDiagnosticSource) return;
                if (!Feedback.TryGetCameraPoint(finished, out _)) renderedSource = null;
                else if (observation.frame_id > sourceFrame) {
                    renderedSource = observation.Copy(); sourceFrame = observation.frame_id;
                    sourceStarted = started; sourceReceived = finished;
                }
            } catch (ArgumentException) { Feedback.Fail("INVALID OBSERVATION"); renderedSource = null; }
        }

        public TrackedAlignmentDiagnostic CreateTrackedDiagnostic(CandidateProjection candidate, string hash)
        {
            if (background == null) throw new InvalidOperationException("Background polling required");
            return new TrackedAlignmentDiagnostic(config, candidate, hash);
        }

        public bool RenderDiagnostic(TrackedAlignmentDiagnostic diagnostic, double now, StereoProbeView view,
            out double[] left, out double[] right)
        {
            left = right = null;
            if (renderedSource == null || !Feedback.TryGetCameraPoint(now, out _)) {
                diagnostic.Invalidate(); return false;
            }
            return diagnostic.TryRender(renderedSource, sourceStarted, sourceReceived, now, out left, out right, view);
        }

        public void SaveDiagnostic(TrackedAlignmentDiagnostic diagnostic, double now)
        {
            try {
                if (!Feedback.TryGetCameraPoint(now, out _)) throw new InvalidOperationException("NO FRESH POSE");
                var record = diagnostic.CreateRecord(now);
                string path = Path.Combine(config.directory, "diagnostic-frame-" + record.observation.frame_id + ".json");
                if (File.Exists(path)) throw new InvalidOperationException("FRAME ALREADY SAVED");
                string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
                try {
                    using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write))
                    using (var writer = new StreamWriter(stream)) writer.Write(JsonUtility.ToJson(record, true));
                    File.Move(temporary, path);
                } finally { if (File.Exists(temporary)) File.Delete(temporary); }
                diagnostic.MarkSaved(); Status = "SAVED";
                Debug.Log("[TRACKED DIAGNOSTIC] saved target=" + record.observation.target_id
                    + " frame=" + record.observation.frame_id + " age_ms="
                    + record.conservative_age_ms.ToString("F1") + " path=" + path);
            } catch (InvalidOperationException exc) { RejectBeforeCapture(exc.Message); }
              catch (IOException) { RejectBeforeCapture("SAVE FAILED"); }
              catch (UnauthorizedAccessException) { RejectBeforeCapture("SAVE FAILED"); }
        }

        // Also driven by the Editor batch smoke test, using the same real HTTP/parser/write path.
        public IEnumerator CollectRoutine(StereoAlignmentPoint point, Func<bool> stillValid, Action<StereoAlignmentPoint> onSaved)
        {
            if (background != null) throw new InvalidOperationException("Continuous polling is display-only");
            if (Pending) yield break;
            Pending = true;
            int attempt = generation;
            double captureStarted = Time.realtimeSinceStartupAsDouble;
            Status = polling ? "WAITING FOR REQUEST" : "CAPTURING";
            try {
                // Finish an in-flight diagnostic poll, then request a NEW observation for this Enter.
                while (polling && attempt == generation) yield return null;
                if (attempt != generation) yield break;
                if (config == null || point == null || (point.selected_view != "Left" && point.selected_view != "Right"
                    && point.selected_view != "Both") || !stillValid()) { Status = "ALIGN EYES FIRST"; yield break; }
                Status = "CAPTURING";
                yield return RequestRoutine(attempt, (observation, started, finished) => {
                    if (!stillValid()) { Status = "DISPLAY CHANGED"; return; }
                    try {
                        var candidate = DisplayCorrespondenceRules.Create(config, observation, point,
                            point.framebuffer_width, point.height, captureStarted, finished);
                        // Each eye has its own current pose; stability is local to this capture, not across eyes.
                        candidate.stability = Feedback.PairEvidence(finished);
                        if (candidate.stability == null || candidate.stability.last_frame_id != observation.frame_id) {
                            Status = "HOLD STILL"; return;
                        }
                        string path = store.Save(candidate, JsonUtility.ToJson(candidate, true));
                        onSaved(point);
                        Status = "SAVED";
                        Debug.Log("[CORRESPONDENCE] saved eye=" + candidate.eye + " frame=" + observation.frame_id
                            + " age_ms=" + candidate.conservative_age_ms.ToString("F1") + " path=" + path);
                    } catch (ArgumentException exc) {
                        Status = exc.Message == "STALE" ? "STALE" : exc.Message == "NO POSE" ? "NO POSE"
                            : exc.Message == "SETUP REQUIRED" ? "SETUP REQUIRED"
                            : exc.Message == "HOLD STILL" ? "HOLD STILL"
                            : exc.Message == "PAIR REQUIRES 1080P" ? "PAIR REQUIRES 1080P" : "INVALID OBSERVATION";
                    } catch (InvalidOperationException) { Status = "DUPLICATE OR CHANGED"; }
                      catch (IOException) { Status = "SAVE FAILED"; }
                      catch (UnauthorizedAccessException) { Status = "SAVE FAILED"; }
                }, error => Status = error);
                if (attempt == generation && Status != "SAVED") Debug.Log("[CORRESPONDENCE] rejected " + Status);
            } finally { if (attempt == generation) Pending = false; }
        }

        private IEnumerator RequestRoutine(int attempt, Action<DisplayObservation, double, double> received, Action<string> failed)
        {
            if (attempt != generation) yield break;
            UnityWebRequest request = null;
            try {
                if (active != null || config == null) { failed("CONNECTION ERROR"); yield break; }
                var download = new BoundedDownload();
                UnityWebRequestAsyncOperation operation;
                double started = Time.realtimeSinceStartupAsDouble;
                try {
                    request = new UnityWebRequest(config.observation_url, "GET", download, null) {
                        timeout = 1, redirectLimit = 0
                    };
                    active = request;
                    request.SetRequestHeader("Authorization", "Bearer " + config.token);
                    operation = request.SendWebRequest();
                } catch (Exception) { Feedback.Fail("CONNECTION ERROR"); failed("CONNECTION ERROR"); yield break; }
                yield return operation;
                double finished = Time.realtimeSinceStartupAsDouble;
                if (attempt != generation) yield break;
                if (request.result != UnityWebRequest.Result.Success || request.responseCode != 200) {
                    Feedback.Fail("CONNECTION ERROR"); failed("CONNECTION ERROR"); yield break;
                }
                DisplayObservation observation;
                try {
                    observation = new DisplayObservation();
                    // Overwrite an initialized DTO so omitted numeric fields remain invalid sentinels.
                    JsonUtility.FromJsonOverwrite(download.Text, observation);
                } catch (ArgumentException) { Feedback.Fail("INVALID OBSERVATION"); failed("INVALID OBSERVATION"); yield break; }
                Feedback.Apply(config, observation, started, finished);
                received(observation, started, finished);
            } finally {
                if (active == request) active = null;
                request?.Dispose();
            }
        }

        public void Cancel()
        {
            generation++;
            Pending = false;
            polling = false;
            Status = "CANCELLED";
            Feedback.Fail("CANCELLED");
            active?.Abort();
            active?.Dispose();
            active = null;
            background?.Dispose();
            background = null;
            stagePoll = null;
            renderedSource = null;
            LastNetworkMs = -1;
        }

        private void OnDisable() { Cancel(); }

        private sealed class BoundedDownload : DownloadHandlerScript
        {
            private readonly MemoryStream buffer = new MemoryStream();
            public BoundedDownload() : base(new byte[4096]) { }
            public string Text => Encoding.UTF8.GetString(buffer.ToArray());
            protected override bool ReceiveData(byte[] data, int length)
            {
                if (data == null || length < 0 || buffer.Length + length > 65536) return false;
                buffer.Write(data, 0, length);
                return true;
            }
        }
    }
}
