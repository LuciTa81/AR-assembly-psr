using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using ARAssembly;
using NUnit.Framework;

public class BoxOutlineTests
{
    private static BoxOutlineProfile RoundedProfile()
    {
        var b=Profile();
        for(int i=0;i<4;i++) { b.vertices_mm[12+3*i]=b.vertices_mm[3*i]; b.vertices_mm[13+3*i]=b.vertices_mm[1+3*i]; }
        b.staged_rounded=true; b.lid_height_mm=10; b.corner_radius_mm=3;
        return b;
    }

    [Test]
    public void RoundedBackCornerKeepsNormalEmphasis()
    {
        var b=RoundedProfile(); b.Validate(CandidateProjectionTests.Profile());
        var strokes=b.BuildStrokes(State("S0","box").LastSnapshot);
        var vertical=strokes.Single(s=>s.Points.Length==2 && s.Points[0][2]==0 && s.Points[1][2]==50
            && Math.Abs(s.Points[0][0]-100.75)<1e-8 && Math.Abs(s.Points[0][1]-70.75)<1e-8);
        Assert.That(vertical.Level,Is.EqualTo(2));
    }

    [TestCase("S0","box",0,50,2,20)]
    [TestCase("S1","lid",50,60,3,20)]
    [TestCase("S2","screw_a",50,60,2,20)]
    [TestCase("S3","screw_b",50,60,2,20)]
    [TestCase("S4","screw_c",50,60,2,20)]
    [TestCase("S5","screw_d",50,60,2,20)]
    [TestCase("S6","complete",0,60,2,32)]
    public void RoundedStagesSeparateBodyAndLid(string step,string target,double bottom,double height,int level,int count)
    {
        var p=CandidateProjectionTests.Profile(); var b=RoundedProfile(); b.Validate(p);
        // View direction must not dim the body's rear or bottom edges.
        var strokes=b.BuildStrokes(State(step,target).LastSnapshot);
        Assert.That(strokes.Length,Is.EqualTo(count));
        Assert.That(strokes.SelectMany(s=>s.Points).Max(v=>v[2]),Is.EqualTo(height));
        Assert.That(strokes.SelectMany(s=>s.Points).Min(v=>v[2]),Is.EqualTo(bottom));
        Assert.That(strokes.Min(s=>s.Level),Is.EqualTo(level));
        Assert.That(strokes.Max(s=>s.Level),Is.EqualTo(level));
        Assert.That(strokes.SelectMany(s=>s.Points).Any(v=>v[2]==50),Is.True);
        Assert.That(strokes.Any(s=>s.Points.Length>2),Is.True);
        Assert.That(strokes.SelectMany(s=>s.Points).All(v=>v[0]>=100 && v[0]<=230 && v[1]>=70 && v[1]<=200),Is.True);
        // Every endpoint meets another segment; no floating vertical lines at old sharp corners.
        var ends=strokes.SelectMany(s=>new[]{s.Points[0],s.Points[s.Points.Length-1]}).ToArray();
        foreach(var end in ends) Assert.That(strokes.SelectMany(s=>s.Points).Count(v=>v.Zip(end,(a,c)=>Math.Abs(a-c)).Max()<1e-8),Is.GreaterThanOrEqualTo(2));
    }

    private static void FinalFrame(GuidanceState state,DisplayObservationFeedback feedback,long id,double now,
        string phase="AWAITING_CONFIRMATION")
    {
        var frame=AssemblyGuidanceTests.Frame(id,phase);
        frame.session_id="session"; frame.current_state="S6"; frame.target="complete";
        frame.guidance.reason="operator_confirmation";
        Assert.That(state.Apply(frame,now,now+.01),Is.True);
        var observation=Observation(); observation.frame_id=id;
        feedback.Apply(DisplayObservationTests.Config(),observation,now,now+.01);
    }

