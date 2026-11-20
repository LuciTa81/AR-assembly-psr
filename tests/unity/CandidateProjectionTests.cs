using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using ARAssembly;
using NUnit.Framework;

public class CandidateProjectionTests
{
    [Test]
    public void BoxOutlineRequiresExplicitContextModeAndPath()
    {
        var args = new[] {"--candidate-presentation", "--display-name", "VITURE",
            "--candidate-projection", "candidate.json", "--display-observation-config", "live.json",
            "--stage-targets"};
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(
            args.Concat(new[]{"--box-outline-config", "box.json"}).ToArray()));
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(
            args.Concat(new[]{"--stage-context", "--box-outline-config"}).ToArray()));
        Assert.That(SbsGuidanceOptions.Parse(args).BoxOutlinePath, Is.Null);
        Assert.That(SbsGuidanceOptions.Parse(args.Concat(new[]{"--stage-context", "--box-outline-config", "box.json"})
            .ToArray()).BoxOutlinePath, Is.EqualTo("box.json"));
    }

    [Test]
    public void StageContextIsOptInAndCannotMixLegacyOffsets()
    {
        var args = new[] {"--candidate-presentation", "--display-name", "VITURE",
            "--candidate-projection", "candidate.json", "--display-observation-config", "live.json",
            "--stage-targets"};
        Assert.That(SbsGuidanceOptions.Parse(args).StageContext, Is.False);
        Assert.That(SbsGuidanceOptions.Parse(args.Concat(new[]{"--stage-context"}).ToArray()).StageContext, Is.True);
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(new[]{"--sbs-guidance", "--stage-context"}));
        foreach (var extra in new[]{new[]{"--trial-a-right"}, new[]{"--stage-depth-config", "depth.json"}})
            Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(
                args.Concat(new[]{"--stage-context"}).Concat(extra).ToArray()));
    }

    [TestCase("S2", "screw_a", 0)]
    [TestCase("S3", "screw_b", 1)]
    [TestCase("S4", "screw_c", 2)]
    [TestCase("S5", "screw_d", 3)]
    public void ContextMatchesActivePixelsAndRequiresTheSameLiveSession(string step, string target, int index)
    {
        var p = Profile(); var c = DisplayObservationTests.Config(); p.Validate(c);
        var f = new DisplayObservationFeedback(); f.Apply(c, CornerObservation(), 1, 1.01);
        var s = new GuidanceState(); var frame = AssemblyGuidanceTests.Frame();
        frame.current_state = step; frame.target = target;
        Assert.That(s.Apply(frame, 1, 1.01), Is.True);
        Assert.That(p.PresentationStatus(f, s, "timed", 1.02, out var activeL, out var activeR, true), Is.EqualTo("VISIBLE"));
        Assert.That(p.TryProjectStageContext(f, s, "timed", 1.02, out var l, out var r), Is.True);
        Assert.That(l[index], Is.EqualTo(activeL)); Assert.That(r[index], Is.EqualTo(activeR));
        Assert.That(p.TryProjectStageContext(f, s, "other", 1.02, out l, out r), Is.False);
        Assert.That(l, Is.Null); Assert.That(r, Is.Null);
        Assert.That(p.TryProjectStageContext(f, s, "timed", 1.2, out _, out _), Is.False);
        frame.frame_id++; frame.timestamp_ms += 40; frame.marker_status = "LOST";
        s.Apply(frame, 1.03, 1.04);
        Assert.That(p.TryProjectStageContext(f, s, "timed", 1.05, out _, out _), Is.False);
    }

    [TestCase("S0", "box")][TestCase("S1", "lid")][TestCase("S6", "complete")]
    public void ContextIsAbsentOutsideScrewStages(string step, string target)
    {
        var p = Profile(); var c = DisplayObservationTests.Config(); p.Validate(c);
        var f = new DisplayObservationFeedback(); f.Apply(c, CornerObservation(), 1, 1.01);
        var s = new GuidanceState(); var frame = AssemblyGuidanceTests.Frame();
        frame.current_state = step; frame.target = target;
        s.Apply(frame, 1, 1.01);
        Assert.That(p.TryProjectStageContext(f, s, "timed", 1.02, out _, out _), Is.False);
    }

    [Test]
    public void ContextFailureDoesNotSuppressAnOtherwiseVisibleActiveScrew()
    {
        var p = Profile(); var c = DisplayObservationTests.Config(); p.Validate(c);
        var f = new DisplayObservationFeedback(); var o = CornerObservation();
        o.camera_targets[0].camera_xyz_mm[0] = 10000;
        f.Apply(c, o, 1, 1.01);
        var s = new GuidanceState(); s.Apply(AssemblyGuidanceTests.Frame(), 1, 1.01);
        Assert.That(p.TryProjectStageContext(f, s, "timed", 1.02, out _, out _), Is.False);
        Assert.That(p.PresentationStatus(f, s, "timed", 1.02, out _, out _, true), Is.EqualTo("VISIBLE"));
    }

    [Test]
    public void OfflineReportMatchesActualProjectionCodeWithoutDeviceAccess()
    {
        string path = Environment.GetEnvironmentVariable("BEAST_OFFLINE_PROJECTION_REPORT");
        if (string.IsNullOrEmpty(path)) Assert.Ignore("Set BEAST_OFFLINE_PROJECTION_REPORT for the local replay audit.");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        var report = document.RootElement;
        Assert.That(report.GetProperty("schema_version").GetString(), Is.EqualTo("beast_joint_fit_comparison_v1"));
        Assert.That(report.GetProperty("activation_status").GetString(), Is.EqualTo("not_activated"));
        var projections = report.GetProperty("joint").GetProperty("projections");
        var candidate = Profile();
        candidate.left_projection = projections.GetProperty("left").EnumerateArray()
            .SelectMany(row => row.EnumerateArray().Select(value => value.GetDouble())).ToArray();
        candidate.right_projection = projections.GetProperty("right").EnumerateArray()
            .SelectMany(row => row.EnumerateArray().Select(value => value.GetDouble())).ToArray();
        candidate.Validate(DisplayObservationTests.Config());
        int count = 0;
        foreach (string split in new[] {"fit", "check"}) {
            var ids = report.GetProperty(split + "_pose_ids").EnumerateArray().ToArray();
            if (ids.Length == 0) continue;
            var expected = report.GetProperty("joint").GetProperty(split + "_error_px").GetProperty("predicted_px");
            for (int i = 0; i < ids.Length; i++) {
                var sample = report.GetProperty("baseline_dlt").GetProperty("samples").EnumerateArray()
                    .Single(s => s.GetProperty("pose_id").GetString() == ids[i].GetString()
                        && s.GetProperty("eye").GetString() == "left");
                double[] xyz = sample.GetProperty("camera_xyz_mm").EnumerateArray().Select(v => v.GetDouble()).ToArray();
                Assert.That(candidate.TryProject(xyz, out var left, out var right), Is.True, ids[i].GetString());
                for (int axis = 0; axis < 2; axis++) {
                    Assert.That(left[axis], Is.EqualTo(expected[i][0][axis].GetDouble()).Within(1e-8));
                    Assert.That(right[axis], Is.EqualTo(expected[i][1][axis].GetDouble()).Within(1e-8));
                }
                count++;
            }
        }
        Assert.That(count, Is.GreaterThan(0));
        Assert.That(candidate.calibration_valid || candidate.display_alignment_verified, Is.False);
        TestContext.Progress.WriteLine("Offline C#/Python parity: " + count + " paired poses; no device opened.");
    }

    [Test]
    public void ContinuousModeRequiresExplicitOptInAndBothProfiles()
    {
        var args = new[] {"--candidate-presentation", "--display-name", "VITURE",
            "--candidate-projection", "candidate.json", "--display-observation-config", "live.json"};
        var options = SbsGuidanceOptions.Parse(args);
        Assert.That(options.Enabled && options.CandidatePresentation, Is.True);
        Assert.That(options.CandidatePath, Is.EqualTo("candidate.json"));
        Assert.That(options.ObservationPath, Is.EqualTo("live.json"));
        Assert.That(SbsGuidanceOptions.Parse(new[] {"--sbs-guidance"}).CandidatePresentation, Is.False);
        Assert.That(SbsGuidanceOptions.Parse(new[] {"--stereo-alignment-probe", "--candidate-projection",
            "candidate.json"}).Enabled, Is.False);
        foreach (string mode in new[] {"--test-ring", "--alignment-probe", "--stereo-alignment-probe",
            "--spatial-preview-config"})
            Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(
                new System.Collections.Generic.List<string>(args) {mode, "preview.json"}.ToArray()));
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(new[] {"--candidate-presentation"}));
        Assert.Throws<ArgumentException>(() => SbsGuidanceOptions.Parse(new[] {"--candidate-presentation",
            "--display-name", "VITURE", "--candidate-projection", "candidate.json",
            "--display-observation-config"}));
    }

    [Test]
    public void ContinuousReferenceRequiresCurrentStateFromTheSameSession()
    {
        var p = Profile(); var config = DisplayObservationTests.Config(); p.Validate(config);
        var feedback = new DisplayObservationFeedback();
        var observation = DisplayObservationTests.Observation();
        observation.camera_xyz_mm = new double[] {0, 0, 500};
        feedback.Apply(config, observation, 1, 1.01);
        var state = new GuidanceState();
        var frame = AssemblyGuidanceTests.Frame();
        state.Apply(frame, 1, 1.01);
        Assert.That(p.TryProjectPresentation(feedback, state, "timed", 1.02, out _, out _), Is.True);
        Assert.That(state.Presentation(1.02, false).Instruction, Is.EqualTo("Fasten screw A"));
        Assert.That(state.Spatial.Status(1.02), Is.EqualTo("NOT_CALIBRATED"));
        Assert.That(p.TryProjectPresentation(feedback, state, "other", 1.02, out _, out _), Is.False);
        Assert.That(p.TryProjectPresentation(feedback, state, "timed", 2, out _, out _), Is.False);
        state.Disconnect();
        Assert.That(p.TryProjectPresentation(feedback, state, "timed", 1.02, out _, out _), Is.False);
    }

    [Test]
    public void ContinuousPresentationKeepsFreshnessAndExactDisplayGuards()
    {
        Assert.That(CandidateProjection.IsPresentationOutput(3840,1080,3840,1080,"VITURE Beast",true),Is.True);
        Assert.That(CandidateProjection.IsPresentationOutput(3840,1080,1920,1080,"VITURE Beast",true),Is.False);
        Assert.That(CandidateProjection.IsPresentationOutput(3840,1200,3840,1200,"VITURE Beast",true),Is.False);
        Assert.That(CandidateProjection.IsPresentationOutput(3840,1080,3840,1080,"Laptop",true),Is.False);
        Assert.That(CandidateProjection.IsPresentationOutput(3840,1080,3840,1080,"VITURE Beast",false),Is.False);
        var p=Profile(); var c=DisplayObservationTests.Config(); p.Validate(c);
        var f=new DisplayObservationFeedback(); var o=DisplayObservationTests.Observation();
        o.camera_xyz_mm=new double[]{0,0,500};
        f.Apply(c,o,1000,1000.01);
        Assert.That(p.TryProjectFresh(f,1000.02,out _,out _),Is.True);
        Assert.That(p.TryProjectFresh(f,1001,out var l,out var r),Is.False);
        Assert.That(l,Is.Null); Assert.That(r,Is.Null);
    }

    [Test]
    public void PresentationReasonIdentifiesTheActualVisibilityGate()
    {
        var p = Profile(); var config = DisplayObservationTests.Config(); p.Validate(config);
        var feedback = new DisplayObservationFeedback();
        var observation = DisplayObservationTests.Observation();
        observation.camera_xyz_mm = new double[] {0, 0, 500};
        feedback.Apply(config, observation, 1, 1.01);
        var state = new GuidanceState();
        var frame = AssemblyGuidanceTests.Frame();
        state.Apply(frame, 1, 1.01);
        Assert.That(p.PresentationStatus(feedback, state, "timed", 1.02, out _, out _), Is.EqualTo("VISIBLE"));
        Assert.That(p.PresentationStatus(feedback, state, "other", 1.02, out _, out _), Is.EqualTo("SESSION MISMATCH"));
        Assert.That(p.PresentationStatus(feedback, state, "timed", 1.2, out _, out _), Is.EqualTo("POSE STALE"));
        Assert.That(p.PresentationStatus(feedback, state, "timed", 2, out _, out _), Is.EqualTo("STATE STALE"));
        frame.frame_id++; frame.timestamp_ms += 100; frame.marker_status = "LOST";
        state.Apply(frame, 1.03, 1.04);
        Assert.That(p.PresentationStatus(feedback, state, "timed", 1.05, out _, out _), Is.EqualTo("STATE TRACKING_LOST"));
        frame.frame_id++; frame.timestamp_ms += 100; frame.marker_status = "OK";
        state.Apply(frame, 1.06, 1.07);
        observation.frame_id++; observation.age_ms = 0;
        observation.camera_xyz_mm = new double[] {10000, 0, 500};
        feedback.Apply(config, observation, 1.06, 1.07);
        Assert.That(p.PresentationStatus(feedback, state, "timed", 1.08, out var l, out var rr),
            Is.EqualTo("OUTSIDE EYE VIEW"));
        Assert.That(l, Is.Null); Assert.That(rr, Is.Null);
    }

    public static CandidateProjection Profile() => new CandidateProjection {
        schema_version="beast_candidate_projection_probe_v1", candidate_only=true,
        camera_profile_id="camera", workspace_profile_id="workspace",
        camera_profile_sha256=new string('a',64), workspace_profile_sha256=new string('b',64),
        coordinate_convention="eye_local_pixels_top_left", display_mode="full_sbs",
        channel_order="left_half_left_eye_right_half_right_eye", eye_width=1920, eye_height=1080,
        left_projection=new double[]{1500,0,960,45000,0,1500,540,0,0,0,1,0},
        right_projection=new double[]{1500,0,960,-45000,0,1500,540,0,0,0,1,0}
    };

    private static DisplayObservation CornerObservation()
    {
        var o = DisplayObservationTests.Observation();
        o.age_ms = 0;
        o.camera_xyz_mm = new double[] {0, 0, 500};
        o.camera_targets = new[] {
            new DisplayCameraTarget {target_id="B", camera_xyz_mm=new double[]{40,0,500}},
            new DisplayCameraTarget {target_id="D", camera_xyz_mm=new double[]{40,40,500}},
            new DisplayCameraTarget {target_id="A", camera_xyz_mm=new double[]{0,0,500}},
            new DisplayCameraTarget {target_id="C", camera_xyz_mm=new double[]{0,40,500}}
        };
        return o;
    }

    [Test]
    public void IntegratedStagesUseTheirOwnDepthAndKeepInstructionsWhenRingIsHidden()
    {
        var p=Profile(); var config=DisplayObservationTests.Config(); p.Validate(config);
        string hash=new string('c',64);
        TrackedAlignmentRecord[] Rows(string target,int dx) {
            return new double[]{320,420,500}.Select(z=>{
                var o=DisplayObservationTests.Observation(); o.target_id=target; o.camera_xyz_mm=new[]{0d,0d,z};
                o.age_ms=0; var cfg=DisplayObservationTests.Config(); cfg.target_id=target;
                var m=new TrackedAlignmentDiagnostic(cfg,p,hash);
                m.Move(StereoProbeView.Left,dx,4); m.Move(StereoProbeView.Right,-dx,8);
                Assert.That(m.TryRender(o,1,1.01,1.02,out _,out _),Is.True);
                m.ConfirmEye(StereoProbeView.Left); m.ConfirmEye(StereoProbeView.Right);
                return m.CreateRecord(1.03);
            }).ToArray();
        }
        p.BindStageDepthRecords(hash,Rows("C",12),Rows("D",-9));
        var state=new GuidanceState(); var feedback=new DisplayObservationFeedback();
        for(int i=0;i<5;i++){
            int n=Math.Min(i,3); string id="ABCD"[n].ToString();
            var frame=AssemblyGuidanceTests.Frame(i+1); frame.guidance.reason="operator_confirmation";
            frame.current_state="S"+(2+n); frame.target="screw_"+id.ToLowerInvariant();
            frame.next_action="Fasten screw "+id;
            double now=2+i; Assert.That(state.Apply(frame,now,now+.01),Is.True);
            var o=CornerObservation(); o.frame_id+=i; var xyz=o.camera_targets.Single(t=>t.target_id==id).camera_xyz_mm;
            if(n>=2) xyz[2]=i==4 ? 520 : 420;
            feedback.Apply(config,o,now,now+.01);
            Assert.That(state.Presentation(now+.02).Instruction,Is.EqualTo(frame.next_action));
            var gate=p.PresentationStatus(feedback,state,"timed",now+.02,out var l,out var r,true,true);
            if(i==4){Assert.That(gate,Is.EqualTo("OUTSIDE TARGET DEPTH"));Assert.That(l,Is.Null);Assert.That(r,Is.Null);continue;}
            Assert.That(gate,Is.EqualTo("VISIBLE"));
            Assert.That(p.TryProject(xyz,out var bl,out var br),Is.True);
            Assert.That(l,Is.EqualTo(new[]{bl[0]+new[]{17,0,12,-9}[n],bl[1]+(n>=2?4:0)}).Within(.001));
            Assert.That(r,Is.EqualTo(new[]{br[0]+new[]{17,0,-12,9}[n],br[1]+(n>=2?8:0)}).Within(.001));
        }
    }

    [Test]
    public void OperatorConfirmationSwitchesBothEyesFromAtoBAndDropsTheRingOnLoss()
    {
        var p = Profile(); var c = DisplayObservationTests.Config(); var o = CornerObservation();
        c.session_id = o.session_id = "timed"; p.Validate(c);
        var feedback = new DisplayObservationFeedback(); feedback.Apply(c, o, 1, 1.01);
        var state = new GuidanceState();
        var frame = AssemblyGuidanceTests.Frame(); frame.guidance.reason = "operator_confirmation";
        state.Apply(frame, 1, 1.01);
        string Gate(double now, out double[] left, out double[] right) =>
            p.PresentationStatus(feedback, state, c.session_id, now, out left, out right, stageTargets: true);
        Assert.That(Gate(1.02, out var l, out var r), Is.EqualTo("VISIBLE"));
        Assert.That(l[0], Is.EqualTo(1050)); Assert.That(r[0], Is.EqualTo(870));
        frame.frame_id++; frame.timestamp_ms += 40; frame.current_state = "S3";
        frame.target = "screw_b"; frame.next_action = "Fasten screw B | Operator confirmation";
        state.Apply(frame, 1.03, 1.04);
        Assert.That(Gate(1.05, out l, out r), Is.EqualTo("VISIBLE"));
        Assert.That(l[0], Is.EqualTo(1170)); Assert.That(r[0], Is.EqualTo(990));
        Assert.That(state.Presentation(1.05).Instruction, Is.EqualTo(frame.next_action));
        Assert.That(Gate(1.16, out l, out r), Is.Not.EqualTo("VISIBLE"));
        Assert.That(l, Is.Null); Assert.That(r, Is.Null);
        frame.frame_id++; frame.timestamp_ms += 100; frame.marker_status = "LOST";
        state.Apply(frame, 1.17, 1.18);
        Assert.That(Gate(1.19, out l, out r), Is.EqualTo("STATE TRACKING_LOST"));
        Assert.That(state.Presentation(1.19, keepOperatorActionOnLoss: true).Instruction, Is.EqualTo(frame.next_action));
        Assert.That(state.Presentation(2, keepOperatorActionOnLoss: true).Instruction, Does.Not.Contain("Fasten"));
        o.frame_id++; feedback.Apply(c, o, 1.2, 1.21);
        frame.frame_id++; frame.timestamp_ms += 50; frame.marker_status = "OK"; state.Apply(frame, 1.2, 1.21);
        Assert.That(Gate(1.22, out l, out r), Is.EqualTo("VISIBLE"));
        Assert.That(l[0], Is.EqualTo(1170));
    }

    [TestCase("GUIDING", "")]
    [TestCase("OBSERVING", "")]
    [TestCase("OBSERVED", "")]
    [TestCase("PAUSED", "tool_not_visible")]
    [TestCase("PAUSED", "tool_position_unknown")]
    [TestCase("PAUSED", "invalid_observation")]
    [TestCase("PAUSED", "observation_gap")]
    public void AutomaticStageKeepsCurrentTargetWhileWaitingForToolEvidence(string phase, string reason)
    {
        var p=Profile(); var config=DisplayObservationTests.Config(); p.Validate(config);
        var feedback=new DisplayObservationFeedback(); feedback.Apply(config,CornerObservation(),1,1.01);
        var state=new GuidanceState(); var frame=AssemblyGuidanceTests.Frame();
        frame.guidance.phase=phase; frame.guidance.reason=reason;
        Assert.That(state.Apply(frame,1,1.01),Is.True);
        Assert.That(p.PresentationStatus(feedback,state,"timed",1.02,out var l,out var r,true),Is.EqualTo("VISIBLE"));
        Assert.That(l[0],Is.EqualTo(1050)); Assert.That(r[0],Is.EqualTo(870));
        frame.frame_id++; frame.timestamp_ms+=30; frame.current_state="S3"; frame.target="screw_b";
        frame.guidance.phase="GUIDING"; frame.guidance.reason=""; frame.next_action="Fasten screw B";
        Assert.That(state.Apply(frame,1.03,1.04),Is.True);
        Assert.That(p.PresentationStatus(feedback,state,"timed",1.05,out l,out r,true),Is.EqualTo("VISIBLE"));
        Assert.That(l[0],Is.EqualTo(1170)); Assert.That(r[0],Is.EqualTo(990));
        Assert.That(p.PresentationStatus(feedback,state,"timed",1.17,out _,out _,true),Is.Not.EqualTo("VISIBLE"));
        frame.frame_id++; frame.timestamp_ms+=30; frame.marker_status="LOST";
        Assert.That(state.Apply(frame,1.18,1.19),Is.True);
        Assert.That(p.PresentationStatus(feedback,state,"timed",1.2,out _,out _,true),Is.EqualTo("STATE TRACKING_LOST"));
    }

    [TestCase("marker_not_stable")][TestCase("invalid_frame")][TestCase("invalid_threshold")]
    public void AutomaticStageDoesNotRenderOnNonToolFault(string reason)
    {
        var p=Profile(); var config=DisplayObservationTests.Config(); p.Validate(config);
        var feedback=new DisplayObservationFeedback(); feedback.Apply(config,CornerObservation(),1,1.01);
        var state=new GuidanceState(); var frame=AssemblyGuidanceTests.Frame();
        frame.guidance.phase="PAUSED"; frame.guidance.reason=reason; state.Apply(frame,1,1.01);
        Assert.That(p.PresentationStatus(feedback,state,"timed",1.02,out _,out _,true),Is.Not.EqualTo("VISIBLE"));
    }

    [TestCase("S0","box")][TestCase("S1","lid")][TestCase("S6","complete")]
    public void StageTrialNeverShowsAReferenceAtOtherSteps(string step, string target)
    {
        var p=Profile(); var c=DisplayObservationTests.Config(); p.Validate(c);
        var f=new DisplayObservationFeedback(); f.Apply(c,CornerObservation(),1,1.01);
        var s=new GuidanceState(); var frame=AssemblyGuidanceTests.Frame();
        frame.current_state=step; frame.target=target; frame.guidance.reason="operator_confirmation";
        if (step=="S6") frame.guidance.phase="AWAITING_CONFIRMATION";
        Assert.That(s.Apply(frame,1,1.01),Is.True);
        Assert.That(p.PresentationStatus(f,s,"timed",1.02,out var l,out var r,true),Is.EqualTo("NO STAGE TARGET"));
        Assert.That(l,Is.Null); Assert.That(r,Is.Null);
    }

    [Test]
    public void MissingBIsNotReplacedByPrimaryAAndModeRequiresExplicitOptIn()
    {
        var p=Profile(); var c=DisplayObservationTests.Config(); p.Validate(c);
        var f=new DisplayObservationFeedback(); var o=CornerObservation(); o.camera_targets=null;
        f.Apply(c,o,1,1.01); var s=new GuidanceState(); var frame=AssemblyGuidanceTests.Frame();
        frame.current_state="S3"; frame.target="screw_b"; frame.guidance.reason="operator_confirmation"; s.Apply(frame,1,1.01);
        Assert.That(p.PresentationStatus(f,s,"timed",1.02,out var l,out var r,true),Is.EqualTo("STAGE TARGET UNAVAILABLE"));
        Assert.That(l,Is.Null); Assert.That(r,Is.Null);
        Assert.That(p.PresentationStatus(f,s,"timed",1.02,out _,out _),Is.EqualTo("VISIBLE"));
        Assert.Throws<ArgumentException>(()=>SbsGuidanceOptions.Parse(new[]{"--sbs-guidance","--stage-targets"}));
    }

    [TestCase("S2","screw_a",1050,870,540,17)]
    [TestCase("S3","screw_b",1170,990,540,0)]
    [TestCase("S4","screw_c",1050,870,660,0)]
    [TestCase("S5","screw_d",1170,990,660,0)]
    public void TrialShiftsOnlyAAndPreservesDisparity(string step, string target, int lx, int rx, int y, int dx)
    {
        var p=Profile(); var c=DisplayObservationTests.Config(); p.Validate(c);
        var f=new DisplayObservationFeedback(); f.Apply(c,CornerObservation(),1,1.01);
        var s=new GuidanceState(); var frame=AssemblyGuidanceTests.Frame();
        frame.current_state=step; frame.target=target; frame.guidance.reason="operator_confirmation";
        Assert.That(s.Apply(frame,1,1.01),Is.True);
        Assert.That(p.PresentationStatus(f,s,"timed",1.02,out var l,out var r,true),Is.EqualTo("VISIBLE"));
        Assert.That(l,Is.EqualTo(new double[]{lx,y})); Assert.That(r,Is.EqualTo(new double[]{rx,y}));
        Assert.That(p.PresentationStatus(f,s,"timed",1.02,out l,out r,true,true),Is.EqualTo("VISIBLE"));
        Assert.That(l,Is.EqualTo(new double[]{lx+dx,y})); Assert.That(r,Is.EqualTo(new double[]{rx+dx,y}));
        Assert.That(p.PresentationStatus(f,s,"timed",2,out l,out r,true,true),Is.Not.EqualTo("VISIBLE"));
        Assert.That(l,Is.Null); Assert.That(r,Is.Null);
    }

    [Test]
    public void TrialDoesNotClampAStereoPairAtTheRightEdge()
    {
        var p=Profile(); var c=DisplayObservationTests.Config(); p.Validate(c);
        var o=CornerObservation(); o.camera_xyz_mm[0]=288; o.camera_targets[2].camera_xyz_mm[0]=288;
        var f=new DisplayObservationFeedback(); f.Apply(c,o,1,1.01);
        var s=new GuidanceState(); var frame=AssemblyGuidanceTests.Frame();
        frame.guidance.reason="operator_confirmation"; s.Apply(frame,1,1.01);
        Assert.That(p.PresentationStatus(f,s,"timed",1.02,out _,out _,true),Is.EqualTo("VISIBLE"));
        Assert.That(p.PresentationStatus(f,s,"timed",1.02,out var l,out var r,true,true),Is.EqualTo("OUTSIDE EYE VIEW"));
        Assert.That(l,Is.Null); Assert.That(r,Is.Null);
        Assert.Throws<ArgumentException>(()=>SbsGuidanceOptions.Parse(new[]{"--sbs-guidance","--trial-a-right"}));
    }

    [Test]
    public void FourCornersUseOneFreshPoseAndTheSameEyeMatrices()
    {
        var c = DisplayObservationTests.Config(); var p = Profile(); p.Validate(c);
        var f = new DisplayObservationFeedback(); var o = CornerObservation();
        f.Apply(c, o, 2, 2.01);
        Assert.That(p.TryProjectCorners(f, 2.02, out var left, out var right), Is.True);
        Assert.That(left.Length, Is.EqualTo(4)); Assert.That(right.Length, Is.EqualTo(4));
        Assert.That(left[0], Is.EqualTo(new double[]{1050,540}));
        Assert.That(left[1], Is.EqualTo(new double[]{1170,540}));
        Assert.That(left[2], Is.EqualTo(new double[]{1050,660}));
        Assert.That(left[3], Is.EqualTo(new double[]{1170,660}));
        Assert.That(right[0], Is.EqualTo(new double[]{870,540}));
        Assert.That(right[3], Is.EqualTo(new double[]{990,660}));
        Assert.That(CandidateProjection.LidPerimeter, Is.EqualTo("ABDCA"));
        Assert.That(p.TryProjectFresh(f, 2.02, out var aLeft, out var aRight), Is.True);
        Assert.That(aLeft, Is.EqualTo(left[0])); Assert.That(aRight, Is.EqualTo(right[0]));
        Assert.That(p.calibration_valid || p.display_alignment_verified, Is.False);
        Assert.That(p.TryProjectCorners(f, 2.16, out left, out right), Is.False);
        Assert.That(left, Is.Null); Assert.That(right, Is.Null);
    }

    [TestCase("missing")][TestCase("duplicate")][TestCase("nan")][TestCase("behind")]
    [TestCase("wrong_a")][TestCase("unknown")][TestCase("extra")][TestCase("null_entry")]
    [TestCase("bad_vector")]
    public void InvalidOptionalCornersHideTheQuadWithoutBreakingLegacyA(string change)
    {
        var c=DisplayObservationTests.Config(); var p=Profile(); p.Validate(c);
        var f=new DisplayObservationFeedback(); var o=CornerObservation();
        switch (change) {
            case "missing": o.camera_targets=null; break;
            case "duplicate": o.camera_targets[1].target_id="B"; break;
            case "nan": o.camera_targets[0].camera_xyz_mm[0]=double.NaN; break;
            case "behind": o.camera_targets[0].camera_xyz_mm[2]=-1; break;
            case "wrong_a": o.camera_targets[2].camera_xyz_mm[0]=1; break;
            case "unknown": o.camera_targets[1].target_id="X"; break;
            case "extra": o.camera_targets=o.camera_targets.Concat(new[]{o.camera_targets[0]}).ToArray(); break;
            case "null_entry": o.camera_targets[0]=null; break;
            case "bad_vector": o.camera_targets[0].camera_xyz_mm=new double[]{0,500}; break;
        }
        f.Apply(c,o,2,2.01);
        Assert.That(p.TryProjectFresh(f,2.02,out _,out _),Is.True);
        Assert.That(p.TryProjectCorners(f,2.02,out var left,out var right),Is.False);
        Assert.That(left,Is.Null); Assert.That(right,Is.Null);
    }

    [Test]
    public void CornersAreCopiedAndNeverMixFramesOrReviveAfterFailure()
    {
        var c=DisplayObservationTests.Config(); var p=Profile(); p.Validate(c);
        var f=new DisplayObservationFeedback(); var o=CornerObservation();
        f.Apply(c,o,2,2.01);
        o.camera_targets[0].camera_xyz_mm[0]=80;
        f.Apply(c,o,2.02,2.03);
        Assert.That(p.TryProjectCorners(f,2.04,out var left,out _),Is.True);
        Assert.That(left[1][0],Is.EqualTo(1170));
        left[1][0]=999;
        Assert.That(p.TryProjectCorners(f,2.05,out left,out _),Is.True);
        Assert.That(left[1][0],Is.EqualTo(1170));
        o.frame_id++; o.camera_targets=null;
        f.Apply(c,o,2.06,2.07);
        Assert.That(p.TryProjectFresh(f,2.08,out _,out _),Is.True);
        Assert.That(p.TryProjectCorners(f,2.08,out _,out _),Is.False);
        o=CornerObservation(); o.frame_id=3;
        f.Apply(c,o,2.09,2.10);
        Assert.That(p.TryProjectCorners(f,2.11,out _,out _),Is.True);
        f.Fail("CONNECTION ERROR");
        f.Apply(c,o,2.12,2.13);
        Assert.That(p.TryProjectCorners(f,2.14,out _,out _),Is.False);
        o.frame_id=4;
        f.Apply(c,o,2.15,2.16);
        Assert.That(p.TryProjectCorners(f,2.17,out _,out _),Is.True);
        o.frame_id=5; o.status="pose_rejected";
        f.Apply(c,o,2.18,2.19);
        Assert.That(p.TryProjectCorners(f,2.20,out _,out _),Is.False);
    }

    [Test]
    public void AnyCornerOutsideEitherEyeHidesTheWholeQuad()
    {
        var c=DisplayObservationTests.Config(); var p=Profile(); p.Validate(c);
        var f=new DisplayObservationFeedback(); var o=CornerObservation();
        o.camera_targets[0].camera_xyz_mm[0]=10000;
        f.Apply(c,o,2,2.01);
        Assert.That(p.TryProjectCorners(f,2.02,out var left,out var right),Is.False);
        Assert.That(left,Is.Null); Assert.That(right,Is.Null);
        Assert.That(p.TryProjectFresh(f,2.02,out _,out _),Is.True);
    }

    [Test]
    public void CandidateProjectsSeparateEyesWithoutActivatingCalibration()
    {
        var p=Profile();
        p.Validate(DisplayObservationTests.Config());
        Assert.That(p.TryProject(new double[]{0,0,500},out var l,out var r),Is.True);
        Assert.That(l,Is.EqualTo(new double[]{1050,540}));
        Assert.That(r,Is.EqualTo(new double[]{870,540}));
        Assert.That(p.calibration_valid || p.display_alignment_verified,Is.False);
    }

    [TestCase(3840,1200,30)][TestCase(1920,1080,30)][TestCase(3840,1080,31)]
    [TestCase(3840,1080,double.NaN)][TestCase(3840,1080,0)]
    public void CandidateRequiresExactOutputAndShortDuration(int width,int height,double seconds)
    {
        Assert.Throws<ArgumentException>(()=>Profile().ValidateOutput(width,height,seconds));
        Assert.DoesNotThrow(()=>Profile().ValidateOutput(3840,1080,30));
    }

    [TestCase("schema")][TestCase("binding")][TestCase("matrix")][TestCase("nan")]
    [TestCase("size")][TestCase("verified")][TestCase("candidate")][TestCase("singular")]
    public void InvalidProfilesAreRejected(string change)
    {
        var p=Profile();
        switch(change) {
            case "schema": p.schema_version="synthetic"; break;
            case "binding": p.workspace_profile_id="other"; break;
            case "matrix": p.right_projection=new double[4]; break;
            case "nan": p.left_projection[0]=double.NaN; break;
            case "size": p.eye_width=1280; break;
            case "verified": p.display_alignment_verified=true; break;
            case "candidate": p.candidate_only=false; break;
            case "singular": p.right_projection[0]=0; break;
        }
        Assert.Throws<ArgumentException>(()=>p.Validate(DisplayObservationTests.Config()));
    }

    [TestCase(0,0,-500)][TestCase(10000,0,500)][TestCase(0,10000,500)]
    [TestCase(double.NaN,0,500)]
    public void InvalidTargetsHideBothEyes(double x,double y,double z)
    {
        var p=Profile(); p.Validate(DisplayObservationTests.Config());
        Assert.That(p.TryProject(new[]{x,y,z},out var l,out var r),Is.False);
        Assert.That(l,Is.Null); Assert.That(r,Is.Null);
    }

    [Test]
    public void ProjectionRefusesUseBeforeValidationAndBehindEitherEye()
    {
        var p=Profile();
        Assert.That(p.TryProject(new double[]{0,0,500},out _,out _),Is.False);
        p.right_projection[11]=-600;
        p.Validate(DisplayObservationTests.Config());
        Assert.That(p.TryProject(new double[]{0,0,500},out _,out _),Is.False);
    }

    [Test]
    public void LatestPointExpiresDoesNotMutateOrResurrectOnSameFrame()
    {
        var f=new DisplayObservationFeedback();
        var obs=DisplayObservationTests.Observation();
        var config=DisplayObservationTests.Config();
        Assert.That(f.TryGetCameraPoint(2,out _),Is.False);
        f.Apply(config,obs,2,2.01);
        Assert.That(f.TryGetCameraPoint(2.02,out var xyz),Is.True);
        xyz[0]=999; obs.camera_xyz_mm[0]=888;
        Assert.That(f.TryGetCameraPoint(2.03,out xyz),Is.True);
        Assert.That(xyz[0],Is.EqualTo(1));
        Assert.That(f.TryGetCameraPoint(2.08,out _),Is.False);
        f.Fail("CONNECTION ERROR");
        obs.age_ms=0;
        f.Apply(config,obs,2.1,2.1);
        Assert.That(f.TryGetCameraPoint(2.1,out _),Is.False);
        obs.frame_id=2;
        f.Apply(config,obs,2.2,2.2);
        Assert.That(f.TryGetCameraPoint(2.21,out _),Is.True);
        obs.frame_id=3; obs.status="pose_rejected";
        f.Apply(config,obs,2.22,2.22);
        Assert.That(f.TryGetCameraPoint(2.23,out _),Is.False);
    }

    [Test]
    public void CandidatePollingReducesAvoidableExpiryGapsWithoutExtendingPoseAge()
    {
        // Simulated 10 Hz source, 30 ms processing and 20 ms RTT, rendered at 60 Hz.
        Assert.That(HiddenFrames(CandidateProjection.PollIntervalSeconds),Is.LessThan(HiddenFrames(.1)));
    }

    private static int HiddenFrames(double interval)
    {
        var feedback=new DisplayObservationFeedback();
        var config=DisplayObservationTests.Config();
        DisplayObservation pending=null;
        double sent=0,receive=0,nextPoll=0;
        int hidden=0;
        for (int tick=0;tick<180;tick++) {
            double now=1+tick/60.0;
            if (pending!=null && now>=receive) {
                feedback.Apply(config,pending,sent,now);
                pending=null;
            }
            if (pending==null && now>=nextPoll) {
                long frame=(long)Math.Floor((now-.03)*10);
                pending=DisplayObservationTests.Observation();
                pending.frame_id=frame;
                pending.age_ms=(now-frame/10.0)*1000;
                sent=now; receive=now+.02; nextPoll=now+interval;
            }
            if (tick>30 && !feedback.TryGetCameraPoint(now,out _)) hidden++;
        }
        return hidden;
    }
}
