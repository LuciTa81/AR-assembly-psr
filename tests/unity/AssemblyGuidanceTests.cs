using ARAssembly;
using NUnit.Framework;

public class AssemblyGuidanceTests
{
    [TestCase("OK")]
    [TestCase("LOST")]
    public void CompletedCheckpointIsKeptButNeverAnActionOrAStalePromise(string marker)
    {
        var state = new GuidanceState();
        var frame = HoldFrame("checkpoint", 0);
        frame.marker_status = marker;
        Assert.That(state.Apply(frame, 1, 1.01), Is.True);
        var view = state.Presentation(1.02);
        Assert.That(view.Cue, Is.EqualTo("HOLD KEPT"));
        Assert.That(view.HoldProgress, Is.EqualTo("checkpoint"));
        Assert.That(view.ShowTarget, Is.False);
        Assert.That(state.Presentation(2).HoldProgress, Is.EqualTo("none"));
        state.Disconnect();
        Assert.That(state.Presentation(2.1).HoldProgress, Is.EqualTo("none"));
    }

    private static GuidanceSnapshot HoldFrame(string progress, long remaining, string phase = "PAUSED")
    {
        var frame = Frame(1, phase);
        frame.guidance.hold_progress = progress;
        frame.guidance.hold_remaining_ms = remaining;
        return frame;
    }

    [TestCase("OK")]
    [TestCase("LOST")]
    public void RetainedHoldIsFreshBoundedAndNeverMoveClear(string marker)
    {
        var state = new GuidanceState();
        var frame = HoldFrame("retained", 200);
        frame.marker_status = marker;
        frame.frame_age_ms = 50;
        Assert.That(state.Apply(frame, 1, 1.05), Is.True);
        var kept = state.Presentation(1.10);
        Assert.That(kept.Cue, Is.EqualTo("PAUSED - KEPT"));
        Assert.That(kept.Instruction, Is.EqualTo(marker == "OK"
            ? frame.next_action : "Bring the workspace markers into view"));
        Assert.That(kept.ShowTarget, Is.False);
        Assert.That(state.Presentation(1.16).Cue, Is.EqualTo("PAUSED"));
        state.Apply(frame, 1.17, 1.18);
        Assert.That(state.Presentation(1.19).Cue, Is.EqualTo("PAUSED"));
        state.Disconnect();
        Assert.That(state.Presentation(1.2).Instruction, Does.Contain("Connection lost"));
    }

    [TestCase("PAUSED")]
    [TestCase("GUIDING")]
    public void RecheckRefersOnlyToCurrentScrewAndClearsOnNewEngagement(string phase)
    {
        var state = new GuidanceState();
        Assert.That(state.Apply(HoldFrame("recheck", 0, phase), 1, 1.01), Is.True);
        Assert.That(state.Presentation(1.02).Cue, Is.EqualTo("RECHECK A"));
        Assert.That(state.Presentation(1.02).Instruction, Is.EqualTo("Fasten screw A"));
        Assert.That(state.Apply(Frame(2, "OBSERVING"), 1.03, 1.04), Is.True);
        Assert.That(state.Presentation(1.05).Cue, Is.EqualTo("HOLD AT A"));
    }

    [TestCase("retained", 0, "PAUSED")]
    [TestCase("retained", 3001, "PAUSED")]
    [TestCase("retained", 100, "OBSERVED")]
    [TestCase("recheck", 1, "PAUSED")]
    [TestCase("recheck", 0, "OBSERVING")]
    [TestCase("unknown", 0, "PAUSED")]
    [TestCase("checkpoint", 1, "PAUSED")]
    [TestCase("checkpoint", 0, "OBSERVED")]
    public void InvalidHoldMetadataFailsClosed(string progress, long remaining, string phase)
    {
        var state = new GuidanceState();
        Assert.That(state.Apply(HoldFrame(progress, remaining, phase), 1, 1.01), Is.False);
        Assert.That(state.Status(1.02), Is.EqualTo("INVALID_DATA"));
    }

    [Test]
    public void DuplicateCannotChangeHoldMetadata()
    {
        var state = new GuidanceState();
        Assert.That(state.Apply(HoldFrame("retained", 200), 1, 1.01), Is.True);
        Assert.That(state.Apply(HoldFrame("recheck", 0), 1.02, 1.03), Is.False);
        Assert.That(state.Status(1.04), Is.EqualTo("INVALID_DATA"));
    }

    [Test]
    public void MultipleToolCandidatesStayPausedWithTheServerExplanation()
    {
        var frame = Frame(1, "PAUSED");
        frame.guidance.reason = "multiple_tool_candidates";
        frame.next_action = "Multiple tool candidates. Recheck the target with one driver.";
        var state = new GuidanceState();
        Assert.That(state.Apply(frame, 1, 1.01), Is.True);
        var view = state.Presentation(1.02);
        Assert.That(view.Cue, Is.EqualTo("PAUSED"));
        Assert.That(view.Instruction, Is.EqualTo(frame.next_action));
        Assert.That(view.ShowTarget, Is.False);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
    }