    [Test]
    public void FinalInspectionShowsFullBoxUntilConfirmationThenTextOnly()
    {
        var p=CandidateProjectionTests.Profile(); p.Validate(DisplayObservationTests.Config());
        var b=RoundedProfile(); b.Validate(p);
        var s=new GuidanceState(); var f=new DisplayObservationFeedback();
        FinalFrame(s,f,1,1);
        Assert.That(b.TryProjectStrokes(p,f,s,"session",1.02,out var l,out var r),Is.True);
        Assert.That(l.Length,Is.EqualTo(32)); Assert.That(r.Length,Is.EqualTo(32));
        Assert.That(l.All(stroke=>stroke.Level==2),Is.True);
        Assert.That(b.TryProjectStrokes(p,f,s,"session",1.2,out _,out _),Is.False,"Expired pose cannot be held during inspection");
        FinalFrame(s,f,2,10);
        Assert.That(b.TryProjectStrokes(p,f,s,"session",10.02,out _,out _),Is.True,"Inspection has no display timeout");
        FinalFrame(s,f,3,10.1,"COMPLETED");
        Assert.That(b.WantsObservation(s,10.12),Is.False);
        Assert.That(b.BuildStrokes(s.LastSnapshot),Is.Empty);
        Assert.That(b.TryProjectStrokes(p,f,s,"session",10.12,out _,out _),Is.False);
        FinalFrame(s,f,4,11,"COMPLETED");
        Assert.That(b.TryProject(p,f,s,"session",11.02,out _,out _),Is.False);
        Assert.That(s.Presentation(11.02).Cue,Is.EqualTo("CONFIRMED"));
    }

    [Test]
    public void FinalInspectionCannotShowWithoutOperatorCheckContract()
    {
        var b=RoundedProfile(); b.Validate(CandidateProjectionTests.Profile());
        var frame=State("S6","complete").LastSnapshot;
        frame.guidance.reason="";
        Assert.That(b.IncludesStage(frame),Is.False);
        frame.guidance.reason="operator_confirmation"; frame.target="screw_d";
        Assert.That(b.IncludesStage(frame),Is.False);
    }

    [TestCase("session")][TestCase("disconnect")][TestCase("lost")][TestCase("stale_state")]
    public void FinalInspectionStillRequiresValidStateAndPose(string fault)
    {
        var p=CandidateProjectionTests.Profile(); p.Validate(DisplayObservationTests.Config());
        var b=RoundedProfile(); b.Validate(p);
        var s=new GuidanceState(); var f=new DisplayObservationFeedback();
        FinalFrame(s,f,1,1);
        if(fault=="disconnect") s.Disconnect();
        if(fault=="lost") {
            var frame=s.LastSnapshot.Copy(); frame.frame_id++; frame.timestamp_ms+=100;
            frame.marker_status="LOST";
            Assert.That(s.Apply(frame,1.02,1.03),Is.True);
        }
        Assert.That(b.TryProjectStrokes(p,f,s,fault=="session"?"other":"session",
            fault=="stale_state"?1.6:1.04,out _,out _),Is.False);
    }

    [Test]
    public void InspectionRecoversWithFreshPoseButNeverResurrectsAfterConfirmation()
    {
        var p=CandidateProjectionTests.Profile(); p.Validate(DisplayObservationTests.Config());
        var b=RoundedProfile(); b.Validate(p);
        var s=new GuidanceState(); var f=new DisplayObservationFeedback();
        FinalFrame(s,f,1,1);
        Assert.That(b.WantsObservation(s,1.02),Is.True);
        s.Disconnect();
        Assert.That(b.TryProjectStrokes(p,f,s,"session",1.03,out _,out _),Is.False);
        FinalFrame(s,f,2,2);
        Assert.That(b.TryProjectStrokes(p,f,s,"session",2.02,out _,out _),Is.True);
        FinalFrame(s,f,3,3,"COMPLETED");
        Assert.That(b.TryProjectStrokes(p,f,s,"session",3.02,out _,out _),Is.False);
        s.Disconnect();
        FinalFrame(s,f,4,4,"COMPLETED");
        Assert.That(b.TryProjectStrokes(p,f,s,"session",4.02,out _,out _),Is.False);
        Assert.That(b.WantsObservation(State("S0","box"),4.2),Is.True);
        var legacy=Profile(); legacy.Validate(p);
        Assert.That(legacy.WantsObservation(State("S6","complete"),1.02),Is.False);
    }

