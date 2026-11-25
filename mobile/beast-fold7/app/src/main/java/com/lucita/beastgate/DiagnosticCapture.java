package com.lucita.beastgate;

import android.graphics.Bitmap;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONObject;

/** Opt-in workbench stills. Called by one writer; never changes tracking decisions. */
final class DiagnosticCapture {
    final File directory;
    final int limit;
    private volatile int saved;
    private long lastFrame=-1;

    DiagnosticCapture(File root) throws IOException {
        this(root,100);
    }

    DiagnosticCapture(File root,int limit) throws IOException {
        if(limit<1||limit>100)throw new IllegalArgumentException("Photo limit must be 1..100");
        this.limit=limit;
        directory=new File(root,"marker-"+UUID.randomUUID());
        if(!directory.mkdirs())throw new IOException("Cannot create diagnostic directory");
    }

    int count(){return saved;}

    boolean save(Bitmap bitmap,WorkspaceTracker.Result result,long received,int session) throws Exception {
        if(saved>=limit||(lastFrame>=0&&received-lastFrame<500))return false;
        JSONObject corners=new JSONObject();
        for(var entry:result.markers.entrySet()){
            JSONArray quad=new JSONArray();
            for(var p:entry.getValue())quad.put(new JSONArray().put(p.x).put(p.y));
            corners.put(Integer.toString(entry.getKey()),quad);
        }
        String stem=String.format(Locale.ROOT,"%04d",saved+1);
        JSONObject metadata=new JSONObject().put("frame_ms",received).put("session",session)
            .put("image",stem+".png").put("width",bitmap.getWidth()).put("height",bitmap.getHeight())
            .put("valid",result.valid).put("reason",result.reason).put("corners",corners)
            .put("rms",Double.isFinite(result.rms)?result.rms:JSONObject.NULL)
            .put("max_error",Double.isFinite(result.maxError)?result.maxError:JSONObject.NULL);
        try(FileOutputStream out=new FileOutputStream(new File(directory,stem+".png"))){
            if(!bitmap.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("PNG save failed");
        }
        try(FileOutputStream out=new FileOutputStream(new File(directory,stem+".json"))){
            out.write(metadata.toString().getBytes(StandardCharsets.UTF_8));
        }
        saved++;lastFrame=received;
        return true;
    }
}
