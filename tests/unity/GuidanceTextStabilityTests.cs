using ARAssembly;
using NUnit.Framework;

public class GuidanceTextStabilityTests
{
    [TestCase("retained", "PAUSED - KEPT")]
    [TestCase("recheck", "RECHECK A")]
    [TestCase("checkpoint", "HOLD KEPT")]
    public void ServerProgressStatusIsImmediateButNeverRememberedAfterExpiry(string progress, string cue)
    {
        var f = new GuidanceTextStability();
        f.Apply(View("OBSERVED"), "s|A", 1);
        var raw = View("PAUSED", "Progress information");
        raw.Cue = cue; raw.HoldProgress = progress;
        Assert.That(f.Apply(raw, "s|A", 1.01).Cue, Is.EqualTo(cue));
        Assert.That(f.Apply(View("PAUSED", "Waiting"), "s|A", 1.02).Cue, Is.EqualTo("PAUSED"));
        Assert.That(f.Apply(View("DISCONNECTED", "Connection lost"), "s|A", 1.03).Instruction,
            Is.EqualTo("Connection lost"));
    }

    [TestCase("retained", "PAUSED - KEPT")]
    [TestCase("checkpoint", "HOLD KEPT")]
    public void ProgressDoesNotBypassInvalidOrReversedTime(string progress, string cue)
    {
        var f = new GuidanceTextStability();
        var raw = View("PAUSED", "Progress kept"); raw.HoldProgress = progress; raw.Cue = cue;
        f.Apply(raw, "s|A", 1);
        Assert.That(f.Apply(raw, "s|A", .9).Cue, Is.EqualTo("PAUSED"));
        Assert.That(f.Apply(raw, "s|A", double.NaN).Cue, Is.EqualTo("PAUSED"));
    }

    [TestCase("retained", "PAUSED - KEPT")]
    [TestCase("recheck", "RECHECK A")]
    [TestCase("checkpoint", "HOLD KEPT")]
    public void ProgressCueIsImmediateWhileChangingReasonsStillSettle(string progress, string cue)
    {
        var f = new GuidanceTextStability();
        for (int i = 0; i < 10; i++) {
            var raw = View("PAUSED", i % 2 == 0 ? "Markers" : "Tool");
            raw.HoldProgress = progress; raw.Cue = cue;
            var result = f.Apply(raw, "s|A", 1 + i * .1);
            Assert.That(result.Cue, Is.EqualTo(cue));
            Assert.That(result.Instruction, Is.EqualTo("Checking input. Guidance paused."));
        }
        var stable = View("PAUSED", "Keep only one driver in view.");
        stable.HoldProgress = progress; stable.Cue = cue;
        f.Apply(stable, "s|A", 2);
        Assert.That(f.Apply(stable, "s|A", 2.51).Instruction, Is.EqualTo(stable.Instruction));
    }

    private static GuidancePresentation View(string status, string text = "Fasten screw A") => new GuidancePresentation {
        Status = status, Cue = status == "OBSERVED" ? "MOVE CLEAR" : "WORK AT A",
        Instruction = text, StepTitle = "SCREW A", Acknowledgement = "A done",
        ShowTarget = status == "OBSERVED" || status == "GUIDING", IsReference = false
    };

    [Test]
    public void LossReplacesMoveClearImmediatelyAndNeverKeepsOldAction()
    {
        var f = new GuidanceTextStability();
        Assert.That(f.Apply(View("OBSERVED"), "s|A", 1).Cue, Is.EqualTo("MOVE CLEAR"));
        var paused = f.Apply(View("TRACKING_LOST", "Bring markers into view"), "s|A", 1.1);
        Assert.That(paused.Cue, Is.EqualTo("PAUSED"));
        Assert.That(paused.Instruction, Is.EqualTo("Checking input. Guidance paused."));
        Assert.That(paused.Acknowledgement, Is.Empty);
    }

    [Test]
    public void RapidFaultReasonsAndBriefRecoveriesStayNeutral()
    {
        var f = new GuidanceTextStability();
        for (int i = 0; i < 20; i++) {
            var raw = i % 3 == 0 ? View("TRACKING_LOST", "Markers")
                : i % 3 == 1 ? View("PAUSED", "Tool") : View("OBSERVED", "Move driver");
            Assert.That(f.Apply(raw, "s|A", 1 + i * .1).Instruction,
                Is.EqualTo("Checking input. Guidance paused."));
        }
    }

