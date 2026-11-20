using System;
using System.Collections.Generic;
using System.IO;

namespace ARAssembly
{
    [Serializable]
    public sealed class DisplayCollectionConfig
    {
        public string schema_version, session_id, observation_url, token, directory;
        public string camera_profile_id, camera_profile_sha256, workspace_profile_id, workspace_profile_sha256;
        public string target_id, setup_id;
        public int[] image_size;
    }

    [Serializable]
    public sealed class DisplayCameraTarget
    {
        public string target_id;
        public double[] camera_xyz_mm;
    }

    [Serializable]
    public sealed class DisplayObservation
    {
        public string schema_version, session_id, status, reason, reason_code, target_id;
        public string camera_profile_id, camera_profile_sha256, workspace_profile_id, workspace_profile_sha256;
        public int[] image_size, marker_ids;
        public int marker_count = -1;
        public long frame_id = -1;
        public double age_ms = double.NaN, rms_px = double.NaN, max_error_px = double.NaN;
        public double[] rvec, tvec_mm, world_xyz_mm, camera_xyz_mm, target_pixel;
        public DisplayCameraTarget[] camera_targets;

        public DisplayObservation Copy()
        {
            var copy = (DisplayObservation)MemberwiseClone();
            copy.image_size = (int[])image_size?.Clone(); copy.marker_ids = (int[])marker_ids?.Clone();
            copy.rvec = (double[])rvec?.Clone(); copy.tvec_mm = (double[])tvec_mm?.Clone();
            copy.world_xyz_mm = (double[])world_xyz_mm?.Clone(); copy.camera_xyz_mm = (double[])camera_xyz_mm?.Clone();
            copy.target_pixel = (double[])target_pixel?.Clone();
            if (camera_targets != null) {
                copy.camera_targets = new DisplayCameraTarget[camera_targets.Length];
                for (int i = 0; i < camera_targets.Length; i++)
                    if (camera_targets[i] != null) copy.camera_targets[i] = new DisplayCameraTarget {
                        target_id = camera_targets[i].target_id,
                        camera_xyz_mm = (double[])camera_targets[i].camera_xyz_mm?.Clone()
                    };
            }
            return copy;
        }
    }

    [Serializable]
    public sealed class DisplayCorrespondenceCandidate
    {
        public string schema_version = "beast_display_correspondence_candidate_v1";
        public bool candidate_only = true, calibration_valid = false, display_alignment_verified = false;
        public string eye, setup_id;
        public bool binocular_confirmed_by_user;
        public DisplayPairStability stability;
        public StereoAlignmentPoint display;
        public DisplayObservation observation;
        public int output_width, output_height;
        public double request_started_seconds, response_received_seconds, request_rtt_ms, conservative_age_ms;
    }

    public static class DisplayCorrespondenceRules
    {
        public static bool IsLocalCollectionPath(string path, string localApplicationData)
        {
            string full = Path.GetFullPath(path);
            string local = Path.GetFullPath(localApplicationData);
            string root = Path.Combine(local, "ARAssembly", "beast-mvp", "display_correspondence") + Path.DirectorySeparatorChar;
            if (full.StartsWith(root, StringComparison.OrdinalIgnoreCase)) return true;
            string packages = Path.Combine(local, "Packages") + Path.DirectorySeparatorChar;
            if (!full.StartsWith(packages, StringComparison.OrdinalIgnoreCase)) return false;
            var parts = full.Substring(packages.Length).Split(Path.DirectorySeparatorChar);
            // Windows packaged Codex can resolve LocalAppData to its physical LocalCache alias.
            if (parts.Length < 7 || !parts[0].StartsWith("OpenAI.Codex_", StringComparison.OrdinalIgnoreCase)) return false;
            string[] expected = { "LocalCache", "Local", "ARAssembly", "beast-mvp", "display_correspondence" };
            for (int i = 0; i < expected.Length; i++)
                if (!parts[i + 1].Equals(expected[i], StringComparison.OrdinalIgnoreCase)) return false;
            return true;
        }