    [TestCase("AWAITING_CONFIRMATION")]
    [TestCase("COMPLETED")]
    public void ExplicitFinalCheckRemainsReadableWithoutMarkersButStillExpires(string phase)
    {
        var frame = Frame(1, phase);
        frame.current_state = "S6"; frame.target = "complete";
        frame.marker_status = "LOST"; frame.guidance.reason = "operator_confirmation";
        var state = new GuidanceState();
        Assert.That(state.Apply(frame, 1, 1.01), Is.True);
        Assert.That(state.Presentation(1.02).Status, Is.EqualTo(phase));
        Assert.That(state.Presentation(1.02).ShowTarget, Is.False);
        Assert.That(state.Presentation(2).Status, Is.EqualTo("STALE"));
        state.Disconnect();
        Assert.That(state.Presentation(1.03).Status, Is.EqualTo("DISCONNECTED"));
    }

    [TestCase("GUIDING", "WORK AT D")]
    [TestCase("OBSERVING", "HOLD AT D")]
    [TestCase("OBSERVED", "MOVE CLEAR")]
    [TestCase("PAUSED", "PAUSED")]
    public void ActionCueShowsCurrentTargetAndNeverClaimsTightening(string phase, string cue)
    {
        var frame = Frame(1, phase);
        frame.current_state = "S5"; frame.target = "screw_d";
        frame.current_label = "Screw C engagement observed";
        var state = new GuidanceState();
        Assert.That(state.Apply(frame, 1, 1.01), Is.True);
        var view = state.Presentation(1.02);
        Assert.That(view.StepTitle, Is.EqualTo("SCREW D  |  4 / 4"));
        Assert.That(view.Cue, Is.EqualTo(cue));
        Assert.That(state.Presentation(2).Cue, Is.EqualTo("PAUSED"));
        state.Disconnect();
        Assert.That(state.Presentation(1.03).Cue, Is.EqualTo("PAUSED"));
    }

    [Test]
    public void LossImmediatelyClearsMoveClearCueWithoutChangingStep()
    {
        var state = new GuidanceState();
        state.Apply(Frame(1,"OBSERVED"),1,1.01);
        Assert.That(state.Presentation(1.02).Cue,Is.EqualTo("MOVE CLEAR"));
        var lost = Frame(2,"OBSERVED"); lost.marker_status="LOST";
        state.Apply(lost,1.03,1.04);
        Assert.That(state.Presentation(1.05).Cue,Is.EqualTo("PAUSED"));
        Assert.That(state.Presentation(1.05).StepTitle,Is.EqualTo("SCREW A  |  1 / 4"));
    }

    [Test]
    public void FinalCueRequestsHumanCheckRatherThanDeclaringCompletion()
    {
        var frame = Frame(1,"AWAITING_CONFIRMATION");
        frame.current_state="S6"; frame.target="complete";
        var state = new GuidanceState(); state.Apply(frame,1,1.01);
        Assert.That(state.Presentation(1.02).Cue,Is.EqualTo("FINAL CHECK"));
        Assert.That(state.Presentation(1.02).ShowTarget,Is.False);
    }

    [Test]
    public void OperatorCompletionIsExplicitAndStillExpires()
    {
        var frame = Frame(1, "COMPLETED");
        frame.current_state = "S6"; frame.target = "complete";
        frame.next_action = "Assembly complete - confirmed by operator";
        var state = new GuidanceState();
        Assert.That(state.Apply(frame, 1, 1.01), Is.False);
        frame.guidance.reason = "operator_confirmation";
        Assert.That(state.Apply(frame, 1, 1.01), Is.True);
        Assert.That(state.Presentation(1.02).Status, Is.EqualTo("COMPLETED"));
        Assert.That(state.Presentation(1.02).ShowTarget, Is.False);
        Assert.That(state.Presentation(2).Status, Is.EqualTo("STALE"));
    }

    [Test]
    public void TextGuidanceDoesNotRequireOrInventEyeCalibration()
    {
        var state = new GuidanceState();
        state.Apply(Frame(), 1, 1.01);
        Assert.That(state.Presentation(1.02).Instruction, Is.EqualTo("Fasten screw A"));
        Assert.That(state.Spatial.TryGetPixels(1.02, out _), Is.False);
    }

