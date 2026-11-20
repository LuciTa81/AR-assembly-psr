using ARAssembly;
using NUnit.Framework;

public class GuidanceStateTests
{
    private static GuidanceSnapshot Frame(long id = 1, string session = "session-a")
    {
        return new GuidanceSnapshot {
            schema_version = "realtime_v1", session_id = session, frame_id = id,
            timestamp_ms = 1000 + id * 100, frame_age_ms = 50,
            system_status = "RUNNING", marker_status = "OK",
            current_state = "S2", current_label = "Lid closed",
            next_action = "Fasten screw A", target = "screw_a"
        };
    }

    [Test]
    public void NewFrameProvidesServerStateWithoutInferringAnotherStage()
    {
        var state = new GuidanceState();
        Assert.That(state.Apply(Frame(), 1, 1.05), Is.True);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
        Assert.That(state.LastSnapshot.next_action, Is.EqualTo("Fasten screw A"));
        Assert.That(state.Status(1.1), Is.EqualTo("LIVE"));
        Assert.That(state.ShowTestRing(1.1, true), Is.True);
        Assert.That(state.ShowTestRing(1.1, false), Is.False);
    }

    [Test]
    public void ServerAgeAndRoundTripTimeReduceRemainingLifetime()
    {
        var state = new GuidanceState();
        var frame = Frame();
        frame.frame_age_ms = 300;
        state.Apply(frame, 1, 1.1);
        Assert.That(state.ShowTestRing(1.15, true), Is.True);
        Assert.That(state.Status(1.201), Is.EqualTo("STALE"));
        Assert.That(state.ShowTestRing(1.201, true), Is.False);
    }

    [Test]
    public void DuplicateFrameDoesNotExtendLifetimeOrChangeStep()
    {
        var state = new GuidanceState();
        state.Apply(Frame(), 1, 1.01);
        var duplicate = Frame();
        duplicate.current_state = "S5";
        duplicate.frame_age_ms = 0;
        Assert.That(state.Apply(duplicate, 1.3, 1.31), Is.False);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
        Assert.That(state.Status(1.6), Is.EqualTo("STALE"));
    }

    [Test]
    public void StaleFirstResponseNeverBecomesCurrentInstruction()
    {
        var state = new GuidanceState();
        var frame = Frame();
        frame.frame_age_ms = 600;
        Assert.That(state.Apply(frame, 1, 1.01), Is.False);
        Assert.That(state.LastSnapshot, Is.Null);
        Assert.That(state.Status(1.1), Is.EqualTo("STALE"));
    }

