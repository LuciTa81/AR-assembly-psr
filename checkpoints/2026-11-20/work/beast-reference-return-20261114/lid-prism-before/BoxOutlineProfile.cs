using System;
using System.Collections.Generic;

namespace ARAssembly
{
    [Serializable]
    public sealed class BoxOutlineProfile
    {
        public string schema_version, camera_profile_sha256, workspace_profile_sha256;
        public bool candidate_only;
        // Top far-left, far-right, near-right, near-left; then matching bottom vertices.
        public double[] vertices_mm;
        public bool staged_rounded;
        public double lid_height_mm, corner_radius_mm;
        public bool RoundedStaged { get; private set; }
        private double[] vertices;
        private double lidHeight, radius;
        private GeometryStroke[] openGeometry, closedGeometry, screwGeometry;
        private string cameraHash, workspaceHash;
        private string completionSession;
        private double completionStarted;

        public void Validate(CandidateProjection projection)
        {
            vertices = null;
            RoundedStaged = false;
            completionSession = null;
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
            if(staged_rounded) {
                Require(Finite(lid_height_mm) && lid_height_mm >= 1 && lid_height_mm <= top-bottom-5,
                    "Invalid lid height");
                Require(Finite(corner_radius_mm) && corner_radius_mm > 0, "Invalid corner radius");
                for(int i=0;i<4;i++) {
                    int a=3*i, b=3*((i+1)%4), c=3*((i+2)%4);
                    double x=vertices_mm[b]-vertices_mm[a], y=vertices_mm[b+1]-vertices_mm[a+1];
                    double nx=vertices_mm[c]-vertices_mm[b], ny=vertices_mm[c+1]-vertices_mm[b+1];
                    Require(Math.Abs(vertices_mm[a]-vertices_mm[a+12])<1e-6
                        && Math.Abs(vertices_mm[a+1]-vertices_mm[a+13])<1e-6
                        && Math.Abs(x*nx+y*ny)<1e-6, "Rounded outline requires an upright rectangular box");
                    Require(corner_radius_mm*4 <= Math.Sqrt(x*x+y*y), "Corner radius too large");
                }
                lidHeight=lid_height_mm; radius=corner_radius_mm; RoundedStaged=true;
            }
            vertices=(double[])vertices_mm.Clone();
            cameraHash=camera_profile_sha256; workspaceHash=workspace_profile_sha256;
            if(RoundedStaged) {
                openGeometry=BuildGeometry(false); closedGeometry=BuildGeometry(true);
                screwGeometry=Array.FindAll(closedGeometry,
                    s=>s.Lid && Array.TrueForAll(s.Points,p=>p[2]==top));
            }
        }

        public static bool IsStage(GuidanceSnapshot frame)
        {
            return CandidateProjection.StageTarget(frame) != null || frame?.current_state == "S1"
                && frame.target == "lid" && (frame.guidance?.phase == "GUIDING" || frame.guidance?.phase == "OBSERVING");
        }

        public bool IncludesStage(GuidanceSnapshot frame) => IsStage(frame) || RoundedStaged
            && (frame?.current_state == "S0" && frame.target == "box"
                && (frame.guidance?.phase == "GUIDING" || frame.guidance?.phase == "OBSERVING")
                || Confirmed(frame));

        private static bool Confirmed(GuidanceSnapshot frame) => frame?.current_state == "S6"
            && frame.target == "complete" && frame.guidance?.phase == "COMPLETED"
            && frame.guidance.reason == "operator_confirmation";

        internal bool CompletionCueVisible(GuidanceState state,double now)
        {
            var frame=state?.LastSnapshot;
            if(!RoundedStaged || !Confirmed(frame)) { completionSession=null; return false; }
            if(!Finite(now) || string.IsNullOrEmpty(frame.session_id)) return false;
            // New frames and temporary tracking loss never restart this one-shot cue.
            if(completionSession!=frame.session_id) {
                completionSession=frame.session_id; completionStarted=now;
            }
            return state.Status(now)=="COMPLETED" && now>=completionStarted && now-completionStarted<1;
        }

        public bool WantsObservation(GuidanceState state,double now)
        {
            bool completion=CompletionCueVisible(state,now);
            return IncludesStage(state?.LastSnapshot) && (state.LastSnapshot.current_state!="S6" || completion);
        }

        public bool TryProject(CandidateProjection projection, DisplayObservationFeedback feedback,
            GuidanceState state, string sessionId, double now, out double[][] left, out double[][] right)
        {
            left=right=null;
            if(!TryPose(projection,feedback,state,sessionId,now,out var pose)) return false;
            var l=new double[8][]; var r=new double[8][];
            for(int i=0;i<8;i++) {
                var xyz=new[]{vertices[i*3],vertices[i*3+1],vertices[i*3+2]};
                if(!projection.TryProject(ToCamera(xyz,pose.rvec,pose.tvec_mm),out l[i],out r[i])) return false;
            }
            left=l; right=r;
            return true;
        }

