$ErrorActionPreference='Stop'
$reference='C:/Users/fresh/Documents/Codex/AR-Assembly-Checkpoint-20261120/repository/client_unity/Assets/Scripts/BoxOutlineProfile.cs'
# Compile the frozen Unity geometry itself; stubs only satisfy unused transport contracts.
$stubs=@'
namespace ARAssembly {
 public class Guidance { public string phase,reason; }
 public class GuidanceSnapshot { public string current_state,target,session_id,marker_status; public Guidance guidance; }
 public class GuidanceState { public GuidanceSnapshot LastSnapshot; public string Status(double now)=>"LIVE"; }
 public class DisplayObservation { public string session_id,camera_profile_sha256,workspace_profile_sha256; public double[] world_xyz_mm,rvec,tvec_mm,camera_xyz_mm; }
 public class DisplayObservationFeedback { public bool TryGetObservation(double now,out DisplayObservation value){value=null;return false;} }
 public class CandidateProjection {
  public string camera_profile_sha256,workspace_profile_sha256;
  public static string StageTarget(GuidanceSnapshot s)=>s!=null&&(s.target=="A"||s.target=="B"||s.target=="C"||s.target=="D")?s.target:null;
  public bool TryProject(double[] xyz,out double[] l,out double[] r){l=r=null;return false;}
 }
 public static class OutlineReference {
  public static BoxOutlineProfile.Stroke[] Geometry(BoxOutlineProfile profile,GuidanceSnapshot frame)=>profile.BuildStrokes(frame);
 }
}
'@
Add-Type -TypeDefinition ((Get-Content -LiteralPath $reference -Raw)+$stubs)
$profile=Get-Content app/src/main/assets/box-outline.json -Raw | ConvertFrom-Json
$outline=[ARAssembly.BoxOutlineProfile]::new()
foreach($key in 'schema_version','candidate_only','camera_profile_sha256','workspace_profile_sha256','vertices_mm','staged_rounded','lid_height_mm','corner_radius_mm'){$outline.$key=$profile.$key}
$projection=[ARAssembly.CandidateProjection]::new()
$projection.camera_profile_sha256=$profile.camera_profile_sha256
$projection.workspace_profile_sha256=$profile.workspace_profile_sha256
$outline.Validate($projection)
$result=@()
foreach($stage in 0..3){
 $frame=[ARAssembly.GuidanceSnapshot]::new()
 $frame.current_state=@('S0','S1','S2','S6')[$stage]
 $frame.target=@('box','lid','A','complete')[$stage]
 $frame.guidance=[ARAssembly.Guidance]::new()
 $frame.guidance.phase=if($stage -eq 3){'AWAITING_CONFIRMATION'}else{'GUIDING'}
 $frame.guidance.reason='operator_confirmation'
 $strokes=@([ARAssembly.OutlineReference]::Geometry($outline,$frame) | ForEach-Object { @{level=$_.Level;points=$_.Points} })
 $result+=@{stage=$stage;strokes=$strokes}
}
@{reference=$reference;reference_sha256=(Get-FileHash -LiteralPath $reference).Hash;stages=$result} | ConvertTo-Json -Depth 12 | Set-Content app/src/main/assets/box-outline-fixtures.json -Encoding utf8NoBOM
"Generated frozen C# fixtures: $((($result | ForEach-Object {$_.strokes.Count}) -join ',')) strokes"
