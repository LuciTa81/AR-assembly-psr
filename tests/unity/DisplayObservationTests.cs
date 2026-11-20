using System;
using System.IO;
using ARAssembly;
using NUnit.Framework;

public class DisplayObservationTests
{
    [TestCase("left")] [TestCase("right")]
    public void SingleEyeCaptureRequiresWearingSetup(string eye)
    {
        var state = State();
        if (eye == "right") state.Select(StereoProbeView.Right, 2);
        var config = Config(); config.setup_id = null;
        Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.Create(config, Observation(),
            state.PreviewMark(2), 3840, 1080, 2, 2));
    }

    [TestCase("missing")] [TestCase("frame")] [TestCase("motion")]
    [TestCase("span")] [TestCase("count")] [TestCase("nan")]
    public void StoreRejectsUnstableSingleEyeWithoutWriting(string change)
    {
        string directory = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try {
            var config = Config(directory);
            var store = new DisplayCorrespondenceStore(config);
            var candidate = StableCandidate(DisplayCorrespondenceRules.Create(config, Observation(),
                State().PreviewMark(2), 3840, 1080, 2, 2));
            if (change == "missing") candidate.stability = null;
            if (change == "frame") candidate.stability.last_frame_id = 3;
            if (change == "motion") candidate.stability.max_target_delta_mm = 3;
            if (change == "span") candidate.stability.span_ms = 100;
            if (change == "count") candidate.stability.distinct_frames = 1;
            if (change == "nan") candidate.stability.max_target_delta_mm = double.NaN;
            Assert.Throws<ArgumentException>(() => store.Save(candidate, "{}"));
            Assert.That(store.Count, Is.Zero);
            Assert.That(Directory.GetFiles(directory), Is.Empty);
        } finally { Directory.Delete(directory, true); }
    }

    private static DisplayCorrespondenceCandidate StableCandidate(DisplayCorrespondenceCandidate candidate)
    {
        candidate.observation.frame_id = 4;
        candidate.stability = new DisplayPairStability { distinct_frames = 4,
            first_frame_id = 1, last_frame_id = 4, span_ms = 300, max_target_delta_mm = 0 };
        return candidate;
    }

    private static DisplayObservationFeedback StableFeedback()
    {
        var feedback = new DisplayObservationFeedback();
        for (int i = 0; i < 4; i++) {
            var obs = Observation(); obs.frame_id = i + 1; obs.age_ms = 10;
            feedback.Apply(Config(), obs, 2 + i * .1, 2.01 + i * .1);
        }
        return feedback;
    }

    [Test]
    public void PairEvidenceNeedsDistinctStableFramesAndExpires()
    {
        var feedback = StableFeedback();
        var evidence = feedback.PairEvidence(2.32);
        Assert.That(evidence, Is.Not.Null);
        Assert.That(evidence.distinct_frames, Is.EqualTo(4));
        Assert.That(evidence.span_ms, Is.EqualTo(300).Within(.001));
        Assert.That(evidence.max_target_delta_mm, Is.Zero);
        Assert.That(feedback.PairEvidence(2.5), Is.Null);
    }

    [Test]
    public void DuplicatePollsCannotCreateStability()
    {
        var feedback = new DisplayObservationFeedback();
        for (int i = 0; i < 4; i++) {
            var obs = Observation(); obs.age_ms = 0;
            feedback.Apply(Config(), obs, 2 + i * .03, 2 + i * .03);
        }
        Assert.That(feedback.PairEvidence(2.1), Is.Null);
    }

    [TestCase("move")] [TestCase("lost")] [TestCase("gap")] [TestCase("restart")]
    public void PairEvidenceClearsOnMotionLossOrGap(string change)
    {
        var feedback = StableFeedback();
        Assert.That(feedback.PairEvidence(2.32), Is.Not.Null);
        var obs = Observation(); obs.frame_id = 5; obs.age_ms = 10;
        double started = 2.4;
        if (change == "move") obs.camera_xyz_mm[0] += 3;
        if (change == "lost") obs.status = "pose_rejected";
        if (change == "gap") started = 3;
        if (change == "restart") feedback.Fail("CONNECTION ERROR");
        feedback.Apply(Config(), obs, started, started + .01);
        Assert.That(feedback.PairEvidence(started + .02), Is.Null);
    }

    [Test]
    public void ConfirmedBothViewCreatesOneAtomicPairNotTwoIndependentObservations()
    {
        var state = State();
        state.Mark(2);
        state.Select(StereoProbeView.Right, 2);
        state.Mark(2);
        state.Select(StereoProbeView.Both, 2);
        var candidate = DisplayCorrespondenceRules.Create(Config(), Observation(),
            state.PreviewMark(2), 3840, 1080, 2, 2.02);
        Assert.That(candidate.schema_version, Is.EqualTo("beast_display_correspondence_pair_v2"));
        Assert.That(candidate.eye, Is.EqualTo("both"));
        Assert.That(candidate.setup_id, Is.EqualTo("fixed-fit-and-osd"));
        Assert.That(candidate.display.left_marked && candidate.display.right_marked, Is.True);
        Assert.That(candidate.observation.frame_id, Is.EqualTo(1));
        Assert.That(candidate.calibration_valid || candidate.display_alignment_verified, Is.False);
    }

    [Test]
    public void PairNeedsAnExplicitUnchangedWearingAndDisplaySetupId()
    {
        var state = State(); state.Mark(2);
        state.Select(StereoProbeView.Right, 2); state.Mark(2);
        state.Select(StereoProbeView.Both, 2);
        var config = Config(); config.setup_id = null;
        Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.Create(config, Observation(),
            state.PreviewMark(2), 3840, 1080, 2, 2));
    }

    [TestCase("size")] [TestCase("count")]
    public void PairContractMatchesOfflineReader(string change)
    {
        var state = State(); state.Mark(2);
        state.Select(StereoProbeView.Right, 2); state.Mark(2);
        state.Select(StereoProbeView.Both, 2);
        var point = state.PreviewMark(2);
        var observation = Observation();
        if (change == "size") point.height = 1200;
        else observation.marker_count = -1;
        Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.Create(Config(), observation,
            point, 3840, point.height, 2, 2));
    }

    [Test]
    public void PairSaveRejectsOverlappingPreviouslySavedEyeAndFrame()
    {
        string directory = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try {
            var config = Config(directory);
            var store = new DisplayCorrespondenceStore(config);
            var state = State();
            state.Mark(2); state.Select(StereoProbeView.Right, 2); state.Mark(2);
            state.Select(StereoProbeView.Both, 2);
            var pair = DisplayCorrespondenceRules.Create(config, Observation(), state.PreviewMark(2), 3840, 1080, 2, 2);
            StableCandidate(pair);
            Assert.That(File.Exists(store.Save(pair, "{}")), Is.True);
            var single = DisplayCorrespondenceRules.Create(config, Observation(), State().PreviewMark(2), 3840, 1080, 2, 2);
            StableCandidate(single);
            Assert.Throws<InvalidOperationException>(() => store.Save(single, "{}"));
            Assert.Throws<InvalidOperationException>(() => store.Save(pair, "{}"));
            Assert.That(store.Count, Is.EqualTo(1));
        } finally { Directory.Delete(directory, true); }
    }

    [Test]
    public void PoseHoldHintUsesFreshReasonsAndClearsOnRecovery()
    {
        var feedback = new DisplayObservationFeedback();
        var obs = Observation();
        obs.status = "pose_rejected";
        obs.reason_code = "marker_geometry";
        feedback.Apply(Config(), obs, 2, 2.01);
        string Hint(string gate, double now) => feedback.PresentationHint(gate, now);
        Assert.That(Hint("POSE NO POSE", 2.02), Does.Contain("marker layout"));
        Assert.That(Hint("POSE NO POSE", 2.2), Does.Contain("delayed"));
        Assert.That(Hint("STATE DISCONNECTED", 2.02), Does.Contain("connection"));
        Assert.That(Hint("DISPLAY CHANGED", 2.02), Does.Contain("Display"));
        obs = Observation(); obs.frame_id = 2;
        feedback.Apply(Config(), obs, 3, 3.01);
        Assert.That(Hint("VISIBLE", 3.02), Is.EqualTo("Reference visible"));
        feedback.Fail("CONNECTION ERROR");
        Assert.That(Hint("POSE CONNECTION ERROR", 3.03), Does.Not.Contain("marker layout"));
        Assert.That(feedback.TryGetCameraPoint(3.03, out _), Is.False);
    }

    [TestCase("insufficient_markers", "Too few")]
    [TestCase("solver_failed", "calculation")]
    [TestCase("pose_quality", "uncertain")]
    [TestCase("target_outside", "outside")]
    [TestCase(null, "unavailable")]
    [TestCase("<b>unknown</b>", "unavailable")]
    public void PoseHoldReasonsAreWhitelisted(string code, string expected)
    {
        var feedback = new DisplayObservationFeedback();
        var obs = Observation();
        obs.status = "pose_rejected"; obs.reason_code = code;
        feedback.Apply(Config(), obs, 2, 2.01);
        Assert.That(feedback.PresentationHint("POSE NO POSE", 2.02), Does.Contain(expected));
        Assert.That(feedback.PresentationHint("STATE INVALID_DATA", 2.02), Is.EqualTo("Position guide paused"));
        Assert.That(feedback.TryGetCameraPoint(2.02, out _), Is.False);
    }

    [Test]
    public void DiagnosticsSeparateResponseAgeAndRttWithoutExtendingFreshness()
    {
        var feedback = new DisplayObservationFeedback();
        var obs = Observation(); obs.age_ms = 140;
        feedback.Apply(Config(), obs, 2, 2.02);
        Assert.That(feedback.Status(2.02), Is.EqualTo("STALE"));
        Assert.That(feedback.DiagnosticFrameId, Is.EqualTo(1));
        Assert.That(feedback.DiagnosticResponseStatus, Is.EqualTo("tracking"));
        Assert.That(feedback.DiagnosticServerAgeMs, Is.EqualTo(140));
        Assert.That(feedback.DiagnosticRttMs, Is.EqualTo(20).Within(.001));
        Assert.That(feedback.DiagnosticAgeMs(2.04), Is.EqualTo(180).Within(.001));
        Assert.That(feedback.TryGetCameraPoint(2.04, out _), Is.False);
        feedback.Fail("CONNECTION ERROR");
        Assert.That(feedback.DiagnosticFrameId, Is.EqualTo(-1));
        Assert.That(feedback.DiagnosticAgeMs(2.05), Is.EqualTo(-1));
    }

    [Test]
    public void FeedbackExpiresAndNeverTurnsMissingMarkersIntoZero()
    {
        var feedback = new DisplayObservationFeedback();
        var obs = Observation();
        feedback.Apply(Config(), obs, 2, 2.02);
        Assert.That(feedback.Status(2.03), Is.EqualTo("POSE READY"));
        Assert.That(feedback.Detail(2.03), Does.Contain("Markers 4"));
        Assert.That(feedback.Status(2.08), Is.EqualTo("STALE"));
        obs.frame_id = 2; obs.status = "pose_rejected"; obs.reason = "need four markers"; obs.marker_ids = null;
        feedback.Apply(Config(), obs, 3, 3.01);
        Assert.That(feedback.Status(3.02), Is.EqualTo("NO POSE"));
        Assert.That(feedback.Detail(3.02), Does.Contain("Markers ?").And.Contain("need four markers"));
        obs.frame_id = 3; obs.marker_ids = new int[0];
        feedback.Apply(Config(), obs, 4, 4.01);
        Assert.That(feedback.Detail(4.02), Does.Contain("Markers 0"));
        feedback.Fail("CONNECTION ERROR");
        Assert.That(feedback.Detail(4.03), Does.Not.Contain("Markers 0"));
    }

    [Test]
    public void FeedbackRejectsForeignAndMalformedTrackingAndDuplicateCannotRefresh()
    {
        var feedback = new DisplayObservationFeedback();
        var obs = Observation();
        feedback.Apply(Config(), obs, 2, 2.01);
        obs.age_ms = 0;
        feedback.Apply(Config(), obs, 2.1, 2.1);
        Assert.That(feedback.Status(2.1), Is.EqualTo("STALE"));
        feedback.Fail("CONNECTION ERROR");
        feedback.Apply(Config(), obs, 2.2, 2.2);
        Assert.That(feedback.Status(2.2), Is.EqualTo("STALE"));
        obs.frame_id = 2; obs.camera_xyz_mm = null;
        feedback.Apply(Config(), obs, 3, 3);
        Assert.That(feedback.Status(3), Is.EqualTo("INVALID OBSERVATION"));
        obs = Observation(); obs.session_id = "foreign";
        feedback.Apply(Config(), obs, 4, 4);
        Assert.That(feedback.Status(4), Is.EqualTo("INVALID OBSERVATION"));
    }

    public static DisplayCollectionConfig Config(string directory = null) => new DisplayCollectionConfig {
        schema_version = "beast_display_collection_config_v1", session_id = "session",
        observation_url = "http://127.0.0.1:32123/observation", token = "test-token",
        camera_profile_id = "camera", workspace_profile_id = "workspace",
        camera_profile_sha256 = new string('a', 64), workspace_profile_sha256 = new string('b', 64),
        image_size = new[] {1280, 720}, target_id = "A", directory = directory ?? Path.GetTempPath(),
        setup_id = "fixed-fit-and-osd"
    };

    public static DisplayObservation Observation() => new DisplayObservation {
        schema_version = "beast_display_observation_v1", session_id = "session",
        camera_profile_id = "camera", workspace_profile_id = "workspace",
        camera_profile_sha256 = new string('a', 64), workspace_profile_sha256 = new string('b', 64),
        image_size = new[] {1280, 720}, target_id = "A", frame_id = 1, status = "tracking", reason = "",
        age_ms = 80, rvec = new[] {1.0, 0.0, 0.0}, tvec_mm = new[] {0.0, 0.0, 400.0},
        world_xyz_mm = new[] {150.0, 150.0, 60.0}, camera_xyz_mm = new[] {1.0, 2.0, 500.0},
        target_pixel = new[] {600.0, 300.0}, marker_ids = new[] {0, 2, 3, 5}, marker_count = 4, rms_px = .2, max_error_px = .3
    };

    public static StereoAlignmentState State()
    {
        var state = new StereoAlignmentState(3840, 1080, 0, 300);
        state.ConfirmChannels(1);
        return state;
    }

    [Test]
    public void FreshCandidatePreservesEyeAndObservationWithoutActivatingCalibration()
    {
        var point = State().PreviewMark(2);
        var candidate = DisplayCorrespondenceRules.Create(Config(), Observation(), point, 3840, 1080, 2, 2.02);
        Assert.That(candidate.eye, Is.EqualTo("left"));
        Assert.That(candidate.request_rtt_ms, Is.EqualTo(20).Within(.0001));
        Assert.That(candidate.conservative_age_ms, Is.EqualTo(100).Within(.0001));
        Assert.That(candidate.candidate_only && !candidate.calibration_valid && !candidate.display_alignment_verified);
        Assert.That(candidate.observation.frame_id, Is.EqualTo(1));
    }

    [TestCase(150, true)] [TestCase(150.01, false)] [TestCase(-1, false)]
    [TestCase(double.NaN, false)] [TestCase(double.PositiveInfinity, false)]
    public void ExactAgeBoundary(double age, bool accepts)
    {
        var observation = Observation(); observation.age_ms = age;
        TestDelegate action = () => DisplayCorrespondenceRules.Create(Config(), observation, State().PreviewMark(2), 3840, 1080, 2, 2);
        if (accepts) Assert.DoesNotThrow(action); else Assert.Throws<ArgumentException>(action);
    }

    [TestCase("session")] [TestCase("hash")] [TestCase("size")] [TestCase("target")]
    [TestCase("xyz")] [TestCase("behind")] [TestCase("pixel")] [TestCase("missing")]
    [TestCase("lost")] [TestCase("duplicate")] [TestCase("quality")]
    public void InvalidEvidenceIsRejected(string change)
    {
        var observation = Observation();
        switch(change) {
            case "session": observation.session_id = "other"; break;
            case "hash": observation.camera_profile_sha256 = new string('c', 64); break;
            case "size": observation.image_size[0] = 640; break;
            case "target": observation.target_id = "B"; break;
            case "xyz": observation.camera_xyz_mm = new double[2]; break;
            case "behind": observation.camera_xyz_mm[2] = -1; break;
            case "pixel": observation.target_pixel[0] = 1280; break;
            case "missing": observation = new DisplayObservation(); break;
            case "lost": observation.status = "pose_rejected"; break;
            case "duplicate": observation.marker_ids[1] = 0; break;
            case "quality": observation.rms_px = double.NaN; break;
        }
        Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.Create(Config(), observation, State().PreviewMark(2), 3840, 1080, 2, 2.02));
    }

    [TestCase("Both")] [TestCase("Channels")]
    public void ComparisonViewsCannotBecomeCorrespondences(string view)
    {
        var point = State().PreviewMark(2); point.selected_view = view;
        Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.Create(Config(), Observation(), point, 3840, 1080, 2, 2));
    }

    [Test]
    public void RttAndPhysicalOutputMustBeValid()
    {
        var point = State().PreviewMark(2);
        foreach (double finish in new[] {1.9, 2.2, double.NaN, double.PositiveInfinity})
            Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.Create(Config(), Observation(), point, 3840, 1080, 2, finish));
        Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.Create(Config(), Observation(), point, 1920, 1080, 2, 2));
    }

    [TestCase("http://localhost:32123/observation")]
    [TestCase("http://127.0.0.1.evil.test:32123/observation")]
    [TestCase("http://user@127.0.0.1:32123/observation")]
    [TestCase("http://127.0.0.1:32123/observation?token=x")]
    [TestCase("https://127.0.0.1:32123/observation")]
    public void ConfigOnlyAcceptsExactLoopbackEndpoint(string url)
    {
        var config = Config(); config.observation_url = url;
        Assert.Throws<ArgumentException>(() => DisplayCorrespondenceRules.ValidateConfig(config));
    }

    [Test]
    public void PreviewDoesNotCommitAndChangedOrExpiredStateCannotCommit()
    {
        var state = State(); var point = state.PreviewMark(2);
        Assert.That(state.MarkedCount, Is.Zero);
        state.Move(2, 0, 2);
        Assert.Throws<InvalidOperationException>(() => state.CommitMark(point, 2));
        Assert.Throws<InvalidOperationException>(() => state.CommitMark(state.PreviewMark(2), 301));
        point = state.PreviewMark(2); state.Select(StereoProbeView.Right, 2);
        Assert.Throws<InvalidOperationException>(() => state.CommitMark(point, 2));
        point = state.PreviewMark(2); state.CommitMark(point, 2);
        Assert.That(state.MarkedCount, Is.EqualTo(1));
    }

    [Test]
    public void LocalCollectionAcceptsCodexVirtualizationButNotArbitraryFolders()
    {
        string local = Path.Combine(Path.GetTempPath(), "AppDataLocal");
        Assert.That(DisplayCorrespondenceRules.IsLocalCollectionPath(Path.Combine(local,
            "ARAssembly/beast-mvp/display_correspondence/session/client-config.json"), local), Is.True);
        Assert.That(DisplayCorrespondenceRules.IsLocalCollectionPath(Path.Combine(local,
            "Packages/OpenAI.Codex_test/LocalCache/Local/ARAssembly/beast-mvp/display_correspondence/session/client-config.json"), local), Is.True);
        foreach (string bad in new[] {"OneDrive/session/client-config.json", "Packages/OtherApp/LocalCache/Local/ARAssembly/beast-mvp/display_correspondence/session/client-config.json",
            "ARAssembly/beast-mvp/display_correspondence/../../elsewhere.json"})
            Assert.That(DisplayCorrespondenceRules.IsLocalCollectionPath(Path.Combine(local, bad), local), Is.False);
    }

    [Test]
    public void ExclusiveWriteCountsOnlySuccessAndRejectsDuplicateEyeFrame()
    {
        string directory = Path.Combine(Path.GetTempPath(), "Beast 한글 " + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try {
            var config = Config(directory); var store = new DisplayCorrespondenceStore(config);
            var candidate = DisplayCorrespondenceRules.Create(config, Observation(), State().PreviewMark(2), 3840, 1080, 2, 2);
            StableCandidate(candidate);
            File.WriteAllText(Path.Combine(directory, "point-001.json"), "existing");
            Assert.Throws<IOException>(() => store.Save(candidate, "{}"));
            Assert.That(store.Count, Is.Zero);
            Assert.That(File.ReadAllText(Path.Combine(directory, "point-001.json")), Is.EqualTo("existing"));
            File.Delete(Path.Combine(directory, "point-001.json"));
            Assert.That(File.Exists(store.Save(candidate, "{}")), Is.True);
            Assert.That(store.Count, Is.EqualTo(1));
            Assert.Throws<InvalidOperationException>(() => store.Save(candidate, "{}"));
            candidate.eye = "right";
            Assert.That(File.Exists(store.Save(candidate, "{}")), Is.True);
            Assert.That(store.Count, Is.EqualTo(2));
            candidate.observation.session_id = "other";
            Assert.Throws<ArgumentException>(() => store.Save(candidate, "{}"));
        } finally { Directory.Delete(directory, true); }
    }
}
