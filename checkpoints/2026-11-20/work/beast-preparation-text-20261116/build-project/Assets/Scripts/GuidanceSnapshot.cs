using System;

namespace ARAssembly
{
    [Serializable]
    public sealed class AssemblyGuidance
    {
        public string schema_version, phase, reason, acknowledgement;
        public long acknowledgement_remaining_ms = -1;
        public string hold_progress;
        public long hold_remaining_ms = -1;
        public AssemblyGuidance Copy() => (AssemblyGuidance)MemberwiseClone();
    }

    [Serializable]
    public sealed class SpatialGuidance
    {
        public string schema_version, display_profile_id;
        public string camera_profile_id, workspace_profile_id, camera_profile_sha256, workspace_profile_sha256;
        public string calibration_status, coordinate_convention, channel_order, display_mode, target_id, reason;
        public bool display_alignment_verified, target_visible;
        public int eye_width, eye_height;
        public long pose_frame_id = -1, pose_timestamp_ms = -1, pose_age_ms = -1;
        public double[] left_pixel, right_pixel;
    }

    [Serializable]
    public sealed class GuidanceSnapshot
    {
        public string schema_version;
        public string session_id;
        public long frame_id;
        public long timestamp_ms;
        public long frame_age_ms = -1;
        public string system_status;
        public string marker_status;
        public string current_state;
        public string current_label;
        public string next_action;
        public string target;
        // Optional location evidence, validated separately from the assembly state.
        public SpatialGuidance spatial;
        public AssemblyGuidance guidance;

        public GuidanceSnapshot Copy()
        {
            var copy = (GuidanceSnapshot)MemberwiseClone();
            copy.guidance = guidance?.Copy();
            return copy;
        }
    }
}