    [TestCase("https://example.com/state.json")]
    [TestCase("http://localhost:8765/state.json")]
    [TestCase("http://127.0.0.1:8765/state.json?url=other")]
    public void StateEndpointRejectsNonlocalOrNoncanonicalUrl(string url)
    {
        Assert.Throws<System.ArgumentException>(() => SbsGuidanceOptions.Parse(new[] {"--state-url", url}));
    }

    [Test]
    public void LocalStateEndpointCanUseAnAvailablePort()
    {
        Assert.That(SbsGuidanceOptions.Parse(new[] {"--sbs-guidance", "--state-url",
            "http://127.0.0.1:18765/state.json"}).StateUrl,
            Is.EqualTo("http://127.0.0.1:18765/state.json"));
    }

    public static GuidanceSnapshot Frame(long id = 1, string phase = "GUIDING")
    {
        return new GuidanceSnapshot {
            schema_version = "realtime_v1", session_id = "timed", frame_id = id,
            timestamp_ms = 1000 + id * 100, frame_age_ms = 10,
            system_status = "RUNNING", marker_status = "OK",
            current_state = "S2", current_label = "Lid closed", target = "screw_a",
            next_action = phase == "OBSERVED" ? "When finished, move driver clear of screw A" : "Fasten screw A",
            guidance = new AssemblyGuidance { schema_version = "assembly_guidance_v1",
                phase = phase, reason = "", acknowledgement = "", acknowledgement_remaining_ms = 0 }
        };
    }

    [TestCase("GUIDING")]
    [TestCase("OBSERVING")]
    [TestCase("OBSERVED")]
    public void PresentationNeverSelectsNextTargetWhileCurrentWorkIsObserved(string phase)
    {
        var state = new GuidanceState();
        state.Apply(Frame(1, phase), 1, 1.01);
        var view = state.Presentation(1.02);
        Assert.That(view.Status, Is.EqualTo(phase));
        Assert.That(view.Instruction, Does.Contain("screw A"));
        Assert.That(state.LastSnapshot.target, Is.EqualTo("screw_a"));
    }