    [Test]
    public void PersistentFaultGetsItsActualReasonAfterHalfSecond()
    {
        var f = new GuidanceTextStability();
        var bad = View("PAUSED", "Keep the driver visible");
        f.Apply(bad, "s|A", 1);
        Assert.That(f.Apply(bad, "s|A", 1.49).Instruction, Does.StartWith("Checking input"));
        Assert.That(f.Apply(bad, "s|A", 1.51).Instruction, Is.EqualTo(bad.Instruction));
        Assert.That(f.Apply(View("TRACKING_LOST", "Markers"), "s|A", 1.6).Instruction,
            Does.StartWith("Checking input"));
    }

    [Test]
    public void RecoveryRequiresQuarterSecondAndUsesCurrentNotRememberedAction()
    {
        var f = new GuidanceTextStability();
        f.Apply(View("TRACKING_LOST"), "s|A", 1);
        Assert.That(f.Apply(View("OBSERVED", "Old move"), "s|A", 1.1).Cue, Is.EqualTo("PAUSED"));
        Assert.That(f.Apply(View("GUIDING", "Current work"), "s|A", 1.34).Cue, Is.EqualTo("PAUSED"));
        Assert.That(f.Apply(View("GUIDING", "Current work"), "s|A", 1.36).Instruction,
            Is.EqualTo("Current work"));
    }

    [TestCase("DISCONNECTED")]
    [TestCase("INVALID_DATA")]
    [TestCase("PROFILE_MISMATCH")]
    [TestCase("DISPLAY_CHANGED")]
    [TestCase("COMPLETED")]
    [TestCase("AWAITING_CONFIRMATION")]
    public void FaultsAndExplicitFinalConfirmationAreImmediate(string status)
    {
        var f = new GuidanceTextStability();
        f.Apply(View("TRACKING_LOST"), "s|A", 1);
        Assert.That(f.Apply(View(status, "Important"), "s|A", 1.01).Instruction, Is.EqualTo("Important"));
    }

    [TestCase("other-session|A")]
    [TestCase("s|B")]
    public void SessionOrTargetChangeDoesNotShowPreviousInstruction(string context)
    {
        var f = new GuidanceTextStability();
        f.Apply(View("TRACKING_LOST"), "s|A", 1);
        Assert.That(f.Apply(View("GUIDING", "New target"), context, 1.01).Instruction, Is.EqualTo("New target"));
    }

    [Test]
    public void HealthyPhaseChangesAreNotDelayedAndVisibilityIsNotFiltered()
    {
        var f = new GuidanceTextStability();
        f.Apply(View("GUIDING"), "s|A", 1);
        var good = View("OBSERVED");
        Assert.That(f.Apply(good, "s|A", 1.01).Cue, Is.EqualTo("MOVE CLEAR"));
        var bad = View("TRACKING_LOST");
        var result = f.Apply(bad, "s|A", 1.02);
        Assert.That(result.ShowTarget, Is.EqualTo(bad.ShowTarget));
        Assert.That(result.StepTitle, Is.EqualTo(bad.StepTitle));
        Assert.That(bad.Status, Is.EqualTo("TRACKING_LOST"));
    }

    [Test]
    public void FooterHasSeparateStableRecoveryWithoutBlockingWorkInstructions()
    {
        var f = new GuidanceTextStability();
        Assert.That(f.Hint("Markers", "STATE TRACKING_LOST", "s|A", 1), Is.EqualTo("Checking position"));
        Assert.That(f.Hint("Too few markers", "POSE NO POSE", "s|A", 1.1), Is.EqualTo("Checking position"));
        Assert.That(f.Hint("Target visible", "VISIBLE", "s|A", 1.2), Is.EqualTo("Checking position"));
        Assert.That(f.Apply(View("OBSERVED"), "s|A", 1.2).Cue, Is.EqualTo("MOVE CLEAR"));
        Assert.That(f.Hint("Target visible", "VISIBLE", "s|A", 1.46), Is.EqualTo("Target visible"));
    }

    [TestCase("DISPLAY CHANGED")]
    [TestCase("PROFILE ERROR")]
    [TestCase("SESSION MISMATCH")]
    [TestCase("STATE DISCONNECTED")]
    [TestCase("POSE CAMERA ERROR")]
    [TestCase("POSE CONNECTION ERROR")]
    public void FooterCriticalErrorsAreImmediate(string gate)
    {
        var f = new GuidanceTextStability();
        f.Hint("Wait", "POSE WAITING", "s|A", 1);
        Assert.That(f.Hint("Failure", gate, "s|A", 1.01), Is.EqualTo("Failure"));
    }

    [TestCase(double.NaN)]
    [TestCase(double.PositiveInfinity)]
    [TestCase(.5)]
    public void InvalidOrReversedTimeDoesNotShowAnAction(double time)
    {
        var f = new GuidanceTextStability();
        f.Apply(View("OBSERVED"), "s|A", 1);
        Assert.That(f.Apply(View("OBSERVED"), "s|A", time).Cue, Is.EqualTo("PAUSED"));
    }
}
