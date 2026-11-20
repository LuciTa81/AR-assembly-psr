using System;
using System.Globalization;

namespace ARAssembly
{
    [Serializable]
    public sealed class SpatialPreviewConfig
    {
        public string schema_version, session_id, state_url, display_profile_id;
        public string camera_profile_id, workspace_profile_id, camera_profile_sha256, workspace_profile_sha256;
        public double duration_seconds = -1;

        public SpatialPreviewConfig ValidatedCopy()
        {
            Uri uri;
            if (schema_version != "beast_spatial_preview_config_v1"
                || string.IsNullOrWhiteSpace(session_id) || string.IsNullOrWhiteSpace(display_profile_id)
                || string.IsNullOrWhiteSpace(camera_profile_id) || string.IsNullOrWhiteSpace(workspace_profile_id)
                || !Hash(camera_profile_sha256) || !Hash(workspace_profile_sha256)
                || double.IsNaN(duration_seconds) || duration_seconds < 1 || duration_seconds > 300
                || !Uri.TryCreate(state_url, UriKind.Absolute, out uri)
                || uri.Scheme != "http" || uri.Host != "127.0.0.1" || uri.Port <= 0
                || state_url != "http://127.0.0.1:" + uri.Port + "/state.json")
                throw new ArgumentException("Invalid local synthetic preview config");
            return (SpatialPreviewConfig)MemberwiseClone();
        }

        private static bool Hash(string value)
        {
            if (value == null || value.Length != 64) return false;
            foreach (char c in value)
                if (!(c >= '0' && c <= '9' || c >= 'a' && c <= 'f')) return false;
            return true;
        }
    }

    public sealed class SbsGuidanceOptions
    {
        public bool Enabled { get; private set; }
        public bool ActionKorean { get; private set; }
        public string PreviewPath { get; private set; }
        public bool CandidatePresentation { get; private set; }
        public bool StageTargets { get; private set; }
        public bool StageContext { get; private set; }
        public string BoxOutlinePath { get; private set; }
        public bool TrialARight { get; private set; }
        public int ObservedCueDelayMs { get; private set; }
        public string StageDepthPath { get; private set; }
        public string CandidatePath { get; private set; }
        public string ObservationPath { get; private set; }
        public string StateUrl { get; private set; } = "http://127.0.0.1:8765/state.json";

        public static SbsGuidanceOptions Parse(string[] args)
        {
            var result = new SbsGuidanceOptions { Enabled = Array.IndexOf(args, "--sbs-guidance") >= 0 };
            if (Array.IndexOf(args, "--state-url") >= 0) {
                string url = RequiredValue(args, "--state-url");
                if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme != "http"
                    || uri.Host != "127.0.0.1" || uri.Port <= 0
                    || url != "http://127.0.0.1:" + uri.Port + "/state.json")
                    throw new ArgumentException("State endpoint must be a canonical local URL");
                result.StateUrl = url;
            }
            if (Array.IndexOf(args, "--candidate-presentation") >= 0) {
                RequiredValue(args, "--display-name");
                result.CandidatePath = RequiredValue(args, "--candidate-projection");
                result.ObservationPath = RequiredValue(args, "--display-observation-config");
                if (Array.IndexOf(args, "--spatial-preview-config") >= 0)
                    throw new ArgumentException("Candidate presentation cannot use synthetic preview");
                result.CandidatePresentation = result.Enabled = true;
            }
            result.StageTargets = Array.IndexOf(args, "--stage-targets") >= 0;
            if (result.StageTargets && !result.CandidatePresentation)
                throw new ArgumentException("Stage targets require candidate presentation");
            result.TrialARight = Array.IndexOf(args, "--trial-a-right") >= 0;
            if (result.TrialARight && !result.StageTargets)
                throw new ArgumentException("A offset trial requires stage targets");
            if (Array.IndexOf(args, "--stage-depth-config") >= 0) {
                if (!result.StageTargets) throw new ArgumentException("Stage depth records require stage targets");
                result.StageDepthPath = RequiredValue(args, "--stage-depth-config");
            }
            result.StageContext = Array.IndexOf(args, "--stage-context") >= 0;
            if (result.StageContext && (!result.StageTargets || result.TrialARight || result.StageDepthPath != null))
                throw new ArgumentException("Stage context requires shared-projection stage targets without legacy offsets");
            if (Array.IndexOf(args, "--box-outline-config") >= 0) {
                if (!result.StageContext) throw new ArgumentException("Box outline requires stage context");
                result.BoxOutlinePath = RequiredValue(args, "--box-outline-config");
            }
            int index = Array.IndexOf(args, "--spatial-preview-config");
            if (index >= 0) {
                if (index + 1 >= args.Length || string.IsNullOrWhiteSpace(args[index + 1]) || args[index + 1].StartsWith("--"))
                    throw new ArgumentException("Missing spatial preview config");
                if (Array.IndexOf(args, "--display-name") >= 0)
                    throw new ArgumentException("Synthetic preview is laptop-only");
                result.PreviewPath = args[index + 1];
                result.Enabled = true;
            }
            if (Array.IndexOf(args, "--observed-cue-delay-ms") >= 0) {
                if (!result.Enabled) throw new ArgumentException("Observed cue delay requires SBS guidance");
                if (!int.TryParse(RequiredValue(args, "--observed-cue-delay-ms"), NumberStyles.None,
                    CultureInfo.InvariantCulture, out int delayMs) || delayMs > 5000)
                    throw new ArgumentException("Observed cue delay must be 0..5000 milliseconds");
                result.ObservedCueDelayMs = delayMs;
            }
            result.ActionKorean = Array.IndexOf(args, "--action-korean") >= 0;
            if (result.ActionKorean && !result.Enabled)
                throw new ArgumentException("Korean action view requires SBS guidance");
            if (result.Enabled)
                foreach (string mode in new[] {"--test-ring", "--alignment-probe", "--stereo-alignment-probe"})
                    if (Array.IndexOf(args, mode) >= 0)
                        throw new ArgumentException("Choose one guidance/probe mode");
            return result;
        }

        private static string RequiredValue(string[] args, string key)
        {
            int index = Array.IndexOf(args, key);
            if (index < 0 || index + 1 >= args.Length || string.IsNullOrWhiteSpace(args[index + 1])
                || args[index + 1].StartsWith("-"))
                throw new ArgumentException("Missing " + key);
            return args[index + 1];
        }
    }
}
