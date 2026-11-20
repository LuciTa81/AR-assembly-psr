using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace ARAssembly
{
    [Serializable]
    public sealed class StageDepthTransfer
    {
        public string schema_version;
        public bool candidate_only, calibration_valid, display_alignment_verified;
        public string source_candidate_path, source_candidate_sha256, destination_candidate_sha256;
        public string source_workspace_path, source_workspace_sha256;
        public string destination_workspace_path, destination_workspace_sha256;
        public string[] c_sha256, d_sha256;

        public bool HasValues => schema_version != null || candidate_only || calibration_valid || display_alignment_verified
            || source_candidate_path != null || source_candidate_sha256 != null || destination_candidate_sha256 != null
            || source_workspace_path != null || source_workspace_sha256 != null
            || destination_workspace_path != null || destination_workspace_sha256 != null
            || c_sha256?.Length > 0 || d_sha256?.Length > 0;
    }

    [Serializable]
    public sealed class DepthWorkspaceTargets
    {
        public string schema_version, profile_id, units, axes;
        public int origin_marker_id;
        public Points targets_mm;
        [Serializable] public sealed class Points { public double[] A, B, C, D; }
    }

    [Serializable]
    public sealed class StageDepthConfig
    {
        public string schema_version;
        public string[] c, d;
        public StageDepthTransfer transfer;

        // The manifest is an explicit reviewed allowlist, not automatic calibration migration.
        public static void LoadAndBind(CandidateProjection destination, byte[] candidateBytes,
            DisplayCollectionConfig live, string manifestPath, string local,
            Func<string, Type, object> parse)
        {
            destination.Validate(live);
            T Decode<T>(byte[] bytes) where T : class {
                var value = parse(Encoding.UTF8.GetString(bytes).TrimStart('\uFEFF'), typeof(T)) as T;
                if (value == null) throw new ArgumentException("Missing depth configuration object");
                return value;
            }
            var files = Decode<StageDepthConfig>(ReadSmall(manifestPath));
            Require(files.c?.Length == 3 && files.d?.Length == 3, "Expected three records per target");
            string root = Path.Combine(local, "ARAssembly", "beast-mvp", "display_correspondence");
            byte[] ReadRecord(string relative) {
                Require(!string.IsNullOrEmpty(relative) && !Path.IsPathRooted(relative), "Expected collection-relative record");
                string path = Path.GetFullPath(Path.Combine(root, relative));
                Require(DisplayCorrespondenceRules.IsLocalCollectionPath(path, local), "Record outside local collection");
                return ReadSmall(path);
            }
            var cBytes = Array.ConvertAll(files.c, ReadRecord);
            var dBytes = Array.ConvertAll(files.d, ReadRecord);
            var cRows = Array.ConvertAll(cBytes, Decode<TrackedAlignmentRecord>);
            var dRows = Array.ConvertAll(dBytes, Decode<TrackedAlignmentRecord>);
            // Unity may instantiate an omitted inline object; the scalar version selects the format.
            if (string.IsNullOrEmpty(files.schema_version)) {
                Require(files.transfer == null || !files.transfer.HasValues, "Transfer requires explicit v2 manifest");
                destination.BindStageDepthRecords(Hash(candidateBytes), cRows, dRows);
                return;
            }
            Require(files.schema_version == "beast_stage_depth_config_v2" && files.transfer != null,
                "Expected versioned depth transfer manifest");
            var t = files.transfer;
            Require(t.schema_version == "beast_stage_depth_transfer_v1" && t.candidate_only
                && !t.calibration_valid && !t.display_alignment_verified, "Expected unverified depth transfer");
            Require(Hash(candidateBytes) == t.destination_candidate_sha256, "Destination candidate changed");
            CheckRecords(cBytes, t.c_sha256); CheckRecords(dBytes, t.d_sha256);
            var source = Decode<CandidateProjection>(ReadPinned(t.source_candidate_path, t.source_candidate_sha256));
            var oldWorld = Decode<DepthWorkspaceTargets>(ReadPinned(t.source_workspace_path, t.source_workspace_sha256));
            var newWorld = Decode<DepthWorkspaceTargets>(ReadPinned(t.destination_workspace_path, t.destination_workspace_sha256));
            Require(source.workspace_profile_sha256 == t.source_workspace_sha256
                && destination.workspace_profile_sha256 == t.destination_workspace_sha256
                && oldWorld.profile_id == source.workspace_profile_id && newWorld.profile_id == destination.workspace_profile_id,
                "Workspace binding changed");
            Require(oldWorld.schema_version == "beast_workspace_metric_v1" && newWorld.schema_version == oldWorld.schema_version
                && oldWorld.units == "mm" && newWorld.units == oldWorld.units
                && oldWorld.axes == "x_right_y_away_z_up" && newWorld.axes == oldWorld.axes
                && oldWorld.origin_marker_id == newWorld.origin_marker_id, "Workspace coordinate convention changed");
            Require(oldWorld.targets_mm != null && newWorld.targets_mm != null, "Missing targets");
            var oldPoints = new[]{oldWorld.targets_mm.A, oldWorld.targets_mm.B, oldWorld.targets_mm.C, oldWorld.targets_mm.D};
            var newPoints = new[]{newWorld.targets_mm.A, newWorld.targets_mm.B, newWorld.targets_mm.C, newWorld.targets_mm.D};
            for (int i=0; i<4; i++)
                Require(oldPoints[i]?.Length == 3 && newPoints[i]?.Length == 3
                    && oldPoints[i].All(v => !double.IsNaN(v) && !double.IsInfinity(v))
                    && oldPoints[i].SequenceEqual(newPoints[i]), "Physical target coordinates changed");
            foreach (var row in cRows)
                Require(row.observation?.world_xyz_mm?.SequenceEqual(oldPoints[2]) == true, "C record target changed");
            foreach (var row in dRows)
                Require(row.observation?.world_xyz_mm?.SequenceEqual(oldPoints[3]) == true, "D record target changed");
            source.Validate(new DisplayCollectionConfig {
                schema_version=live.schema_version, session_id=live.session_id, observation_url=live.observation_url,
                token=live.token, directory=live.directory, target_id=live.target_id, image_size=live.image_size,
                camera_profile_id=live.camera_profile_id, camera_profile_sha256=live.camera_profile_sha256,
                workspace_profile_id=source.workspace_profile_id, workspace_profile_sha256=source.workspace_profile_sha256
            });
            destination.BindReviewedStageDepths(source, t.source_candidate_sha256, cRows, dRows);
        }

        private static byte[] ReadSmall(string path)
        {
            Require(!string.IsNullOrWhiteSpace(path), "Missing local file");
            path = Path.GetFullPath(path);
            Require(!path.StartsWith(@"\\") && new FileInfo(path).Length <= 65536, "Expected small local depth file");
            return File.ReadAllBytes(path);
        }
        private static byte[] ReadPinned(string path, string hash)
        {
            byte[] bytes = ReadSmall(path);
            Require(Hash(bytes) == hash, "Depth transfer file changed");
            return bytes;
        }
        private static void CheckRecords(byte[][] bytes, string[] hashes)
        {
            Require(hashes?.Length == 3, "Expected three pinned records");
            for (int i=0; i<3; i++) Require(Hash(bytes[i]) == hashes[i], "Original depth record changed");
        }
        private static string Hash(byte[] bytes)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }
        private static void Require(bool valid, string reason) { if (!valid) throw new ArgumentException(reason); }
    }
}
