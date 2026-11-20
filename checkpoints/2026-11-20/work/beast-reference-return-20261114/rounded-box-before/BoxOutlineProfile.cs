using System;

namespace ARAssembly
{
    [Serializable]
    public sealed class BoxOutlineProfile
    {
        public string schema_version, camera_profile_sha256, workspace_profile_sha256;
        public bool candidate_only;
        // Top far-left, far-right, near-right, near-left; then matching bottom vertices.
        public double[] vertices_mm;
        private double[] vertices;
        private string cameraHash, workspaceHash;

        public void Validate(CandidateProjection projection)
        {
            vertices = null;
            Require(projection != null && schema_version == "beast_box_outline_trial_v1" && candidate_only,
                "Expected box outline trial profile");
            Require(!string.IsNullOrEmpty(camera_profile_sha256) && !string.IsNullOrEmpty(workspace_profile_sha256)
                && camera_profile_sha256 == projection.camera_profile_sha256
                && workspace_profile_sha256 == projection.workspace_profile_sha256, "Box outline profile mismatch");
            Require(vertices_mm != null && vertices_mm.Length == 24, "Expected eight box vertices");
            foreach(double v in vertices_mm) Require(Finite(v) && Math.Abs(v) <= 2000, "Invalid box vertex");
            double top = vertices_mm[2], bottom = vertices_mm[14];
            Require(bottom >= 0 && top - bottom >= 5 && top - bottom <= 500, "Invalid box height");
            for(int layer = 0; layer < 2; layer++) {
                int start = layer * 12;
                for(int i = 0; i < 4; i++) {
                    int a=start+3*i, b=start+3*((i+1)%4), c=start+3*((i+2)%4);
                    Require(Math.Abs(vertices_mm[a+2] - (layer==0?top:bottom)) < 1e-6, "Nonplanar box rim");
                    double x=vertices_mm[b]-vertices_mm[a], y=vertices_mm[b+1]-vertices_mm[a+1];
                    double nextX=vertices_mm[c]-vertices_mm[b], nextY=vertices_mm[c+1]-vertices_mm[b+1];
                    Require(x*x+y*y >= 100 && x*x+y*y <= 1000000 && x*nextY-y*nextX < -1,
                        "Box vertices must form clockwise convex rims in x-right/y-away coordinates");
                }
            }
            vertices=(double[])vertices_mm.Clone();
            cameraHash=camera_profile_sha256; workspaceHash=workspace_profile_sha256;
        }

        public static bool IsStage(GuidanceSnapshot frame)
        {
            return CandidateProjection.StageTarget(frame) != null || frame?.current_state == "S1"
                && frame.target == "lid" && (frame.guidance?.phase == "GUIDING" || frame.guidance?.phase == "OBSERVING");
        }

        public bool TryProject(CandidateProjection projection, DisplayObservationFeedback feedback,
            GuidanceState state, string sessionId, double now, out double[][] left, out double[][] right)
        {
            left=right=null;
            if(vertices == null || projection == null || feedback == null || !IsStage(state?.LastSnapshot)
                || string.IsNullOrEmpty(sessionId) || state.LastSnapshot.session_id != sessionId) return false;
            string status=state.Status(now);
            if((status != "LIVE" && status != "PAUSED") || !feedback.TryGetObservation(now,out var pose)
                || pose.session_id != sessionId || pose.camera_profile_sha256 != cameraHash
                || pose.workspace_profile_sha256 != workspaceHash
                || projection.camera_profile_sha256 != cameraHash || projection.workspace_profile_sha256 != workspaceHash)
                return false;
            // The pose and primary target must describe the same source frame and convention.
            var primary=ToCamera(pose.world_xyz_mm,pose.rvec,pose.tvec_mm);
            for(int i=0;i<3;i++) if(Math.Abs(primary[i]-pose.camera_xyz_mm[i]) > 1e-4) return false;
            var l=new double[8][]; var r=new double[8][];
            for(int i=0;i<8;i++) {
                var xyz=new[]{vertices[i*3],vertices[i*3+1],vertices[i*3+2]};
                if(!projection.TryProject(ToCamera(xyz,pose.rvec,pose.tvec_mm),out l[i],out r[i])) return false;
            }
            left=l; right=r;
            return true;
        }

        internal static double[] ToCamera(double[] xyz, double[] rvec, double[] tvec)
        {
            double angle=Math.Sqrt(rvec[0]*rvec[0]+rvec[1]*rvec[1]+rvec[2]*rvec[2]);
            if(angle < 1e-12) return new[]{xyz[0]+tvec[0],xyz[1]+tvec[1],xyz[2]+tvec[2]};
            double x=rvec[0]/angle,y=rvec[1]/angle,z=rvec[2]/angle;
            double c=Math.Cos(angle),s=Math.Sin(angle),dot=x*xyz[0]+y*xyz[1]+z*xyz[2];
            return new[]{xyz[0]*c+(y*xyz[2]-z*xyz[1])*s+x*dot*(1-c)+tvec[0],
                xyz[1]*c+(z*xyz[0]-x*xyz[2])*s+y*dot*(1-c)+tvec[1],
                xyz[2]*c+(x*xyz[1]-y*xyz[0])*s+z*dot*(1-c)+tvec[2]};
        }

        private static bool Finite(double x) => !double.IsNaN(x) && !double.IsInfinity(x);
        private static void Require(bool valid,string reason) { if(!valid) throw new ArgumentException(reason); }
    }
}
