using System;

namespace ARAssembly
{
    public sealed class ObservedCueDelay
    {
        private readonly double delaySeconds;
        private string currentContext;
        private double observedAt = -1, lastTime = -1;

        public ObservedCueDelay(int delayMs)
        {
            if (delayMs < 0 || delayMs > 5000) throw new ArgumentOutOfRangeException(nameof(delayMs));
            delaySeconds = delayMs / 1000.0;
        }

        public GuidancePresentation Apply(GuidancePresentation raw, string context, double now)
        {
            if (delaySeconds == 0) return raw;
            if (double.IsNaN(now) || double.IsInfinity(now) || now < 0 || now < lastTime) {
                observedAt = lastTime = -1;
                return raw.Status == "OBSERVED" ? Working(raw) : raw;
            }
            lastTime = now;
            if (context != currentContext) {
                currentContext = context;
                observedAt = -1;
            }
            if (raw.HoldProgress == "recheck") observedAt = -1;
            if (raw.Status == "OBSERVED") {
                if (observedAt < 0) observedAt = now;
                return now - observedAt < delaySeconds ? Working(raw) : raw;
            }

            // Preserve only the clock through soft input loss, never an actionable view.
            switch (raw.Status) {
                case "PAUSED": case "TRACKING_LOST": case "STALE":
                case "NO_POSE": case "STALE_POSE": case "WAITING":
                    break;
                default:
                    observedAt = -1;
                    break;
            }
            return raw;
        }

        private static GuidancePresentation Working(GuidancePresentation view)
        {
            view.Status = "OBSERVING";
            view.Cue = "WORKING";
            view.Instruction = "Continue fastening the screw.";
            return view;
        }
    }
}