        public static void ValidateConfig(DisplayCollectionConfig config)
        {
            Require(config != null && config.schema_version == "beast_display_collection_config_v1", "Invalid config schema");
            Require(!string.IsNullOrWhiteSpace(config.session_id) && !string.IsNullOrWhiteSpace(config.token)
                && !string.IsNullOrWhiteSpace(config.directory), "Missing config identity");
            Require(!string.IsNullOrWhiteSpace(config.camera_profile_id) && !string.IsNullOrWhiteSpace(config.workspace_profile_id)
                && IsHash(config.camera_profile_sha256) && IsHash(config.workspace_profile_sha256), "Invalid profile binding");
            Require(config.image_size != null && config.image_size.Length == 2
                && config.image_size[0] > 0 && config.image_size[1] > 0
                && config.target_id != null && config.target_id.Length == 1
                && "ABCD".Contains(config.target_id), "Invalid target or image size");
            Uri uri;
            Require(Uri.TryCreate(config.observation_url, UriKind.Absolute, out uri)
                && uri.Scheme == "http" && uri.Host == "127.0.0.1" && uri.Port > 0
                && uri.UserInfo == "" && uri.Query == "" && uri.Fragment == ""
                && uri.AbsolutePath == "/observation"
                && config.observation_url == "http://127.0.0.1:" + uri.Port + "/observation", "Invalid loopback endpoint");
        }

        public static DisplayCorrespondenceCandidate Create(DisplayCollectionConfig config, DisplayObservation observation,
            StereoAlignmentPoint point, int outputWidth, int outputHeight, double requestStarted, double responseReceived)
        {
            double age = ValidateObservation(config, observation, requestStarted, responseReceived);
            bool paired = point != null && point.selected_view == "Both" && point.left_marked && point.right_marked;
            Require(!string.IsNullOrWhiteSpace(config.setup_id) && config.setup_id.Length <= 128,
                "SETUP REQUIRED");
            Require(!paired || point.height == 1080, "PAIR REQUIRES 1080P");
            Require(!paired || observation.marker_count == observation.marker_ids.Length, "Invalid marker count");
            Require(point != null && point.channels_confirmed_by_user
                && (point.selected_view == "Left" || point.selected_view == "Right" || paired), "Confirm eye alignment");
            Require(StereoAlignmentState.SupportedSize(point.framebuffer_width, point.height)
                && point.eye_width == point.framebuffer_width / 2
                && outputWidth == point.framebuffer_width && outputHeight == point.height, "Display changed");
            Require(Finite(point.left_x) && Finite(point.right_x) && Finite(point.left_y) && Finite(point.right_y)
                && point.left_x >= 24 && point.right_x >= 24 && point.left_x <= point.eye_width - 24
                && point.right_x <= point.eye_width - 24 && point.left_y >= 24 && point.right_y >= 24
                && point.left_y <= point.height - 24 && point.right_y <= point.height - 24, "Invalid eye coordinates");
            return new DisplayCorrespondenceCandidate {
                schema_version = paired ? "beast_display_correspondence_pair_v2" : "beast_display_correspondence_candidate_v1",
                eye = paired ? "both" : point.selected_view == "Left" ? "left" : "right",
                binocular_confirmed_by_user = paired, setup_id = config.setup_id, display = point, observation = observation,
                output_width = outputWidth, output_height = outputHeight, request_started_seconds = requestStarted,
                response_received_seconds = responseReceived, request_rtt_ms = (responseReceived - requestStarted) * 1000,
                conservative_age_ms = age
            };
        }

