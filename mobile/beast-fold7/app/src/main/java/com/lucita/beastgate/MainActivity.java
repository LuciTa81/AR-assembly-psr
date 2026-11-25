package com.lucita.beastgate;

import android.Manifest;
import android.app.Activity;
import android.app.Presentation;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Bitmap;
import android.hardware.display.DisplayManager;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.Display;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ImageButton;
import com.herohan.uvcapp.CameraException;
import com.herohan.uvcapp.CameraHelper;
import com.herohan.uvcapp.ICameraHelper;
import com.serenegiant.usb.Size;
import com.serenegiant.usb.UVCCamera;
import com.serenegiant.utils.UVCUtils;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.opencv.android.OpenCVLoader;
import org.opencv.android.Utils;
import org.opencv.core.Mat;
import org.opencv.core.CvType;
import org.opencv.imgproc.Imgproc;

public class MainActivity extends Activity implements DisplayManager.DisplayListener {
    private static final String TAG = "BeastGate";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final AtomicLong frames = new AtomicLong();
    private CameraHelper camera;
    private Presentation presentation;
    private StereoOverlayView stereoView;
    private PartPreviewView partPreview;
    private boolean partPreviewEnabled;
    private boolean boxOutlineEnabled;
    private BoxOutline boxOutline;
    private String outlineStatus="";
    private boolean targetSphereEnabled;
    private boolean screwContextEnabled;
    private SphereMarker sphereMarker;
    private EyeProjection eyeProjection;
    private DisplayManager displays;
    private TextView status, displayStatus, trackingStatus;
    private TextView taskStatus;
    private SupervisorLink supervisor;
    private RemoteSupervisorLink remoteSupervisor;
    private AssemblyScreen screen;
    private final String processSession=java.util.UUID.randomUUID().toString();
    private String runSession=processSession+"-idle";
    private Button start,stop;
    private boolean standalone,calibrationReady,hasRun,pendingCameraPermission;
    private AnalysisView preview;
    private WorkspaceTracker tracker;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final AtomicBoolean busy=new AtomicBoolean();
    private final AtomicLong lastAnalysis=new AtomicLong();
    private volatile String trackingSummary="추적 대기";
    private long startMs, previousFrames, previousMs;
    private volatile boolean running;
    private boolean selected;
    private volatile int session;
    private String cameraMode = "";
    private String probeTarget;
    private boolean toolProbe;
    private boolean poseProbe;
    private boolean captureProbe;
    private int captureLimit;
    private DiagnosticCapture diagnosticCapture;
    private final ExecutorService captureWorker=Executors.newSingleThreadExecutor();
    private final AtomicBoolean captureBusy=new AtomicBoolean();
    private volatile boolean captureFailed;
    private boolean assemblyProbe;
    private boolean assemblyFull;
    private boolean preparationProbe;
    private PreparationGuide preparation;
    private AssemblyProbe assembly;
    private ToolEvidence toolEvidence;
    private WorkspaceTracker.Result latestPose;
    private long latestPoseAt;
    private String assemblyStatus="";
    private volatile boolean toolReady;
    private YoloDetector toolDetector;
    private final ExecutorService toolWorker=Executors.newSingleThreadExecutor();
    private final AtomicBoolean toolBusy=new AtomicBoolean();
    private volatile String toolSummary="";

