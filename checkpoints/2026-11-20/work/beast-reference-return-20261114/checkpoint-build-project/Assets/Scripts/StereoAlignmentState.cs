using System;

namespace ARAssembly
{
    public enum StereoProbeView { Channels, Left, Right, Both }

    [Serializable]
    public sealed class StereoAlignmentPoint
    {
        public string scope = "manual_stereo_single_point_optical_probe";
        public string target = "screw_a_far_left";
        public string coordinate_convention = "eye_local_pixels_top_left";
        public string channel_order = "left_half_left_eye_right_half_right_eye";
        public bool calibration_valid = false;
        public bool display_alignment_verified = false;
        public bool channels_confirmed_by_user;
        public bool left_marked;
        public bool right_marked;
        public string selected_view;
        public int point_index;
        public int framebuffer_width;
        public int eye_width;
        public int height;
        public double left_x = double.NaN, left_y = double.NaN, right_x = double.NaN, right_y = double.NaN;
        public double left_u, left_v, right_u, right_v;
        public double marked_at_monotonic_seconds;
    }

    public sealed class StereoAlignmentState
    {
        private readonly ManualAlignmentState left;
        private readonly ManualAlignmentState right;
        private bool channelsConfirmed;
        private bool leftMarked;
        private bool rightMarked;
        private bool pairMarked;
        private bool displayInvalid;

        public StereoProbeView View { get; private set; } = StereoProbeView.Channels;
        public int EyeWidth => left.Width;
        public int Height => left.Height;
        public double LeftX => left.X;
        public double LeftY => left.Y;
        public double RightX => right.X;
        public double RightY => right.Y;
        public int MarkedCount { get; private set; }
        public string MarkStatus => View == StereoProbeView.Channels ? "CHANNEL CHECK"
            : View == StereoProbeView.Left ? (leftMarked ? "SAVED" : "UNSAVED")
            : View == StereoProbeView.Right ? (rightMarked ? "SAVED" : "UNSAVED")
            : pairMarked ? "PAIR SAVED" : leftMarked && rightMarked ? "PAIR UNSAVED"
            : !leftMarked && !rightMarked ? "EYES NOT SAVED"
            : !leftMarked ? "LEFT NOT SAVED" : "RIGHT NOT SAVED";

        public void RestorePositions(StereoAlignmentPoint point, double now)
        {
            RequireActive(now);
            if (MarkedCount != 0) throw new InvalidOperationException("Cannot restore after saving this session");
            if (point == null || point.scope != "manual_stereo_single_point_optical_probe"
                || point.target != "screw_a_far_left" || point.coordinate_convention != "eye_local_pixels_top_left"
                || point.channel_order != "left_half_left_eye_right_half_right_eye"
                || point.framebuffer_width != EyeWidth * 2 || point.eye_width != EyeWidth || point.height != Height
                || !Inside(point.left_x, EyeWidth) || !Inside(point.right_x, EyeWidth)
                || !Inside(point.left_y, Height) || !Inside(point.right_y, Height))
                throw new ArgumentException("Start point does not match this stereo display");
            left.Move(point.left_x - LeftX, point.left_y - LeftY, now);
            right.Move(point.right_x - RightX, point.right_y - RightY, now);
            channelsConfirmed = leftMarked = rightMarked = pairMarked = false;
            View = StereoProbeView.Channels;
        }

        private static bool Inside(double value, int size) => !double.IsNaN(value)
            && !double.IsInfinity(value) && value >= 24 && value <= size - 24;

        public static bool Requested(string[] args)
        {
            return Array.IndexOf(args, "--stereo-alignment-probe") >= 0;
        }

        public static bool SupportedSize(int width, int height)
        {
            return width == 3840 && (height == 1080 || height == 1200);
        }

        public StereoAlignmentState(int width, int height, double started, double seconds, bool trackedDiagnostic = false)
        {
            if (!SupportedSize(width, height))
                throw new ArgumentException("Full SBS requires 3840x1080 or 3840x1200");
            left = new ManualAlignmentState(width / 2, height, started, seconds, trackedDiagnostic);
            right = new ManualAlignmentState(width / 2, height, started, seconds, trackedDiagnostic);
        }

        public bool Visible(double now, int width, int height)
        {
            return !displayInvalid && width == EyeWidth * 2 && left.Visible(now, EyeWidth, height);
        }