        public static void ValidateBinding(DisplayCollectionConfig config, DisplayObservation observation)
        {
            ValidateConfig(config);
            Require(observation != null && observation.schema_version == "beast_display_observation_v1", "Invalid observation schema");
            Require(observation.session_id == config.session_id && observation.camera_profile_id == config.camera_profile_id
                && observation.workspace_profile_id == config.workspace_profile_id
                && observation.camera_profile_sha256 == config.camera_profile_sha256
                && observation.workspace_profile_sha256 == config.workspace_profile_sha256, "Observation binding mismatch");
            Require(observation.image_size != null && observation.image_size.Length == 2
                && observation.image_size[0] == config.image_size[0] && observation.image_size[1] == config.image_size[1]
                && observation.target_id == config.target_id, "Observation geometry mismatch");
        }

        public static double ValidateObservation(DisplayCollectionConfig config, DisplayObservation observation,
            double requestStarted, double responseReceived)
        {
            ValidateBinding(config, observation);
            Require(observation.status == "tracking" && observation.reason != null && observation.frame_id > 0, "NO POSE");
            Require(Finite(requestStarted) && Finite(responseReceived) && requestStarted >= 0
                && responseReceived >= requestStarted, "Invalid request clock");
            double rtt = (responseReceived - requestStarted) * 1000;
            double age = observation.age_ms + rtt;
            Require(Finite(observation.age_ms) && observation.age_ms >= 0 && Finite(age) && age <= 150, "STALE");
            Vector(observation.rvec, 3); Vector(observation.tvec_mm, 3); Vector(observation.world_xyz_mm, 3);
            Vector(observation.camera_xyz_mm, 3); Vector(observation.target_pixel, 2);
            Require(observation.camera_xyz_mm[2] > 0 && observation.world_xyz_mm[2] >= 0
                && observation.target_pixel[0] >= 0 && observation.target_pixel[0] < config.image_size[0]
                && observation.target_pixel[1] >= 0 && observation.target_pixel[1] < config.image_size[1], "Target not visible");
            Require(Finite(observation.rms_px) && Finite(observation.max_error_px) && observation.rms_px >= 0
                && observation.rms_px <= 3 && observation.max_error_px >= observation.rms_px
                && observation.max_error_px <= 5, "Invalid pose quality");
            Require(observation.marker_ids != null && observation.marker_ids.Length >= 4, "Missing marker IDs");
            var ids = new HashSet<int>();
            foreach (int id in observation.marker_ids) Require(id >= 0 && id < 50 && ids.Add(id), "Invalid marker IDs");
            return age;
        }

        private static void Vector(double[] value, int size)
        {
            Require(value != null && value.Length == size, "Missing vector");
            foreach (double component in value) Require(Finite(component), "Non-finite vector");
        }
        private static bool IsHash(string value)
        {
            if (value == null || value.Length != 64) return false;
            foreach (char c in value) if (!(c >= '0' && c <= '9' || c >= 'a' && c <= 'f')) return false;
            return true;
        }
        private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
        private static void Require(bool condition, string reason)
        {
            if (!condition) throw new ArgumentException(reason);
        }
    }

    public sealed class DisplayObservationFeedback
    {
        private sealed class StableSample
        {
            public long Frame;
            public double CaptureAt;
            public double[] Point;
        }
        private readonly List<StableSample> stable = new List<StableSample>();

        public DisplayPairStability PairEvidence(double now)
        {
            if (Status(now) != "POSE READY" || stable.Count < 3) return null;
            double span = (stable[stable.Count - 1].CaptureAt - stable[0].CaptureAt) * 1000;
            if (span < 180) return null;
            double maximum = 0;
            foreach (var a in stable)
                foreach (var b in stable) maximum = Math.Max(maximum, Distance(a.Point, b.Point));
            return new DisplayPairStability {
                distinct_frames = stable.Count, first_frame_id = stable[0].Frame,
                last_frame_id = stable[stable.Count - 1].Frame,
                span_ms = span, max_target_delta_mm = maximum
            };
        }

        private static double Distance(double[] a, double[] b)
        {
            double sum = 0;
            for (int i = 0; i < 3; i++) sum += (a[i] - b[i]) * (a[i] - b[i]);
            return Math.Sqrt(sum);
        }

