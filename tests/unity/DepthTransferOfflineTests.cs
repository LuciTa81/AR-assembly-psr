using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using ARAssembly;
using NUnit.Framework;

public class DepthTransferOfflineTests
{
    private static readonly JsonSerializerOptions Json = new JsonSerializerOptions {
        IncludeFields = true, WriteIndented = true
    };

    private static DisplayCollectionConfig Config(CandidateProjection p) => new DisplayCollectionConfig {
        schema_version = "beast_display_collection_config_v1", session_id = "offline",
        token = "offline-unused", directory = "offline", observation_url = "http://127.0.0.1:1/observation",
        target_id = "A", image_size = new[]{1280,720}, camera_profile_id = p.camera_profile_id,
        camera_profile_sha256 = p.camera_profile_sha256, workspace_profile_id = p.workspace_profile_id,
        workspace_profile_sha256 = p.workspace_profile_sha256
    };

    public sealed class Input
    {
        public string schema_version, source_candidate_sha256, trial_candidate_sha256;
        public CandidateProjection source_candidate, trial_candidate;
        public Dictionary<string, TrackedAlignmentRecord[]> records;
        public Case[] cases;
    }
    public sealed class Case
    {
        public string id, group, target, old_reason, new_reason;
        public double[] old_xyz_mm, new_xyz_mm;
    }
    public sealed class Result
    {
        public string id, group, target, old_status, new_status;
        public double[] old_left, old_right, new_left, new_right;
        public double? left_delta_px, right_delta_px, depth_delta_mm;
        public double[] disparity_delta_px;
    }

    private static string Project(TargetDepthTrial model, double[] xyz, out double[] l, out double[] r)
    {
        l = r = null;
        if (xyz == null) return "no_pose";
        Assert.That(xyz.Length, Is.EqualTo(3));
        Assert.That(xyz.All(double.IsFinite), Is.True);
        if (!model.ContainsDepth(xyz[2])) return "outside_depth";
        return model.TryProject(xyz, out l, out r) ? "visible" : "outside_eye_view";
    }

