namespace ARAssembly
{
    public sealed class GuidanceTextStability
    {
        private readonly Channel instruction = new Channel();
        private readonly Channel position = new Channel();

        public GuidancePresentation Apply(GuidancePresentation raw, string context, double now)
        {
            bool healthy = raw.Status == "LIVE" || raw.Status == "GUIDING" || raw.Status == "OBSERVING"
                || raw.Status == "OBSERVED" || raw.Status == "AWAITING_CONFIRMATION" || raw.Status == "COMPLETED";
            bool soft = raw.Status == "PAUSED" || raw.Status == "TRACKING_LOST" || raw.Status == "STALE"
                || raw.Status == "NO_POSE" || raw.Status == "STALE_POSE" || raw.Status == "WAITING";
            bool urgent = !healthy && !soft || raw.Status == "AWAITING_CONFIRMATION" || raw.Status == "COMPLETED";
            bool progress = raw.HoldProgress == "retained" || raw.HoldProgress == "recheck"
                || raw.HoldProgress == "checkpoint";
            if (instruction.UseRaw(context, now, healthy, urgent, raw.Status + "|" + raw.Instruction)) return raw;
            raw.Status = "PAUSED";
            if (!progress || !instruction.TimeValid) {
                raw.Cue = "PAUSED";
                raw.HoldProgress = "none";
            }
            raw.Instruction = "Checking input. Guidance paused.";
            raw.Acknowledgement = "";
            raw.IsReference = true;
            return raw;
        }

        public string Hint(string raw, string gate, string context, double now)
        {
            bool healthy = gate == "VISIBLE" || gate == "NO STAGE TARGET" || gate == "STATE COMPLETED";
            bool soft = gate == "STATE WAITING" || gate == "STATE TRACKING_LOST" || gate == "STATE STALE"
                || gate == "POSE WAITING" || gate == "POSE STALE" || gate == "POSE NO POSE" || gate == "WAITING"
                || gate == "OUTSIDE EYE VIEW" || gate == "OUTSIDE TARGET DEPTH" || gate == "STAGE TARGET UNAVAILABLE";
            return position.UseRaw(context, now, healthy, !healthy && !soft, gate + "|" + raw)
                ? raw : "Checking position";
        }

        // This channel stores timing/reasons only, never a previous actionable instruction.
        private sealed class Channel
        {
            private string context, reason;
            private double lastTime = -1, reasonSince, healthySince = -1;
            private bool recovering;
            public bool TimeValid { get; private set; }

            public bool UseRaw(string scope, double now, bool healthy, bool urgent, string key)
            {
                TimeValid = !double.IsNaN(now) && !double.IsInfinity(now) && now >= 0 && now >= lastTime;
                if (!TimeValid) {
                    recovering = true;
                    reason = null;
                    healthySince = lastTime = -1;
                    return urgent;
                }
                lastTime = now;
                if (scope != context) {
                    context = scope;
                    recovering = false;
                    reason = null;
                    healthySince = -1;
                }
                if (urgent) {
                    recovering = true;
                    reason = null;
                    healthySince = -1;
                    return true;
                }
                if (!healthy) {
                    recovering = true;
                    healthySince = -1;
                    if (key != reason) { reason = key; reasonSince = now; }
                    return now - reasonSince >= .5;
                }
                reason = null;
                if (!recovering) return true;
                if (healthySince < 0) healthySince = now;
                if (now - healthySince < .25) return false;
                recovering = false;
                return true;
            }
        }
    }
}