    [TestCase("zero")][TestCase("height")][TestCase("radius")][TestCase("nan")][TestCase("taper")]
    public void RoundedDimensionsAreValidated(string fault)
    {
        var b=RoundedProfile();
        if(fault=="zero") b.lid_height_mm=0;
        if(fault=="height") b.lid_height_mm=60;
        if(fault=="radius") b.corner_radius_mm=70;
        if(fault=="nan") b.corner_radius_mm=double.NaN;
        if(fault=="taper") b.vertices_mm[12]+=2;
        Assert.Throws<ArgumentException>(()=>b.Validate(CandidateProjectionTests.Profile()));
    }

    [Test]
    public void RoundedProjectionIsOptInFreshAndSessionBound()
    {
        var p=CandidateProjectionTests.Profile(); p.Validate(DisplayObservationTests.Config());
        var b=RoundedProfile(); b.Validate(p);
        b.lid_height_mm=59; b.corner_radius_mm=60; b.staged_rounded=false;
        var f=new DisplayObservationFeedback(); f.Apply(DisplayObservationTests.Config(),Observation(),1,1.01);
        Assert.That(b.RoundedStaged,Is.True);
        Assert.That(b.IncludesStage(State("S0","box").LastSnapshot),Is.True);
        Assert.That(b.TryProjectStrokes(p,f,State("S0","box"),"session",1.02,out var l,out var r),Is.True);
        Assert.That(l.Length,Is.EqualTo(20)); Assert.That(r.Length,Is.EqualTo(20));
        Assert.That(b.TryProjectStrokes(p,f,State(),"other",1.02,out _,out _),Is.False);
        Assert.That(b.TryProjectStrokes(p,f,State(),"session",1.2,out _,out _),Is.False);
        Assert.That(b.TryProjectStrokes(p,f,State("S6","complete"),"session",1.02,out _,out _),Is.True);
        var wrong=State("S0","box").LastSnapshot; wrong.target="lid";
        Assert.That(b.IncludesStage(wrong),Is.False);
        var legacy=Profile(); legacy.Validate(p);
        Assert.That(legacy.IncludesStage(State("S0","box").LastSnapshot),Is.False);
        Assert.That(legacy.TryProjectStrokes(p,f,State(),"session",1.02,out _,out _),Is.False);
    }

    public static BoxOutlineProfile Profile() => new BoxOutlineProfile {
        schema_version="beast_box_outline_trial_v1", candidate_only=true,
        camera_profile_sha256=new string('a',64), workspace_profile_sha256=new string('b',64),
        vertices_mm=new double[]{100,200,60, 230,200,60, 230,70,60, 100,70,60,
            102,198,0, 228,198,0, 228,72,0, 102,72,0}
    };

    private static DisplayObservation Observation()
    {
        var o=DisplayObservationTests.Observation();
        o.age_ms=0; o.rvec=new double[3]; o.tvec_mm=new double[]{-165,-135,500};
        o.camera_xyz_mm=new double[]{-15,15,560};
        return o;
    }

    private static GuidanceState State(string step="S1", string target="lid")
    {
        var s=new GuidanceState(); var f=AssemblyGuidanceTests.Frame(1,step=="S6"?"AWAITING_CONFIRMATION":"GUIDING");
        f.session_id="session"; f.current_state=step; f.target=target;
        if(step=="S6") f.guidance.reason="operator_confirmation";
        Assert.That(s.Apply(f,1,1.01),Is.True);
        return s;
    }

