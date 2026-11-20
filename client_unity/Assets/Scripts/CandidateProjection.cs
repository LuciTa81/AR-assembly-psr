using System;

namespace ARAssembly
{
    [Serializable]
    public sealed class CandidateProjection
    {
        public string schema_version, camera_profile_id, workspace_profile_id;
        public string camera_profile_sha256, workspace_profile_sha256;
        public string coordinate_convention, display_mode, channel_order;
        public bool candidate_only, calibration_valid, display_alignment_verified;
        public int eye_width, eye_height;
        public double[] left_projection, right_projection;

        private double[] leftMatrix, rightMatrix;
        private TargetDepthTrial cDepth, dDepth;
        public const double PollIntervalSeconds = 1.0 / 30.0;
        public const string LidPerimeter = "ABDCA";
        public const int TrialARightPx = 17;

        public bool TryProjectStageContext(DisplayObservationFeedback feedback, GuidanceState state,
            string sessionId, double now, out double[][] left, out double[][] right)
        {
            left = right = null;
            if (cDepth != null || dDepth != null
                || PresentationStatus(feedback, state, sessionId, now, out _, out _, stageTargets: true) != "VISIBLE")
                return false;
            return TryProjectCorners(feedback, now, out left, out right);
        }

        public bool TryProjectCorners(DisplayObservationFeedback feedback, double now,
            out double[][] left, out double[][] right)
        {
            left = right = null;
            if (feedback == null || !feedback.TryGetCameraTargets(now, out var points)) return false;
            var l = new double[4][]; var r = new double[4][];
            for (int i = 0; i < 4; i++)
                if (!TryProject(points[i], out l[i], out r[i])) return false;
            left = l; right = r;
            return true;
        }
        public static bool IsPresentationOutput(int width, int height, int physicalWidth, int physicalHeight,
            string displayName, bool fullScreen)
        {
            return fullScreen && width == 3840 && height == 1080 && physicalWidth == width
                && physicalHeight == height && displayName != null
                && displayName.IndexOf("VITURE Beast", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        public bool TryProjectFresh(DisplayObservationFeedback feedback, double now,
            out double[] left, out double[] right)
        {
            left = right = null;
            return feedback != null && feedback.TryGetCameraPoint(now, out var xyz)
                && TryProject(xyz, out left, out right);
        }

        public bool TryProjectPresentation(DisplayObservationFeedback feedback, GuidanceState state,
            string sessionId, double now, out double[] left, out double[] right)
        {
            return PresentationStatus(feedback, state, sessionId, now, out left, out right) == "VISIBLE";
        }

        public static string StageTarget(GuidanceSnapshot frame)
        {
            var g = frame?.guidance;
            if (g == null) return null;
            bool toolWait = g.phase == "PAUSED" && (g.reason == "tool_not_visible"
                || g.reason == "tool_position_unknown" || g.reason == "invalid_observation" || g.reason == "observation_gap");
            if (!toolWait && g.phase != "GUIDING" && g.phase != "OBSERVING" && g.phase != "OBSERVED") return null;
            if (frame.current_state == "S2" && frame.target == "screw_a") return "A";
            if (frame.current_state == "S3" && frame.target == "screw_b") return "B";
            if (frame.current_state == "S4" && frame.target == "screw_c") return "C";
            if (frame.current_state == "S5" && frame.target == "screw_d") return "D";
            return null;
        }

        public void BindStageDepthRecords(string hash, TrackedAlignmentRecord[] c, TrackedAlignmentRecord[] d)
        {
            var first = new TargetDepthTrial(this, hash, "C", c);
            var second = new TargetDepthTrial(this, hash, "D", d);
            cDepth = first; dDepth = second;
        }

        internal void BindReviewedStageDepths(CandidateProjection source, string sourceHash,
            TrackedAlignmentRecord[] c, TrackedAlignmentRecord[] d)
        {
            Require(source != null && leftMatrix != null && source.leftMatrix != null
                && workspace_profile_sha256 != source.workspace_profile_sha256
                && camera_profile_id == source.camera_profile_id && camera_profile_sha256 == source.camera_profile_sha256,
                "Depth transfer requires validated compatible candidates");
            for (int i=0; i<12; i++)
                Require(leftMatrix[i] == source.leftMatrix[i] && rightMatrix[i] == source.rightMatrix[i],
                    "Depth transfer cannot change eye projections");
            var first = new TargetDepthTrial(source, sourceHash, "C", c);
            var second = new TargetDepthTrial(source, sourceHash, "D", d);
            cDepth = first; dDepth = second;
        }

        public string PresentationStatus(DisplayObservationFeedback feedback, GuidanceState state,
            string sessionId, double now, out double[] left, out double[] right, bool stageTargets = false,
            bool trialARight = false)
        {
            left = right = null;
            if (state?.LastSnapshot == null) return "STATE WAITING";
            if (string.IsNullOrEmpty(sessionId) || state.LastSnapshot.session_id != sessionId)
                return "SESSION MISMATCH";
            string status = state.Status(now);
            if (status != "LIVE" && status != "PAUSED" && status != "AWAITING_CONFIRMATION") return "STATE " + status;
            if (stageTargets) {
                string target = StageTarget(state.LastSnapshot);
                if (target == null || (status != "LIVE" && status != "PAUSED")) return "NO STAGE TARGET";
                if (feedback == null) return "POSE WAITING";
                if (!feedback.TryGetCameraTargets(now, out var corners)) {
                    string pose = feedback.Status(now);
                    return pose == "POSE READY" ? "STAGE TARGET UNAVAILABLE" : "POSE " + pose;
                }
                var corner = corners[target[0] - 'A'];
                var depth = target == "C" ? cDepth : target == "D" ? dDepth : null;
                if (depth != null) {
                    if (!depth.ContainsDepth(corner[2])) return "OUTSIDE TARGET DEPTH";
                    return depth.TryProject(corner, out left, out right) ? "VISIBLE" : "OUTSIDE EYE VIEW";
                }
                if (!TryProject(corner, out left, out right)) return "OUTSIDE EYE VIEW";
                if (trialARight && target == "A") {
                    // A-only display trial: translate both eye-local pixels equally, never the world point.
                    left[0] += TrialARightPx; right[0] += TrialARightPx;
                    if (left[0] >= eye_width || right[0] >= eye_width) {
                        left = right = null; return "OUTSIDE EYE VIEW";
                    }
                }
                return "VISIBLE";
            }
            if (feedback == null) return "POSE WAITING";
            if (!feedback.TryGetCameraPoint(now, out var xyz)) return "POSE " + feedback.Status(now);
            return TryProject(xyz, out left, out right) ? "VISIBLE" : "OUTSIDE EYE VIEW";
        }

        public void ValidateOutput(int width, int height, double seconds, bool trackedDiagnostic = false)
        {
            Require(width == 3840 && height == 1080 && Finite(seconds) && seconds >= 1
                && seconds <= (trackedDiagnostic ? 600 : 30),
                "Candidate probe requires 3840x1080 and its mode-specific time limit");
        }

        public void Validate(DisplayCollectionConfig config)
        {
            leftMatrix = rightMatrix = null;
            cDepth = dDepth = null;
            DisplayCorrespondenceRules.ValidateConfig(config);
            Require(schema_version == "beast_candidate_projection_probe_v1" && candidate_only
                && !calibration_valid && !display_alignment_verified, "Expected unverified candidate probe");
            Require(camera_profile_id == config.camera_profile_id && workspace_profile_id == config.workspace_profile_id
                && camera_profile_sha256 == config.camera_profile_sha256
                && workspace_profile_sha256 == config.workspace_profile_sha256, "Candidate profile mismatch");
            Require(eye_width == 1920 && eye_height == 1080 && display_mode == "full_sbs"
                && coordinate_convention == "eye_local_pixels_top_left"
                && channel_order == "left_half_left_eye_right_half_right_eye", "Candidate display mismatch");
            ValidateMatrix(left_projection); ValidateMatrix(right_projection);
            leftMatrix = (double[])left_projection.Clone();
            rightMatrix = (double[])right_projection.Clone();
        }

        public bool TryProject(double[] xyz, out double[] left, out double[] right)
        {
            left = right = null;
            if (leftMatrix == null || rightMatrix == null || xyz == null || xyz.Length != 3
                || !Finite(xyz[0]) || !Finite(xyz[1]) || !Finite(xyz[2]) || xyz[2] <= 0) return false;
            var l = Project(leftMatrix, xyz); var r = Project(rightMatrix, xyz);
            if (l == null || r == null) return false;
            left = l; right = r;
            return true;
        }

        private static double[] Project(double[] m, double[] xyz)
        {
            double x=m[0]*xyz[0]+m[1]*xyz[1]+m[2]*xyz[2]+m[3];
            double y=m[4]*xyz[0]+m[5]*xyz[1]+m[6]*xyz[2]+m[7];
            double z=m[8]*xyz[0]+m[9]*xyz[1]+m[10]*xyz[2]+m[11];
            if (!Finite(x) || !Finite(y) || !Finite(z) || z <= 1e-9) return null;
            x /= z; y /= z;
            return Finite(x) && Finite(y) && x >= 0 && x < 1920 && y >= 0 && y < 1080
                ? new[]{x,y} : null;
        }

        private static void ValidateMatrix(double[] m)
        {
            Require(m != null && m.Length == 12, "Expected row-major 3x4 projection");
            foreach (double v in m) Require(Finite(v), "Invalid projection value");
            double det=m[0]*(m[5]*m[10]-m[6]*m[9])-m[1]*(m[4]*m[10]-m[6]*m[8])
                +m[2]*(m[4]*m[9]-m[5]*m[8]);
            Require(Finite(det) && Math.Abs(det)>1e-12, "Singular projection");
        }
        private static bool Finite(double v) => !double.IsNaN(v) && !double.IsInfinity(v);
        private static void Require(bool valid, string reason) { if (!valid) throw new ArgumentException(reason); }
    }
}
