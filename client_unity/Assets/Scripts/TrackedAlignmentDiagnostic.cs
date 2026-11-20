using System;

namespace ARAssembly
{
    [Serializable]
    public sealed class TrackedAlignmentRecord
    {
        public string schema_version = "beast_tracked_alignment_diagnostic_v1";
        public bool candidate_only = true, calibration_valid = false, display_alignment_verified = false;
        public bool binocular_confirmed_by_user;
        public string rendered_view;
        public string setup_id, candidate_sha256;
        public string coordinate_convention = "eye_local_pixels_top_left";
        public string channel_order = "left_half_left_eye_right_half_right_eye";
        public int output_width = 3840, output_height = 1080;
        public DisplayObservation observation;
        public double[] left_base_px, right_base_px, left_offset_px, right_offset_px, left_final_px, right_final_px;
        public double request_started_seconds, response_received_seconds, rendered_seconds, saved_seconds;
        public double conservative_age_ms;
    }

    // Each row is a user-selected binocular alignment for one target, not an active calibration.
    public sealed class TargetDepthTrial
    {
        private readonly CandidateProjection projection;
        private readonly double[] depth = new double[3];
        private readonly double[,] offset = new double[3,4];

        public TargetDepthTrial(CandidateProjection projection, string hash, string target, TrackedAlignmentRecord[] rows)
        {
            if (projection == null || hash == null || hash.Length != 64 || (target != "C" && target != "D") || rows?.Length != 3)
                throw new ArgumentException("Three C or D probe records required, ordered near to far");
            this.projection = projection;
            for (int i=0; i<3; i++) {
                var r = rows[i];
                var o = r?.observation;
                if (o?.target_id != target || o.status != "tracking" || r.candidate_sha256 != hash
                    || (target == "C" && (string.IsNullOrWhiteSpace(r.setup_id) || r.setup_id != rows[0].setup_id))
                    || o.camera_profile_sha256 != projection.camera_profile_sha256
                    || o.workspace_profile_sha256 != projection.workspace_profile_sha256
                    || r.schema_version != "beast_tracked_alignment_diagnostic_v1" || r.rendered_view != "Both"
                    || !r.candidate_only || r.calibration_valid || r.display_alignment_verified || !r.binocular_confirmed_by_user
                    || r.coordinate_convention != projection.coordinate_convention || r.channel_order != projection.channel_order
                    || r.output_width != 3840 || r.output_height != 1080 || !(r.conservative_age_ms >= 0 && r.conservative_age_ms <= 150)
                    || !projection.TryProject(o.camera_xyz_mm, out var l, out var rr))
                    throw new ArgumentException("Observation or projection binding mismatch: " + target);
                depth[i] = o.camera_xyz_mm[2];
                if (i>0 && depth[i]<=depth[i-1]) throw new ArgumentException("Depths must increase");
                CopyEye(i, 0, l, r.left_offset_px, r.left_final_px);
                CopyEye(i, 2, rr, r.right_offset_px, r.right_final_px);
            }
        }

        private void CopyEye(int row, int col, double[] basis, double[] delta, double[] final)
        {
            if (delta?.Length != 2 || final?.Length != 2) throw new ArgumentException("Missing eye pixels");
            for (int k=0;k<2;k++) {
                if (!(Math.Abs(basis[k]+delta[k]-final[k]) <= .01) || !Inside(final[k], k))
                    throw new ArgumentException("Inconsistent eye pixels");
                offset[row,col+k]=delta[k];
            }
        }

        private static bool Inside(double x, int axis) => x >= 24 && x <= (axis == 0 ? 1896 : 1056);

        public bool ContainsDepth(double z) => depth[0] <= z && z <= depth[2];

        public bool TryProject(double[] xyz, out double[] left, out double[] right)
        {
            left = right = null;
            if (xyz?.Length != 3 || !ContainsDepth(xyz[2])
                || !projection.TryProject(xyz, out var l, out var r)) return false;
            int i = xyz[2] <= depth[1] ? 0 : 1;
            double t = (1/xyz[2] - 1/depth[i]) / (1/depth[i+1] - 1/depth[i]);
            for (int k=0;k<2;k++) {
                l[k] += (1-t)*offset[i,k] + t*offset[i+1,k];
                r[k] += (1-t)*offset[i,k+2] + t*offset[i+1,k+2];
                if (!Inside(l[k],k) || !Inside(r[k],k)) return false;
            }
            left=l; right=r; return true;
        }
    }

    // Diagnostic residuals only. This schema is deliberately not an active calibration.
    public sealed class TrackedAlignmentDiagnostic
    {
        private readonly DisplayCollectionConfig config;
        private readonly CandidateProjection projection;
        private readonly string candidateHash;
        private readonly double[] leftOffset = new double[2], rightOffset = new double[2];
        private bool leftChecked, rightChecked;
        private TrackedAlignmentRecord rendered;
        public string Status { get; private set; } = "ALIGN EYES";