    [TestCase("LOST")]
    [TestCase("FALLBACK")]
    [TestCase("DISABLED")]
    [TestCase("UNSTABLE")]
    public void InvalidTrackingHidesRingButKeepsStage(string marker)
    {
        var state = new GuidanceState();
        var frame = Frame();
        frame.marker_status = marker;
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Status(1.1), Is.EqualTo("TRACKING_LOST"));
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
        Assert.That(state.ShowTestRing(1.1, true), Is.False);
    }

    [Test]
    public void DisconnectKeepsLastStageButDuplicateCannotReviveGuidance()
    {
        var state = new GuidanceState();
        state.Apply(Frame(), 1, 1.01);
        state.Disconnect();
        Assert.That(state.Status(1.1), Is.EqualTo("DISCONNECTED"));
        Assert.That(state.ShowTestRing(1.1, true), Is.False);
        state.Apply(Frame(), 1.15, 1.16);
        Assert.That(state.ShowTestRing(1.2, true), Is.False);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
        state.Apply(Frame(2), 1.2, 1.21);
        Assert.That(state.ShowTestRing(1.25, true), Is.True);
    }

    [Test]
    public void EarlierFrameDoesNotRewindState()
    {
        var state = new GuidanceState();
        state.Apply(Frame(10), 1, 1.01);
        Assert.That(state.Apply(Frame(9), 1.1, 1.11), Is.False);
        Assert.That(state.LastSnapshot.frame_id, Is.EqualTo(10));
        Assert.That(state.ShowTestRing(1.15, true), Is.False);
    }

    [Test]
    public void TimestampCannotMoveBackwardWithinSession()
    {
        var state = new GuidanceState();
        state.Apply(Frame(10), 1, 1.01);
        var next = Frame(11);
        next.timestamp_ms = 1200;
        Assert.That(state.Apply(next, 1.1, 1.11), Is.False);
        Assert.That(state.LastSnapshot.frame_id, Is.EqualTo(10));
    }

    [Test]
    public void NewSessionAcceptsResetFrameNumber()
    {
        var state = new GuidanceState();
        state.Apply(Frame(10), 1, 1.01);
        var next = Frame(1, "session-b");
        next.current_state = "S0";
        Assert.That(state.Apply(next, 1.1, 1.11), Is.True);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S0"));
        Assert.That(state.LastSnapshot.session_id, Is.EqualTo("session-b"));
    }

    [Test]
    public void NewSessionWithUnstableMarkersReplacesOldStageButHidesRing()
    {
        var state = new GuidanceState();
        state.Apply(Frame(10), 1, 1.01);
        var next = Frame(1, "session-b");
        next.current_state = "S0";
        next.marker_status = "UNSTABLE";
        Assert.That(state.Apply(next, 1.1, 1.11), Is.True);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S0"));
        Assert.That(state.Status(1.2), Is.EqualTo("TRACKING_LOST"));
        Assert.That(state.ShowTestRing(1.2, true), Is.False);
    }

    [Test]
    public void LastScrewObservationIsNotClaimedAsCompletedAssembly()
    {
        var state = new GuidanceState();
        var frame = Frame();
        frame.current_state = "S6";
        frame.target = "complete";
        frame.next_action = "Confirm assembly sequence completion";
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Status(1.1), Is.EqualTo("AWAITING_CONFIRMATION"));
        Assert.That(state.ShowTestRing(1.1, true), Is.False);
    }

    [TestCase("schema")]
    [TestCase("session")]
    [TestCase("frame")]
    [TestCase("timestamp")]
    [TestCase("age")]
    [TestCase("state")]
    [TestCase("action")]
    [TestCase("system")]
    [TestCase("marker")]
    public void MissingOrInvalidContractFailsClosed(string field)
    {
        var state = new GuidanceState();
        var frame = Frame();
        switch (field) {
            case "schema": frame.schema_version = null; break;
            case "session": frame.session_id = ""; break;
            case "frame": frame.frame_id = 0; break;
            case "timestamp": frame.timestamp_ms = 0; break;
            case "age": frame.frame_age_ms = -1; break;
            case "state": frame.current_state = "S8"; break;
            case "action": frame.next_action = null; break;
            case "system": frame.system_status = "ERROR"; break;
            case "marker": frame.marker_status = "unexpected"; break;
        }
        Assert.That(state.Apply(frame, 1, 1.01), Is.False);
        Assert.That(state.Status(1.1), Is.EqualTo("INVALID_DATA"));
        Assert.That(state.ShowTestRing(1.1, true), Is.False);
    }

    [Test]
    public void InvalidJsonClearsVisibleInstructionUntilNewValidFrame()
    {
        var state = new GuidanceState();
        state.Apply(Frame(), 1, 1.01);
        state.InvalidResponse();
        Assert.That(state.Status(1.1), Is.EqualTo("INVALID_DATA"));
        Assert.That(state.ShowTestRing(1.1, true), Is.False);
    }

    [Test]
    public void SlowHttpResponseIsAlreadyStaleOnArrival()
    {
        var state = new GuidanceState();
        Assert.That(state.Apply(Frame(), 1, 1.7), Is.False);
        Assert.That(state.Status(1.7), Is.EqualTo("STALE"));
    }
}
