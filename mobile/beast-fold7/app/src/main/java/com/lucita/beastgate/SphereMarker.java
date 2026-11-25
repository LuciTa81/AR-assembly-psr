package com.lucita.beastgate;

import android.content.Context;
import android.graphics.*;
import java.io.IOException;

/** Three.js-lit sphere sprites; depth comes only from the unchanged eye-local centers. */
final class SphereMarker implements AutoCloseable {
    private final Bitmap[] images=new Bitmap[3];
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
    private final RectF bounds=new RectF();
    SphereMarker(Context context)throws IOException {
        String[] names={"orange","blue","green"};
        try{
            for(int i=0;i<3;i++){
                try(var input=context.getAssets().open("markers/"+names[i]+".png")){images[i]=BitmapFactory.decodeStream(input);}
                if(images[i]==null||images[i].getWidth()!=96||images[i].getHeight()!=96||!images[i].hasAlpha())throw new IOException("Invalid sphere sprite: "+names[i]);
                images[i].setDensity(Bitmap.DENSITY_NONE);
            }
        }catch(IOException|RuntimeException error){close();throw error;}
    }
    void draw(Canvas canvas,float x,float y,AssemblyProbe.Phase phase){
        int index=phase==AssemblyProbe.Phase.APPROACH?0:phase==AssemblyProbe.Phase.WORKING?1:2;
        // 44px texture with transparent padding gives about 40px visible diameter.
        bounds.set(x-22,y-22,x+22,y+22);
        canvas.drawBitmap(images[index],null,bounds,paint);
    }
    @Override public void close(){for(Bitmap image:images)if(image!=null&&!image.isRecycled())image.recycle();}
}