        private void ObserveStability(DisplayObservation observation, double started)
        {
            // Estimate capture time in the client clock; repeated HTTP polls are not new evidence.
            double captureAt = started - observation.age_ms / 1000;
            if (stable.Count > 0) {
                var last = stable[stable.Count - 1];
                if (observation.frame_id == last.Frame) return;
                if (captureAt <= last.CaptureAt || captureAt - last.CaptureAt > .25) stable.Clear();
            }
            stable.RemoveAll(sample => captureAt - sample.CaptureAt > .6);
            foreach (var sample in stable)
                if (Distance(sample.Point, observation.camera_xyz_mm) > 2) { stable.Clear(); break; }
            stable.Add(new StableSample { Frame = observation.frame_id, CaptureAt = captureAt,
                Point = (double[])observation.camera_xyz_mm.Clone() });
        }

        public long DiagnosticFrameId { get; private set; } = -1;
        public string DiagnosticResponseStatus { get; private set; } = "none";
        public double DiagnosticServerAgeMs { get; private set; } = -1;
        public double DiagnosticRttMs { get; private set; } = -1;
        private double diagnosticReceivedAt = -1;
        public double DiagnosticAgeMs(double now) => diagnosticReceivedAt < 0 || DiagnosticServerAgeMs < 0
            || !Finite(now) || now < diagnosticReceivedAt ? -1
            : DiagnosticServerAgeMs + DiagnosticRttMs + (now - diagnosticReceivedAt) * 1000;
        public string Diagnostic(double now) => string.Format(System.Globalization.CultureInfo.InvariantCulture,
            "pose_frame={0} response={1} server_age_ms={2:F1} rtt_ms={3:F1} age_now_ms={4:F1}",
            DiagnosticFrameId, DiagnosticResponseStatus, DiagnosticServerAgeMs, DiagnosticRttMs, DiagnosticAgeMs(now));

        private double[] cameraPoint;
        private double[][] cameraTargets;
        private DisplayObservation poseObservation;

        public bool TryGetObservation(double now, out DisplayObservation observation)
        {
            observation = null;
            if (!TryGetCameraPoint(now, out _) || poseObservation == null) return false;
            observation = poseObservation.Copy();
            return true;
        }

        public bool TryGetCameraTargets(double now, out double[][] xyz)
        {
            xyz = null;
            if (!TryGetCameraPoint(now, out _) || cameraTargets == null) return false;
            xyz = new double[4][];
            for (int i = 0; i < 4; i++) xyz[i] = (double[])cameraTargets[i].Clone();
            return true;
        }

        private static double[][] ReadCameraTargets(DisplayObservation observation)
        {
            if (observation.camera_targets == null || observation.camera_targets.Length != 4) return null;
            var result = new double[4][];
            foreach (var target in observation.camera_targets) {
                if (target == null || target.target_id == null || target.target_id.Length != 1) return null;
                int index = "ABCD".IndexOf(target.target_id, StringComparison.Ordinal);
                var point = target.camera_xyz_mm;
                if (index < 0 || result[index] != null || point == null || point.Length != 3
                    || !Finite(point[0]) || !Finite(point[1]) || !Finite(point[2]) || point[2] <= 0) return null;
                result[index] = (double[])point.Clone();
            }
            // Optional corners must belong to the validated primary observation.
            int primary = "ABCD".IndexOf(observation.target_id, StringComparison.Ordinal);
            return primary >= 0 && Distance(result[primary], observation.camera_xyz_mm) <= 1e-6 ? result : null;
        }
        public bool TryGetCameraPoint(double now, out double[] xyz)
        {
            xyz = null;
            if (Status(now) != "POSE READY" || now >= expiresAt || cameraPoint == null) return false;
            xyz = (double[])cameraPoint.Clone();
            return true;
        }
        private string status = "WAITING", detail = "Markers ?", reasonCode;
        private double expiresAt = double.PositiveInfinity, receivedAt;
        private long latestFrame = -1;