    [Test]
    public void PauseFromRecognitionHidesTargetAndAckButPreservesStage()
    {
        var state = new GuidanceState();
        var frame = Frame(1, "PAUSED");
        frame.next_action = "Tool not visible. Keep the driver in view.";
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Status(1.02), Is.EqualTo("PAUSED"));
        Assert.That(state.ShowTestRing(1.02, true), Is.False);
        Assert.That(state.Presentation(1.02).Instruction, Is.EqualTo(frame.next_action));
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
    }

    [TestCase("S0", "box", "Place the enclosure box")]
    [TestCase("S1", "lid", "Close the lid")]
    public void NonpositionalInstructionsRemainUsefulWithoutDisplayCalibration(string step, string target, string instruction)
    {
        var state = new GuidanceState();
        var frame = Frame();
        frame.current_state = step; frame.target = target; frame.next_action = instruction;
        state.Apply(frame, 1, 1.01);
        var view = state.Presentation(1.02, true);
        Assert.That(view.Status, Is.EqualTo("GUIDING"));
        Assert.That(view.Instruction, Is.EqualTo(instruction));
        Assert.That(view.ShowTarget, Is.False);
        Assert.That(state.Spatial.Status(1.02), Is.EqualTo("NOT_CALIBRATED"));
    }

    [Test]
    public void ScrewGuidanceWithoutCalibrationDoesNotClaimSpatialGuidance()
    {
        var state = new GuidanceState();
        state.Apply(Frame(), 1, 1.01);
        var view = state.Presentation(1.02, true);
        Assert.That(view.Status, Is.EqualTo("NOT_CALIBRATED"));
        Assert.That(view.ShowTarget, Is.False);
    }

    [Test]
    public void AcknowledgementIsSeparateBoundedAndNotRenewedByNewOrDuplicateParents()
    {
        var state = new GuidanceState();
        var first = Frame();
        first.current_state = "S3"; first.target = "screw_b"; first.next_action = "Fasten screw B";
        first.guidance.acknowledgement = "Screw A interaction observed";
        first.guidance.acknowledgement_remaining_ms = 300;
        state.Apply(first, 1, 1.05);
        var view = state.Presentation(1.1);
        Assert.That(view.Instruction, Is.EqualTo("Fasten screw B"));
        Assert.That(view.Acknowledgement, Does.Contain("Screw A"));
        first.frame_id++; first.timestamp_ms += 100; first.guidance.acknowledgement_remaining_ms = 1200;
        state.Apply(first, 1.15, 1.16);
        state.Apply(first, 1.2, 1.21);
        Assert.That(state.Presentation(1.291).Acknowledgement, Is.Empty);
    }

    [Test]
    public void CalibrationBlockTakesPrecedenceEvenWhenRecognitionIsPaused()
    {
        var state = new GuidanceState();
        var frame = Frame(1, "PAUSED");
        frame.next_action = "Tool not visible. Keep the driver in view.";
        state.Apply(frame, 1, 1.01);
        var view = state.Presentation(1.02, true);
        Assert.That(view.Status, Is.EqualTo("NOT_CALIBRATED"));
        Assert.That(view.Instruction, Is.EqualTo("Display calibration required"));
        Assert.That(view.ShowTarget, Is.False);
    }

    [TestCase(false)]
    [TestCase(true)]
    public void PausedRecognitionCannotHidePoseFailureOrEnableARing(bool visible)
    {
        var state = SpatialGuidanceStateTests.State();
        var frame = Frame(8, "PAUSED");
        frame.session_id = "synthetic-r2";
        frame.next_action = "Tool not visible. Keep the driver in view.";
        frame.spatial = SpatialGuidanceStateTests.Frame().spatial;
        if (!visible) { frame.spatial.target_visible = false; frame.spatial.reason = "no_pose"; }
        state.Apply(frame, 1, 1.01);
        var view = state.Presentation(1.02, true);
        Assert.That(view.Status, Is.EqualTo(visible ? "PAUSED" : state.Spatial.Status(1.02)));
        Assert.That(view.ShowTarget, Is.False);
    }

    [TestCase("phase")]
    [TestCase("target")]
    [TestCase("schema")]
    [TestCase("missing_ack_age")]
    [TestCase("huge_ack_age")]
    [TestCase("terminal")]
    public void InvalidGuidanceCannotBecomeInstruction(string fault)
    {
        var state = new GuidanceState();
        var frame = Frame();
        if (fault == "phase") frame.guidance.phase = "MADE_UP";
        if (fault == "target") frame.target = "screw_b";
        if (fault == "schema") frame.guidance.schema_version = "wrong";
        if (fault == "missing_ack_age") frame.guidance.acknowledgement_remaining_ms = -1;
        if (fault == "huge_ack_age") frame.guidance.acknowledgement_remaining_ms = 90000;
        if (fault == "terminal") frame.guidance.phase = "AWAITING_CONFIRMATION";
        Assert.That(state.Apply(frame, 1, 1.01), Is.False);
        Assert.That(state.Presentation(1.02).Status, Is.EqualTo("INVALID_DATA"));
    }

    [Test]
    public void ParentAndGuidanceMutationCannotRewriteAcceptedInstructions()
    {
        var state = new GuidanceState();
        var frame = Frame();
        state.Apply(frame, 1, 1.01);
        frame.guidance.phase = "OBSERVED"; frame.next_action = "Fasten screw B";
        Assert.That(state.Presentation(1.02).Status, Is.EqualTo("GUIDING"));
        Assert.That(state.Presentation(1.02).Instruction, Does.Contain("screw A"));
        state.Apply(frame, 1.03, 1.04);
        Assert.That(state.Presentation(1.05).Status, Is.EqualTo("INVALID_DATA"));
    }

    [Test]
    public void LossAndStaleStateOverrideRecognitionMessagesAndFinalConfirmation()
    {
        var state = new GuidanceState();
        var frame = Frame(1, "OBSERVED");
        frame.marker_status = "LOST";
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Presentation(1.02).Status, Is.EqualTo("TRACKING_LOST"));
        Assert.That(state.Presentation(1.02).Instruction, Does.Not.Contain("move driver"));
        state.Disconnect();
        Assert.That(state.Presentation(1.03).Status, Is.EqualTo("DISCONNECTED"));
        frame = Frame(2, "AWAITING_CONFIRMATION");
        frame.current_state = "S6"; frame.target = "complete";
        frame.next_action = "Confirm assembly sequence completion";
        state.Apply(frame, 1.1, 1.11);
        Assert.That(state.Presentation(1.12, true).Instruction, Is.EqualTo(frame.next_action));
        Assert.That(state.Presentation(1.12, true).ShowTarget, Is.False);
        Assert.That(state.Presentation(1.7).Status, Is.EqualTo("STALE"));
    }

    [TestCase("recheck", 0, "multiple_tool_candidates", "Keep only one driver in view.")]
    [TestCase("retained", 1000, "tool_not_visible", "Keep the driver in view.")]
    public void HoldProgressKeepsTheCauseSpecificRecoveryInstruction(string progress, long remaining,
        string reason, string instruction)
    {
        var state = new GuidanceState();
        var frame = Frame(1, "PAUSED");
        frame.guidance.hold_progress = progress;
        frame.guidance.hold_remaining_ms = remaining;
        frame.guidance.reason = reason;
        frame.next_action = instruction;
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Presentation(1.02).Instruction, Is.EqualTo(instruction));
        Assert.That(state.Presentation(1.02).HoldProgress, Is.EqualTo(progress));
    }
}
