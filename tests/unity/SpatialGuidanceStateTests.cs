using System;
using System.IO;
using System.Text.Json;
using ARAssembly;
using NUnit.Framework;

public class SpatialGuidanceStateTests
{
    public static SpatialPreviewConfig Config() => new SpatialPreviewConfig {
        schema_version = "beast_spatial_preview_config_v1", session_id = "synthetic-r2",
        state_url = "http://127.0.0.1:18765/state.json", duration_seconds = 30,
        display_profile_id = "synthetic-display-r2", camera_profile_id = "synthetic-camera",
        workspace_profile_id = "synthetic-workspace",
        camera_profile_sha256 = new string('a', 64), workspace_profile_sha256 = new string('b', 64)
    };

    public static GuidanceSnapshot Frame(long id = 8, long pose = 7)
    {
        using (var json = JsonDocument.Parse(File.ReadAllText(Path.Combine(
            TestContext.CurrentContext.TestDirectory, "spatial_guidance_v1.json")))) {
            var value = JsonSerializer.Deserialize<GuidanceSnapshot>(json.RootElement.GetProperty("expected").GetRawText(),
                new JsonSerializerOptions { IncludeFields = true });
            value.frame_id = id;
            value.timestamp_ms = 1020 + (id - 8) * 100;
            value.spatial.pose_frame_id = pose;
            value.spatial.pose_timestamp_ms = 1000 + (pose - 7) * 100;
            return value;
        }
    }

    public static GuidanceState State(SpatialPreviewConfig config = null)
    {
        var state = new GuidanceState(config ?? Config());
        state.Spatial.ObserveOutput("Laptop", 1536, 432, true);
        return state;
    }