    [Test]
    public void ProfileIsBoundAndFrozenAfterValidation()
    {
        var p=CandidateProjectionTests.Profile(); p.Validate(DisplayObservationTests.Config());
        var b=Profile(); b.Validate(p); b.vertices_mm[0]=100000;
        var f=new DisplayObservationFeedback(); f.Apply(DisplayObservationTests.Config(),Observation(),1,1.01);
        Assert.That(b.TryProject(p,f,State(),"session",1.02,out var l,out var r),Is.True);
        Assert.That(l.Length,Is.EqualTo(8)); Assert.That(r.Length,Is.EqualTo(8));
        Assert.That(p.TryProject(new double[]{-65,65,560},out var expectedL,out var expectedR),Is.True);
        Assert.That(l[0],Is.EqualTo(expectedL).Within(1e-8));
        Assert.That(r[0],Is.EqualTo(expectedR).Within(1e-8));
        Assert.That(CandidateProjection.StageTarget(State().LastSnapshot),Is.Null);
    }

    [TestCase("hash")][TestCase("size")][TestCase("nan")][TestCase("height")]
    [TestCase("crossed")][TestCase("duplicate")][TestCase("plane")][TestCase("candidate")]
    public void InvalidProfileRejected(string fault)
    {
        var b=Profile(); var p=CandidateProjectionTests.Profile();
        if(fault=="hash") b.workspace_profile_sha256=new string('c',64);
        if(fault=="size") b.vertices_mm=new double[23];
        if(fault=="nan") b.vertices_mm[0]=double.NaN;
        if(fault=="height") b.vertices_mm[2]=-1;
        if(fault=="crossed") for(int i=0;i<3;i++) {
            double t=b.vertices_mm[3+i]; b.vertices_mm[3+i]=b.vertices_mm[6+i]; b.vertices_mm[6+i]=t;
        }
        if(fault=="duplicate") Array.Copy(b.vertices_mm,0,b.vertices_mm,3,3);
        if(fault=="plane") b.vertices_mm[5]=59;
        if(fault=="candidate") b.candidate_only=false;
        Assert.Throws<ArgumentException>(()=>b.Validate(p));
    }

    [TestCase("S1","lid",true)][TestCase("S2","screw_a",true)]
    [TestCase("S3","screw_b",true)][TestCase("S4","screw_c",true)]
    [TestCase("S5","screw_d",true)][TestCase("S0","box",false)]
    [TestCase("S6","complete",false)]
    public void OnlyLidAndScrewStagesAreEligible(string step,string target,bool expected)
    {
        var p=CandidateProjectionTests.Profile(); p.Validate(DisplayObservationTests.Config());
        var b=Profile(); b.Validate(p);
        var f=new DisplayObservationFeedback(); f.Apply(DisplayObservationTests.Config(),Observation(),1,1.01);
        var s=State(step,target);
        Assert.That(BoxOutlineProfile.IsStage(s.LastSnapshot),Is.EqualTo(expected));
        Assert.That(b.TryProject(p,f,s,"session",1.02,out _,out _),Is.EqualTo(expected));
    }

    [TestCase("session")][TestCase("stale")][TestCase("lost")][TestCase("disconnect")]
    [TestCase("mismatch")][TestCase("behind")][TestCase("outside")][TestCase("rejected")]
    public void InvalidOrExpiredPoseCannotDrawBox(string fault)
    {
        foreach(bool rounded in new[]{false,true}) {
        var p=CandidateProjectionTests.Profile(); p.Validate(DisplayObservationTests.Config());
        var b=rounded?RoundedProfile():Profile(); b.Validate(p); var o=Observation(); var s=State();
        var f=new DisplayObservationFeedback();
        if(fault=="mismatch") o.camera_xyz_mm[0]+=1;
        if(fault=="behind" || fault=="outside") {
            o.tvec_mm[0]=fault=="outside"?10000:-165;
            o.tvec_mm[2]=fault=="behind"?-30:500;
            o.camera_xyz_mm=new[]{150+o.tvec_mm[0],15,60+o.tvec_mm[2]};
        }
        if(fault=="rejected") { o.status="pose_rejected"; o.reason="No pose"; }
        f.Apply(DisplayObservationTests.Config(),o,1,1.01);
        if(fault=="disconnect") s.Disconnect();
        if(fault=="lost") {
            var frame=AssemblyGuidanceTests.Frame(2); frame.session_id="session";
            frame.current_state="S1"; frame.target="lid"; frame.marker_status="LOST";
            s.Apply(frame,1.02,1.03);
        }
        Assert.That(b.TryProject(p,f,s,fault=="session"?"other":"session",
            fault=="stale"?1.2:1.04,out var l,out var r),Is.False);
        Assert.That(l,Is.Null); Assert.That(r,Is.Null);
        if(rounded) Assert.That(b.TryProjectStrokes(p,f,s,fault=="session"?"other":"session",
            fault=="stale"?1.2:1.04,out _,out _),Is.False);
        }
    }

