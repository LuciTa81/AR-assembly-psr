using System;
using NUnit.Framework;

namespace ARAssembly.Tests
{
    public class ActionGuidanceTextTests
    {
        private static GuidanceSnapshot Frame(string step, string reason = "") => new GuidanceSnapshot {
            current_state = step, guidance = new AssemblyGuidance { reason = reason }
        };

        [TestCase("S0", "상자 배치", "상자를 놓아주세요")]
        [TestCase("S1", "뚜껑 닫기", "뚜껑을 덮어주세요")]
        [TestCase("S2", "나사 A · 1/4", "드라이버 끝을 나사 A에 맞춰주세요")]
        [TestCase("S3", "나사 B · 2/4", "드라이버 끝을 나사 B에 맞춰주세요")]
        [TestCase("S4", "나사 C · 3/4", "드라이버 끝을 나사 C에 맞춰주세요")]
        [TestCase("S5", "나사 D · 4/4", "드라이버 끝을 나사 D에 맞춰주세요")]
        public void ActiveStagesShowOneAction(string step, string title, string action)
        {
            var text = ActionGuidanceText.From(new GuidancePresentation { Status = "GUIDING" }, Frame(step));
            Assert.That(text.Title, Is.EqualTo(title));
            Assert.That(text.Action, Is.EqualTo(action));
            Assert.That(text.NeedsAttention, Is.False);
        }

        [Test]
        public void DelayedGreenStillAsksToWorkAndNeverClaimsFasteningComplete()
        {
            var delay = new ObservedCueDelay(2000);
            var observed = new GuidancePresentation { Status = "OBSERVED" };
            var frame = Frame("S2");
            Assert.That(ActionGuidanceText.From(delay.Apply(observed, "A", 1), frame).Action,
                Is.EqualTo("나사 A를 조여주세요"));
            Assert.That(ActionGuidanceText.From(delay.Apply(observed, "A", 2.99), frame).Action,
                Is.EqualTo("나사 A를 조여주세요"));
            Assert.That(ActionGuidanceText.From(delay.Apply(observed, "A", 3), frame).Action,
                Is.EqualTo("드라이버를 떼어주세요"));
        }

        [Test]
        public void RecheckAsksToAlignRatherThanContinueFastening()
        {
            var text = ActionGuidanceText.From(new GuidancePresentation {
                Status = "GUIDING", HoldProgress = "recheck"
            }, Frame("S3"));
            Assert.That(text.Action, Is.EqualTo("드라이버 끝을 나사 B에 맞춰주세요"));
        }

        [TestCase("AWAITING_CONFIRMATION", "조립 상태를 확인해주세요")]
        [TestCase("COMPLETED", "조립 안내를 마쳤습니다")]
        public void FinalStageIsNotAutomaticallyCompleted(string status, string action)
        {
            Assert.That(ActionGuidanceText.From(new GuidancePresentation { Status = status }, Frame("S6")).Action,
                Is.EqualTo(action));
        }

        [TestCase("TRACKING_LOST", "작업대가 보이도록 바라봐주세요")]
        [TestCase("DISCONNECTED", "멈추고 연결을 확인해주세요")]
        [TestCase("INVALID_DATA", "멈추고 관제 화면을 확인해주세요")]
        [TestCase("DISPLAY_CHANGED", "화면 설정을 확인해주세요")]
        [TestCase("STALE", "잠시 멈추고 작업대를 봐주세요")]
        [TestCase("UNKNOWN", "멈추고 관제 화면을 확인해주세요")]
        public void FaultsCannotBecomeWorkInstructions(string status, string action)
        {
            var text = ActionGuidanceText.From(new GuidancePresentation { Status = status }, Frame("S2"));
            Assert.That(text.Action, Is.EqualTo(action));
            Assert.That(text.NeedsAttention, Is.True);
        }

        [TestCase("tool_not_visible", "드라이버가 보이도록 해주세요")]
        [TestCase("tool_position_unknown", "드라이버가 보이도록 해주세요")]
        [TestCase("multiple_tool_candidates", "드라이버 하나만 보여주세요")]
        [TestCase("marker_not_stable", "작업대가 보이도록 바라봐주세요")]
        [TestCase("observation_gap", "잠시 멈추고 작업대를 봐주세요")]
        public void PausesGiveConcreteActions(string reason, string action)
        {
            Assert.That(ActionGuidanceText.From(new GuidancePresentation { Status = "PAUSED" },
                Frame("S2", reason)).Action, Is.EqualTo(action));
        }