        private bool TryPose(CandidateProjection projection, DisplayObservationFeedback feedback,
            GuidanceState state, string sessionId, double now, out DisplayObservation pose)
        {
            pose=null;
            if(vertices == null || projection == null || feedback == null || !WantsObservation(state,now)
                || string.IsNullOrEmpty(sessionId) || state.LastSnapshot.session_id != sessionId) return false;
            string status=state.Status(now);
            bool completed=RoundedStaged && Confirmed(state.LastSnapshot) && status=="COMPLETED"
                && state.LastSnapshot.marker_status=="OK";
            if((status != "LIVE" && status != "PAUSED" && !completed) || !feedback.TryGetObservation(now,out pose)
                || pose.session_id != sessionId || pose.camera_profile_sha256 != cameraHash
                || pose.workspace_profile_sha256 != workspaceHash
                || projection.camera_profile_sha256 != cameraHash || projection.workspace_profile_sha256 != workspaceHash)
                return false;
            // The pose and primary target must describe the same source frame and convention.
            var primary=ToCamera(pose.world_xyz_mm,pose.rvec,pose.tvec_mm);
            for(int i=0;i<3;i++) if(Math.Abs(primary[i]-pose.camera_xyz_mm[i]) > 1e-4) return false;
            return true;
        }

        public sealed class Stroke
        {
            public readonly double[][] Points;
            public readonly int Level;
            public Stroke(double[][] points,int level) { Points=points; Level=level; }
        }

        public bool TryProjectStrokes(CandidateProjection projection, DisplayObservationFeedback feedback,
            GuidanceState state,string sessionId,double now,out Stroke[] left,out Stroke[] right)
        {
            left=right=null;
            if(!RoundedStaged || !TryPose(projection,feedback,state,sessionId,now,out var pose)) return false;
            var world=BuildStrokes(state.LastSnapshot);
            var l=new Stroke[world.Length]; var r=new Stroke[world.Length];
            for(int i=0;i<world.Length;i++) {
                var lp=new double[world[i].Points.Length][]; var rp=new double[lp.Length][];
                for(int j=0;j<lp.Length;j++)
                    if(!projection.TryProject(ToCamera(world[i].Points[j],pose.rvec,pose.tvec_mm),out lp[j],out rp[j])) return false;
                l[i]=new Stroke(lp,world[i].Level); r[i]=new Stroke(rp,world[i].Level);
            }
            left=l; right=r;
            return true;
        }

        internal Stroke[] BuildStrokes(GuidanceSnapshot frame)
        {
            if(!RoundedStaged || !IncludesStage(frame)) return Array.Empty<Stroke>();
            var geometry=frame.current_state=="S0"?openGeometry:
                CandidateProjection.StageTarget(frame)!=null?screwGeometry:closedGeometry;
            var strokes=new Stroke[geometry.Length];
            for(int i=0;i<geometry.Length;i++) {
                var part=geometry[i];
                int level=Confirmed(frame) || part.Lid && frame.current_state=="S1"?3:2;
                strokes[i]=new Stroke(part.Points,level);
            }
            Array.Sort(strokes,(a,b)=>a.Level.CompareTo(b.Level));
            return strokes;
        }

        private sealed class GeometryStroke
        {
            public double[][] Points;
            public bool Lid;
        }

        private GeometryStroke[] BuildGeometry(bool closed)
        {
            var strokes=new List<GeometryStroke>();
            double bottom=vertices[14], top=vertices[2], body=top-lidHeight;
            var directions=new double[4][];
            for(int i=0;i<4;i++) {
                int next=(i+1)%4;
                double x=vertices[3*next]-vertices[3*i], y=vertices[3*next+1]-vertices[3*i+1];
                double length=Math.Sqrt(x*x+y*y);
                directions[i]=new[]{x/length,y/length,0};
            }
            double[] Point(int i,double z) => new[]{vertices[3*i],vertices[3*i+1],z};
            double[] Offset(double[] p,double[] d,double amount) => new[]{p[0]+d[0]*amount,p[1]+d[1]*amount,p[2]};
            void Add(double[][] points,bool lid) =>
                strokes.Add(new GeometryStroke {Points=points,Lid=lid});
            double[] CornerMiddle(int i,double z) {
                var p=Point(i,z); var prev=directions[(i+3)%4]; var next=directions[i];
                return new[]{p[0]+radius*(next[0]-prev[0])*0.25,p[1]+radius*(next[1]-prev[1])*0.25,z};
            }
            void Rim(double z,bool lid) {
                for(int i=0;i<4;i++) {
                    int prev=(i+3)%4,next=(i+1)%4;
                    var corner=Point(i,z);
                    var start=Offset(corner,directions[prev],-radius);
                    var end=Offset(corner,directions[i],radius);
                    var curve=new double[9][];
                    for(int j=0;j<curve.Length;j++) {
                        double t=j/8.0,u=1-t;
                        curve[j]=new[]{u*u*start[0]+2*u*t*corner[0]+t*t*end[0],
                            u*u*start[1]+2*u*t*corner[1]+t*t*end[1],z};
                    }
                    Add(curve,lid);
                    Add(new[]{end,Offset(Point(next,z),directions[i],-radius)},lid);
                }
            }
            Rim(bottom,false);
            Rim(body,false);
            for(int i=0;i<4;i++) Add(new[]{CornerMiddle(i,bottom),CornerMiddle(i,body)},false);
            if(closed) {
                Rim(top,true);
                for(int i=0;i<4;i++) Add(new[]{CornerMiddle(i,body),CornerMiddle(i,top)},true);
            }
            return strokes.ToArray();
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