        public void Apply(DisplayCollectionConfig config, DisplayObservation observation, double started, double finished)
        {
            try {
                DisplayCorrespondenceRules.ValidateBinding(config, observation);
                if (!Finite(started) || !Finite(finished) || started < 0 || finished < started)
                    throw new ArgumentException("Invalid clock");
                DiagnosticFrameId = observation.frame_id;
                DiagnosticResponseStatus = observation.status;
                DiagnosticServerAgeMs = Finite(observation.age_ms) && observation.age_ms >= 0 ? observation.age_ms : -1;
                DiagnosticRttMs = (finished - started) * 1000;
                diagnosticReceivedAt = finished;
                if (observation.status == "waiting" || observation.status == "camera_error" || observation.status == "stale") {
                    SetUnavailable(observation.status == "waiting" ? "WAITING" : observation.status == "stale" ? "STALE" : "CAMERA ERROR");
                    return;
                }
                if (observation.status != "tracking" && observation.status != "pose_rejected") throw new ArgumentException("Invalid status");
                double age = observation.age_ms + (finished - started) * 1000;
                if (!Finite(age) || observation.age_ms < 0 || age > 150) { SetUnavailable("STALE"); return; }
                if (observation.frame_id < 1 || observation.frame_id < latestFrame) throw new ArgumentException("Invalid frame");
                if (observation.status == "tracking") DisplayCorrespondenceRules.ValidateObservation(config, observation, started, finished);
                if (observation.status == "tracking") ObserveStability(observation, started);
                else stable.Clear();
                double deadline = finished + (150 - age) / 1000;
                if (observation.status != "tracking") { cameraPoint = null; cameraTargets = null; poseObservation = null; }
                else if (observation.frame_id > latestFrame) {
                    cameraPoint = (double[])observation.camera_xyz_mm.Clone();
                    cameraTargets = ReadCameraTargets(observation);
                    poseObservation = observation.Copy();
                }
                expiresAt = observation.frame_id == latestFrame ? Math.Min(expiresAt, deadline) : deadline;
                latestFrame = observation.frame_id;
                receivedAt = finished;
                status = observation.status == "tracking" ? "POSE READY" : "NO POSE";
                reasonCode = observation.reason_code;
                string markers = observation.marker_ids == null ? "?" : observation.marker_ids.Length.ToString();
                string reason = (observation.reason ?? "").Replace('\r', ' ').Replace('\n', ' ');
                detail = "Markers " + markers + " | " + (status == "POSE READY"
                    ? "RMS " + observation.rms_px.ToString("F2", System.Globalization.CultureInfo.InvariantCulture) + "px"
                    : reason.Substring(0, Math.Min(reason.Length, 150)));
            } catch (ArgumentException) { Fail("INVALID OBSERVATION"); }
        }

        public void Fail(string reason)
        {
            DiagnosticFrameId = -1;
            DiagnosticResponseStatus = "none";
            DiagnosticServerAgeMs = DiagnosticRttMs = diagnosticReceivedAt = -1;
            SetUnavailable(reason);
        }

        private void SetUnavailable(string reason)
        {
            stable.Clear();
            cameraPoint = null;
            cameraTargets = null;
            poseObservation = null;
            reasonCode = null;
            status = reason; detail = "Markers ?";
        }