    [Test]
    public void FreshPoseIsClonedAndCannotBeRevivedByDuplicatePolls()
    {
        var f=new DisplayObservationFeedback(); var o=Observation(); var c=DisplayObservationTests.Config();
        f.Apply(c,o,1,1.01); o.tvec_mm[0]=999;
        Assert.That(f.TryGetObservation(1.02,out var first),Is.True);
        Assert.That(first.tvec_mm[0],Is.EqualTo(-165)); first.tvec_mm[0]=888;
        f.Apply(c,o,1.04,1.05);
        Assert.That(f.TryGetObservation(1.06,out var second),Is.True);
        Assert.That(second.tvec_mm[0],Is.EqualTo(-165));
        Assert.That(f.TryGetObservation(1.16,out _),Is.False);
        f.Fail("CONNECTION ERROR");
        Assert.That(f.TryGetObservation(1.07,out _),Is.False);
    }

    [Test]
    public void RodriguesTransformHandlesZeroAndQuarterTurn()
    {
        Assert.That(BoxOutlineProfile.ToCamera(new double[]{1,2,3},new double[3],new double[]{4,5,6}),
            Is.EqualTo(new double[]{5,7,9}).Within(1e-9));
        Assert.That(BoxOutlineProfile.ToCamera(new double[]{1,2,3},new double[]{0,0,Math.PI/2},new double[]{4,5,6}),
            Is.EqualTo(new double[]{2,6,9}).Within(1e-9));
    }

    [TestCase("S2","screw_a",false)]
    [TestCase("S2","screw_a",true)][TestCase("S3","screw_b",true)]
    [TestCase("S4","screw_c",true)][TestCase("S5","screw_d",true)]
    public void BoxFailureDoesNotChangeActiveScrewPixels(string step,string target,bool stageTargets)
    {
        foreach(bool rounded in new[]{false,true}) {
        var p=CandidateProjectionTests.Profile(); var config=DisplayObservationTests.Config(); p.Validate(config);
        var b=rounded?RoundedProfile():Profile();
        for(int i=0;i<8;i++) b.vertices_mm[3*i]+=1000;
        b.Validate(p);
        var o=Observation();
        o.camera_targets=Enumerable.Range(0,4).Select(i=>new DisplayCameraTarget {
            target_id=((char)('A'+i)).ToString(),camera_xyz_mm=new double[]{-15+i*20,15,560}
        }).ToArray();
        var f=new DisplayObservationFeedback(); f.Apply(config,o,1,1.01);
        var s=State(step,target);
        Assert.That(p.PresentationStatus(f,s,"session",1.02,out var beforeL,out var beforeR,stageTargets),Is.EqualTo("VISIBLE"));
        Assert.That(b.TryProject(p,f,s,"session",1.02,out _,out _),Is.False);
        if(rounded) Assert.That(b.TryProjectStrokes(p,f,s,"session",1.02,out _,out _),Is.False);
        Assert.That(p.PresentationStatus(f,s,"session",1.02,out var afterL,out var afterR,stageTargets),Is.EqualTo("VISIBLE"));
        Assert.That(afterL,Is.EqualTo(beforeL)); Assert.That(afterR,Is.EqualTo(beforeR));
        }
    }

