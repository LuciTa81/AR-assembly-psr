using System;

namespace ARAssembly
{
    public struct EyePixelPair
    {
        public double LeftX, LeftY, RightX, RightY;
    }

    public sealed class SpatialGuidanceState
    {
        private const double PoseBudgetMs = 150;
        private readonly SpatialPreviewConfig preview;
        private EyePixelPair pixels;
        private long latestFrame = -1, latestTimestamp = -1;
        private string latestTarget, fault = "WAITING_POSE";
        private double expiresAt, receivedAt;
        private string displayName;
        private int width, height;
        private bool outputChanged;

        public SpatialGuidanceState(SpatialPreviewConfig config = null)
        {
            preview = config?.ValidatedCopy();
        }

        public void ObserveOutput(string name, int outputWidth, int outputHeight, bool windowed)
        {
            if (preview == null || outputChanged) return;
            if (string.IsNullOrWhiteSpace(name) || name.IndexOf("VITURE", StringComparison.OrdinalIgnoreCase) >= 0
                || outputWidth <= 0 || outputHeight <= 0 || !windowed) { outputChanged = true; return; }
            if (displayName == null) { displayName = name; width = outputWidth; height = outputHeight; }
            else if (name != displayName || outputWidth != width || outputHeight != height) outputChanged = true;
        }

        public void Invalidate(string reason) { fault = reason; }

        public void Apply(GuidanceSnapshot frame, double started, double finished)
        {
            if (preview == null) return;
            if (!Finite(started) || !Finite(finished) || started < 0 || finished < started || finished < receivedAt) {
                Invalidate("INVALID_SPATIAL"); return;
            }
            receivedAt = finished;
            var p = frame.spatial;
            if (p == null) { Invalidate("NO_POSE"); return; }
            if (frame.session_id != preview.session_id || p.display_profile_id != preview.display_profile_id
                || p.camera_profile_id != preview.camera_profile_id || p.workspace_profile_id != preview.workspace_profile_id
                || p.camera_profile_sha256 != preview.camera_profile_sha256 || p.workspace_profile_sha256 != preview.workspace_profile_sha256) {
                Invalidate("PROFILE_MISMATCH"); return;
            }
            if (p.pose_frame_id < 1 || p.pose_frame_id < latestFrame) {
                Invalidate("INVALID_SPATIAL"); return;
            }
            bool duplicate = p.pose_frame_id == latestFrame;
            bool validTimestamp = p.pose_timestamp_ms > 0 && p.pose_timestamp_ms <= frame.timestamp_ms
                && (duplicate ? p.pose_timestamp_ms == latestTimestamp : p.pose_timestamp_ms > latestTimestamp);
            bool sameTarget = !duplicate || p.target_id == latestTarget;
            if (!duplicate) {
                // Consume a bound observation's ID even when its other fields are rejected.
                latestFrame = p.pose_frame_id; latestTarget = p.target_id;
                if (validTimestamp) latestTimestamp = p.pose_timestamp_ms;
            }
            if (!validTimestamp || !sameTarget
                || p.schema_version != "beast_spatial_guidance_v1" || p.calibration_status != "synthetic"
                || p.display_alignment_verified || p.coordinate_convention != "eye_local_pixels_top_left"
                || p.channel_order != "left_half_left_eye_right_half_right_eye" || p.display_mode != "full_sbs"
                || p.eye_width != 1920 || p.eye_height != 1080
                || p.pose_age_ms < 0 || p.reason == null) {
                Invalidate("INVALID_SPATIAL"); return;
            }
            double age = p.pose_age_ms + (finished - started) * 1000;
            double deadline = finished + (PoseBudgetMs - age) / 1000;
            if (duplicate) expiresAt = Math.Min(expiresAt, deadline);
            else expiresAt = deadline;
            if (age >= PoseBudgetMs) { Invalidate("STALE_POSE"); return; }
            if (frame.marker_status != "OK") { Invalidate("TRACKING_LOST"); return; }
            if (!p.target_visible || p.reason != "") { Invalidate("NO_POSE"); return; }
            if (!TargetMatches(frame, p.target_id)) { Invalidate("NO_TARGET"); return; }
            if (!Pixel(p.left_pixel) || !Pixel(p.right_pixel)) { Invalidate("INVALID_SPATIAL"); return; }
            if (duplicate) return;
            pixels = new EyePixelPair { LeftX = p.left_pixel[0], LeftY = p.left_pixel[1],
                RightX = p.right_pixel[0], RightY = p.right_pixel[1] };
            fault = null;
        }

        public string Status(double now)
        {
            if (preview == null) return "NOT_CALIBRATED";
            if (outputChanged) return "DISPLAY_CHANGED";
            if (displayName == null) return "WAITING_DISPLAY";
            if (!Finite(now) || now < receivedAt) return "INVALID_SPATIAL";
            if (fault != null) return fault;
            return now >= expiresAt ? "STALE_POSE" : "SYNTHETIC_PREVIEW";
        }

        public bool TryGetPixels(double now, out EyePixelPair value)
        {
            bool visible = Status(now) == "SYNTHETIC_PREVIEW";
            value = visible ? pixels : default(EyePixelPair);
            return visible;
        }

        private static bool TargetMatches(GuidanceSnapshot frame, string id)
        {
            int index = frame.current_state == "S2" ? 0 : frame.current_state == "S3" ? 1
                : frame.current_state == "S4" ? 2 : frame.current_state == "S5" ? 3 : -1;
            return index >= 0 && id == "ABCD"[index].ToString() && frame.target == "screw_" + "abcd"[index];
        }
        private static bool Pixel(double[] point) => point != null && point.Length == 2
            && Finite(point[0]) && Finite(point[1]) && point[0] >= 24 && point[0] <= 1920 - 24
            && point[1] >= 24 && point[1] <= 1080 - 24;
        private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
    }
}
