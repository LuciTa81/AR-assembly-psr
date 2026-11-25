package com.lucita.beastgate;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.os.Handler;
import android.os.Looper;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.Toast;
import java.net.Inet4Address;
import java.util.concurrent.Executors;
import java.util.function.Supplier;

/** Optional foreground-only observer; closing it never stops the assembly session. */
final class SupervisorLink {
    private final Activity activity;
    private final Supplier<String> state;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Switch toggle;
    private final ImageButton addressButton;
    private SupervisorServer server;
    private String address;
    private int generation;

    SupervisorLink(Activity activity,LinearLayout row,Supplier<String> state){
        this.activity=activity;this.state=state;
        toggle=new Switch(activity);toggle.setText("같은 Wi-Fi 관제");toggle.setTextColor(AssemblyScreen.INK);toggle.setTextSize(15);
        toggle.setMinHeight((int)(48*activity.getResources().getDisplayMetrics().density));
        row.addView(toggle,new LinearLayout.LayoutParams(0,-2,1));
        addressButton=new ImageButton(activity);addressButton.setImageResource(R.drawable.ic_wifi);
        addressButton.setImageTintList(new android.content.res.ColorStateList(
            new int[][]{{-android.R.attr.state_enabled},{}},new int[]{AssemblyScreen.LINE,AssemblyScreen.MINT}));
        addressButton.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        addressButton.setContentDescription("관제 주소");addressButton.setTooltipText("관제 주소");addressButton.setEnabled(false);
        int size=(int)(48*activity.getResources().getDisplayMetrics().density);
        row.addView(addressButton,new LinearLayout.LayoutParams(size,size));
        addressButton.setOnClickListener(v->showLink());
        toggle.setOnCheckedChangeListener((button,checked)->{
            if(!checked){close();return;}
            new AlertDialog.Builder(activity).setTitle("노트북 관제 연결")
                .setMessage("같은 Wi-Fi에서 작업 상태를 공유합니다. 영상·음성은 전송하지 않아요. 연결 주소를 아는 기기만 볼 수 있습니다.\n\nHTTP 연결은 암호화되지 않으므로 신뢰하는 Wi-Fi에서만 사용해 주세요.")
                .setPositiveButton("연결",(dialog,which)->begin()).setNegativeButton("취소",(dialog,which)->toggle.setChecked(false))
                .setOnCancelListener(dialog->toggle.setChecked(false)).show();
        });
    }
    static String wifiAddress(Activity activity){
        ConnectivityManager manager=(ConnectivityManager)activity.getSystemService(Activity.CONNECTIVITY_SERVICE);
        var network=manager.getActiveNetwork();var capabilities=manager.getNetworkCapabilities(network);
        if(capabilities==null||!capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
            ||capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN))return null;
        var properties=manager.getLinkProperties(network);
        if(properties!=null)for(var link:properties.getLinkAddresses())
            if(link.getAddress() instanceof Inet4Address&&link.getAddress().isSiteLocalAddress())return link.getAddress().getHostAddress();
        return null;
    }
    void begin(){
        String ip=wifiAddress(activity);
        if(ip==null){fail("같은 Wi-Fi 연결을 확인해 주세요");return;}
        int token=++generation;toggle.setEnabled(false);address=ip;
        var executor=Executors.newSingleThreadExecutor();
        executor.execute(()->{
            SupervisorServer ready=null;Exception error=null;
            try{ready=new SupervisorServer(activity.getApplicationContext(),ip,8766);ready.start(2500,true);}
            catch(Exception e){if(ready!=null)ready.stop();error=e;}
            SupervisorServer result=ready;Exception failure=error;
            handler.post(()->{
                if(token!=generation||activity.isDestroyed()){if(result!=null)result.stop();return;}
                toggle.setEnabled(true);
                if(failure!=null){fail("관제 연결을 열지 못했어요. Wi-Fi와 포트를 확인해 주세요");return;}
                server=result;addressButton.setEnabled(true);update.run();
            });
        });executor.shutdown();
    }
    private final Runnable update=new Runnable(){public void run(){
        if(server==null)return;
        if(!java.util.Objects.equals(address,wifiAddress(activity))){fail("Wi-Fi가 변경되어 관제 연결을 종료했어요");return;}
        server.publish(state.get());handler.postDelayed(this,250);
    }};
    private void showLink(){
        if(server==null)return;
        String link=server.link();
        android.widget.TextView text=new android.widget.TextView(activity);text.setText(link);text.setTextIsSelectable(true);
        int padding=(int)(24*activity.getResources().getDisplayMetrics().density);text.setPadding(padding,padding,padding,padding);
        new AlertDialog.Builder(activity).setTitle("노트북에서 열 주소").setView(text)
            .setPositiveButton("주소 복사",(dialog,which)->{
                ClipboardManager clipboard=(ClipboardManager)activity.getSystemService(Activity.CLIPBOARD_SERVICE);
                clipboard.setPrimaryClip(ClipData.newPlainText("AR Assembly",link));
            }).setNegativeButton("닫기",null).show();
    }
    private void fail(String message){close();Toast.makeText(activity,message,Toast.LENGTH_LONG).show();}
    void close(){
        ++generation;handler.removeCallbacks(update);
        if(server!=null){server.stop();server=null;}
        addressButton.setEnabled(false);toggle.setEnabled(true);
        if(toggle.isChecked())toggle.setChecked(false);
    }
}
