package com.lucita.beastgate;

final class VideoFrame {
    private VideoFrame(){}
    static byte[] halfNv21(byte[] source,int width,int height){
        if(width<=0||height<=0||width%4!=0||height%4!=0||source.length!=(long)width*height*3/2)throw new IllegalArgumentException("NV21 dimensions");
        int w=width/2,h=height/2;byte[] result=new byte[w*h*3/2];
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)result[y*w+x]=source[y*2*width+x*2];
        for(int y=0;y<h/2;y++)for(int x=0;x<w;x+=2){
            int input=width*height+y*2*width+x*2,output=w*h+y*w+x;
            result[output]=source[input];result[output+1]=source[input+1];
        }
        return result;
    }
}