    [Test]
    public void NoLocalProfileCannotEnableRingsEvenIfServerClaimsVerified()
    {
        var state = new GuidanceState();
        var frame = Frame();
        frame.spatial.calibration_status = "verified";
        frame.spatial.display_alignment_verified = true;
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Spatial.Status(1.02), Is.EqualTo("NOT_CALIBRATED"));
        Assert.That(state.Spatial.TryGetPixels(1.02, out _), Is.False);
    }

    [Test]
    public void PoseExpiresEarlierThanStateWithFullRoundTripAndLocalElapsed()
    {
        var state = State();
        Assert.That(state.Apply(Frame(), 1, 1.05), Is.True);
        Assert.That(state.Spatial.TryGetPixels(1.10, out var pixels), Is.True);
        Assert.That(pixels.LeftX, Is.EqualTo(1008));
        Assert.That(pixels.RightX, Is.EqualTo(908.8));
        Assert.That(state.Spatial.Status(1.126), Is.EqualTo("STALE_POSE"));
        Assert.That(state.Status(1.126), Is.EqualTo("LIVE"));
        Assert.That(state.Spatial.TryGetPixels(1.126, out _), Is.False);
    }

    [Test]
    public void DuplicatePoseOnNewStateFrameCannotRefreshDeadlineOrChangeCoordinates()
    {
        var state = State();
        state.Apply(Frame(), 1, 1.01);
        var duplicate = Frame(9, 7);
        duplicate.spatial.pose_age_ms = 0;
        duplicate.spatial.left_pixel[0] = 1300;
        state.Apply(duplicate, 1.1, 1.11);
        Assert.That(state.Spatial.TryGetPixels(1.12, out var pixels), Is.True);
        Assert.That(pixels.LeftX, Is.EqualTo(1008));
        Assert.That(state.Spatial.TryGetPixels(1.126, out _), Is.False);
    }

    [Test]
    public void CallerMutationCannotChangeAcceptedCoordinatesOrPinnedProfile()
    {
        var config = Config();
        var state = State(config);
        var frame = Frame();
        state.Apply(frame, 1, 1.01);
        frame.spatial.left_pixel[0] = 700;
        config.display_profile_id = "changed";
        Assert.That(state.Spatial.TryGetPixels(1.02, out var pixels), Is.True);
        Assert.That(pixels.LeftX, Is.EqualTo(1008));
        state.Apply(Frame(9, 8), 1.03, 1.04);
        Assert.That(state.Spatial.Status(1.05), Is.EqualTo("SYNTHETIC_PREVIEW"));
    }

    [TestCase("disconnect")]
    [TestCase("invalid")]
    [TestCase("lost")]
    [TestCase("hidden")]
    public void FailureRequiresNewPoseNotDuplicateSuccess(string fault)
    {
        var state = State();
        state.Apply(Frame(), 1, 1.01);
        if (fault == "disconnect") state.Disconnect();
        else if (fault == "invalid") state.InvalidResponse();
        else {
            var lost = Frame(9, 7);
            if (fault == "lost") lost.marker_status = "LOST";
            else { lost.spatial.target_visible = false; lost.spatial.reason = "no_pose"; }
            state.Apply(lost, 1.02, 1.03);
        }
        state.Apply(Frame(10, 7), 1.04, 1.05);
        Assert.That(state.Spatial.TryGetPixels(1.06, out _), Is.False);
        state.Apply(Frame(11, 8), 1.07, 1.08);
        Assert.That(state.Spatial.TryGetPixels(1.09, out _), Is.True);
    }

    [Test]
    public void HiddenNewObservationIsRememberedSoSameIdCannotBecomeFreshAgain()
    {
        var state = State();
        state.Apply(Frame(), 1, 1.01);
        var lost = Frame(9, 8);
        lost.spatial.target_visible = false;
        lost.spatial.reason = "no_pose";
        state.Apply(lost, 1.02, 1.03);
        state.Apply(Frame(10, 8), 1.04, 1.05);
        Assert.That(state.Spatial.TryGetPixels(1.06, out _), Is.False);
        state.Apply(Frame(11, 9), 1.07, 1.08);
        Assert.That(state.Spatial.TryGetPixels(1.09, out _), Is.True);
    }

    [TestCase("profile")]
    [TestCase("camera_hash")]
    [TestCase("workspace_hash")]
    [TestCase("session")]
    [TestCase("schema")]
    [TestCase("convention")]
    [TestCase("channel")]
    [TestCase("size")]
    [TestCase("verified")]
    [TestCase("target")]
    [TestCase("null")]
    [TestCase("nan")]
    [TestCase("outside")]
    [TestCase("margin")]
    [TestCase("missing_age")]
    [TestCase("future")]
    [TestCase("timestamp")]
    [TestCase("slow")]
    public void InvalidSpatialNeverLeavesPreviousRingVisible(string fault)
    {
        var state = State();
        state.Apply(Frame(), 1, 1.01);
        var next = Frame(9, 8);
        double finished = 1.04;
        switch (fault) {
            case "profile": next.spatial.display_profile_id = "other"; break;
            case "camera_hash": next.spatial.camera_profile_sha256 = new string('c', 64); break;
            case "workspace_hash": next.spatial.workspace_profile_sha256 = new string('c', 64); break;
            case "session": next.session_id = "other"; break;
            case "schema": next.spatial.schema_version = "other"; break;
            case "convention": next.spatial.coordinate_convention = "bottom_left"; break;
            case "channel": next.spatial.channel_order = "swapped"; break;
            case "size": next.spatial.eye_width = 960; break;
            case "verified": next.spatial.display_alignment_verified = true; break;
            case "target": next.spatial.target_id = "B"; break;
            case "null": next.spatial = null; break;
            case "nan": next.spatial.left_pixel[0] = double.NaN; break;
            case "outside": next.spatial.right_pixel[0] = 1921; break;
            case "margin": next.spatial.left_pixel[0] = 5; break;
            case "missing_age": next.spatial.pose_age_ms = -1; break;
            case "future": next.spatial.pose_timestamp_ms = next.timestamp_ms + 1; break;
            case "timestamp": next.spatial.pose_timestamp_ms = -1; break;
            case "slow": finished = 1.3; break;
        }
        state.Apply(next, 1.03, finished);
        Assert.That(state.Spatial.TryGetPixels(finished + .001, out _), Is.False);
    }

    [TestCase("missing_age")]
    [TestCase("schema")]
    [TestCase("size")]
    [TestCase("missing_reason")]
    [TestCase("missing_timestamp")]
    [TestCase("future_timestamp")]
    public void RejectedBoundObservationCannotRecoverByRepairingSameId(string fault)
    {
        var state = State();
        state.Apply(Frame(), 1, 1.01);
        var rejected = Frame(9, 8);
        switch (fault) {
            case "missing_age": rejected.spatial.pose_age_ms = -1; break;
            case "schema": rejected.spatial.schema_version = "other"; break;
            case "size": rejected.spatial.eye_width = 960; break;
            case "missing_reason": rejected.spatial.reason = null; break;
            case "missing_timestamp": rejected.spatial.pose_timestamp_ms = -1; break;
            case "future_timestamp": rejected.spatial.pose_timestamp_ms = rejected.timestamp_ms + 1000; break;
        }
        state.Apply(rejected, 1.02, 1.03);
        Assert.That(state.Spatial.Status(1.031), Is.EqualTo("INVALID_SPATIAL"));
        state.Apply(Frame(9, 8), 1.04, 1.05);
        Assert.That(state.Spatial.TryGetPixels(1.051, out _), Is.False, "Same parent and pose cannot recover");
        state.Apply(Frame(10, 8), 1.06, 1.07);
        Assert.That(state.Spatial.TryGetPixels(1.071, out _), Is.False, "New parent cannot repair the old pose");
        state.Apply(Frame(11, 9), 1.08, 1.09);
        Assert.That(state.Spatial.TryGetPixels(1.091, out _), Is.True);
    }

    [TestCase("older")]
    [TestCase("duplicate_timestamp_changed")]
    [TestCase("new_id_same_timestamp")]
    public void PoseOrderCannotBeRewritten(string fault)
    {
        var state = State();
        state.Apply(Frame(10, 9), 1, 1.01);
        var next = Frame(11, fault == "older" ? 8 : fault == "duplicate_timestamp_changed" ? 9 : 10);
        if (fault == "duplicate_timestamp_changed") next.spatial.pose_timestamp_ms++;
        if (fault == "new_id_same_timestamp") next.spatial.pose_timestamp_ms = 1200;
        state.Apply(next, 1.03, 1.04);
        Assert.That(state.Spatial.TryGetPixels(1.05, out _), Is.False);
    }

    [Test]
    public void DuplicateParentCannotSmuggleDifferentStageOrTarget()
    {
        var state = State();
        state.Apply(Frame(), 1, 1.01);
        var duplicate = Frame();
        duplicate.current_state = "S3";
        duplicate.target = "screw_b";
        duplicate.spatial.target_id = "B";
        state.Apply(duplicate, 1.02, 1.03);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
        Assert.That(state.Spatial.TryGetPixels(1.04, out _), Is.False);
    }

    [TestCase("S2", "screw_a", "A")]
    [TestCase("S3", "screw_b", "B")]
    [TestCase("S4", "screw_c", "C")]
    [TestCase("S5", "screw_d", "D")]
    public void EachAssemblyStepUsesServerSelectedTarget(string step, string target, string id)
    {
        var state = State();
        var frame = Frame();
        frame.current_state = step; frame.target = target; frame.spatial.target_id = id;
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Spatial.TryGetPixels(1.02, out _), Is.True);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo(step));
    }

    [TestCase("S0")]
    [TestCase("S1")]
    [TestCase("S6")]
    public void NonScrewStepCannotShowPreviousTarget(string step)
    {
        var state = State();
        var frame = Frame();
        frame.current_state = step;
        state.Apply(frame, 1, 1.01);
        Assert.That(state.Spatial.TryGetPixels(1.02, out _), Is.False);
    }

    [TestCase("size")]
    [TestCase("display")]
    [TestCase("fullscreen")]
    public void OutputChangesLatchHiddenUntilRestart(string kind)
    {
        var state = State();
        state.Apply(Frame(), 1, 1.01);
        state.Spatial.ObserveOutput(kind == "display" ? "Other" : "Laptop", kind == "size" ? 1280 : 1536,
            432, kind != "fullscreen");
        state.Spatial.ObserveOutput("Laptop", 1536, 432, true);
        state.Apply(Frame(9, 8), 1.03, 1.04);
        Assert.That(state.Spatial.Status(1.05), Is.EqualTo("DISPLAY_CHANGED"));
        Assert.That(state.Spatial.TryGetPixels(1.05, out _), Is.False);
    }

    [Test]
    public void SyntheticPreviewCannotUseVitureOutput()
    {
        var state = new GuidanceState(Config());
        state.Spatial.ObserveOutput("VITURE Beast", 3840, 1080, true);
        state.Apply(Frame(), 1, 1.01);
        Assert.That(state.Spatial.TryGetPixels(1.02, out _), Is.False);
    }

    [TestCase("http://example.com/state.json")]
    [TestCase("http://127.0.0.1:123/state.json?extra=1")]
    [TestCase("http://user@127.0.0.1:123/state.json")]
    public void PreviewConfigCannotChooseRemoteOrAmbiguousEndpoint(string endpoint)
    {
        var config = Config(); config.state_url = endpoint;
        Assert.Throws<ArgumentException>(() => new GuidanceState(config));
    }

    [Test]
    public void SbsOptionsRejectMixedAndMissingModes()
    {
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(new[] {"--spatial-preview-config"}));
        foreach (string flag in new[] {"--test-ring", "--alignment-probe", "--stereo-alignment-probe", "--display-name"})
            Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(
                new[] {"--spatial-preview-config", "preview.json", flag, "VITURE"}));
        Assert.That(SbsGuidanceOptions.Parse(new[] {"--spatial-preview-config", "preview.json"}).Enabled, Is.True);
        Assert.That(SbsGuidanceOptions.Parse(new[] {"--sbs-guidance"}).PreviewPath, Is.Null);
    }
}
