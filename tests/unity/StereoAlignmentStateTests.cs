using System;
using ARAssembly;
using NUnit.Framework;

public class StereoAlignmentStateTests
{
    [Test]
    public void StereoModeRequiresItsOwnExactOptIn()
    {
        Assert.That(StereoAlignmentState.Requested(new[] { "app", "--stereo-alignment-probe" }), Is.True);
        Assert.That(StereoAlignmentState.Requested(new[] { "--alignment-probe" }), Is.False);
        Assert.That(StereoAlignmentState.Requested(new[] { "--stereo-alignment-probe-extra" }), Is.False);
    }

    [TestCase(1920, 1080)]
    [TestCase(2880, 1800)]
    [TestCase(3839, 1080)]
    [TestCase(3840, 720)]
    public void NonFullSbsFramebuffersAreRejected(int width, int height)
    {
        Assert.Throws<ArgumentException>(() => new StereoAlignmentState(width, height, 0, 120));
    }

    [TestCase(1080, 540)]
    [TestCase(1200, 600)]
    public void SeparateEyeOriginsUseHalfWidthPixels(int height, int centerY)
    {
        var state = new StereoAlignmentState(3840, height, 0, 120);
        Assert.That(state.EyeWidth, Is.EqualTo(1920));
        Assert.That(state.LeftX, Is.EqualTo(960));
        Assert.That(state.RightX, Is.EqualTo(960));
        Assert.That(state.LeftY, Is.EqualTo(centerY));
        Assert.That(state.FramebufferX(false), Is.EqualTo(960));
        Assert.That(state.FramebufferX(true), Is.EqualTo(2880));
    }

    [Test]
    public void IdentityCheckCannotSaveMoveOrEnterAlignmentBeforeUserConfirmation()
    {
        var state = new StereoAlignmentState(3840, 1080, 0, 120);
        Assert.That(state.View, Is.EqualTo(StereoProbeView.Channels));
        Assert.That(state.ShowEye(false), Is.True);
        Assert.That(state.ShowEye(true), Is.True);
        Assert.That(state.Move(20, 10, 1), Is.False);
        Assert.That(state.Select(StereoProbeView.Left, 1), Is.False);
        Assert.Throws<InvalidOperationException>(() => state.Mark(1));
        Assert.That(state.MarkedCount, Is.Zero);
        state.ConfirmChannels(2);
        Assert.That(state.View, Is.EqualTo(StereoProbeView.Left));
        Assert.That(state.ShowEye(true), Is.False);
    }

    [Test]
    public void MovingOneEyeDoesNotMoveTheOtherEye()
    {
        var state = Ready();
        state.Move(20, -10, 2);
        Assert.That(state.LeftX, Is.EqualTo(980));
        Assert.That(state.LeftY, Is.EqualTo(530));
        Assert.That(state.RightX, Is.EqualTo(960));
        Assert.That(state.RightY, Is.EqualTo(540));
        state.Select(StereoProbeView.Right, 3);
        state.Move(-30, 8, 3);
        Assert.That(state.RightX, Is.EqualTo(930));
        Assert.That(state.RightY, Is.EqualTo(548));
        Assert.That(state.FramebufferX(true), Is.EqualTo(2850));
        Assert.That(state.LeftX, Is.EqualTo(980));
        Assert.That(state.ShowEye(false), Is.False);
    }

    [Test]
    public void RingStaysInsideItsEyeViewportAndResetAffectsSelectedEyeOnly()
    {
        var state = Ready();
        state.Move(-10000, 10000, 2);
        state.Select(StereoProbeView.Right, 3);
        state.Move(10000, -10000, 3);
        Assert.That(state.LeftX, Is.EqualTo(24));
        Assert.That(state.LeftY, Is.EqualTo(1056));
        Assert.That(state.RightX, Is.EqualTo(1896));
        Assert.That(state.RightY, Is.EqualTo(24));
        state.ResetSelected(4);
        Assert.That(state.RightX, Is.EqualTo(960));
        Assert.That(state.LeftX, Is.EqualTo(24));
    }

