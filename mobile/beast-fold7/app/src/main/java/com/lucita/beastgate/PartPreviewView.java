package com.lucita.beastgate;

import android.annotation.SuppressLint;
import android.content.Context;
import android.graphics.Color;
import android.net.Uri;
import android.util.Log;
import android.webkit.*;
import java.io.ByteArrayInputStream;
import java.util.Set;

/** Read-only local 3D layer; never supplies tracking or assembly evidence. */
@SuppressLint("SetJavaScriptEnabled")
final class PartPreviewView extends WebView {
    private static final String URL="https://appassets.androidplatform.net/parts/index.html";
    private static final Set<String> FILES=Set.of("index.html","parts.css","parts.js","three.module.min.js","three.core.min.js");
    private boolean ready,closed;
    private int part=4;

    static int selectPart(int preparationStage,int target){
        if(preparationStage==0||preparationStage==1)return preparationStage;
        return target==4?3:target>=0&&target<4?2:4;
    }

    PartPreviewView(Context context){
        super(context);
        setBackgroundColor(Color.TRANSPARENT);setFocusable(false);setClickable(false);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        getSettings().setJavaScriptEnabled(true);
        getSettings().setAllowFileAccess(false);getSettings().setAllowContentAccess(false);
        getSettings().setBlockNetworkLoads(true);getSettings().setDomStorageEnabled(false);
        getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return true;}
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();String file=uri.getLastPathSegment();
                if("https".equals(uri.getScheme())&&"appassets.androidplatform.net".equals(uri.getHost())
                    &&file!=null&&FILES.contains(file)&&("/parts/"+file).equals(uri.getPath())){
                    try{
                        String mime=file.endsWith(".js")?"application/javascript":file.endsWith(".css")?"text/css":"text/html";
                        return new WebResourceResponse(mime,"UTF-8",context.getAssets().open("parts/"+file));
                    }catch(java.io.IOException e){Log.e("BeastGate","PARTS_ASSET_FAILED",e);}
                }
                return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));
            }
            @Override public boolean onRenderProcessGone(WebView view,RenderProcessGoneDetail detail){
                Log.e("BeastGate","PARTS_RENDERER_GONE");close();return true;
            }
        });
        setWebChromeClient(new WebChromeClient(){
            @Override public boolean onConsoleMessage(ConsoleMessage message){
                String text=message.message();
                if("PARTS_READY".equals(text)&&!closed){ready=true;sendPart();}
                if(text.startsWith("PARTS_"))Log.i("BeastGate",text);
                if(message.messageLevel()==ConsoleMessage.MessageLevel.ERROR){
                    Log.e("BeastGate","PARTS_ERROR "+text);setVisibility(INVISIBLE);
                }
                return true;
            }
        });
        loadUrl(URL);
    }

    void showPart(int next){
        if(next<0||next>4)throw new IllegalArgumentException("part");
        if(part==next||closed)return;
        part=next;if(ready)sendPart();
    }
    private void sendPart(){if(!closed)evaluateJavascript("window.setPart("+part+")",null);}
    void close(){
        if(closed)return;closed=true;ready=false;
        stopLoading();setVisibility(GONE);
        if(getParent() instanceof android.view.ViewGroup parent)parent.removeView(this);
        destroy();
    }
}
