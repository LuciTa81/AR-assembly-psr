package com.lucita.beastgate;

import android.content.Context;
import fi.iki.elonen.NanoHTTPD;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** Read-only, opt-in LAN observer. Never owns camera or assembly objects. */
final class SupervisorServer extends NanoHTTPD {
    private final Map<String,byte[]> assets=new HashMap<>();
    private final String token;
    private final String address;
    private volatile String snapshot="{\"running\":false,\"stage\":-1}";

    SupervisorServer(Context context,String address,int port)throws IOException{
        super(address,port);this.address=address;
        byte[] secret=new byte[24];new SecureRandom().nextBytes(secret);
        token=android.util.Base64.encodeToString(secret,android.util.Base64.URL_SAFE|android.util.Base64.NO_WRAP|android.util.Base64.NO_PADDING);
        for(String name:new String[]{"index.html","base.css","observer.css","observer.js",
            "fonts/IBMPlexSansKR-Regular.woff2","fonts/IBMPlexSansKR-Medium.woff2",
            "fonts/IBMPlexSansKR-SemiBold.woff2","fonts/IBMPlexSansKR-Bold.woff2"}){
            try(var input=context.getAssets().open("supervisor/"+name)){assets.put("/"+name,input.readAllBytes());}
        }
        // Bound simultaneous sockets; no upload parsing, file paths, or request bodies.
        setAsyncRunner(new AsyncRunner(){
            private final Set<ClientHandler> active=new HashSet<>();
            public synchronized void exec(ClientHandler client){
                if(active.size()>=6){client.close();return;}
                active.add(client);Thread thread=new Thread(client,"SupervisorHTTP");thread.setDaemon(true);thread.start();
            }
            public synchronized void closed(ClientHandler client){active.remove(client);}
            public synchronized void closeAll(){for(ClientHandler client:active)client.close();active.clear();}
        });
    }
    String link(){return "http://"+address+":"+getListeningPort()+"/#key="+token;}
    void publish(String json){snapshot=json;}

    @Override public Response serve(IHTTPSession request){
        String host=address+":"+getListeningPort();
        if(!host.equals(request.getHeaders().get("host")))return reply(Response.Status.FORBIDDEN,"text/plain","Invalid host");
        if(request.getMethod()!=Method.GET)return reply(Response.Status.METHOD_NOT_ALLOWED,"text/plain","Read only");
        String origin=request.getHeaders().get("origin");
        if(origin!=null&&!origin.equals("http://"+host))return reply(Response.Status.FORBIDDEN,"text/plain","Invalid origin");
        String path=request.getUri();
        if("/state.json".equals(path)){
            String auth=request.getHeaders().getOrDefault("authorization","");
            if(!MessageDigest.isEqual(("Bearer "+token).getBytes(StandardCharsets.US_ASCII),auth.getBytes(StandardCharsets.US_ASCII)))
                return reply(Response.Status.UNAUTHORIZED,"text/plain","Connection link required");
            return reply(Response.Status.OK,"application/json; charset=utf-8",snapshot);
        }
        if("/".equals(path))path="/index.html";
        byte[] bytes=assets.get(path);
        if(bytes==null)return reply(Response.Status.NOT_FOUND,"text/plain","Not found");
        String mime=path.endsWith(".css")?"text/css":path.endsWith(".js")?"application/javascript":path.endsWith(".woff2")?"font/woff2":"text/html";
        return secure(newFixedLengthResponse(Response.Status.OK,mime,new java.io.ByteArrayInputStream(bytes),bytes.length));
    }
    private Response reply(Response.Status status,String mime,String body){return secure(newFixedLengthResponse(status,mime,body));}
    private Response secure(Response response){
        response.addHeader("Cache-Control","no-store");response.addHeader("Referrer-Policy","no-referrer");
        response.addHeader("X-Content-Type-Options","nosniff");response.addHeader("X-Frame-Options","DENY");
        response.addHeader("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");
        response.closeConnection(true);return response;
    }
}