        public bool Visible(double now, int width, int height, int outputWidth, int outputHeight)
        {
            // Borderless fullscreen can keep a 3840px render buffer after the physical mode changes.
            if (outputWidth != EyeWidth * 2 || outputHeight != Height)
                displayInvalid = true;
            return Visible(now, width, height);
        }

        public double FramebufferX(bool rightEye) => rightEye ? EyeWidth + RightX : LeftX;

        public bool ShowEye(bool rightEye)
        {
            return !displayInvalid && (View == StereoProbeView.Channels || View == StereoProbeView.Both
                || View == (rightEye ? StereoProbeView.Right : StereoProbeView.Left));
        }

        public void ConfirmChannels(double now)
        {
            RequireActive(now);
            if (View != StereoProbeView.Channels) return;
            channelsConfirmed = true;
            View = StereoProbeView.Left;
        }

        public bool Select(StereoProbeView view, double now)
        {
            RequireActive(now);
            if (!Enum.IsDefined(typeof(StereoProbeView), view)) throw new ArgumentException("Invalid view");
            if (view == StereoProbeView.Channels)
            {
                channelsConfirmed = leftMarked = rightMarked = pairMarked = false;
                View = view;
                return true;
            }
            if (!channelsConfirmed) return false;
            View = view;
            return true;
        }

        public bool Move(double dx, double dy, double now)
        {
            RequireActive(now);
            if (View != StereoProbeView.Left && View != StereoProbeView.Right) return false;
            var selected = View == StereoProbeView.Left ? left : right;
            selected.Move(dx, dy, now);
            ClearSelectedMark();
            return true;
        }

        public void ResetSelected(double now)
        {
            RequireActive(now);
            if (View != StereoProbeView.Left && View != StereoProbeView.Right) return;
            (View == StereoProbeView.Left ? left : right).Reset(now);
            ClearSelectedMark();
        }

        public StereoAlignmentPoint Mark(double now)
        {
            var point = PreviewMark(now);
            CommitMark(point, now);
            return point;
        }

        public StereoAlignmentPoint PreviewMark(double now)
        {
            RequireActive(now);
            if (!channelsConfirmed || View == StereoProbeView.Channels)
                throw new InvalidOperationException("CHANNEL CHECK REQUIRED");
            if (View == StereoProbeView.Both && !(leftMarked && rightMarked))
                throw new InvalidOperationException(MarkStatus);
            return new StereoAlignmentPoint {
                point_index = MarkedCount + 1, selected_view = View.ToString(),
                channels_confirmed_by_user = channelsConfirmed,
                left_marked = leftMarked || View == StereoProbeView.Left,
                right_marked = rightMarked || View == StereoProbeView.Right,
                framebuffer_width = EyeWidth * 2, eye_width = EyeWidth, height = Height,
                left_x = LeftX, left_y = LeftY, right_x = RightX, right_y = RightY,
                left_u = LeftX / EyeWidth, left_v = LeftY / Height,
                right_u = RightX / EyeWidth, right_v = RightY / Height,
                marked_at_monotonic_seconds = now
            };
        }

        public void CommitMark(StereoAlignmentPoint point, double now)
        {
            RequireActive(now);
            if (point == null || point.point_index != MarkedCount + 1 || point.selected_view != View.ToString()
                || !channelsConfirmed || !point.channels_confirmed_by_user
                || point.left_x != LeftX || point.left_y != LeftY || point.right_x != RightX || point.right_y != RightY
                || point.framebuffer_width != EyeWidth * 2 || point.height != Height)
                throw new InvalidOperationException("Alignment changed before save");
            leftMarked = point.left_marked;
            rightMarked = point.right_marked;
            pairMarked = View == StereoProbeView.Both;
            MarkedCount++;
        }

        private void ClearSelectedMark()
        {
            pairMarked = false;
            if (View == StereoProbeView.Left) leftMarked = false;
            else rightMarked = false;
        }

        private void RequireActive(double now)
        {
            if (displayInvalid) throw new InvalidOperationException("DISPLAY CHANGED");
            if (!Visible(now, EyeWidth * 2, Height)) throw new InvalidOperationException("PROBE EXPIRED");
        }
    }
}
