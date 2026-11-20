using System;

namespace ARAssembly
{
    [Serializable]
    public sealed class ManualAlignmentPoint
    {
        public string scope = "manual_single_point_optical_probe";
        public string target = "screw_a_far_left";
        public string coordinate_convention = "native_display_pixels_top_left";
        public bool calibration_valid = false;
        public bool display_alignment_verified = false;
        public int point_index;
        public int width;
        public int height;
        public double x;
        public double y;
        public double display_u;
        public double display_v;
        public double marked_at_monotonic_seconds;
    }

    public sealed class ManualAlignmentState
    {
        public int Width { get; }
        public int Height { get; }
        public double X { get; private set; }
        public double Y { get; private set; }
        public int MarkedCount { get; private set; }
        private readonly double startedAt;
        private readonly double deadline;

        public static bool Requested(string[] args)
        {
            return Array.IndexOf(args, "--alignment-probe") >= 0;
        }

        public ManualAlignmentState(int width, int height, double started, double seconds, bool trackedDiagnostic = false)
        {
            if (width < 96 || height < 96 || !Finite(started) || started < 0
                || !Finite(seconds) || seconds < 1 || seconds > (trackedDiagnostic ? 600 : 300))
                throw new ArgumentException("Invalid manual probe dimensions, clock, or duration");
            Width = width;
            Height = height;
            startedAt = started;
            deadline = started + seconds;
            X = width / 2d;
            Y = height / 2d;
        }

        public bool Visible(double now, int width, int height)
        {
            return Finite(now) && now >= startedAt && now < deadline && width == Width && height == Height;
        }

        public void Move(double dx, double dy, double now)
        {
            RequireActive(now);
            if (!Finite(dx) || !Finite(dy)) throw new ArgumentException("Move must be finite");
            X = Math.Max(24, Math.Min(Width - 24, X + dx));
            Y = Math.Max(24, Math.Min(Height - 24, Y + dy));
        }

        public void Reset(double now)
        {
            RequireActive(now);
            X = Width / 2d;
            Y = Height / 2d;
        }

        public ManualAlignmentPoint Mark(double now)
        {
            RequireActive(now);
            return new ManualAlignmentPoint {
                point_index = ++MarkedCount, width = Width, height = Height,
                x = X, y = Y, display_u = X / Width, display_v = Y / Height,
                marked_at_monotonic_seconds = now
            };
        }

        private void RequireActive(double now)
        {
            if (!Visible(now, Width, Height)) throw new InvalidOperationException("Manual probe expired");
        }

        private static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }
    }
}