    [Test]
    public void BothViewDisplaysButDoesNotMoveEitherEyeAndNeedsBothMarksToRecord()
    {
        var state = Ready();
        state.Select(StereoProbeView.Both, 2);
        Assert.That(state.ShowEye(false), Is.True);
        Assert.That(state.ShowEye(true), Is.True);
        Assert.That(state.Move(20, 20, 2), Is.False);
        Assert.Throws<InvalidOperationException>(() => state.Mark(2));
        Assert.That(state.LeftX, Is.EqualTo(960));
        Assert.That(state.RightX, Is.EqualTo(960));
    }

    [Test]
    public void PairRecordPreservesEyeLocalCoordinatesAndDoesNotClaimCalibration()
    {
        var state = Ready();
        state.Move(20, -10, 2);
        var left = state.Mark(2);
        Assert.That(left.selected_view, Is.EqualTo("Left"));
        Assert.That(left.left_marked, Is.True);
        Assert.That(left.right_marked, Is.False);
        state.Select(StereoProbeView.Right, 3);
        state.Move(-30, 8, 3);
        state.Mark(3);
        state.Select(StereoProbeView.Both, 4);
        var pair = state.Mark(4);
        Assert.That(pair.point_index, Is.EqualTo(3));
        Assert.That(pair.eye_width, Is.EqualTo(1920));
        Assert.That(pair.framebuffer_width, Is.EqualTo(3840));
        Assert.That(pair.left_x, Is.EqualTo(980));
        Assert.That(pair.right_x, Is.EqualTo(930));
        Assert.That(pair.left_u, Is.EqualTo(980d / 1920).Within(1e-9));
        Assert.That(pair.right_v, Is.EqualTo(548d / 1080).Within(1e-9));
        Assert.That(pair.channels_confirmed_by_user, Is.True);
        Assert.That(pair.left_marked && pair.right_marked, Is.True);
        Assert.That(pair.calibration_valid, Is.False);
        Assert.That(pair.display_alignment_verified, Is.False);
    }

    [Test]
    public void ChangingAnEyeInvalidatesItsPreviousMark()
    {
        var state = Ready();
        state.Mark(2);
        state.Select(StereoProbeView.Right, 3);
        state.Mark(3);
        state.Move(2, 0, 4);
        state.Select(StereoProbeView.Both, 5);
        Assert.Throws<InvalidOperationException>(() => state.Mark(5));
        state.Select(StereoProbeView.Right, 6);
        var changed = state.Mark(6);
        Assert.That(changed.left_marked, Is.True);
        state.ResetSelected(7);
        state.Select(StereoProbeView.Both, 8);
        Assert.Throws<InvalidOperationException>(() => state.Mark(8));
    }

    [Test]
    public void ReenteringChannelCheckRequiresFreshMarksAndConfirmation()
    {
        var state = Ready();
        state.Mark(2);
        state.Select(StereoProbeView.Channels, 3);
        Assert.That(state.Select(StereoProbeView.Both, 4), Is.False);
        Assert.Throws<InvalidOperationException>(() => state.Mark(4));
        state.ConfirmChannels(5);
        Assert.That(state.Mark(6).right_marked, Is.False);
    }

    [Test]
    public void ExpiryResolutionChangeAndInvalidClockHideBothEyes()
    {
        var state = new StereoAlignmentState(3840, 1080, 10, 120);
        Assert.That(state.Visible(11, 3840, 1080), Is.True);
        Assert.That(state.Visible(11, 1920, 1080), Is.False);
        Assert.That(state.Visible(11, 3840, 1200), Is.False);
        Assert.That(state.Visible(9, 3840, 1080), Is.False);
        Assert.That(state.Visible(double.NaN, 3840, 1080), Is.False);
        state.ConfirmChannels(129);
        state.Mark(129);
        Assert.That(state.Visible(130, 3840, 1080), Is.False);
        Assert.Throws<InvalidOperationException>(() => state.Move(2, 0, 130));
        Assert.Throws<InvalidOperationException>(() => state.Mark(130));
    }