        [Test]
        public void StableRecoveryMessageDoesNotLeakChangingToolReasons()
        {
            var view = new GuidancePresentation { Status = "PAUSED",
                Instruction = "Checking input. Guidance paused." };
            Assert.That(ActionGuidanceText.From(view, Frame("S2", "tool_not_visible")).Action,
                Is.EqualTo("잠시 멈추고 작업대를 봐주세요"));
        }

        [Test]
        public void UnavailablePositionCannotInviteScrewWork()
        {
            var view = new GuidancePresentation { Status = "GUIDING" };
            Assert.That(ActionGuidanceText.From(view, Frame("S3"), "Checking position").NeedsAttention, Is.True);
            Assert.That(ActionGuidanceText.From(view, Frame("S3"), "Return to the tested working distance").Action,
                Is.EqualTo("원래 작업 거리로 돌아와주세요"));
        }

        [Test]
        public void WaitingAndMalformedStepsAreNonActionable()
        {
            Assert.That(ActionGuidanceText.From(new GuidancePresentation { Status = "WAITING" }, null).Action,
                Is.EqualTo("작업대를 바라봐주세요"));
            Assert.That(ActionGuidanceText.From(new GuidancePresentation { Status = "GUIDING" }, Frame("S9")).NeedsAttention,
                Is.True);
        }

        [Test]
        public void OptionIsExplicitAndRequiresGuidance()
        {
            Assert.That(SbsGuidanceOptions.Parse(new[] { "--sbs-guidance" }).ActionKorean, Is.False);
            Assert.That(SbsGuidanceOptions.Parse(new[] { "--sbs-guidance", "--action-korean" }).ActionKorean, Is.True);
            Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(new[] { "--action-korean" }));
        }

        private static GuidanceSnapshot SessionFrame(string step = "S2", string session = "test")
        {
            var frame = Frame(step);
            frame.session_id = session;
            return frame;
        }