    [Test]
    public void SavedOpenCvPosesMatchBoxCameraAndEyeProjection()
    {
        string path=Environment.GetEnvironmentVariable("BEAST_BOX_OFFLINE_REPORT");
        if(string.IsNullOrEmpty(path)) Assert.Ignore("Set BEAST_BOX_OFFLINE_REPORT for the saved-pose parity check.");
        using var report=JsonDocument.Parse(File.ReadAllText(path));
        using var geometry=JsonDocument.Parse(File.ReadAllText(report.RootElement.GetProperty("geometry_profile").GetString()));
        using var eye=JsonDocument.Parse(File.ReadAllText(report.RootElement.GetProperty("eye_projection").GetString()));
        double[] vertices=Values(geometry.RootElement.GetProperty("vertices_mm"));
        var p=CandidateProjectionTests.Profile();
        p.left_projection=Values(eye.RootElement.GetProperty("left_projection"));
        p.right_projection=Values(eye.RootElement.GetProperty("right_projection"));
        var config=DisplayObservationTests.Config();
        p.camera_profile_sha256=config.camera_profile_sha256=geometry.RootElement.GetProperty("camera_profile_sha256").GetString();
        p.workspace_profile_sha256=config.workspace_profile_sha256=geometry.RootElement.GetProperty("workspace_profile_sha256").GetString();
        p.Validate(config);
        string roundedPath=Environment.GetEnvironmentVariable("BEAST_ROUNDED_BOX_PROFILE");
        var rounded=string.IsNullOrEmpty(roundedPath)?RoundedProfile():JsonSerializer.Deserialize<BoxOutlineProfile>(
            File.ReadAllText(roundedPath),new JsonSerializerOptions {IncludeFields=true});
        if(string.IsNullOrEmpty(roundedPath)) {
            rounded.vertices_mm=vertices;
            rounded.camera_profile_sha256=p.camera_profile_sha256; rounded.workspace_profile_sha256=p.workspace_profile_sha256;
        }
        rounded.Validate(p);
        Assert.That(rounded.RoundedStaged,Is.True);
        Assert.That(rounded.lid_height_mm,Is.EqualTo(10));
        var preview=new System.Collections.Generic.List<object>();
        int count=0;
        foreach(var record in report.RootElement.GetProperty("records").EnumerateArray()) {
            var rotation=Values(record.GetProperty("rvec")); var translation=Values(record.GetProperty("tvec_mm"));
            for(int i=0;i<8;i++) {
                var xyz=BoxOutlineProfile.ToCamera(vertices.Skip(i*3).Take(3).ToArray(),rotation,translation);
                Assert.That(xyz,Is.EqualTo(Values(record.GetProperty("camera_xyz_mm")[i])).Within(1e-8));
                Assert.That(p.TryProject(xyz,out var left,out var right),Is.True);
                Assert.That(left,Is.EqualTo(Values(record.GetProperty("eye_pixels").GetProperty("left")[i])).Within(1e-8));
                Assert.That(right,Is.EqualTo(Values(record.GetProperty("eye_pixels").GetProperty("right")[i])).Within(1e-8));
                count++;
            }
            foreach(var step in new[]{"S0","S1","S2","S6"}) {
                var f=State(step,step=="S0"?"box":step=="S1"?"lid":step=="S6"?"complete":"screw_a").LastSnapshot;
                var world=rounded.BuildStrokes(f);
                var projected=new System.Collections.Generic.List<object>();
                foreach(var stroke in world) {
                    var left=new double[stroke.Points.Length][]; var right=new double[left.Length][];
                    for(int i=0;i<left.Length;i++) Assert.That(p.TryProject(
                        BoxOutlineProfile.ToCamera(stroke.Points[i],rotation,translation),out left[i],out right[i]),Is.True);
                    projected.Add(new {level=stroke.Level,left,right});
                }
                preview.Add(new {step,strokes=projected});
            }
        }
        Assert.That(count,Is.GreaterThanOrEqualTo(24));
        TestContext.Progress.WriteLine("Saved OpenCV/C# parity: "+count+" box vertices; no camera opened.");
        string output=Environment.GetEnvironmentVariable("BEAST_ROUNDED_BOX_PREVIEW_DATA");
        if(!string.IsNullOrEmpty(output)) File.WriteAllText(output,JsonSerializer.Serialize(preview));
    }

    private static double[] Values(JsonElement array) => array.EnumerateArray().Select(v=>v.GetDouble()).ToArray();
}
