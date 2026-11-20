using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace ARAssembly
{
    public static class CandidateProjectionSmoke
    {
        public static void Run()
        {
            try {
                var args=Environment.GetCommandLineArgs();
                int index=Array.IndexOf(args,"--candidate-projection");
                if (index<0 || index+1>=args.Length) throw new ArgumentException("Candidate required");
                var p=new CandidateProjection();
                JsonUtility.FromJsonOverwrite(File.ReadAllText(args[index+1]),p);
                var config=new DisplayCollectionConfig {
                    schema_version="beast_display_collection_config_v1",session_id="smoke",token="fixture",
                    directory=Path.GetTempPath(),observation_url="http://127.0.0.1:12345/observation",
                    camera_profile_id=p.camera_profile_id,workspace_profile_id=p.workspace_profile_id,
                    camera_profile_sha256=p.camera_profile_sha256,workspace_profile_sha256=p.workspace_profile_sha256,
                    image_size=new[]{1280,720},target_id="A"
                };
                p.Validate(config);
                int depthIndex=Array.IndexOf(args,"--stage-depth-config");
                if (depthIndex>=0) {
                    if (depthIndex+1>=args.Length) throw new ArgumentException("Depth manifest required");
                    StageDepthConfig.LoadAndBind(p,File.ReadAllBytes(args[index+1]),config,args[depthIndex+1],
                        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        (text,type)=>JsonUtility.FromJson(text,type));
                    Debug.Log("[DEPTH CONFIG SMOKE] PASS; actual Unity JSON, pinned source records and workspace targets; no device opened");
                }
                if (!p.TryProject(new double[]{0,100,550},out var l,out var r))
                    throw new Exception("Expected visible sample");
                Debug.Log("[CANDIDATE SMOKE] actual JSON parsed, left="+l[0]+","+l[1]+" right="+r[0]+","+r[1]);
                if (p.TryProject(new double[]{0,0,-500},out _,out _))
                    throw new Exception("Behind camera must be hidden");
                int fixtureIndex=Array.IndexOf(args,"--observation-fixture");
                if (fixtureIndex>=0) {
                    if (fixtureIndex+1>=args.Length) throw new ArgumentException("Observation fixture required");
                    var observation=JsonUtility.FromJson<DisplayObservation>(File.ReadAllText(args[fixtureIndex+1]));
                    config.session_id=observation.session_id;
                    observation.age_ms=0;
                    var feedback=new DisplayObservationFeedback();
                    feedback.Apply(config,observation,1,1.01);
                    if (!p.TryProjectCorners(feedback,1.02,out var left,out var right)
                        || left.Length!=4 || right.Length!=4)
                        throw new Exception("Server four-corner payload did not project");
                    for (int i=0;i<4;i++)
                        Debug.Log("[CORNERS SMOKE] "+(char)('A'+i)+" left="+left[i][0]+","+left[i][1]
                            +" right="+right[i][0]+","+right[i][1]);
                    if (!p.TryProjectFresh(feedback,1.02,out var aLeft,out var aRight)
                        || Math.Abs(aLeft[0]-left[0][0])>1e-8 || Math.Abs(aRight[1]-right[0][1])>1e-8
                        || CandidateProjection.LidPerimeter!="ABDCA")
                        throw new Exception("A compatibility or lid perimeter mismatch");
                    if (p.TryProjectCorners(feedback,1.16,out _,out _))
                        throw new Exception("Expired corners must be hidden");
                    Debug.Log("[CORNERS SMOKE] PASS; server JSON, both eyes, ABDCA, expiry; no device opened");
                    int replayIndex=Array.IndexOf(args,"--operator-replay");
                    if (replayIndex>=0)
                        CheckStageReplay(args[replayIndex+1], p, config, observation, left, right);
                    RunDiagnosticChecks(p, config, observation);
                }
                config.workspace_profile_id="mismatch";
                bool rejected=false;
                try { p.Validate(config); } catch (ArgumentException) { rejected=true; }
                if (!rejected || p.TryProject(new double[]{0,100,550},out _,out _))
                    throw new Exception("Invalid binding must deactivate projection");
                Debug.Log("[CANDIDATE SMOKE] PASS; no camera, no display activation");
                EditorApplication.Exit(0);
            } catch (Exception exc) {
                Debug.LogError("[CANDIDATE SMOKE] FAIL "+exc);
                EditorApplication.Exit(1);
            }
        }

        private static void CheckStageReplay(string path, CandidateProjection p, DisplayCollectionConfig config,
            DisplayObservation fixture, double[][] left, double[][] right)
        {
            var state = new GuidanceState();
            var feedback = new DisplayObservationFeedback();
            var c = JsonUtility.FromJson<DisplayCollectionConfig>(JsonUtility.ToJson(config));
            var pose = fixture.Copy();
            int visibleSteps = 0;
            double now = 1;
            foreach (string line in File.ReadLines(path)) {
                var frame = GuidanceReceiver.ParseSnapshot(line);
                // Replay recorded operator states with one fixed pose fixture and a synthetic clock.
                if (state.LastSnapshot == null) c.session_id = pose.session_id = frame.session_id;
                frame.frame_age_ms = 0; pose.age_ms = 0; pose.frame_id++;
                feedback.Apply(c, pose, now, now);
                if (!state.Apply(frame, now, now)) throw new Exception("Invalid replay state " + frame.current_state);
                string gate = p.PresentationStatus(feedback, state, c.session_id, now, out var l, out var r, true, true);
                int index = Array.IndexOf(new[]{"S2","S3","S4","S5"},frame.current_state);
                if (index < 0) {
                    if (gate=="VISIBLE" || l!=null || r!=null) throw new Exception("Unexpected ring: "+frame.current_state);
                } else {
                    if (gate!="VISIBLE" || visibleSteps!=index || state.Presentation(now).Instruction!=frame.next_action)
                        throw new Exception("Instruction/selection mismatch: "+frame.current_state);
                    for (int axis=0; axis<2; axis++) {
                        double dx = index==0 && axis==0 ? 17 : 0;
                        if (Math.Abs(l[axis]-left[index][axis]-dx)>1e-7 || Math.Abs(r[axis]-right[index][axis]-dx)>1e-7)
                            throw new Exception("Wrong stereo target: "+frame.current_state);
                    }
                    visibleSteps++;
                }
                now += .1;
            }
            if (visibleSteps!=4) throw new Exception("Replay must include S2 to S5");
            Debug.Log("[STAGE ABCD SMOKE] PASS; operator A/B/C/D; A-only +17 px in both eyes; other steps text only");
        }

        private static void RunDiagnosticChecks(CandidateProjection projection, DisplayCollectionConfig config,
            DisplayObservation observation)
        {
            string directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "ARAssembly", "beast-mvp", "display_correspondence", "tracked-smoke-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            config.directory = directory; config.setup_id = "synthetic-smoke";
            string path = Path.Combine(directory, "client-config.json");
            File.WriteAllText(path, JsonUtility.ToJson(config));
            var host = new GameObject("Tracked diagnostic smoke");
            try {
                var recorder = host.AddComponent<DisplayObservationRecorder>();
                recorder.Initialize(path, projection, backgroundPolling: true);
                var model = recorder.CreateTrackedDiagnostic(projection, new string('c', 64));
                recorder.Feedback.Apply(config, observation, 1, 1.01);
                if (!model.TryRender(observation, 1, 1.01, 1.02, out _, out _))
                    throw new Exception("Diagnostic render failed");
                model.ConfirmEye(StereoProbeView.Left); model.ConfirmEye(StereoProbeView.Right);
                long frame = observation.frame_id;
                observation.frame_id += 100;
                recorder.SaveDiagnostic(model, 1.03);
                string recordPath = Path.Combine(directory, "diagnostic-frame-" + frame + ".json");
                var saved = JsonUtility.FromJson<TrackedAlignmentRecord>(File.ReadAllText(recordPath));
                if (recorder.Status != "SAVED" || saved.observation.frame_id != frame || saved.rendered_view != "Both"
                    || !saved.binocular_confirmed_by_user || saved.calibration_valid || saved.display_alignment_verified
                    || saved.schema_version != "beast_tracked_alignment_diagnostic_v1")
                    throw new Exception("Diagnostic serialized different frame or invalid flags");
                recorder.SaveDiagnostic(model, 1.04);
                if (recorder.Status != "FRAME ALREADY SAVED") throw new Exception("Duplicate diagnostic accepted");
                recorder.Feedback.Fail("NO POSE");
                recorder.SaveDiagnostic(model, 1.05);
                if (recorder.Status != "NO FRESH POSE" || Directory.GetFiles(directory, "diagnostic-*.json").Length != 1)
                    throw new Exception("Lost pose allowed a diagnostic save");
                recorder.Cancel();
                Debug.Log("[TRACKED DIAGNOSTIC SMOKE] PASS; exact rendered frame, Unity JSON, real atomic save, duplicate/lost rejection; " + directory);
            } finally { UnityEngine.Object.DestroyImmediate(host); }
        }
    }
}