    [Test, Explicit("Opt-in local numeric replay; never opens a camera or Unity")]
    public void ReplayImmutableDepthRecordsWithBothWorkspacePoses()
    {
        var path = Environment.GetEnvironmentVariable("BEAST_DEPTH_TRANSFER_INPUT");
        Assert.That(path, Is.Not.Null.And.Not.Empty, "Provide the offline input JSON");
        var input = JsonSerializer.Deserialize<Input>(File.ReadAllText(path), Json);
        Assert.That(input.schema_version, Is.EqualTo("beast_depth_transfer_input_v1"));
        var source = input.source_candidate;
        var trial = input.trial_candidate;
        Assert.That(trial.camera_profile_sha256, Is.EqualTo(source.camera_profile_sha256));
        Assert.That(trial.workspace_profile_sha256, Is.Not.EqualTo(source.workspace_profile_sha256));
        Assert.That(trial.left_projection, Is.EqualTo(source.left_projection));
        Assert.That(trial.right_projection, Is.EqualTo(source.right_projection));
        source.Validate(Config(source));
        Assert.Throws<ArgumentException>(() => trial.Validate(Config(source)));
        trial.Validate(Config(trial));
        var models = new Dictionary<string, TargetDepthTrial>();
        foreach (var target in new[]{"C","D"}) {
            var rows = input.records[target];
            var model = new TargetDepthTrial(source, input.source_candidate_sha256, target, rows);
            models.Add(target, model);
            // Original records cannot be silently attached to the new candidate/workspace.
            Assert.Throws<ArgumentException>(() => new TargetDepthTrial(trial, input.trial_candidate_sha256, target, rows));
            Assert.Throws<ArgumentException>(() => new TargetDepthTrial(source, input.trial_candidate_sha256, target, rows));
            Assert.Throws<ArgumentException>(() => new TargetDepthTrial(source, input.source_candidate_sha256,
                target == "C" ? "D" : "C", rows));
            foreach (var row in rows) {
                Assert.That(model.TryProject(row.observation.camera_xyz_mm, out var l, out var r), Is.True);
                Assert.That(l, Is.EqualTo(row.left_final_px).Within(1e-6));
                Assert.That(r, Is.EqualTo(row.right_final_px).Within(1e-6));
            }
            foreach (var z in new[]{rows[0].observation.camera_xyz_mm[2] - .001,
                                   rows[2].observation.camera_xyz_mm[2] + .001})
                Assert.That(model.TryProject(new[]{0d,0d,z}, out _, out _), Is.False);
        }
        Assert.That(input.cases.Length, Is.GreaterThan(6));
        Assert.That(input.cases.Select(c => c.id).Distinct().Count(), Is.EqualTo(input.cases.Length));
        var results = new List<Result>();
        foreach (var c in input.cases) {
            Assert.That(c.old_xyz_mm != null, Is.EqualTo(c.old_reason == "tracking"));
            Assert.That(c.new_xyz_mm != null, Is.EqualTo(c.new_reason == "tracking"));
            var row = new Result {id=c.id, group=c.group, target=c.target};
            row.old_status = Project(models[c.target], c.old_xyz_mm, out row.old_left, out row.old_right);
            row.new_status = Project(models[c.target], c.new_xyz_mm, out row.new_left, out row.new_right);
            if (c.old_xyz_mm != null && c.new_xyz_mm != null)
                row.depth_delta_mm = c.new_xyz_mm[2] - c.old_xyz_mm[2];
            if (row.old_status == "visible" && row.new_status == "visible") {
                row.left_delta_px = Distance(row.old_left, row.new_left);
                row.right_delta_px = Distance(row.old_right, row.new_right);
                row.disparity_delta_px = Enumerable.Range(0,2).Select(k =>
                    (row.new_left[k]-row.new_right[k])-(row.old_left[k]-row.old_right[k])).ToArray();
            }
            results.Add(row);
        }
        var output = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path)),
            Path.GetFileNameWithoutExtension(path) + ".replay-" + Guid.NewGuid().ToString("N") + ".json");
        using (var stream = new FileStream(output, FileMode.CreateNew))
            JsonSerializer.Serialize(stream, new {schema_version="beast_depth_transfer_replay_v1",
                method="Original TargetDepthTrial evaluated at old/new camera coordinates; no runtime binding migration",
                source_records_reproduced=6, direct_new_binding_rejected=true,
                calibration_valid=false, display_alignment_verified=false, results}, Json);
        TestContext.WriteLine("Offline depth replay: " + output);
    }

    private static double Distance(double[] a, double[] b) =>
        Math.Sqrt(Math.Pow(a[0]-b[0],2)+Math.Pow(a[1]-b[1],2));

    [Test, Explicit("Real source-bound manifest against stored coordinates; no devices")]
    public void LoadedTransferMatchesReviewedCases()
    {
        string path=Environment.GetEnvironmentVariable("BEAST_DEPTH_TRANSFER_INPUT");
        string folder=Environment.GetEnvironmentVariable("BEAST_DEPTH_TRANSFER_TRIAL");
        Assert.That(path,Is.Not.Null.And.Not.Empty);
        Assert.That(folder,Is.Not.Null.And.Not.Empty);
        var input=JsonSerializer.Deserialize<Input>(File.ReadAllText(path),Json);
        byte[] bytes=File.ReadAllBytes(Path.Combine(folder,"candidate-cd.json"));
        var trial=JsonSerializer.Deserialize<CandidateProjection>(bytes,Json);
        var config=Config(trial);
        StageDepthConfig.LoadAndBind(trial,bytes,config,Path.Combine(folder,"depth-transfer.json"),
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            (text,type)=>JsonSerializer.Deserialize(text,type,Json));
        input.source_candidate.Validate(Config(input.source_candidate));
        var source=new Dictionary<string,TargetDepthTrial>();
        foreach(string target in new[]{"C","D"})
            source[target]=new TargetDepthTrial(input.source_candidate,input.source_candidate_sha256,target,input.records[target]);
        int compared=0, visible=0, outside=0, noPose=0;
        foreach(var c in input.cases) {
            string expected=Project(source[c.target],c.new_xyz_mm,out var el,out var er);
            if(c.new_xyz_mm==null) {
                var state=new GuidanceState(); var frame=AssemblyGuidanceTests.Frame();
                frame.session_id=config.session_id; frame.current_state=c.target=="C" ? "S4" : "S5";
                frame.target="screw_"+c.target.ToLowerInvariant(); state.Apply(frame,2,2.01);
                Assert.That(trial.PresentationStatus(new DisplayObservationFeedback(),state,config.session_id,2.02,
                    out var absentL,out var absentR,true),Is.Not.EqualTo("VISIBLE"),c.id);
                Assert.That(absentL,Is.Null); Assert.That(absentR,Is.Null); noPose++; continue;
            }
            string actual=StageDepthConfigTests.Gate(trial,config,c.target,c.new_xyz_mm,out var l,out var r);
            string gate=expected=="visible" ? "VISIBLE" : expected=="outside_depth" ? "OUTSIDE TARGET DEPTH" : "OUTSIDE EYE VIEW";
            Assert.That(actual,Is.EqualTo(gate),c.id);
            if(expected=="visible") {
                Assert.That(l,Is.EqualTo(el).Within(1e-9),c.id);
                Assert.That(r,Is.EqualTo(er).Within(1e-9),c.id); visible++;
            } else { Assert.That(l,Is.Null); Assert.That(r,Is.Null); outside++; }
            compared++;
        }
        TestContext.WriteLine("Transfer parity: "+compared+" poses; "+visible+" visible; "+outside+" outside; "+noPose+" no-pose hidden.");
        Assert.That(compared+noPose,Is.EqualTo(input.cases.Length));
    }
}
