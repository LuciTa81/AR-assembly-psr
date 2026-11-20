using System;
using ARAssembly;
using NUnit.Framework;

public class ObservedCueDelayTests
{
    [Test]
    public void CheckpointDoesNotRestartWorkingDelayOrShowMoveClearWhilePaused()
    {
        var f = new ObservedCueDelay(2000);
        f.Apply(View(), "s|A", 1);
        var paused = View("PAUSED", "checkpoint");
        Assert.That(f.Apply(paused, "s|A", 30).Status, Is.EqualTo("PAUSED"));
        Assert.That(f.Apply(View(), "s|A", 30.1).Cue, Is.EqualTo("MOVE CLEAR"));
        Assert.That(f.Apply(View(), "s|B", 31).Cue, Is.EqualTo("WORKING"));
    }

    private static GuidancePresentation View(string status = "OBSERVED", string progress = "none")
        => new GuidancePresentation {
            Status = status, Cue = status == "OBSERVED" ? "MOVE CLEAR" : status,
            Instruction = status == "OBSERVED" ? "When finished, move driver clear of screw A" : "Current instruction",
            StepTitle = "SCREW A", Acknowledgement = "", HoldProgress = progress,
            ShowTarget = status == "OBSERVED", IsReference = status == "PAUSED"
        };

    [Test]
    public void DelaysGreenStatusAndMoveCueForTwoSecondsWithoutMutatingRawView()
    {
        var f = new ObservedCueDelay(2000);
        var raw = View();
        var waiting = f.Apply(raw, "session|S2|A", 10);
        Assert.That(waiting.Status, Is.EqualTo("OBSERVING"));
        Assert.That(waiting.Cue, Is.EqualTo("WORKING"));
        Assert.That(waiting.Instruction, Is.EqualTo("Continue fastening the screw."));
        Assert.That(waiting.ShowTarget, Is.EqualTo(raw.ShowTarget));
        Assert.That(raw.Cue, Is.EqualTo("MOVE CLEAR"));
        Assert.That(f.Apply(raw, "session|S2|A", 10).Cue, Is.EqualTo("WORKING"));
        Assert.That(f.Apply(raw, "session|S2|A", 11.999).Cue, Is.EqualTo("WORKING"));
        Assert.That(f.Apply(raw, "session|S2|A", 12).Cue, Is.EqualTo("MOVE CLEAR"));
    }

    [TestCase("PAUSED")]
    [TestCase("TRACKING_LOST")]
    [TestCase("STALE")]
    [TestCase("NO_POSE")]
    public void PauseHidesActionButDoesNotRestartTheElapsedClock(string status)
    {
        var f = new ObservedCueDelay(2000);
        f.Apply(View(), "s|A", 1);
        var paused = View(status, "retained");
        Assert.That(f.Apply(paused, "s|A", 1.5).Cue, Is.EqualTo(status));
        Assert.That(f.Apply(paused, "s|A", 3.1).Status, Is.EqualTo(status));
        Assert.That(f.Apply(View(), "s|A", 3.2).Cue, Is.EqualTo("MOVE CLEAR"));
    }

    [TestCase("GUIDING", "none")]
    [TestCase("OBSERVING", "none")]
    [TestCase("PAUSED", "recheck")]
    [TestCase("DISCONNECTED", "none")]
    [TestCase("PROFILE_MISMATCH", "none")]
    public void RenewedWorkOrFaultRestartsDelay(string status, string progress)
    {
        var f = new ObservedCueDelay(2000);
        f.Apply(View(), "s|A", 1);
        var other = View(status, progress);
        Assert.That(f.Apply(other, "s|A", 1.1).Cue, Is.EqualTo(status));
        Assert.That(f.Apply(View(), "s|A", 4).Cue, Is.EqualTo("WORKING"));
        Assert.That(f.Apply(View(), "s|A", 6).Cue, Is.EqualTo("MOVE CLEAR"));
    }

    [TestCase("s|B")]
    [TestCase("new|A")]
    public void NewTargetOrSessionDoesNotInheritDeadline(string context)
    {
        var f = new ObservedCueDelay(2000);
        f.Apply(View(), "s|A", 1);
        Assert.That(f.Apply(View(), context, 10).Cue, Is.EqualTo("WORKING"));
    }

    [TestCase("GUIDING")]
    [TestCase("AWAITING_CONFIRMATION")]
    [TestCase("COMPLETED")]
    public void StageChangesAndFinalConfirmationAreNotDelayed(string status)
    {
        var f = new ObservedCueDelay(2000);
        f.Apply(View(), "s|A", 1);
        var next = View(status);
        Assert.That(f.Apply(next, "s|next", 1.2), Is.EqualTo(next));
    }

    [TestCase(double.NaN)]
    [TestCase(double.PositiveInfinity)]
    [TestCase(-1)]
    [TestCase(.5)]
    public void InvalidOrReversedTimeNeverReleasesTheDelayedCue(double time)
    {
        var f = new ObservedCueDelay(2000);
        f.Apply(View(), "s|A", 1);
        Assert.That(f.Apply(View(), "s|A", time).Cue, Is.EqualTo("WORKING"));
        Assert.That(f.Apply(View(), "s|A", 4).Cue, Is.EqualTo("WORKING"));
    }

    [Test]
    public void ZeroDelayPreservesLegacyPresentation()
    {
        var raw = View();
        Assert.That(new ObservedCueDelay(0).Apply(raw, "s|A", 1), Is.EqualTo(raw));
        Assert.That(SbsGuidanceOptions.Parse(new[] { "--sbs-guidance" }).ObservedCueDelayMs, Is.Zero);
    }

    [TestCase("2000", 2000)]
    [TestCase("0", 0)]
    [TestCase("5000", 5000)]
    public void ParsesExplicitSbsDelay(string value, int expected)
    {
        Assert.That(SbsGuidanceOptions.Parse(new[] { "--sbs-guidance", "--observed-cue-delay-ms", value })
            .ObservedCueDelayMs, Is.EqualTo(expected));
    }

    [TestCase("-1")]
    [TestCase("5001")]
    [TestCase("NaN")]
    [TestCase("2.0")]
    [TestCase("")]
    public void RejectsInvalidDelay(string value)
    {
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(
            new[] { "--sbs-guidance", "--observed-cue-delay-ms", value }));
    }

    [Test]
    public void TextRecoveryDoesNotReleaseTheCueUntilInputIsStable()
    {
        var f = new ObservedCueDelay(2000);
        var text = new GuidanceTextStability();
        GuidancePresentation Apply(GuidancePresentation raw, double now)
            => text.Apply(f.Apply(raw, "s|A", now), "s|A", now);
        Assert.That(Apply(View(), 1).Cue, Is.EqualTo("WORKING"));
        Assert.That(Apply(View("PAUSED", "retained"), 2).Status, Is.EqualTo("PAUSED"));
        Assert.That(Apply(View(), 3.1).Status, Is.EqualTo("PAUSED"));
        Assert.That(Apply(View(), 3.36).Cue, Is.EqualTo("MOVE CLEAR"));
    }

    [TestCase(-1)]
    [TestCase(5001)]
    public void RejectsInvalidConstructorDelay(int delay)
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => new ObservedCueDelay(delay));
    }

    [Test]
    public void DelayRequiresSbsGuidance()
    {
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(
            new[] { "--observed-cue-delay-ms", "2000" }));
    }
}
