using System;

namespace ARAssembly
{
    public struct GuidancePresentation
    {
        public string Status, Instruction, Acknowledgement, StepTitle, Cue, HoldProgress;
        public bool ShowTarget, IsReference;
    }

    public sealed class GuidanceState
    {
        public GuidanceSnapshot LastSnapshot { get; private set; }
        public SpatialGuidanceState Spatial { get; }
        private const double TestDisplayBudgetMs = 500;
        private double expiresAt;
        private string fault = "WAITING";
        private string acknowledgementKey;
        private double acknowledgementExpiresAt;
        private double holdExpiresAt;

        public GuidanceState(SpatialPreviewConfig preview = null)
        {
            Spatial = new SpatialGuidanceState(preview);
        }

        public bool Apply(GuidanceSnapshot snapshot, double requestStarted, double receivedAt)
        {
            if (snapshot != null && snapshot.system_status == "STARTING")
            {
                fault = "WAITING";
                Spatial.Invalidate("WAITING_POSE");
                return false;
            }
            if (!Valid(snapshot) || !Finite(requestStarted) || !Finite(receivedAt)
                || receivedAt < requestStarted)
            {
                InvalidResponse();
                return false;
            }
            // Clocks are not shared: use server age plus a conservative full RTT.
            double ageMs = snapshot.frame_age_ms + (receivedAt - requestStarted) * 1000;
            if (ageMs >= TestDisplayBudgetMs)
            {
                fault = "STALE";
                Spatial.Invalidate("STALE_STATE");
                return false;
            }
            double deadline = receivedAt + (TestDisplayBudgetMs - ageMs) / 1000;
            if (LastSnapshot != null && snapshot.session_id == LastSnapshot.session_id)
            {
                if (snapshot.frame_id < LastSnapshot.frame_id
                    || snapshot.timestamp_ms < LastSnapshot.timestamp_ms)
                {
                    InvalidResponse();
                    return false;
                }
                if (snapshot.frame_id == LastSnapshot.frame_id)
                {
                    expiresAt = Math.Min(expiresAt, deadline);
                    if (!SameGuidance(snapshot.guidance, LastSnapshot.guidance)
                        || ((snapshot.guidance != null || LastSnapshot.guidance != null)
                            && (snapshot.current_state != LastSnapshot.current_state || snapshot.target != LastSnapshot.target
                                || snapshot.next_action != LastSnapshot.next_action))) {
                        InvalidResponse();
                        return false;
                    }
                    UpdateAcknowledgement(snapshot, receivedAt, ageMs);
                    holdExpiresAt = Math.Min(holdExpiresAt,
                        receivedAt + Math.Max(0, (snapshot.guidance?.hold_remaining_ms ?? 0) - ageMs) / 1000);
                    if (snapshot.current_state != LastSnapshot.current_state || snapshot.target != LastSnapshot.target
                        || snapshot.marker_status != LastSnapshot.marker_status
                        || snapshot.next_action != LastSnapshot.next_action || snapshot.current_label != LastSnapshot.current_label)
                        Spatial.Invalidate("INVALID_SPATIAL");
                    else Spatial.Apply(snapshot, requestStarted, receivedAt);
                    return false;
                }
            }
            LastSnapshot = snapshot.Copy();
            Spatial.Apply(snapshot, requestStarted, receivedAt);
            UpdateAcknowledgement(snapshot, receivedAt, ageMs);
            holdExpiresAt = receivedAt + Math.Max(0, (snapshot.guidance?.hold_remaining_ms ?? 0) - ageMs) / 1000;
            expiresAt = deadline;
            fault = null;
            return true;
        }

        public void Disconnect() { fault = "DISCONNECTED"; Spatial.Invalidate("DISCONNECTED"); }
        public void InvalidResponse() { fault = "INVALID_DATA"; Spatial.Invalidate("INVALID_SPATIAL"); }

