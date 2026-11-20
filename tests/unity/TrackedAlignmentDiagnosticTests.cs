using System;
using ARAssembly;
using NUnit.Framework;

public class TrackedAlignmentDiagnosticTests
{
    private static TrackedAlignmentDiagnostic Model(string target = "A")
    {
        var config = DisplayObservationTests.Config();
        config.target_id = target;
        return new TrackedAlignmentDiagnostic(config, CandidateProjectionTests.Profile(), new string('c', 64));
    }
    private static DisplayObservation Pose(string target = "A")
    {
        var o = DisplayObservationTests.Observation();
        o.target_id = target; o.age_ms = 10; o.camera_xyz_mm = new double[]{0, 0, 500};
        return o;
    }
    private static void Confirm(TrackedAlignmentDiagnostic model)
    {
        model.ConfirmEye(StereoProbeView.Left);
        model.ConfirmEye(StereoProbeView.Right);
    }
    [TestCase("C")]
    [TestCase("D")]
    public void DepthTrialUsesOnlyItsTargetAndNeverExtrapolates(string target)
    {
        var p = CandidateProjectionTests.Profile();
        p.Validate(DisplayObservationTests.Config());
        var rows = new TrackedAlignmentRecord[3];
        double[] z = {320, 400, 500};
        for (int i=0; i<3; i++) {
            var o = Pose(target); o.camera_xyz_mm[2] = z[i];
            var m = Model(target);
            m.Move(StereoProbeView.Left, -10*i*i, -2*i);
            m.Move(StereoProbeView.Right, -5*i, 4*i*i);
            Assert.That(m.TryRender(o, 1, 1.01, 1.02, out _, out _), Is.True);
            Confirm(m); rows[i] = m.CreateRecord(1.03);
        }
        string hash = rows[0].candidate_sha256;
        var trial = new TargetDepthTrial(p, hash, target, rows);
        foreach (var row in rows) {
            Assert.That(trial.TryProject(row.observation.camera_xyz_mm, out var l, out var r), Is.True);
            Assert.That(l, Is.EqualTo(row.left_final_px).Within(1e-6));
            Assert.That(r, Is.EqualTo(row.right_final_px).Within(1e-6));
        }
        foreach (var i in new[]{0,1}) {
            var xyz = new[]{0d, 0d, 2/(1/z[i]+1/z[i+1])};
            Assert.That(p.TryProject(xyz, out var bl, out var br), Is.True);
            Assert.That(trial.TryProject(xyz, out var l, out var r), Is.True);
            for(int k=0;k<2;k++){
                Assert.That(l[k]-bl[k], Is.EqualTo((rows[i].left_offset_px[k]+rows[i+1].left_offset_px[k])/2).Within(1e-6));
                Assert.That(r[k]-br[k], Is.EqualTo((rows[i].right_offset_px[k]+rows[i+1].right_offset_px[k])/2).Within(1e-6));
            }
        }
        foreach (var depth in new[]{319d,501d,double.NaN})
            Assert.That(trial.TryProject(new[]{0d,0d,depth},out _,out _), Is.False);
        Assert.Throws<ArgumentException>(()=>new TargetDepthTrial(p,hash,"A",rows));
        Assert.Throws<ArgumentException>(()=>new TargetDepthTrial(p,hash,target=="C" ? "D" : "C",rows));
        Assert.Throws<ArgumentException>(()=>new TargetDepthTrial(p,"wrong",target,rows));
        Assert.Throws<ArgumentException>(()=>new TargetDepthTrial(p,hash,target,new[]{rows[0],rows[0],rows[2]}));
        if (target == "C") {
            rows[2].setup_id += "-other";
            Assert.Throws<ArgumentException>(()=>new TargetDepthTrial(p,hash,target,rows));
            rows[2].setup_id = rows[0].setup_id;
        }
        rows[0].binocular_confirmed_by_user=false;
        Assert.Throws<ArgumentException>(()=>new TargetDepthTrial(p,hash,target,rows));
    }
    [Test]
    public void DLeftUpTrialShiftsBothEyesEquallyAndCannotApplyToOtherTargets()
    {
        var m = Model("D"); var o = Pose("D");
        Assert.That(m.TryRender(o, 1, 1.01, 1.02, out var l, out var r), Is.True);
        m.StartDLeftUpTrial();
        Assert.That(m.TryRender(o, 1, 1.01, 1.03, out var lt, out var rt), Is.True);
        Assert.That(lt, Is.EqualTo(new[]{l[0]-8, l[1]-4}));
        Assert.That(rt, Is.EqualTo(new[]{r[0]-8, r[1]-4}));
        Confirm(m);
        var saved = m.CreateRecord(1.04);
        Assert.That(saved.left_offset_px, Is.EqualTo(new double[]{-8,-4}));
        Assert.That(saved.right_offset_px, Is.EqualTo(saved.left_offset_px));
        foreach (var target in new[]{"A","B","C"})
            Assert.Throws<InvalidOperationException>(() => Model(target).StartDLeftUpTrial());
    }
    [Test]
    public void FollowingCircleRetainsOnlyEyeOffsetsNotScreenPosition()
    {
        var m = Model(); var o = Pose();
        Assert.That(m.TryRender(o, 1, 1.01, 1.02, out var l, out var r), Is.True);
        m.Move(StereoProbeView.Left, 4, -2);
        Assert.That(m.TryRender(o, 1, 1.01, 1.03, out var l2, out var r2), Is.True);
        Assert.That(l2[0] - l[0], Is.EqualTo(4)); Assert.That(l2[1] - l[1], Is.EqualTo(-2));
        Assert.That(r2, Is.EqualTo(r));
        o.frame_id++; o.camera_xyz_mm[0] += 20;
        Assert.That(m.TryRender(o, 1.04, 1.05, 1.06, out var l3, out var r3), Is.True);
        Assert.That(l3[0], Is.Not.EqualTo(l2[0])); Assert.That(r3[0], Is.Not.EqualTo(r2[0]));
    }
    [Test]
    public void RecordUsesCopiedRenderedPoseAndPixelsNotLaterObservation()
    {
        var m = Model("D"); var o = Pose("D");
        Assert.That(m.TryRender(o, 1, 1.01, 1.02, out var l, out _), Is.True);
        Confirm(m); long frame = o.frame_id;
        o.frame_id++; o.camera_xyz_mm[0] = 999; l[0] = -500;
        var record = m.CreateRecord(1.03);
        Assert.That(record.observation.frame_id, Is.EqualTo(frame));
        Assert.That(record.observation.target_id, Is.EqualTo("D"));
        Assert.That(record.observation.camera_xyz_mm[0], Is.Zero);
        Assert.That(record.left_final_px[0], Is.GreaterThan(24));
        Assert.That(record.schema_version, Is.EqualTo("beast_tracked_alignment_diagnostic_v1"));
        Assert.That(record.calibration_valid || record.display_alignment_verified, Is.False);
        Assert.That(record.conservative_age_ms, Is.EqualTo(40).Within(1e-6));
    }
    [Test]
    public void SaveRequiresBothEyeConfirmationAndARepaintAfterAdjustment()
    {
        var m = Model(); var o = Pose();
        m.TryRender(o, 1, 1.01, 1.02, out _, out _);
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.03));
        Confirm(m);
        m.Move(StereoProbeView.Left, 2, 0);
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.03));
        Assert.That(m.TryRender(o, 1, 1.01, 1.04, out _, out _), Is.True);
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.05));
        m.ConfirmEye(StereoProbeView.Left);
        Assert.That(m.CreateRecord(1.05).binocular_confirmed_by_user, Is.True);
    }
    [Test]
    public void ExpiredOrInvalidPoseCannotBeRenderedOrSaved()
    {
        var m = Model(); var o = Pose();
        m.TryRender(o, 1, 1.01, 1.02, out _, out _); Confirm(m);
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.2));
        Assert.That(m.TryRender(o, 1, 1.01, 1.2, out _, out _), Is.False);
        o.status = "pose_rejected";
        Assert.That(m.TryRender(o, 1, 1.01, 1.03, out _, out _), Is.False);
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.04));
    }
    [Test]
    public void TargetMismatchAndNonfiniteOrOffscreenAdjustmentFailClosed()
    {
        var m = Model("D");
        Assert.That(m.TryRender(Pose("A"), 1, 1.01, 1.02, out _, out _), Is.False);
        Assert.Throws<ArgumentException>(() => m.Move(StereoProbeView.Left, double.NaN, 0));
        m.Move(StereoProbeView.Left, -5000, 0);
        Assert.That(m.TryRender(Pose("D"), 1, 1.01, 1.02, out _, out _), Is.False);
    }
    [Test]
    public void BothMustBeRepaintedBeforePairSaveAndFocusLossInvalidatesIt()
    {
        var m = Model(); var o = Pose();
        m.TryRender(o, 1, 1.01, 1.02, out _, out _, StereoProbeView.Right);
        Confirm(m);
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.03));
        m.TryRender(o, 1, 1.01, 1.04, out _, out _, StereoProbeView.Both);
        Assert.That(m.CreateRecord(1.05).rendered_view, Is.EqualTo("Both"));
        m.Invalidate();
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.06));
    }
    [Test]
    public void ReturnedRecordIsIndependentAndRepeatedRepaintCannotExtendFreshness()
    {
        var m = Model(); var o = Pose();
        m.TryRender(o, 1, 1.01, 1.02, out _, out _); Confirm(m);
        var first = m.CreateRecord(1.03);
        first.observation.camera_xyz_mm[0] = 200; first.left_final_px[0] = -20;
        var second = m.CreateRecord(1.04);
        Assert.That(second.observation.camera_xyz_mm[0], Is.Zero);
        Assert.That(second.left_final_px[0], Is.GreaterThan(24));
        m.TryRender(o, 1, 1.01, 1.1, out _, out _);
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.15));
    }
    [Test]
    public void ExistingReadOnlyDeadlineRemainsThirtySeconds()
    {
        var p = CandidateProjectionTests.Profile();
        Assert.Throws<ArgumentException>(() => p.ValidateOutput(3840, 1080, 31));
        Assert.DoesNotThrow(() => p.ValidateOutput(3840, 1080, 300, true));
        Assert.DoesNotThrow(() => p.ValidateOutput(3840, 1080, 600, true));
        Assert.Throws<ArgumentException>(() => p.ValidateOutput(3840, 1080, 601, true));
        Assert.That(new StereoAlignmentState(3840,1080,0,600,true).Visible(599,3840,1080), Is.True);
        Assert.Throws<ArgumentException>(() => p.ValidateOutput(1920, 1080, 30, true));
    }
    [Test]
    public void ChannelRepaintThenBothSelectionCannotReuseAnEarlierBothSample()
    {
        var m = Model(); var o = Pose();
        m.TryRender(o, 1, 1.01, 1.02, out _, out _); Confirm(m);
        // The probe invalidates on every 1/2/3/C/Space view transition.
        m.Invalidate();
        Assert.That(m.TryRender(o, 1, 1.01, 1.03, out _, out _, StereoProbeView.Channels), Is.False);
        m.Invalidate();
        Assert.Throws<InvalidOperationException>(() => m.CreateRecord(1.04));
        m.TryRender(o, 1, 1.01, 1.05, out _, out _, StereoProbeView.Both);
        Assert.That(m.CreateRecord(1.06).rendered_seconds, Is.EqualTo(1.05));
    }
}