    [Test]
    public void OutputModeChangeHidesAndInvalidatesEvenWhenRenderBufferIsUnchanged()
    {
        var state = Ready();
        Assert.That(state.Visible(2, 3840, 1080, 3840, 1080), Is.True);
        Assert.That(state.Visible(3, 3840, 1080, 1920, 1080), Is.False);
        Assert.That(state.ShowEye(false), Is.False);
        Assert.That(state.ShowEye(true), Is.False);
        Assert.Throws<InvalidOperationException>(() => state.Mark(4));
        Assert.That(state.Visible(5, 3840, 1080, 3840, 1080), Is.False);
    }

    [Test]
    public void InvalidMovementOrSelectionCannotChangePositions()
    {
        var state = Ready();
        Assert.Throws<ArgumentException>(() => state.Move(double.NaN, 0, 2));
        Assert.Throws<ArgumentException>(() => state.Move(0, double.PositiveInfinity, 2));
        Assert.Throws<ArgumentException>(() => state.Select((StereoProbeView)99, 2));
        Assert.That(state.LeftX, Is.EqualTo(960));
        Assert.That(state.LeftY, Is.EqualTo(540));
    }

    private static StereoAlignmentState Ready()
    {
        var state = new StereoAlignmentState(3840, 1080, 0, 120);
        state.ConfirmChannels(1);
        return state;
    }

    [Test]
    public void RestoreUsesCoordinatesButNeverRestoresConfirmationOrSavedMarks()
    {
        var old = Ready(); old.Move(-180, -100, 2); old.Mark(2);
        old.Select(StereoProbeView.Right, 3); old.Move(-360, -80, 3);
        var point = old.Mark(3);
        var state = new StereoAlignmentState(3840, 1080, 0, 120);
        state.RestorePositions(point, 1);
        Assert.That(state.LeftX, Is.EqualTo(780));
        Assert.That(state.RightX, Is.EqualTo(600));
        Assert.That(state.View, Is.EqualTo(StereoProbeView.Channels));
        Assert.That(state.MarkedCount, Is.Zero);
        Assert.That(state.MarkStatus, Is.EqualTo("CHANNEL CHECK"));
        Assert.Throws<InvalidOperationException>(() => state.Mark(2));
        state.ConfirmChannels(2);
        Assert.That(state.MarkStatus, Is.EqualTo("UNSAVED"));
        var pending = state.PreviewMark(3);
        Assert.That(pending.right_marked, Is.False);
        state.CommitMark(pending, 3);
        Assert.Throws<InvalidOperationException>(() => state.RestorePositions(point, 4));
    }

    [TestCase("size")] [TestCase("scope")] [TestCase("target")] [TestCase("nan")]
    [TestCase("range")] [TestCase("convention")] [TestCase("missing")]
    public void InvalidRestoreCannotPartiallyChangeCoordinates(string change)
    {
        var point = Ready().PreviewMark(2);
        point.left_x = 700;
        switch (change) {
            case "size": point.height = 1200; break;
            case "scope": point.scope = "other"; break;
            case "target": point.target = "other"; break;
            case "nan": point.right_x = double.NaN; break;
            case "range": point.right_y = 0; break;
            case "convention": point.coordinate_convention = "world"; break;
            case "missing": point = new StereoAlignmentPoint(); break;
        }
        var state = Ready();
        Assert.Throws<ArgumentException>(() => state.RestorePositions(point, 2));
        Assert.That(state.LeftX, Is.EqualTo(960));
        Assert.That(state.MarkedCount, Is.Zero);
    }

    [Test]
    public void MarkStatusTracksEachEyeAndMovementRequiresResave()
    {
        var state = Ready(); state.Mark(2);
        Assert.That(state.MarkStatus, Is.EqualTo("SAVED"));
        state.Select(StereoProbeView.Right, 3);
        Assert.That(state.MarkStatus, Is.EqualTo("UNSAVED"));
        state.Mark(3);
        state.Select(StereoProbeView.Both, 4);
        Assert.That(state.MarkStatus, Is.EqualTo("PAIR UNSAVED"));
        state.Mark(4);
        Assert.That(state.MarkStatus, Is.EqualTo("PAIR SAVED"));
        state.Select(StereoProbeView.Left, 5); state.Move(2, 0, 5);
        Assert.That(state.MarkStatus, Is.EqualTo("UNSAVED"));
        state.Select(StereoProbeView.Right, 6);
        Assert.That(state.MarkStatus, Is.EqualTo("SAVED"));
        state.Select(StereoProbeView.Both, 7);
        Assert.That(state.MarkStatus, Is.EqualTo("LEFT NOT SAVED"));
    }