        public string Status(double now)
        {
            if (!Finite(now)) return "INVALID_DATA";
            if (fault != null) return fault;
            if (now >= expiresAt) return "STALE";
            if (LastSnapshot.current_state == "S6" && LastSnapshot.guidance?.reason == "operator_confirmation"
                && (LastSnapshot.guidance.phase == "AWAITING_CONFIRMATION" || LastSnapshot.guidance.phase == "COMPLETED"))
                return LastSnapshot.guidance.phase;
            if (LastSnapshot.marker_status != "OK") return "TRACKING_LOST";
            if (LastSnapshot.guidance?.phase == "PAUSED") return "PAUSED";
            if (LastSnapshot.guidance?.phase == "COMPLETED") return "COMPLETED";
            return LastSnapshot.current_state == "S6" ? "AWAITING_CONFIRMATION" : "LIVE";
        }

        private void UpdateAcknowledgement(GuidanceSnapshot snapshot, double receivedAt, double ageMs)
        {
            var g = snapshot.guidance;
            if (g == null || string.IsNullOrEmpty(g.acknowledgement)) {
                acknowledgementExpiresAt = 0;
                return;
            }
            string key = snapshot.session_id + "|" + snapshot.current_state + "|" + g.acknowledgement;
            double deadline = receivedAt + Math.Max(0, g.acknowledgement_remaining_ms - ageMs) / 1000;
            acknowledgementExpiresAt = key == acknowledgementKey ? Math.Min(acknowledgementExpiresAt, deadline) : deadline;
            acknowledgementKey = key;
        }

        public GuidancePresentation Presentation(double now, bool spatialRequired = false, bool keepOperatorActionOnLoss = false)
        {
            string parent = Status(now);
            string status = parent;
            string instruction = HoldMessage(parent);
            bool active = parent == "LIVE" || parent == "AWAITING_CONFIRMATION" || parent == "COMPLETED";
            bool screw = LastSnapshot != null && LastSnapshot.current_state[1] >= '2' && LastSnapshot.current_state[1] <= '5';
            bool showTarget = parent == "LIVE" && screw;
            if (active) {
                status = LastSnapshot.guidance?.phase ?? parent;
                instruction = LastSnapshot.next_action;
            } else if (parent == "PAUSED") instruction = LastSnapshot.next_action;
            else if (keepOperatorActionOnLoss && parent == "TRACKING_LOST"
                && LastSnapshot.guidance?.reason == "operator_confirmation") instruction = LastSnapshot.next_action;
            if (spatialRequired && screw && (active || parent == "PAUSED")) {
                bool hasPose = Spatial.TryGetPixels(now, out _);
                showTarget = showTarget && hasPose;
                if (!hasPose) { status = Spatial.Status(now); instruction = HoldMessage(status); }
            }
            bool displayActive = status == "LIVE" || status == "GUIDING" || status == "OBSERVING"
                || status == "OBSERVED" || status == "AWAITING_CONFIRMATION";
            string title = LastSnapshot?.current_label ?? "Assembly guide";
            string letter = screw ? "ABCD"[LastSnapshot.current_state[1] - '2'].ToString() : "";
            if (screw) title = "SCREW " + letter + "  |  " + (LastSnapshot.current_state[1] - '1') + " / 4";
            string cue = "PAUSED";
            if (status == "WAITING") cue = "WAITING";
            else if (status == "GUIDING" || status == "LIVE") cue = screw ? "WORK AT " + letter : "READY";
            else if (status == "OBSERVING") cue = screw ? "HOLD AT " + letter : "CHECKING";
            else if (status == "OBSERVED") cue = "MOVE CLEAR";
            else if (status == "AWAITING_CONFIRMATION") cue = "FINAL CHECK";
            else if (status == "COMPLETED") cue = "CONFIRMED";
            string progress = "none";
            if (screw && (status == "PAUSED" || status == "TRACKING_LOST" || status == "GUIDING")) {
                var g = LastSnapshot.guidance;
                if (g?.hold_progress == "checkpoint") {
                    progress = "checkpoint";
                    cue = "HOLD KEPT";
                } else if (g?.hold_progress == "retained" && now < holdExpiresAt) {
                    progress = "retained";
                    cue = "PAUSED - KEPT";
                } else if (g?.hold_progress == "recheck") {
                    progress = "recheck";
                    cue = "RECHECK " + letter;
                }
            }
            return new GuidancePresentation {
                Status = status, Instruction = instruction, ShowTarget = showTarget,
                StepTitle = title, Cue = cue, HoldProgress = progress,
                IsReference = !active,
                Acknowledgement = displayActive && now < acknowledgementExpiresAt
                    ? LastSnapshot?.guidance?.acknowledgement ?? "" : ""
            };
        }

