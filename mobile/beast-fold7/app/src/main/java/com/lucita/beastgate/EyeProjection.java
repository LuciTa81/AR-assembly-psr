package com.lucita.beastgate;

import android.content.Context;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

/** Read-only port of Unity CandidateProjection.TryProject, in eye-local top-left pixels. */
final class EyeProjection {
    private final double[][] matrices=new double[2][12];
    EyeProjection(Context context)throws Exception{
        JSONObject profile=json(context,"eye-projection.json");
        require(profile.getString("schema_version").equals("beast_candidate_projection_probe_v1"),"eye_schema");
        require(profile.getBoolean("candidate_only")&&!profile.getBoolean("calibration_valid")
            &&!profile.getBoolean("display_alignment_verified"),"candidate_flags");
        require(profile.getInt("eye_width")==1920&&profile.getInt("eye_height")==1080
            &&profile.getString("display_mode").equals("full_sbs")
            &&profile.getString("coordinate_convention").equals("eye_local_pixels_top_left")
            &&profile.getString("channel_order").equals("left_half_left_eye_right_half_right_eye"),"eye_layout");
        for(String type:new String[]{"camera","workspace"}){
            byte[] bytes=read(context,type+"-profile.json");
            StringBuilder hash=new StringBuilder();
            for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))hash.append(String.format(Locale.ROOT,"%02x",b&255));
            require(profile.getString(type+"_profile_sha256").equals(hash.toString()),type+"_hash");
            JSONObject source=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
            require(profile.getString(type+"_profile_id").equals(source.getString("profile_id")),type+"_id");
        }
        for(int eye=0;eye<2;eye++){
            JSONArray values=profile.getJSONArray(eye==0?"left_projection":"right_projection");
            require(values.length()==12,"matrix_size");
            double[] m=matrices[eye];
            for(int i=0;i<12;i++){m[i]=values.getDouble(i);require(Double.isFinite(m[i]),"matrix_finite");}
            double det=m[0]*(m[5]*m[10]-m[6]*m[9])-m[1]*(m[4]*m[10]-m[6]*m[8])+m[2]*(m[4]*m[9]-m[5]*m[8]);
            require(Double.isFinite(det)&&Math.abs(det)>1e-12,"matrix_singular");
        }
    }
    double[][] project(double[] xyz){
        if(xyz==null||xyz.length!=3||!Double.isFinite(xyz[0])||!Double.isFinite(xyz[1])||!Double.isFinite(xyz[2])||xyz[2]<=0)return null;
        double[][] result=new double[2][2];
        for(int eye=0;eye<2;eye++){
            double[] m=matrices[eye];
            double x=m[0]*xyz[0]+m[1]*xyz[1]+m[2]*xyz[2]+m[3];
            double y=m[4]*xyz[0]+m[5]*xyz[1]+m[6]*xyz[2]+m[7];
            double z=m[8]*xyz[0]+m[9]*xyz[1]+m[10]*xyz[2]+m[11];
            if(!Double.isFinite(z)||z<=1e-9)return null;
            x/=z;y/=z;
            if(!Double.isFinite(x)||!Double.isFinite(y)||x<0||x>=1920||y<0||y>=1080)return null;
            result[eye][0]=x;result[eye][1]=y;
        }
        return result;
    }
    private static byte[] read(Context c,String name)throws Exception{try(java.io.InputStream in=c.getAssets().open(name)){return in.readAllBytes();}}
    private static JSONObject json(Context c,String name)throws Exception{return new JSONObject(new String(read(c,name),StandardCharsets.UTF_8));}
    private static void require(boolean condition,String reason){if(!condition)throw new IllegalArgumentException(reason);}
}