    [TestCase(false, false, "EYES NOT SAVED")]
    [TestCase(true, false, "RIGHT NOT SAVED")]
    [TestCase(false, true, "LEFT NOT SAVED")]
    public void PairSaveIdentifiesMissingEyeWithoutChangingMarks(bool saveLeft, bool saveRight, string reason)
    {
        var state = Ready();
        if (saveLeft) state.Mark(2);
        state.Select(StereoProbeView.Right, 3);
        if (saveRight) state.Mark(3);
        state.Select(StereoProbeView.Both, 4);
        int count = state.MarkedCount;

        var error = Assert.Throws<InvalidOperationException>(() => state.PreviewMark(4));
        Assert.That(error.Message, Is.EqualTo(reason));
        Assert.That(state.MarkStatus, Is.EqualTo(reason));
        Assert.That(state.MarkedCount, Is.EqualTo(count));
    }

    [Test]
    public void ChannelCheckFailureIsNotReportedAsMissingEyeSave()
    {
        var state = new StereoAlignmentState(3840, 1080, 0, 120);
        var error = Assert.Throws<InvalidOperationException>(() => state.PreviewMark(1));
        Assert.That(error.Message, Is.EqualTo("CHANNEL CHECK REQUIRED"));
        Assert.That(state.MarkStatus, Is.EqualTo("CHANNEL CHECK"));
        Assert.That(state.MarkedCount, Is.Zero);
    }

    [Test]
    public void ExpiredProbeIsNotReportedAsMissingEyeSave()
    {
        var state = Ready();
        state.Select(StereoProbeView.Both, 2);
        var error = Assert.Throws<InvalidOperationException>(() => state.PreviewMark(120));
        Assert.That(error.Message, Is.EqualTo("PROBE EXPIRED"));
        Assert.That(state.MarkedCount, Is.Zero);
    }

    [Test]
    public void OutputChangeIsNotReportedAsExpiredProbeOrMissingEyeSave()
    {
        var state = Ready();
        Assert.That(state.Visible(2, 3840, 1080, 1920, 1080), Is.False);
        var error = Assert.Throws<InvalidOperationException>(() => state.PreviewMark(3));
        Assert.That(error.Message, Is.EqualTo("DISPLAY CHANGED"));
        Assert.That(state.MarkedCount, Is.Zero);
    }

    [TestCase(StereoProbeView.Left, "LEFT NOT SAVED")]
    [TestCase(StereoProbeView.Right, "RIGHT NOT SAVED")]
    public void ReadjustedEyeRequiresItsOwnNewSave(StereoProbeView eye, string reason)
    {
        var state = Ready();
        state.Mark(2);
        state.Select(StereoProbeView.Right, 3);
        state.Mark(3);
        state.Select(StereoProbeView.Both, 4);
        state.Mark(4);
        state.Select(eye, 5);
        state.Move(2, 0, 5);
        state.Select(StereoProbeView.Both, 6);
        Assert.That(state.MarkStatus, Is.EqualTo(reason));
        var error = Assert.Throws<InvalidOperationException>(() => state.PreviewMark(6));
        Assert.That(error.Message, Is.EqualTo(reason));
        Assert.That(state.MarkedCount, Is.EqualTo(3));
    }

    [Test]
    public void PreviewWithoutSuccessfulCommitDoesNotUnlockPairSave()
    {
        var state = Ready();
        state.PreviewMark(2);
        state.Select(StereoProbeView.Right, 3);
        state.PreviewMark(3);
        state.Select(StereoProbeView.Both, 4);
        var error = Assert.Throws<InvalidOperationException>(() => state.PreviewMark(4));
        Assert.That(error.Message, Is.EqualTo("EYES NOT SAVED"));
        Assert.That(state.MarkedCount, Is.Zero);
    }
}