    static String selectProbeTarget(String requested){
        return "A".equals(requested)||"B".equals(requested)||"C".equals(requested)||"D".equals(requested)?requested:"A";
    }
    static boolean isStandalone(android.content.Intent intent){
        for(String key:new String[]{"probe_target","tool_probe","pose_probe","capture_probe","screw_context",
            "target_sphere","box_outline","part_preview","preparation_probe","assembly_full","assembly_probe"})
            if(intent.hasExtra(key))return false;
        return true;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        standalone=isStandalone(getIntent());
        probeTarget=selectProbeTarget(getIntent().getStringExtra("probe_target"));
        toolProbe=getIntent().getBooleanExtra("tool_probe",false);
        poseProbe=getIntent().getBooleanExtra("pose_probe",false);
        captureProbe=getIntent().getBooleanExtra("capture_probe",false);
        captureLimit=Math.max(1,Math.min(100,getIntent().getIntExtra("capture_limit",100)));
        screwContextEnabled=standalone||getIntent().getBooleanExtra("screw_context",false);
        targetSphereEnabled=!screwContextEnabled&&getIntent().getBooleanExtra("target_sphere",false);
        boxOutlineEnabled=screwContextEnabled||targetSphereEnabled||getIntent().getBooleanExtra("box_outline",false);
        partPreviewEnabled=boxOutlineEnabled||getIntent().getBooleanExtra("part_preview",false);
        preparationProbe=partPreviewEnabled||getIntent().getBooleanExtra("preparation_probe",false);
        assemblyFull=preparationProbe||getIntent().getBooleanExtra("assembly_full",false);
        assemblyProbe=assemblyFull||getIntent().getBooleanExtra("assembly_probe",false);
        if(assemblyProbe){captureProbe=false;poseProbe=false;toolProbe=true;probeTarget="A";}
        if(captureProbe){poseProbe=true;toolProbe=false;}
        Log.i(TAG,"PROBE_TARGET "+probeTarget);
        Log.i(TAG,"LAUNCH_MODE "+(standalone?"standalone_v1":"explicit_diagnostic"));
        UVCUtils.init(getApplication());
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout root;
        if(standalone){
            screen=new AssemblyScreen(this);root=screen;
            start=screen.start;stop=screen.stop;status=screen.status;displayStatus=screen.displayStatus;
            trackingStatus=screen.trackingStatus;taskStatus=screen.taskStatus;preview=screen.preview;
            screen.refresh.setOnClickListener(v->{showDisplay();refreshControls();});
            supervisor=new SupervisorLink(this,screen.localHost,this::supervisorSnapshot);
            remoteSupervisor=new RemoteSupervisorLink(this,screen.remoteHost,this::supervisorSnapshot);
        }else{
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);
        root.setBackgroundColor(Color.rgb(20, 24, 26));
        TextView title = label(standalone?"AR Assembly":preparationProbe?"상자·뚜껑 시간 안내 → A~D":assemblyFull?"A → D 단계 안내":assemblyProbe?"A → B 단계 안내":captureProbe?"마커 경계 사진 진단 · 최대 "+captureLimit+"장":poseProbe?"마커 4개 추적 확인":toolProbe?"드라이버 인식 확인":"나사 "+probeTarget+" 양안 위치 확인", 24);
        displayStatus = label("외부 화면 확인 중", 18);
        status = label("카메라 대기", 18);
        trackingStatus=label("추적 대기",18);
        root.addView(title); root.addView(displayStatus); root.addView(status);
        taskStatus=label("시작 대기",20);taskStatus.setMinHeight((int)(48*getResources().getDisplayMetrics().density));
        if(standalone)root.addView(taskStatus);
        LinearLayout actions = new LinearLayout(this);
        start = new Button(this); start.setText(standalone?"작업 시작":preparationProbe?"전체 안내 · 최대 5분":assemblyFull?"A → D 확인 · 최대 5분":assemblyProbe?"A → B 확인 · 90초":captureProbe?"진단 사진 저장 · 30초":poseProbe?"마커 추적 확인 · 30초":toolProbe?"도구 인식 확인 · 30초":probeTarget+" 양안 확인 · 30초");
        stop = new Button(this); stop.setText("작업 종료");stop.setEnabled(false);
        int buttonHeight=(int)(52*getResources().getDisplayMetrics().density);
        actions.addView(start, new LinearLayout.LayoutParams(0, buttonHeight, 1));
        actions.addView(stop, new LinearLayout.LayoutParams(0, buttonHeight, 1));
        ImageButton refresh=new ImageButton(this);refresh.setImageResource(android.R.drawable.ic_menu_rotate);
        refresh.setContentDescription("연결 확인");refresh.setTooltipText("연결 확인");
        refresh.setOnClickListener(v->{showDisplay();refreshControls();});
        actions.addView(refresh,new LinearLayout.LayoutParams(buttonHeight,buttonHeight));
        root.addView(actions);
        root.addView(trackingStatus);
        preview = new AnalysisView(this);
        root.addView(preview, new LinearLayout.LayoutParams(-1, 0, 1));
        }
        setContentView(root);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            android.graphics.Insets bars = insets.getInsets(android.view.WindowInsets.Type.systemBars());
            int padding=standalone?0:24;
            v.setPadding(padding + bars.left, padding + bars.top, padding + bars.right, padding + bars.bottom);
            return insets;
        });
        try {
            if(!OpenCVLoader.initLocal())throw new IllegalStateException("OpenCV load failed");
            tracker=new WorkspaceTracker(this,BuildConfig.PARTIAL_MARKER_CANDIDATE);
            eyeProjection=new EyeProjection(this);
            if(boxOutlineEnabled){boxOutline=new BoxOutline(this);Log.i(TAG,"BOX_OUTLINE_READY frozen_profile=true");}
            if(targetSphereEnabled){sphereMarker=new SphereMarker(this);Log.i(TAG,"SPHERE_MARKER_READY diameter_px=40 opacity=0.58 calibrated_centers_unchanged=true");}
            if(screwContextEnabled)Log.i(TAG,"SCREW_CONTEXT_READY inactive=neutral active=phase_color calibrated_centers_unchanged=true");
            calibrationReady=true;
            Log.i(TAG,"TRACKER_READY OpenCV="+org.opencv.core.Core.VERSION);
        }catch(Exception e){Log.e(TAG,"TRACKER_INIT_FAILED",e);report("보정 로딩 실패");start.setEnabled(false);}
        if(toolProbe&&tracker!=null&&eyeProjection!=null&&(!boxOutlineEnabled||boxOutline!=null)&&(!targetSphereEnabled||sphereMarker!=null)){
            start.setEnabled(false);report("도구 인식 준비 중");
            toolWorker.execute(()->{
                try{
                    toolDetector=new YoloDetector(this);if(assemblyProbe)toolEvidence=new ToolEvidence(this);toolReady=true;
                    handler.post(()->{if(!isFinishing()&&!isDestroyed()){if(!running)report("인식 준비 완료");refreshControls();}});
                    Log.i(TAG,"YOLO_READY CPU threads=2 input=640x384 conf=0.20");
                }catch(Exception e){Log.e(TAG,"YOLO_INIT_FAILED",e);handler.post(()->report("도구 인식 로딩 실패"));}
            });
        }
        start.setOnClickListener(v -> {
            if(!canStart())return;
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED){
                pendingCameraPermission=true;refreshControls();
                requestPermissions(new String[]{Manifest.permission.CAMERA}, 1);
            }else startCamera();
        });
        stop.setOnClickListener(v -> stopCamera("작업을 종료했어요"));
        displays = (DisplayManager) getSystemService(DISPLAY_SERVICE);
        displays.registerDisplayListener(this, handler);
        showDisplay();
    }

    private TextView label(String text, int size) {
        TextView v = new TextView(this); v.setText(text); v.setTextSize(size);
        v.setTextColor(Color.WHITE); v.setPadding(0, 8, 0, 8); return v;
    }

    private void report(String message) {
        status.setText(message);Log.i(TAG,message);refreshControls();
        if(screen!=null&&!running)screen.showNotice(message);
    }

    private boolean hasCameraDevice(){
        UsbManager usb=(UsbManager)getSystemService(USB_SERVICE);
        for(UsbDevice device:usb.getDeviceList().values())
            if(device.getVendorId()==3141&&device.getProductId()==25448)return true;
        return false;
    }
    private boolean canStart(){
        return !running&&!pendingCameraPermission&&calibrationReady&&(!toolProbe||toolReady)
            &&presentation!=null&&presentation.isShowing()&&stereoView!=null
            &&(!partPreviewEnabled||partPreview!=null)&&(!standalone||hasCameraDevice());
    }
    private void refreshControls(){
        if(start==null||stop==null)return;
        start.setEnabled(canStart());stop.setEnabled(running);
        if(standalone){
            start.setText(running?"작업 중":hasRun?"다시 시작":"작업 시작");
            if(!running){
                String state=!calibrationReady?"보정을 확인하고 있어요":toolProbe&&!toolReady?"인식을 준비하고 있어요"
                    :presentation==null?"Beast 연결과 Full SBS 설정을 확인해 주세요"
                    :!hasCameraDevice()?"Beast 카메라 연결을 확인해 주세요"
                    :partPreviewEnabled&&partPreview==null?"3D 안내를 열지 못했어요. 연결을 다시 확인해 주세요"
                    :pendingCameraPermission?"카메라 권한 확인 중":hasRun?"다음 작업 준비":"시작 준비 완료";
                if(screen!=null)screen.idleInstruction(state);
                else if(taskStatus!=null)taskStatus.setText(state);
            }
            refreshScreen();
        }
    }

    private void refreshScreen(){
        if(screen==null)return;
        try{screen.present(new org.json.JSONObject(supervisorSnapshot()),canStart(),hasRun);}
        catch(org.json.JSONException error){Log.w(TAG,"PHONE_UI_STATE_FAILED");}
    }

    private void dismissPresentation(){
        if(partPreview!=null){partPreview.close();partPreview=null;}
        if(presentation!=null)presentation.dismiss();
        presentation=null;stereoView=null;
    }

    private void showDisplay() {
        if(displays==null)return;
        Display target = null;
        for (Display d : displays.getDisplays(DisplayManager.DISPLAY_CATEGORY_PRESENTATION))
            if (d.getName().toLowerCase(java.util.Locale.ROOT).contains("viture")) target = d;
        if (target == null) {
            dismissPresentation();displayStatus.setText("Beast 외부 화면 없음");
            if(running)stopCamera("Beast 화면 연결 종료");refreshControls();return;
        }
        Display.Mode mode = target.getMode();
        String info = "Beast " + mode.getPhysicalWidth() + "x" + mode.getPhysicalHeight() + " @ " + Math.round(mode.getRefreshRate());
        displayStatus.setText(info); Log.i(TAG, "DISPLAY " + info);
        if(mode.getPhysicalWidth()!=3840||mode.getPhysicalHeight()!=1080){
            dismissPresentation();
            if(running)stopCamera("Full SBS 화면이 필요해요");refreshControls();return;
        }
        if (presentation != null && presentation.getDisplay().getDisplayId() == target.getDisplayId()){refreshControls();return;}
        if(running)stopCamera("Beast 화면이 변경됐어요");
        dismissPresentation();
        presentation = new Presentation(this, target);
        stereoView=new StereoOverlayView(presentation.getContext());
        stereoView.setSphereMarker(sphereMarker);
        stereoView.setScrewContextEnabled(screwContextEnabled);
        android.widget.FrameLayout layers=new android.widget.FrameLayout(presentation.getContext());
        layers.addView(stereoView,new android.widget.FrameLayout.LayoutParams(-1,-1));
        if(partPreviewEnabled){
            try{
                partPreview=new PartPreviewView(presentation.getContext());
                layers.addView(partPreview,new android.widget.FrameLayout.LayoutParams(-1,-1));
            }catch(Exception e){Log.e(TAG,"PARTS_INIT_FAILED",e);partPreview=null;}
        }
        presentation.setContentView(layers);
        try {
            presentation.show();
            presentation.getWindow().setLayout(-1, -1);
            presentation.getWindow().getDecorView().setSystemUiVisibility(5894);
        } catch (WindowManager.InvalidDisplayException e) {
            Log.e(TAG, "DISPLAY_FAILED", e);dismissPresentation();
        }
        refreshControls();
    }

    private void startCamera() {
        if (running || tracker==null || eyeProjection==null || (boxOutlineEnabled&&boxOutline==null)
            || (targetSphereEnabled&&sphereMarker==null) || (toolProbe&&!toolReady)) return;
        showDisplay();
        if(presentation==null||stereoView==null||!presentation.isShowing()){
            report("Beast를 Full SBS로 연결해 주세요");return;
        }
        if(!canStart()){refreshControls();return;}
        tracker.resetPartialTracking();
        running = true;hasRun=true; selected = false; frames.set(0); previousFrames = 0;refreshControls();
        if(captureProbe&&diagnosticCapture==null){
            try{
                diagnosticCapture=new DiagnosticCapture(new java.io.File(getFilesDir(),"marker-diagnostics"),captureLimit);
                Log.i(TAG,"CAPTURE_DIRECTORY "+diagnosticCapture.directory);
            }catch(Exception e){running=false;Log.e(TAG,"CAPTURE_INIT_FAILED",e);report("진단 저장 준비 실패");return;}
        }
        lastAnalysis.set(0);trackingSummary="추적 대기";toolSummary="";preview.clear();
        startMs = previousMs = SystemClock.elapsedRealtime();
        int token = ++session;
        runSession=processSession+"-"+token;
        if(assemblyProbe){
            assembly=new AssemblyProbe(startMs,assemblyFull?4:1);latestPose=null;latestPoseAt=0;assemblyStatus="";
            preparation=preparationProbe?new PreparationGuide(startMs):null;
            if(preparation!=null)Log.i(TAG,"PREPARATION_START box_ms="+PreparationGuide.BOX_DURATION_MS+" lid_ms="+PreparationGuide.LID_DURATION_MS+" mode=tracked_instruction_time object_verified=false images_saved=false");
            Log.i(TAG,"ASSEMBLY_START session="+token+" full="+assemblyFull+" engage_ms=800 cue_delay_ms="+AssemblyProbe.WORKING_CUE_DELAY_MS+" green_advance_ms=3000 fastening_verified=false images_saved=false");
            handler.post(assemblyTick);
            renderAssembly();
        }
        report("USB 카메라 연결 중");
        if(remoteSupervisor!=null)remoteSupervisor.cameraRunning(true);
        camera = new CameraHelper();
        camera.setStateCallback(new ICameraHelper.StateCallback() {
            private boolean active() { return running && token == session && camera != null; }
            public void onAttach(UsbDevice device) {
                if (active() && !selected && device.getVendorId() == 3141 && device.getProductId() == 25448) {
                    selected = true; camera.selectDevice(device);
                }
            }
            public void onDeviceOpen(UsbDevice d, boolean first) {
                if(active())camera.openCamera(new Size(UVCCamera.UVC_VS_FRAME_MJPEG,1280,720,30,java.util.Arrays.asList(30)));
            }
            public void onCameraOpen(UsbDevice d) {
                if (!active()) return;
                Size size = camera.getPreviewSize(); cameraMode = String.valueOf(size);
                Log.i(TAG, "CAMERA_OPEN " + cameraMode);
                if(size==null||size.width!=1280||size.height!=720){stopCamera("보정 해상도 불일치");return;}
                camera.setFrameCallback(buffer -> {
                    if(!running||token!=session)return;
                    frames.incrementAndGet();long now=SystemClock.elapsedRealtime();
                    boolean analysis=now-lastAnalysis.get()>=200&&busy.compareAndSet(false,true);
                    boolean video=remoteSupervisor!=null&&remoteSupervisor.wantsFrame(now);
                    if(!analysis&&!video)return;
                    if(analysis)lastAnalysis.set(now);
                    java.nio.ByteBuffer data=buffer.duplicate();data.rewind();
                    if(data.remaining()!=1280*720*3/2){if(analysis)busy.set(false);trackingSummary="프레임 형식 불일치";return;}
                    byte[] copy=new byte[data.remaining()];data.get(copy);
                    if(video)remoteSupervisor.offerFrame(copy,now);
                    if(analysis)worker.execute(()->analyze(copy,now,token));
                }, UVCCamera.PIXEL_FORMAT_NV21);
                camera.startPreview();
                report("카메라 수신 시작 " + cameraMode);
            }
            public void onCameraClose(UsbDevice d) { if (active()) stopCamera("카메라 닫힘"); }
            public void onDeviceClose(UsbDevice d) { if (active()) stopCamera("USB 연결 종료"); }
            public void onDetach(UsbDevice d) { if (active() && d.getVendorId() == 3141) stopCamera("카메라 분리"); }
            public void onCancel(UsbDevice d) { if (active()) stopCamera("USB 권한 취소"); }
            public void onError(UsbDevice d, CameraException e) {
                if (active()) { Log.e(TAG, "CAMERA_ERROR", e); stopCamera("카메라 오류: " + e.getMessage()); }
            }
        });
        handler.postDelayed(tick, 1000);
    }

    private final Runnable tick = new Runnable() {
        public void run() {
            if (!running) return;
            long now = SystemClock.elapsedRealtime(), count = frames.get();
            double fps = (count - previousFrames) * 1000.0 / Math.max(1, now - previousMs);
            previousFrames = count; previousMs = now;
            String metrics=String.format(java.util.Locale.US, "프레임 %d | %.1f fps | %ds", count, fps, (now-startMs)/1000);
            if(standalone){report("실행 중 · "+((now-startMs)/1000)+"초 / 최대 "+(SessionLimits.WORK_MS/60000)+"분");Log.i(TAG,metrics);}
            else report(metrics);
            trackingStatus.setText(trackingSummary+toolSummary+(captureProbe?" | 사진 "+(diagnosticCapture==null?0:diagnosticCapture.count())+"/"+captureLimit:"")+assemblyStatus);Log.i(TAG,"TRACKING "+trackingSummary+toolSummary);
            if (SessionLimits.expired(now-startMs,standalone,assemblyFull,assemblyProbe)) { stopCamera(standalone?(SessionLimits.WORK_MS/60000)+"분이 지나 안내를 종료했어요":assemblyFull?"5분 시험 종료":assemblyProbe?"90초 시험 종료":"30초 시험 종료"); return; }
            if(standalone&&count==0&&now-startMs>=15000){stopCamera("카메라 영상이 없어요. USB 연결과 권한을 확인해 주세요");return;}
            handler.postDelayed(this, 1000);
        }
    };

    private final Runnable assemblyTick=new Runnable(){
        public void run(){
            if(!running||assembly==null)return;
            if(preparation!=null&&!preparation.finished()){handler.postDelayed(this,50);return;}
            long now=SystemClock.elapsedRealtime();
            int previousTarget=assembly.target();long greenAt=assembly.greenAt();
            if(assembly.tick(now)){
                Log.i(TAG,"ASSEMBLY_TRANSITION "+"ABCD".charAt(previousTarget)+"->"+(assembly.target()==4?"INSPECT":"ABCD".substring(assembly.target(),assembly.target()+1))+" reason=rendered_green_timer delay_ms="+(now-greenAt)+" fastening_verified=false");
                renderAssembly();
            }
            if(assembly.finished()&&now-assembly.finishedAt()>=(assemblyFull?10000:5000)){stopCamera(standalone?"안내가 끝났어요":assemblyFull?"A → D 안내 시험 종료":"A → B 확인 종료");return;}
            handler.postDelayed(this,50);
        }
    };

    private boolean currentGuidancePose(long now){
        return latestPose!=null&&latestPose.supportsGuidance()&&now>=latestPoseAt&&now-latestPoseAt<=500;
    }

    private void renderAssembly(){
        if(!running||assembly==null||stereoView==null)return;
        if(standalone&&screen==null){
            String current=preparation!=null&&!preparation.finished()?(preparation.stage()==0?"상자 배치":"뚜껑 닫기")
                :assembly.target()==4?"최종 검사":"나사 "+"ABCD".charAt(assembly.target())+" · "+(assembly.target()+1)+"/4";
            taskStatus.setText(current);
        }
        refreshScreen();
        WorkspaceTracker.Result guidePose=currentGuidancePose(SystemClock.elapsedRealtime())?latestPose:null;
        if(boxOutline!=null){
            int stage=BoxOutline.stage(preparation==null?-1:preparation.stage(),assembly.target());
            var strokes=boxOutline.project(stage,guidePose,eyeProjection);
            stereoView.updateOutline(strokes,latestPoseAt);
            String summary="stage="+stage+" strokes="+(strokes==null?0:strokes.length);
            if(!summary.equals(outlineStatus)){outlineStatus=summary;Log.i(TAG,"BOX_OUTLINE "+summary);}
        }
        if(partPreview!=null)partPreview.showPart(PartPreviewView.selectPart(preparation==null?-1:preparation.stage(),assembly.target()));
        if(preparation!=null&&!preparation.finished()){
            PreparationGuide guide=preparation;
            boolean tracked=guidePose!=null;
            stereoView.updatePreparation(guide.stage(),latestPoseAt,tracked,(stage,frame,now,valid)->{
                if(!running||preparation!=guide)return;
                long duration=guide.durationMs();
                if(guide.onDraw(stage,frame,now,valid)){
                    Log.i(TAG,"PREPARATION_TRANSITION "+(stage==0?"BOX->LID":"LID->A")+" reason=tracked_instruction_time duration_ms="+duration+" object_verified=false");
                    if(guide.finished())assembly=new AssemblyProbe(now,4);
                    renderAssembly();
                }
            });
            assemblyStatus=" | "+(guide.stage()==0?"상자":"뚜껑")+" 안내 "+Math.max(0,(guide.durationMs()-guide.elapsedMs()+999)/1000)+"초";
            return;
        }
        AssemblyProbe gate=assembly;
        if(screwContextEnabled){
            double[][][] points=null;
            if(guidePose!=null){
                points=new double[4][][];
                for(int i=0;i<4;i++)points[i]=eyeProjection.project(latestPose.cameraTargets.get("ABCD".substring(i,i+1)));
            }
            stereoView.updateScrewContext(points,latestPoseAt);
        }
        if(gate.target()==4){stereoView.showInspection();return;}
        String target="ABCD".substring(gate.target(),gate.target()+1);
        double[][] pair=guidePose!=null
            ?eyeProjection.project(latestPose.cameraTargets.get(target)):null;
        stereoView.updateGuide(pair,latestPoseAt,gate.target(),gate.phase(),(drawn,now)->{
            if(!running||assembly!=gate)return;
            long before=gate.greenAt();gate.acknowledgeGreen(drawn,now);
            if(before<0&&gate.greenAt()>=0)Log.i(TAG,"ASSEMBLY_GREEN_DRAWN target="+drawn+" elapsed_ms="+now+" delay_ms=3000");
        });
    }

    private String supervisorSnapshot(){
        long now=SystemClock.elapsedRealtime();
        int stage=SupervisorState.stage(running,preparation,assembly);
        long age=latestPose==null?-1:Math.max(0,now-latestPoseAt);
        boolean tracked=running&&currentGuidancePose(now);
        boolean visible=tracked;
        if(stage>=2&&stage<=5&&tracked)
            visible=eyeProjection.project(latestPose.cameraTargets.get("ABCD".substring(stage-2,stage-1)))!=null;
        AssemblyProbe.Phase phase=assembly==null?AssemblyProbe.Phase.APPROACH:assembly.phase();
        long remaining=preparation!=null&&!preparation.finished()?Math.max(0,preparation.durationMs()-preparation.elapsedMs())
            :assembly!=null&&assembly.greenAt()>=0?Math.max(0,3000-(now-assembly.greenAt())):0;
        return SupervisorState.json(runSession,now,running?Math.max(0,now-startMs):0,running,stage,
            stage<2?"PREPARATION":stage==6?"INSPECTION":phase.name(),SupervisorState.action(stage,phase,visible),
            tracked,visible,latestPose==null?0:latestPose.markers.size(),latestPose==null?Double.NaN:latestPose.rms,
            age,frames.get(),running?(latestPose==null?"waiting_for_frame":latestPose.reason):status.getText().toString(),remaining);
    }

    private void stopCamera(String reason) {
        if(remoteSupervisor!=null)remoteSupervisor.cameraRunning(false);
        if(running)hasRun=true;
        pendingCameraPermission=false;
        running = false; ++session; handler.removeCallbacks(tick);handler.removeCallbacks(assemblyTick);assembly=null;preparation=null;latestPose=null;outlineStatus="";
        if(tracker!=null)tracker.resetPartialTracking();
        if (camera != null) { CameraHelper old = camera; camera = null; old.release(); }
        report(reason + " | frames=" + frames.get());
        preview.clear();trackingSummary="추적 종료";trackingStatus.setText(trackingSummary);
        if(stereoView!=null)stereoView.clear();
        if(partPreview!=null)partPreview.showPart(4);
        refreshControls();
    }

    private void analyze(byte[] bytes,long received,int token){
        Mat yuv=new Mat(1080,1280,CvType.CV_8UC1),gray=null,rgba=new Mat();
        try{
            if(!running||token!=session)return;
            yuv.put(0,0,bytes);gray=yuv.submat(0,720,0,1280);
            WorkspaceTracker.Result result=tracker.process(gray);
            double[][] pair=result.valid?eyeProjection.project(result.cameraTargets.get(probeTarget)):null;
            Bitmap bitmap;
            if(!toolProbe){
                Imgproc.cvtColor(yuv,rgba,Imgproc.COLOR_YUV2RGBA_NV21);
                bitmap=Bitmap.createBitmap(1280,720,Bitmap.Config.ARGB_8888);Utils.matToBitmap(rgba,bitmap);
            }else bitmap=null;
            long duration=SystemClock.elapsedRealtime()-received;
            String eyeStatus=pair==null?probeTarget+" 숨김":String.format(java.util.Locale.US,"%s L %.1f,%.1f R %.1f,%.1f",probeTarget,pair[0][0],pair[0][1],pair[1][0],pair[1][1]);
            String summary=String.format(java.util.Locale.US,"마커 %s | %s | RMS %.2f | %dms | %s",result.markers.keySet(),result.reason,result.rms,duration,eyeStatus);
            handler.post(()->{
                if(running&&token==session){
                    if(poseProbe)logPose(result,pair,received,token);
                    trackingSummary=summary;if(bitmap!=null)preview.update(bitmap,result,received);
                    if(assemblyProbe){
                        latestPose=result;latestPoseAt=received;renderAssembly();
                        if(BuildConfig.PARTIAL_MARKER_CANDIDATE)Log.i("BeastGuideFrame",supervisorSnapshot());
                    }
                    else if(stereoView!=null)stereoView.update(pair,received);
                }
            });
            if(captureProbe&&bitmap!=null&&!captureFailed&&running&&token==session
                &&diagnosticCapture!=null&&diagnosticCapture.count()<captureLimit&&captureBusy.compareAndSet(false,true)){
                captureWorker.execute(()->{
                    try{
                        if(diagnosticCapture.save(bitmap,result,received,token))
                            Log.i(TAG,"CAPTURE_SAVED count="+diagnosticCapture.count()+" frame_ms="+received);
                    }catch(Exception e){
                        captureFailed=true;Log.e(TAG,"CAPTURE_FAILED",e);
                        handler.post(()->{if(running&&token==session)stopCamera("진단 사진 저장 오류");});
                    }finally{captureBusy.set(false);}
                });
            }
            // No inference queue: keep eye tracking independent and preserve the tool frame's pose/time.
            if(toolProbe&&running&&token==session&&toolBusy.compareAndSet(false,true))
                toolWorker.execute(()->analyzeTool(bytes,result,received,token));
        }catch(Exception e){Log.e(TAG,"ANALYSIS_FAILED",e);handler.post(()->{if(running&&token==session)stopCamera("추적 처리 오류");});}
        finally{if(gray!=null)gray.release();yuv.release();rgba.release();busy.set(false);}
    }

    private void logPose(WorkspaceTracker.Result result,double[][] pair,long received,int token){
        try{
            org.json.JSONObject item=new org.json.JSONObject(),corners=new org.json.JSONObject();
            for(var entry:result.markers.entrySet()){
                org.json.JSONArray quad=new org.json.JSONArray();
                for(var p:entry.getValue())quad.put(new org.json.JSONArray().put(p.x).put(p.y));
                corners.put(Integer.toString(entry.getKey()),quad);
            }
            long age=SystemClock.elapsedRealtime()-received;
            String visibility=!result.valid?"pose_rejected":!result.cameraTargets.containsKey(probeTarget)?"target_outside_camera":pair==null?"eye_projection_rejected":age>500?"stale":stereoView==null?"no_stereo_surface":"pair_ready";
            item.put("session",token).put("frame_ms",received).put("age_ms",age).put("count",result.markers.size())
                .put("reason",result.reason).put("valid",result.valid).put("visibility",visibility)
                .put("rms",Double.isFinite(result.rms)?result.rms:org.json.JSONObject.NULL)
                .put("max_error",Double.isFinite(result.maxError)?result.maxError:org.json.JSONObject.NULL)
                .put("corners",corners);
            Log.i("BeastPoseFrame",item.toString());
        }catch(org.json.JSONException e){Log.e(TAG,"POSE_LOG_FAILED",e);}
    }

    private void analyzeTool(byte[] bytes,WorkspaceTracker.Result pose,long received,int token){
        Mat yuv=new Mat(1080,1280,CvType.CV_8UC1),rgba=new Mat();
        try{
            if(!running||token!=session)return;
            yuv.put(0,0,bytes);Imgproc.cvtColor(yuv,rgba,Imgproc.COLOR_YUV2RGBA_NV21);
            long started=SystemClock.elapsedRealtime();
            var detections=toolDetector.detect(rgba);
            ToolEvidence.Result evidence=assemblyProbe?toolEvidence.evaluate(detections,pose):null;
            long inferenceMs=SystemClock.elapsedRealtime()-started;
            Bitmap bitmap=Bitmap.createBitmap(1280,720,Bitmap.Config.ARGB_8888);Utils.matToBitmap(rgba,bitmap);
            long age=SystemClock.elapsedRealtime()-received;
            String summary=" | 도구 "+detections.size()+"개 · "+inferenceMs+"ms";
            Log.i(TAG,"YOLO frame_ms="+received+" age_ms="+age+" inference_ms="+inferenceMs+" detections="+detections);
            handler.post(()->{if(running&&token==session){
                toolSummary=summary;preview.update(bitmap,pose,received,detections);
                if(assemblyProbe&&assembly!=null&&(preparation==null||preparation.finished())){
                    long now=SystemClock.elapsedRealtime();
                    boolean currentPose=currentGuidancePose(now);
                    assembly.observe(received,now,evidence.valid()&&currentPose,evidence.near(assembly.target()));
                    assemblyStatus=" | "+evidence.reason()+" | HOLD "+assembly.holdMs()+"ms";
                    Log.i(TAG,"ASSEMBLY_EVIDENCE session="+token+" frame_ms="+received+" age_ms="+(now-received)+" target="+assembly.target()+" valid="+evidence.valid()+" current_pose="+currentPose+" reason="+evidence.reason()+" source="+evidence.tipSource()+" distances="+java.util.Arrays.toString(evidence.distances())+" phase="+assembly.phase()+" hold_ms="+assembly.holdMs());
                    renderAssembly();
                }
            }});
        }catch(Exception e){Log.e(TAG,"YOLO_FAILED",e);handler.post(()->{if(running&&token==session)stopCamera("도구 인식 오류");});}
        finally{yuv.release();rgba.release();toolBusy.set(false);}
    }

    @Override public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        boolean requested=pendingCameraPermission;pendingCameraPermission=false;
        if(code!=1)return;
        if(requested&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED&&!isFinishing())startCamera();
        else if(results.length==0||results[0]!=PackageManager.PERMISSION_GRANTED)report("카메라 권한이 필요해요");
        refreshControls();
    }
    @Override protected void onResume(){super.onResume();showDisplay();refreshControls();}
    @Override protected void onStop() { if(remoteSupervisor!=null)remoteSupervisor.close();if(supervisor!=null)supervisor.close();if(running||pendingCameraPermission)stopCamera("앱을 벗어나 안내를 종료했어요"); super.onStop(); }
    @Override protected void onDestroy() {
        if(remoteSupervisor!=null)remoteSupervisor.dispose();
        if(supervisor!=null)supervisor.close();
        // Drain the tracker first so it cannot enqueue inference after executor shutdown.
        worker.execute(()->{
            captureWorker.shutdown();
            if(tracker!=null)tracker.close();
            toolWorker.execute(()->{try{if(toolDetector!=null)toolDetector.close();if(toolEvidence!=null)toolEvidence.close();}catch(Exception e){Log.e(TAG,"YOLO_CLOSE_FAILED",e);}});
            toolWorker.shutdown();
        });worker.shutdown();
        dismissPresentation();
        if(sphereMarker!=null){sphereMarker.close();sphereMarker=null;}
        if (displays != null) displays.unregisterDisplayListener(this);
        super.onDestroy();
    }
    public void onDisplayAdded(int id) { showDisplay(); }
    public void onDisplayRemoved(int id) { showDisplay(); }
    public void onDisplayChanged(int id) { showDisplay(); }

}
