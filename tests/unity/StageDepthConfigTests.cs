using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;
using ARAssembly;
using NUnit.Framework;

public class StageDepthConfigTests
{
    private static readonly JsonSerializerOptions Json = new JsonSerializerOptions { IncludeFields = true };
    private string root, manifestPath;
    private CandidateProjection source, destination;
    private DisplayCollectionConfig live;
    private byte[] destinationBytes;
    private StageDepthConfig manifest;

    private string Write(string name, object value) {
        string path = Path.Combine(root, name);
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonSerializer.Serialize(value, Json));
        return path;
    }
    private static string Hash(byte[] bytes) {
        using var sha = SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }
    private static object Parse(string text, Type type) => JsonSerializer.Deserialize(text, type, Json);
    private void Load() {
        Write("depth.json", manifest);
        StageDepthConfig.LoadAndBind(destination, destinationBytes, live, manifestPath, root, Parse);
    }
    private object Workspace(string id, double targetX = 0) => new {
        profile_id = id, schema_version = "beast_workspace_metric_v1", units = "mm",
        axes = "x_right_y_away_z_up", origin_marker_id = 3,
        targets_mm = new { A = new[]{0d,0,60}, B = new[]{100d,0,60},
            C = new[]{targetX,100,60}, D = new[]{100d,100,60} }
    };

    [SetUp]
    public void SetUp() {
        root = Path.Combine(Path.GetTempPath(), "beast-depth-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        manifestPath = Path.Combine(root, "depth.json");
        string oldWorkspace = Write("old-workspace.json", Workspace("workspace"));
        string newWorkspace = Write("new-workspace.json", Workspace("workspace202"));
        source = CandidateProjectionTests.Profile();
        source.workspace_profile_sha256 = Hash(File.ReadAllBytes(oldWorkspace));
        var oldConfig = DisplayObservationTests.Config();
        oldConfig.workspace_profile_sha256 = source.workspace_profile_sha256;
        source.Validate(oldConfig);
        string sourceFile = Write("source.json", source);
        string sourceHash = Hash(File.ReadAllBytes(sourceFile));
        string[] Records(string target, int offset) {
            return new[]{320d,420,500}.Select((z,i) => {
                var o = DisplayObservationTests.Observation();
                o.target_id=target; o.camera_xyz_mm=new[]{0d,0d,z};
                o.workspace_profile_sha256=source.workspace_profile_sha256; o.age_ms=0;
                o.world_xyz_mm=target=="C" ? new[]{0d,100d,60d} : new[]{100d,100d,60d};
                var config=DisplayObservationTests.Config(); config.target_id=target;
                config.workspace_profile_sha256=source.workspace_profile_sha256;
                var diagnostic=new TrackedAlignmentDiagnostic(config, source, sourceHash);
                diagnostic.Move(StereoProbeView.Left,offset,4);
                diagnostic.Move(StereoProbeView.Right,-offset,8);
                Assert.That(diagnostic.TryRender(o,1,1.01,1.02,out _,out _),Is.True);
                diagnostic.ConfirmEye(StereoProbeView.Left); diagnostic.ConfirmEye(StereoProbeView.Right);
                string relative=target+"/frame-"+i+".json";
                Write(Path.Combine("ARAssembly","beast-mvp","display_correspondence",relative),
                    diagnostic.CreateRecord(1.03));
                return relative;
            }).ToArray();
        }
        manifest = new StageDepthConfig { schema_version="beast_stage_depth_config_v2", c=Records("C",12), d=Records("D",-9) };
        destination = CandidateProjectionTests.Profile();
        destination.workspace_profile_id="workspace202";
        destination.workspace_profile_sha256=Hash(File.ReadAllBytes(newWorkspace));
        destinationBytes=System.Text.Encoding.UTF8.GetBytes(JsonSerializer.Serialize(destination,Json));
        live=DisplayObservationTests.Config();
        live.workspace_profile_id=destination.workspace_profile_id;
        live.workspace_profile_sha256=destination.workspace_profile_sha256;
        destination.Validate(live);
        manifest.transfer = new StageDepthTransfer {
            schema_version="beast_stage_depth_transfer_v1", candidate_only=true,
            source_candidate_path=sourceFile, source_candidate_sha256=sourceHash,
            destination_candidate_sha256=Hash(destinationBytes),
            source_workspace_path=oldWorkspace, source_workspace_sha256=source.workspace_profile_sha256,
            destination_workspace_path=newWorkspace, destination_workspace_sha256=destination.workspace_profile_sha256,
            c_sha256=manifest.c.Select(p=>Hash(File.ReadAllBytes(RecordPath(p)))).ToArray(),
            d_sha256=manifest.d.Select(p=>Hash(File.ReadAllBytes(RecordPath(p)))).ToArray()
        };
    }
    private string RecordPath(string p) => Path.Combine(root,"ARAssembly","beast-mvp","display_correspondence",p);

    [TearDown]
    public void TearDown() {
        string full=Path.GetFullPath(root);
        Assert.That(full.StartsWith(Path.GetFullPath(Path.GetTempPath()) + "beast-depth-test-",StringComparison.OrdinalIgnoreCase),Is.True);
        Directory.Delete(full,true);
    }

    public static string Gate(CandidateProjection p, DisplayCollectionConfig config, string target, double z,
        out double[] left, out double[] right) => Gate(p,config,target,new[]{0d,0d,z},out left,out right);

    public static string Gate(CandidateProjection p, DisplayCollectionConfig config, string target, double[] xyz,
        out double[] left, out double[] right) {
        var frame=AssemblyGuidanceTests.Frame();
        frame.session_id=config.session_id;
        frame.current_state="S"+(target[0]-'A'+2); frame.target="screw_"+target.ToLowerInvariant();
        var state=new GuidanceState(); state.Apply(frame,2,2.01);
        var o=DisplayObservationTests.Observation(); o.age_ms=0; o.session_id=config.session_id;
        o.camera_profile_id=config.camera_profile_id; o.camera_profile_sha256=config.camera_profile_sha256;
        o.workspace_profile_id=config.workspace_profile_id; o.workspace_profile_sha256=config.workspace_profile_sha256;
        o.camera_xyz_mm=xyz;
        o.camera_targets="ABCD".Select(t=>new DisplayCameraTarget {target_id=t.ToString(),camera_xyz_mm=xyz}).ToArray();
        var feedback=new DisplayObservationFeedback(); feedback.Apply(config,o,2,2.01);
        return p.PresentationStatus(feedback,state,config.session_id,2.02,out left,out right,true,true);
    }

    [Test]
    public void ExplicitTransferPreservesSourceDepthAndOriginalRecords() {
        var before=manifest.c.Concat(manifest.d).Select(p=>File.ReadAllBytes(RecordPath(p))).ToArray();
        Load();
        foreach (string target in new[]{"A","B","C","D"}) {
            Assert.That(Gate(destination,live,target,420,out var l,out var r),Is.EqualTo("VISIBLE"));
            destination.TryProject(new[]{0d,0d,420d},out var bl,out var br);
            int dx=target=="A"?17:target=="C"?12:target=="D"?-9:0;
            Assert.That(l[0],Is.EqualTo(bl[0]+dx).Within(1e-6));
            Assert.That(r[0],Is.EqualTo(br[0]+(target=="A"?17:-dx)).Within(1e-6));
        }
        foreach(string t in new[]{"C","D"})
            foreach(double z in new[]{319.999,500.001})
                Assert.That(Gate(destination,live,t,z,out _,out _),Is.EqualTo("OUTSIDE TARGET DEPTH"));
        Assert.That(manifest.c.Concat(manifest.d).Select(p=>File.ReadAllBytes(RecordPath(p))).ToArray(),Is.EqualTo(before));
        Assert.That(destination.calibration_valid || destination.display_alignment_verified,Is.False);
    }

    [Test]
    public void LegacyManifestStillRequiresItsOriginalCandidate() {
        manifest.schema_version=null; manifest.transfer=new StageDepthTransfer();
        Assert.Throws<ArgumentException>(Load);
        destination=source;
        destinationBytes=File.ReadAllBytes(Path.Combine(root,"source.json"));
        live.workspace_profile_id=source.workspace_profile_id; live.workspace_profile_sha256=source.workspace_profile_sha256;
        Assert.DoesNotThrow(Load);
        Assert.That(Gate(destination,live,"C",420,out _,out _),Is.EqualTo("VISIBLE"));
    }

    [TestCase("schema")][TestCase("verified")][TestCase("candidate")][TestCase("source_hash")]
    [TestCase("destination_hash")][TestCase("source_workspace")][TestCase("destination_workspace")]
    [TestCase("record")][TestCase("record_hash")][TestCase("camera")][TestCase("matrix")][TestCase("targets")]
    [TestCase("path")][TestCase("no_source")][TestCase("axes")][TestCase("missing_version")]
    [TestCase("empty_transfer")][TestCase("manifest_version")]
    public void InvalidTransferFailsWithoutInstallingPartialDepths(string change) {
        var t=manifest.transfer;
        switch(change) {
            case "missing_version": manifest.schema_version=null; break;
            case "empty_transfer": manifest.transfer=new StageDepthTransfer(); break;
            case "manifest_version": manifest.schema_version="other"; break;
            case "schema": t.schema_version="other"; break;
            case "verified": t.display_alignment_verified=true; break;
            case "candidate": t.candidate_only=false; break;
            case "source_hash": t.source_candidate_sha256=new string('f',64); break;
            case "destination_hash": t.destination_candidate_sha256=new string('f',64); break;
            case "source_workspace": t.source_workspace_sha256=new string('f',64); break;
            case "destination_workspace": t.destination_workspace_sha256=new string('f',64); break;
            case "record": File.AppendAllText(RecordPath(manifest.d[2])," "); break;
            case "record_hash": t.c_sha256=new string[0]; break;
            case "camera": destination.camera_profile_sha256=new string('e',64); break;
            case "matrix": destination.left_projection[0]+=1; break;
            case "targets":
                Write("new-workspace.json",Workspace("workspace202",1));
                t.destination_workspace_sha256=destination.workspace_profile_sha256=Hash(File.ReadAllBytes(t.destination_workspace_path));
                live.workspace_profile_sha256=destination.workspace_profile_sha256;
                break;
            case "path": manifest.d[0]="../outside.json"; break;
            case "no_source": t.source_candidate_path=null; break;
            case "axes":
                var text=File.ReadAllText(t.destination_workspace_path).Replace("x_right_y_away_z_up","other");
                File.WriteAllText(t.destination_workspace_path,text);
                t.destination_workspace_sha256=destination.workspace_profile_sha256=Hash(File.ReadAllBytes(t.destination_workspace_path));
                live.workspace_profile_sha256=destination.workspace_profile_sha256;
                break;
        }
        if (new[]{"camera","matrix","targets","axes"}.Contains(change)) {
            live.camera_profile_sha256=destination.camera_profile_sha256;
            destinationBytes=System.Text.Encoding.UTF8.GetBytes(JsonSerializer.Serialize(destination,Json));
            t.destination_candidate_sha256=Hash(destinationBytes);
        }
        Assert.Throws<ArgumentException>(Load);
        // A failed transfer must not install even C when D is invalid.
        if (change=="record") {
            Assert.That(Gate(destination,live,"C",420,out var l,out _),Is.EqualTo("VISIBLE"));
            destination.TryProject(new[]{0d,0d,420d},out var baseline,out _);
            Assert.That(l,Is.EqualTo(baseline));
        }
    }
}