        public TrackedAlignmentDiagnostic(DisplayCollectionConfig config, CandidateProjection projection, string candidateHash)
        {
            DisplayCorrespondenceRules.ValidateConfig(config);
            if (string.IsNullOrWhiteSpace(config.setup_id) || config.setup_id.Length > 128)
                throw new ArgumentException("SETUP REQUIRED");
            if (candidateHash == null || candidateHash.Length != 64
                || Array.Exists(candidateHash.ToCharArray(), c => !"0123456789abcdef".Contains(c.ToString())))
                throw new ArgumentException("Candidate hash required");
            projection.Validate(config);
            this.config = config; this.projection = projection; this.candidateHash = candidateHash;
        }

        public void StartDLeftUpTrial()
        {
            if (config.target_id != "D") throw new InvalidOperationException("D target required for left/up trial");
            Move(StereoProbeView.Left, -8, -4);
            Move(StereoProbeView.Right, -8, -4);
        }

        public void Move(StereoProbeView eye, double dx, double dy)
        {
            if (!Finite(dx) || !Finite(dy)) throw new ArgumentException("Invalid offset");
            if (eye != StereoProbeView.Left && eye != StereoProbeView.Right) return;
            var offset = eye == StereoProbeView.Left ? leftOffset : rightOffset;
            if (!Finite(offset[0] + dx) || !Finite(offset[1] + dy)) throw new ArgumentException("Invalid offset");
            offset[0] += dx; offset[1] += dy;
            if (eye == StereoProbeView.Left) leftChecked = false; else rightChecked = false;
            rendered = null; Status = "ALIGN EYES";
        }

        public void Reset(StereoProbeView eye)
        {
            if (eye != StereoProbeView.Left && eye != StereoProbeView.Right) return;
            var offset = eye == StereoProbeView.Left ? leftOffset : rightOffset;
            Move(eye, -offset[0], -offset[1]);
        }

        public void Invalidate() { rendered = null; }

        public bool TryRender(DisplayObservation observation, double started, double received, double now,
            out double[] left, out double[] right, StereoProbeView view = StereoProbeView.Both)
        {
            rendered = null; left = right = null;
            try {
                if (view == StereoProbeView.Channels) return false;
                double age = DisplayCorrespondenceRules.ValidateObservation(config, observation, started, received);
                if (!Finite(now) || now < received || age + (now - received) * 1000 > 150
                    || !projection.TryProject(observation.camera_xyz_mm, out var l, out var r)) return false;
                var lf = new[]{l[0] + leftOffset[0], l[1] + leftOffset[1]};
                var rf = new[]{r[0] + rightOffset[0], r[1] + rightOffset[1]};
                if (!Inside(lf) || !Inside(rf)) return false;
                rendered = new TrackedAlignmentRecord {
                    observation = observation.Copy(), setup_id = config.setup_id, candidate_sha256 = candidateHash,
                    rendered_view = view.ToString(),
                    left_base_px = l, right_base_px = r, left_offset_px = (double[])leftOffset.Clone(),
                    right_offset_px = (double[])rightOffset.Clone(), left_final_px = lf, right_final_px = rf,
                    request_started_seconds = started, response_received_seconds = received, rendered_seconds = now,
                    conservative_age_ms = age
                };
                left = (double[])lf.Clone(); right = (double[])rf.Clone();
                return true;
            } catch (ArgumentException) { return false; }
        }

        public void ConfirmEye(StereoProbeView eye)
        {
            if (rendered == null) throw new InvalidOperationException("WAIT FOR TRACKING");
            if (eye == StereoProbeView.Left) { leftChecked = true; Status = "LEFT CHECKED"; }
            else if (eye == StereoProbeView.Right) { rightChecked = true; Status = "RIGHT CHECKED"; }
        }

        public TrackedAlignmentRecord CreateRecord(double now)
        {
            if (rendered == null) throw new InvalidOperationException("WAIT FOR REPAINT");
            if (rendered.rendered_view != "Both") throw new InvalidOperationException("SHOW BOTH EYES");
            if (!leftChecked || !rightChecked) throw new InvalidOperationException("CHECK BOTH EYES");
            double age = rendered.conservative_age_ms + (now - rendered.response_received_seconds) * 1000;
            if (!Finite(now) || now < rendered.rendered_seconds || age > 150)
                throw new InvalidOperationException("STALE");
            return new TrackedAlignmentRecord {
                observation = rendered.observation.Copy(), setup_id = rendered.setup_id, candidate_sha256 = candidateHash,
                binocular_confirmed_by_user = true,
                rendered_view = rendered.rendered_view,
                left_base_px = (double[])rendered.left_base_px.Clone(), right_base_px = (double[])rendered.right_base_px.Clone(),
                left_offset_px = (double[])rendered.left_offset_px.Clone(), right_offset_px = (double[])rendered.right_offset_px.Clone(),
                left_final_px = (double[])rendered.left_final_px.Clone(), right_final_px = (double[])rendered.right_final_px.Clone(),
                request_started_seconds = rendered.request_started_seconds, response_received_seconds = rendered.response_received_seconds,
                rendered_seconds = rendered.rendered_seconds, saved_seconds = now, conservative_age_ms = age
            };
        }

        public void MarkSaved() { Status = "PAIR SAVED"; }
        private static bool Inside(double[] p) => Finite(p[0]) && Finite(p[1])
            && p[0] >= 24 && p[0] <= 1896 && p[1] >= 24 && p[1] <= 1056;
        private static bool Finite(double v) => !double.IsNaN(v) && !double.IsInfinity(v);
    }
}