        private static string HoldMessage(string status)
        {
            switch (status) {
                case "TRACKING_LOST": case "NO_POSE": return "Bring the workspace markers into view";
                case "DISCONNECTED": return "Connection lost. Guidance paused.";
                case "STALE": case "STALE_POSE": return "Updates paused. Guidance paused.";
                case "INVALID_DATA": case "INVALID_SPATIAL": case "PROFILE_MISMATCH":
                    return "Invalid guidance data. Guidance paused.";
                case "NOT_CALIBRATED": return "Display calibration required";
                case "DISPLAY_CHANGED": return "Display changed. Restart guidance.";
                default: return "Waiting for the local vision server";
            }
        }

        private static bool SameGuidance(AssemblyGuidance a, AssemblyGuidance b)
        {
            if (a == null || b == null) return a == b;
            return a.schema_version == b.schema_version && a.phase == b.phase
                && a.reason == b.reason && a.acknowledgement == b.acknowledgement
                && a.hold_progress == b.hold_progress && a.hold_remaining_ms == b.hold_remaining_ms;
        }

        private static bool ValidGuidance(GuidanceSnapshot frame)
        {
            var g = frame.guidance;
            if (g == null) return true;
            if (g.schema_version != "assembly_guidance_v1" || g.reason == null || g.acknowledgement == null
                || g.acknowledgement_remaining_ms < 0 || g.acknowledgement_remaining_ms > 3000
                || g.acknowledgement.Length > 160 || frame.next_action.Length > 256
                || frame.current_label.Length > 128) return false;
            int index = frame.current_state[1] - '0';
            if (!ValidHold(g, index)) return false;
            string target = index == 0 ? "box" : index == 1 ? "lid" : index == 6 ? "complete" : "screw_" + "abcd"[index - 2];
            if (frame.target != target) return false;
            if (g.phase == "PAUSED") return true;
            if (index == 6) return g.phase == "AWAITING_CONFIRMATION"
                || (g.phase == "COMPLETED" && g.reason == "operator_confirmation");
            return g.phase == "GUIDING" || g.phase == "OBSERVING" || (index >= 2 && g.phase == "OBSERVED");
        }

        private static bool ValidHold(AssemblyGuidance g, int index)
        {
            if (g.hold_progress == null) return g.hold_remaining_ms == -1;
            if (g.hold_progress == "none") return g.hold_remaining_ms == 0;
            if (index < 2 || index > 5) return false;
            if (g.hold_progress == "checkpoint") return g.phase == "PAUSED" && g.hold_remaining_ms == 0;
            if (g.hold_progress == "retained") return g.phase == "PAUSED"
                && g.hold_remaining_ms > 0 && g.hold_remaining_ms <= 3000;
            return g.hold_progress == "recheck" && g.hold_remaining_ms == 0
                && (g.phase == "PAUSED" || g.phase == "GUIDING");
        }

        public bool ShowTestRing(double now, bool enabled)
        {
            return enabled && Status(now) == "LIVE";
        }

        private static bool Finite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private static bool Valid(GuidanceSnapshot frame)
        {
            if (frame == null || frame.schema_version != "realtime_v1"
                || string.IsNullOrWhiteSpace(frame.session_id)
                || frame.frame_id < 1 || frame.timestamp_ms <= 0 || frame.frame_age_ms < 0
                || frame.system_status != "RUNNING"
                || string.IsNullOrWhiteSpace(frame.current_label)
                || string.IsNullOrWhiteSpace(frame.next_action))
                return false;
            if (frame.current_state == null || frame.current_state.Length != 2
                || frame.current_state[0] != 'S'
                || frame.current_state[1] < '0' || frame.current_state[1] > '6')
                return false;
            return ValidGuidance(frame) && (frame.marker_status == "OK" || frame.marker_status == "LOST"
                || frame.marker_status == "FALLBACK" || frame.marker_status == "DISABLED"
                || frame.marker_status == "UNSTABLE");
        }
    }
}