        [TestCase("S0", "TRACKING_LOST", "STATE TRACKING_LOST", "상자를 놓아주세요")]
        [TestCase("S1", "TRACKING_LOST", "STATE TRACKING_LOST", "뚜껑을 덮어주세요")]
        [TestCase("S0", "STALE", "STATE STALE", "상자를 놓아주세요")]
        [TestCase("S1", "STALE", "STATE STALE", "뚜껑을 덮어주세요")]
        [TestCase("S0", "PAUSED", "NO STAGE TARGET", "상자를 놓아주세요")]
        [TestCase("S1", "PAUSED", "NO STAGE TARGET", "뚜껑을 덮어주세요")]
        public void BriefPreparationLossKeepsInstructionButNotTracking(
            string step, string status, string gate, string action)
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame(step);
            frame.guidance.reason = "operator_confirmation";
            display.Apply(new GuidancePresentation { Status = "GUIDING" }, frame, "NO STAGE TARGET", null, 1);
            var loss = new GuidancePresentation { Status = status, ShowTarget = false };
            var text = display.Apply(loss, frame, gate, "Checking position", 1.3);
            Assert.That(text.Action, Is.EqualTo(action));
            Assert.That(text.Tone, Is.EqualTo(ActionGuidanceTone.Approach));
            Assert.That(text.Retained, Is.True);
            Assert.That(loss.Status, Is.EqualTo(status));
            Assert.That(loss.ShowTarget, Is.False);
            Assert.That(frame.current_state, Is.EqualTo(step));
            Assert.That(frame.guidance.reason, Is.EqualTo("operator_confirmation"));
        }

        [TestCase("S0")]
        [TestCase("S1")]
        public void PreparationRetentionExpiresAtBoundaryWithoutRenewingOnLoss(string step)
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame(step);
            var active = new GuidancePresentation { Status = "GUIDING" };
            var loss = new GuidancePresentation { Status = "TRACKING_LOST" };
            display.Apply(active, frame, "NO STAGE TARGET", null, 1);
            Assert.That(display.Apply(loss, frame, "STATE TRACKING_LOST", null, 1.74).Retained, Is.True);
            var expired = display.Apply(new GuidancePresentation { Status = "STALE" }, frame,
                "STATE STALE", null, 1.75);
            Assert.That(expired.Retained, Is.False);
            Assert.That(expired.NeedsAttention, Is.True);
            Assert.That(display.Apply(loss, frame, "STATE TRACKING_LOST", null, 1.8).Retained, Is.False);
            Assert.That(display.Apply(active, frame, "NO STAGE TARGET", null, 2).Retained, Is.False);
            Assert.That(display.Apply(loss, frame, "STATE TRACKING_LOST", null, 2.1).Retained, Is.True);
        }

        [TestCase("S0", "S1", "test")]
        [TestCase("S1", "S2", "test")]
        [TestCase("S0", "S0", "new-session")]
        [TestCase("S1", "S1", "new-session")]
        [TestCase("S0", "S0", "")]
        public void PreparationLossCannotCarryInstructionAcrossStageOrSession(
            string before, string after, string session)
        {
            var display = new ActionGuidanceDisplay();
            display.Apply(new GuidancePresentation { Status = "GUIDING" }, SessionFrame(before),
                "NO STAGE TARGET", null, 1);
            var text = display.Apply(new GuidancePresentation { Status = "TRACKING_LOST" },
                SessionFrame(after, session), "STATE TRACKING_LOST", null, 1.1);
            Assert.That(text.Retained, Is.False);
            Assert.That(text.NeedsAttention, Is.True);
        }

        [TestCase("S0", "DISCONNECTED", "STATE DISCONNECTED")]
        [TestCase("S1", "INVALID_DATA", "STATE INVALID_DATA")]
        [TestCase("S0", "PAUSED", "DISPLAY CHANGED")]
        [TestCase("S1", "PAUSED", "PROFILE ERROR")]
        public void PreparationHardFaultDiscardsInstructionImmediately(string step, string status, string gate)
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame(step);
            display.Apply(new GuidancePresentation { Status = "GUIDING" }, frame, "NO STAGE TARGET", null, 1);
            var text = display.Apply(new GuidancePresentation { Status = status }, frame, gate, null, 1.1);
            Assert.That(text.Retained, Is.False);
            Assert.That(text.NeedsAttention, Is.True);
            Assert.That(display.Apply(new GuidancePresentation { Status = "TRACKING_LOST" }, frame,
                "STATE TRACKING_LOST", null, 1.2).Retained, Is.False);
        }

        [TestCase("S0")]
        [TestCase("S1")]
        public void PreparationLossBeforeFirstUsableFrameStillRequestsTracking(string step)
        {
            var text = new ActionGuidanceDisplay().Apply(new GuidancePresentation { Status = "TRACKING_LOST" },
                SessionFrame(step), "STATE TRACKING_LOST", null, 1);
            Assert.That(text.Retained, Is.False);
            Assert.That(text.NeedsAttention, Is.True);
        }

        [TestCase("GUIDING", ActionGuidanceTone.Approach, "드라이버 끝을 나사 A에 맞춰주세요")]
        [TestCase("OBSERVING", ActionGuidanceTone.Working, "나사 A를 조여주세요")]
        [TestCase("OBSERVED", ActionGuidanceTone.Release, "드라이버를 떼어주세요")]
        public void BriefLossPreservesTheActionAndItsColorWithoutChangingSpatialValidity(
            string status, ActionGuidanceTone tone, string action)
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame();
            display.Apply(new GuidancePresentation { Status = status }, frame, "VISIBLE", null, 1);
            var loss = new GuidancePresentation { Status = "PAUSED", ShowTarget = false };
            var text = display.Apply(loss, frame, "POSE STALE", "Checking position", 1.3);
            Assert.That(text.Action, Is.EqualTo(action));
            Assert.That(text.Tone, Is.EqualTo(tone));
            Assert.That(text.Retained, Is.True);
            Assert.That(loss.ShowTarget, Is.False);
        }

        [Test]
        public void ChangingLossReasonsCannotExtendTheRetentionBudget()
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame();
            display.Apply(new GuidancePresentation { Status = "OBSERVED" }, frame, "VISIBLE", null, 1);
            display.Apply(new GuidancePresentation { Status = "PAUSED" }, frame, "POSE STALE", "Checking position", 1.4);
            var expired = display.Apply(new GuidancePresentation { Status = "TRACKING_LOST" }, frame,
                "STATE TRACKING_LOST", "Bring the workspace markers into view", 1.76);
            Assert.That(expired.NeedsAttention, Is.True);
            Assert.That(expired.Retained, Is.False);
            Assert.That(expired.Tone, Is.EqualTo(ActionGuidanceTone.Attention));
        }

        [TestCase("S3", "test")]
        [TestCase("S2", "new-session")]
        public void AnotherStageOrSessionCannotInheritAnAction(string step, string session)
        {
            var display = new ActionGuidanceDisplay();
            display.Apply(new GuidancePresentation { Status = "OBSERVED" }, SessionFrame(), "VISIBLE", null, 1);
            var text = display.Apply(new GuidancePresentation { Status = "PAUSED" }, SessionFrame(step, session),
                "POSE STALE", "Checking position", 1.1);
            Assert.That(text.NeedsAttention, Is.True);
            Assert.That(text.Retained, Is.False);
        }

        [TestCase("DISCONNECTED", "STATE DISCONNECTED")]
        [TestCase("INVALID_DATA", "VISIBLE")]
        [TestCase("PAUSED", "PROFILE ERROR")]
        [TestCase("GUIDING", "DISPLAY CHANGED")]
        [TestCase("GUIDING", "OUTSIDE TARGET DEPTH")]
        public void HardFaultClearsThePreviousActionImmediately(string status, string gate)
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame();
            display.Apply(new GuidancePresentation { Status = "OBSERVED" }, frame, "VISIBLE", null, 1);
            Assert.That(display.Apply(new GuidancePresentation { Status = status }, frame,
                gate, "Position unavailable", 1.1).NeedsAttention, Is.True);
            Assert.That(display.Apply(new GuidancePresentation { Status = "PAUSED" }, frame,
                "POSE STALE", "Checking position", 1.2).Retained, Is.False);
        }

        [TestCase(double.NaN)]
        [TestCase(double.PositiveInfinity)]
        [TestCase(-1)]
        [TestCase(.9)]
        public void InvalidClockClearsRetention(double now)
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame();
            display.Apply(new GuidancePresentation { Status = "OBSERVING" }, frame, "VISIBLE", null, 1);
            Assert.That(display.Apply(new GuidancePresentation { Status = "PAUSED" }, frame,
                "POSE STALE", "Checking position", now).Retained, Is.False);
            Assert.That(display.Apply(new GuidancePresentation { Status = "PAUSED" }, frame,
                "POSE STALE", "Checking position", 1.2).Retained, Is.False);
        }

        [Test]
        public void RecoveryAndGreenDelayRemainControlledByTheCurrentObservation()
        {
            var display = new ActionGuidanceDisplay();
            var delay = new ObservedCueDelay(2000);
            var frame = SessionFrame();
            var observed = new GuidancePresentation { Status = "OBSERVED" };
            var first = display.Apply(delay.Apply(observed, "A", 1), frame, "VISIBLE", null, 1);
            Assert.That(first.Tone, Is.EqualTo(ActionGuidanceTone.Working));
            var loss = display.Apply(delay.Apply(new GuidancePresentation { Status = "PAUSED" }, "A", 1.2),
                frame, "POSE STALE", "Checking position", 1.2);
            Assert.That(loss.Tone, Is.EqualTo(ActionGuidanceTone.Working));
            var green = display.Apply(delay.Apply(observed, "A", 3), frame, "VISIBLE", null, 3);
            Assert.That(green.Tone, Is.EqualTo(ActionGuidanceTone.Release));
            Assert.That(green.Retained, Is.False);
            var recheck = display.Apply(new GuidancePresentation { Status = "GUIDING", HoldProgress = "recheck" },
                frame, "VISIBLE", null, 3.1);
            Assert.That(recheck.Tone, Is.EqualTo(ActionGuidanceTone.Approach));
        }

        [TestCase("recheck", "observation_gap")]
        [TestCase("none", "multiple_tool_candidates")]
        public void ExplicitRecheckOrAmbiguousToolClearsGreenImmediately(string progress, string reason)
        {
            var display = new ActionGuidanceDisplay();
            var frame = SessionFrame();
            display.Apply(new GuidancePresentation { Status = "OBSERVED" }, frame, "VISIBLE", null, 1);
            frame.guidance.reason = reason;
            var text = display.Apply(new GuidancePresentation { Status = "PAUSED", HoldProgress = progress },
                frame, "POSE STALE", "Checking position", 1.1);
            Assert.That(text.NeedsAttention, Is.True);
            Assert.That(text.Retained, Is.False);
        }
    }
}