        public string PresentationHint(string gate, double now)
        {
            // Explain the existing gate; this never changes visibility or freshness.
            switch (gate) {
                case "DISPLAY CHANGED": return "Display changed. Position guide paused";
                case "PROFILE ERROR": return "Profile unavailable. Position guide paused";
                case "SESSION MISMATCH": return "Session mismatch. Position guide paused";
                case "STATE DISCONNECTED": return "State connection lost";
                case "STATE STALE": return "State updates delayed";
                case "STATE TRACKING_LOST": return "Workspace tracking lost";
                case "STATE WAITING": return "Waiting for state";
                case "OUTSIDE EYE VIEW": return "Target outside display area";
                case "WAITING": return "Waiting for position";
            }
            if (gate != "VISIBLE" && gate != "POSE NO POSE" && (gate == null || !gate.StartsWith("POSE ")))
                return "Position guide paused";
            switch (Status(now)) {
                case "STALE": return "Position updates delayed";
                case "WAITING": return "Waiting for position";
                case "CAMERA ERROR": return "Camera unavailable";
                case "CONNECTION ERROR": return "Position connection lost";
                case "POSE READY": return gate == "VISIBLE" ? "Reference visible" : "Position guide paused";
                case "NO POSE":
                    switch (reasonCode) {
                        case "insufficient_markers": return "Too few registered markers in view";
                        case "marker_geometry": return "Need a wider visible marker layout";
                        case "solver_failed": return "Position calculation unavailable";
                        case "pose_quality": return "Position uncertain. Guide paused";
                        case "target_outside": return "Target outside camera view";
                        default: return "Position unavailable";
                    }
                default: return "Position data unavailable";
            }
        }

        public string Status(double now) => !Finite(now) || now < receivedAt ? "INVALID OBSERVATION"
            : (status == "POSE READY" || status == "NO POSE") && now > expiresAt ? "STALE" : status;
        public string Detail(double now) => Status(now) == "STALE" ? "Markers ? | No fresh observation" : detail;
        private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
    }

    public sealed class DisplayCorrespondenceStore
    {
        private readonly DisplayCollectionConfig config;
        private readonly HashSet<string> saved = new HashSet<string>();
        public int Count { get; private set; }

        public DisplayCorrespondenceStore(DisplayCollectionConfig config)
        {
            DisplayCorrespondenceRules.ValidateConfig(config);
            this.config = config;
        }

        public string Save(DisplayCorrespondenceCandidate candidate, string json)
        {
            if (candidate?.observation == null || candidate.observation.session_id != config.session_id
                || (candidate.eye != "left" && candidate.eye != "right" && candidate.eye != "both"))
                throw new ArgumentException("Invalid candidate");
            bool pair = candidate.eye == "both";
            if (pair && (candidate.schema_version != "beast_display_correspondence_pair_v2"
                || !candidate.binocular_confirmed_by_user)) throw new ArgumentException("Invalid pair");
            var stability = candidate.stability;
            if (stability == null || stability.distinct_frames < 3 || stability.distinct_frames > 256
                || stability.first_frame_id <= 0 || stability.first_frame_id >= stability.last_frame_id
                || stability.last_frame_id != candidate.observation.frame_id
                || stability.distinct_frames > stability.last_frame_id - stability.first_frame_id + 1
                || !(stability.span_ms >= 180 && stability.span_ms <= 600.001)
                || !(stability.max_target_delta_mm >= 0 && stability.max_target_delta_mm <= 2))
                throw new ArgumentException("HOLD STILL");
            string[] eyes = pair ? new[] { "left", "right" } : new[] { candidate.eye };
            foreach (string eye in eyes)
                if (saved.Contains(eye + ":" + candidate.observation.frame_id))
                    throw new InvalidOperationException("Duplicate eye/frame");
            string path = Path.Combine(config.directory, "point-" + (Count + 1).ToString("D3") + ".json");
            string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try {
                using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write))
                using (var writer = new StreamWriter(stream)) writer.Write(json);
                File.Move(temporary, path);
            } finally {
                if (File.Exists(temporary)) File.Delete(temporary);
            }
            foreach (string eye in eyes) saved.Add(eye + ":" + candidate.observation.frame_id);
            Count++;
            return path;
        }
    }

    [Serializable]
    public sealed class DisplayPairStability
    {
        public int distinct_frames;
        public long first_frame_id, last_frame_id;
        public double span_ms, max_target_delta_mm;
    }
}
