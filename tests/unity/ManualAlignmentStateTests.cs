using System;
using ARAssembly;
using NUnit.Framework;

public class ManualAlignmentStateTests
{
    [Test]
    public void ManualModeRequiresExactExplicitFlag()
    {
        Assert.That(ManualAlignmentState.Requested(new[] { "app", "--alignment-probe" }), Is.True);
        Assert.That(ManualAlignmentState.Requested(new[] { "app", "--test-ring" }), Is.False);
        Assert.That(ManualAlignmentState.Requested(new[] { "app", "--alignment-probe-extra" }), Is.False);
    }

    [Test]
    public void NativePixelNudgeAndNormalizedRecordAgree()
    {
        var probe = new ManualAlignmentState(1920, 1080, 10, 120);
        probe.Move(10, -20, 11);
        Assert.That(probe.X, Is.EqualTo(970));
        Assert.That(probe.Y, Is.EqualTo(520));
        var point = probe.Mark(12);
        Assert.That(point.display_u, Is.EqualTo(970d / 1920).Within(1e-9));
        Assert.That(point.display_v, Is.EqualTo(520d / 1080).Within(1e-9));
        Assert.That(point.calibration_valid, Is.False);
        Assert.That(point.display_alignment_verified, Is.False);
        Assert.That(point.scope, Is.EqualTo("manual_single_point_optical_probe"));
    }

    [Test]
    public void RingCannotBeMovedOutsideDisplayAndResetRestoresCenter()
    {
        var probe = new ManualAlignmentState(1920, 1080, 0, 120);
        probe.Move(-10000, 10000, 1);
        Assert.That(probe.X, Is.EqualTo(24));
        Assert.That(probe.Y, Is.EqualTo(1056));
        probe.Reset(2);
        Assert.That(probe.X, Is.EqualTo(960));
        Assert.That(probe.Y, Is.EqualTo(540));
    }

    [Test]
    public void DeadlineAndResolutionChangeHideProbe()
    {
        var probe = new ManualAlignmentState(1920, 1080, 10, 120);
        Assert.That(probe.Visible(11, 1920, 1080), Is.True);
        Assert.That(probe.Visible(11, 1280, 720), Is.False);
        Assert.That(probe.Visible(130, 1920, 1080), Is.False);
        Assert.That(probe.Visible(double.NaN, 1920, 1080), Is.False);
        Assert.That(probe.Visible(9, 1920, 1080), Is.False);
        Assert.Throws<InvalidOperationException>(() => probe.Mark(131));
    }

    [TestCase(0, 1080, 120)]
    [TestCase(1920, 0, 120)]
    [TestCase(1920, 1080, 0)]
    [TestCase(1920, 1080, 301)]
    public void InvalidDimensionsOrDurationAreRejected(int width, int height, double duration)
    {
        Assert.Throws<ArgumentException>(() => new ManualAlignmentState(width, height, 0, duration));
    }

    [Test]
    public void InvalidMoveDoesNotChangeSavedPoint()
    {
        var probe = new ManualAlignmentState(1920, 1080, 0, 120);
        Assert.Throws<ArgumentException>(() => probe.Move(double.NaN, 0, 1));
        Assert.That(probe.X, Is.EqualTo(960));
        Assert.Throws<InvalidOperationException>(() => probe.Move(10, 0, 120));
    }

    [Test]
    public void MarkingDoesNotRestartDeadlineOrClaimAutomaticTracking()
    {
        var probe = new ManualAlignmentState(1920, 1080, 0, 120);
        Assert.That(probe.Mark(119).point_index, Is.EqualTo(1));
        Assert.That(probe.Visible(121, 1920, 1080), Is.False);
        Assert.That(probe.MarkedCount, Is.EqualTo(1));
    }
}
