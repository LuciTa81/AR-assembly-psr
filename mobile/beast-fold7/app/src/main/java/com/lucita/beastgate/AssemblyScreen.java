package com.lucita.beastgate;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONObject;

/** Phone-only shell: owns views, not camera, networking or assembly lifecycle. */
final class AssemblyScreen extends LinearLayout {
    static final int BG=0xff151a19, SURFACE=0xff202725, LINE=0xff35413d;
    static final int INK=0xffeff4f1, MUTED=0xffa9b6b0, MINT=0xff79d6bb;
    final Button start,stop;
    final ImageButton refresh;
    final TextView taskStatus,status,displayStatus,trackingStatus;
    final AnalysisView preview;
    final LinearLayout remoteHost,localHost;
    private final TextView eyebrow,instruction,phase,time,tracking,notice,deviceState,previewState;
    private final ScrollView workPage,connectionPage;
    private final LinearLayout workContent,taskColumn,cameraColumn,emptyPreview,diagnostics;
    private final FrameLayout previewFrame;
    private final TextView[] steps=new TextView[7];
    private final View[] bars=new View[7],tabLines=new View[2];
    private final Button[] tabs=new Button[2];
    private int lastWidth=-1;
    private boolean wide;

    AssemblyScreen(Context context){
        super(context);setOrientation(VERTICAL);setBackgroundColor(BG);
        LinearLayout header=row();pad(header,20,12,12,10);
        ImageView brand=new ImageView(context);brand.setImageResource(R.drawable.ic_box);brand.setColorFilter(MINT);
        header.addView(brand,new LayoutParams(dp(30),dp(30)));
        TextView name=text("AR Assembly",21,INK,true);name.setPadding(dp(10),0,0,0);
        header.addView(name,new LayoutParams(0,-2,1));
        refresh=icon(R.drawable.ic_refreshcw,"연결 확인");header.addView(refresh,new LayoutParams(dp(48),dp(48)));addView(header);
        LinearLayout navigation=row();pad(navigation,20,0,20,0);
        for(int i=0;i<2;i++){
            LinearLayout item=column();tabs[i]=button(i==0?"작업":"연결",i==0?R.drawable.ic_box:R.drawable.ic_settings2,false);
            tabs[i].setCompoundDrawablesRelative(null,null,null,null);
            tabs[i].setBackground(new RippleDrawable(ColorStateList.valueOf(0x2279d6bb),null,null));
            final int page=i;tabs[i].setOnClickListener(v->selectPage(page));
            item.addView(tabs[i],new LayoutParams(-1,dp(48)));tabLines[i]=new View(context);
            item.addView(tabLines[i],new LayoutParams(-1,dp(2)));navigation.addView(item,new LayoutParams(0,-2,1));
        }
        addView(navigation);addView(rule(),new LayoutParams(-1,dp(1)));
        FrameLayout pages=new FrameLayout(context);addView(pages,new LayoutParams(-1,0,1));
        workPage=scroll();connectionPage=scroll();pages.addView(workPage);pages.addView(connectionPage);
        workContent=column();pad(workContent,20,24,20,20);workPage.addView(workContent);
        taskColumn=column();cameraColumn=column();workContent.addView(taskColumn);workContent.addView(cameraColumn);
        LinearLayout meta=row();eyebrow=text("시작 전",13,MUTED,true);time=text("00:00",14,MUTED,false);
        time.setTypeface(Typeface.MONOSPACE);meta.addView(eyebrow,new LayoutParams(0,-2,1));meta.addView(time);taskColumn.addView(meta);
        taskStatus=text("작업 준비",30,INK,true);pad(taskStatus,0,12,0,6);taskColumn.addView(taskStatus);
        instruction=text("Beast를 연결해주세요",21,INK,false);instruction.setLineSpacing(dp(3),1);pad(instruction,0,0,0,16);
        taskColumn.addView(instruction);phase=text("안내 대기",14,MUTED,true);taskColumn.addView(phase);
        LinearLayout rail=row();pad(rail,0,22,0,14);
        String[] labels={"상자","뚜껑","A","B","C","D","검사"};
        for(int i=0;i<7;i++){
            LinearLayout cell=column();if(i>0)cell.setPadding(dp(4),0,0,0);
            bars[i]=new View(context);bars[i].setBackgroundColor(LINE);cell.addView(bars[i],new LayoutParams(-1,dp(3)));
            steps[i]=text(labels[i],11,MUTED,false);steps[i].setGravity(Gravity.CENTER);steps[i].setPadding(0,dp(8),0,0);
            cell.addView(steps[i]);rail.addView(cell,new LayoutParams(0,-2,1));
        }
        rail.setContentDescription("작업 순서: 상자, 뚜껑, 나사 A, B, C, D, 최종 검사");taskColumn.addView(rail);
        tracking=text("추적 대기",13,MUTED,false);pad(tracking,0,0,0,12);taskColumn.addView(tracking);
        notice=text("",14,MUTED,false);notice.setVisibility(GONE);pad(notice,0,4,0,16);taskColumn.addView(notice);
        LinearLayout cameraHeader=row();pad(cameraHeader,0,0,0,10);
        TextView cameraTitle=text("작업대",15,INK,true);previewState=text("카메라 꺼짐",12,MUTED,false);
        cameraHeader.addView(cameraTitle,new LayoutParams(0,-2,1));cameraHeader.addView(previewState);cameraColumn.addView(cameraHeader);
        previewFrame=new FrameLayout(context){
            @Override protected void onMeasure(int w,int h){
                int width=MeasureSpec.getSize(w);super.onMeasure(w,MeasureSpec.makeMeasureSpec(Math.max(dp(120),width*9/16),MeasureSpec.EXACTLY));
            }
        };
        previewFrame.setBackground(shape(SURFACE,LINE,8));previewFrame.setClipToOutline(true);
        preview=new AnalysisView(context);previewFrame.addView(preview,new FrameLayout.LayoutParams(-1,-1));
        emptyPreview=column();emptyPreview.setGravity(Gravity.CENTER);
        ImageView cameraIcon=new ImageView(context);cameraIcon.setImageResource(R.drawable.ic_camera);cameraIcon.setColorFilter(MUTED);
        emptyPreview.addView(cameraIcon,new LayoutParams(dp(32),dp(32)));
        TextView emptyLabel=text("카메라 대기",14,MUTED,false);emptyLabel.setGravity(Gravity.CENTER_HORIZONTAL);pad(emptyLabel,0,12,0,0);emptyPreview.addView(emptyLabel);
        previewFrame.addView(emptyPreview,new FrameLayout.LayoutParams(-1,-1));cameraColumn.addView(previewFrame);
        TextView source=text("카메라 시점",12,MUTED,false);pad(source,0,8,0,0);cameraColumn.addView(source);

        LinearLayout settings=column();pad(settings,20,24,20,24);connectionPage.addView(settings);
        settings.addView(text("연결 관리",25,INK,true));deviceState=text("안경 미연결",14,MUTED,true);pad(deviceState,0,8,0,24);settings.addView(deviceState);
        section(settings,"VITURE Beast",R.drawable.ic_glasses);
        displayStatus=text("외부 화면 확인 중",15,INK,false);pad(displayStatus,0,12,0,8);settings.addView(displayStatus);
        TextView mode=text("Full SBS · 0DoF\nExtra Large · 4.5m",14,MUTED,false);mode.setLineSpacing(dp(3),1);settings.addView(mode);
        separator(settings);section(settings,"원격 관제",R.drawable.ic_radio);
        remoteHost=column();pad(remoteHost,0,8,0,0);settings.addView(remoteHost);
        separator(settings);
        Button diagnosticButton=button("진단 및 로컬 연결",R.drawable.ic_chevronright,false);
        diagnosticButton.setGravity(Gravity.CENTER_VERTICAL|Gravity.START);settings.addView(diagnosticButton,new LayoutParams(-1,-2));
        diagnostics=column();diagnostics.setVisibility(GONE);settings.addView(diagnostics);
        diagnosticButton.setOnClickListener(v->{boolean open=diagnostics.getVisibility()!=VISIBLE;diagnostics.setVisibility(open?VISIBLE:GONE);diagnosticButton.setText(open?"진단 및 로컬 연결 닫기":"진단 및 로컬 연결");});
        status=text("카메라 대기",14,MUTED,false);trackingStatus=text("추적 대기",14,MUTED,false);
        pad(status,0,12,0,8);diagnostics.addView(status);diagnostics.addView(trackingStatus);
        localHost=row();pad(localHost,0,16,0,0);diagnostics.addView(localHost);
        separator(settings);TextView privacy=text("영상·음성 저장 안 함",13,MUTED,false);settings.addView(privacy);
        TextView limit=text("작업 세션 최대 "+(SessionLimits.WORK_MS/60000)+"분",13,MUTED,false);pad(limit,0,8,0,0);settings.addView(limit);
        addView(rule(),new LayoutParams(-1,dp(1)));
        LinearLayout controls=row();pad(controls,20,12,20,12);controls.setBackgroundColor(BG);
        start=button("작업 시작",R.drawable.ic_play,true);stop=button("작업 종료",R.drawable.ic_square,false);stop.setEnabled(false);
        LayoutParams primary=new LayoutParams(0,-2,1);primary.setMarginEnd(dp(10));controls.addView(start,primary);controls.addView(stop,new LayoutParams(0,-2,1));
        addView(controls);selectPage(0);
    }

    void present(JSONObject state,boolean ready,boolean hasRun){
        boolean running=state.optBoolean("running");int stage=state.optInt("stage",-1);
        boolean visible=state.optBoolean("overlay_visible");String currentPhase=state.optString("phase");
        int tone=!running||!visible?MUTED:"WORKING".equals(currentPhase)?0xff83bfff:"APPROACH".equals(currentPhase)?0xffefb464:MINT;
        taskStatus.setText(running?AssemblyUiState.title(stage):hasRun?"다음 작업 준비":"작업 준비");
        eyebrow.setText(running?String.format(java.util.Locale.ROOT,"진행 중   %02d / 07",stage+1):ready?"시작 가능":"시작 전");
        eyebrow.setTextColor(running?MINT:MUTED);time.setText(AssemblyUiState.elapsed(state.optLong("elapsed_ms")));
        if(running)instruction.setText(state.optString("action"));
        phase.setText(running?(visible?AssemblyUiState.phase(currentPhase):"작업대 확인 필요"):"안내 대기");phase.setTextColor(tone);
        for(int i=0;i<7;i++){
            bars[i].setBackgroundColor(running&&i<=stage?(i==stage?tone:0xff48766a):LINE);
            steps[i].setTextColor(running&&i==stage?INK:MUTED);
        }
        tracking.setText(running?(state.optBoolean("tracked")?"마커 "+state.optInt("markers")+"개 · 추적 중":"마커 추적 대기"):"안경 연결 후 시작할 수 있어요");
        if(!running&&ready)tracking.setText("안경 연결됨");
        deviceState.setText(ready||running?"안경 연결됨":"연결 확인 필요");deviceState.setTextColor(ready||running?MINT:MUTED);
        emptyPreview.setVisibility(running?GONE:VISIBLE);preview.setVisibility(running?VISIBLE:INVISIBLE);
        previewState.setText(running?"실시간":"카메라 꺼짐");previewState.setTextColor(running?MINT:MUTED);
        if(running)notice.setVisibility(GONE);
    }

    void idleInstruction(String value){instruction.setText(value);}
    void showNotice(String value){String message=AssemblyUiState.message(value);notice.setText(message);notice.setVisibility(message.isEmpty()?GONE:VISIBLE);}

    void selectPage(int page){
        workPage.setVisibility(page==0?VISIBLE:GONE);connectionPage.setVisibility(page==1?VISIBLE:GONE);
        for(int i=0;i<2;i++){tabs[i].setSelected(i==page);tabs[i].setTextColor(i==page?INK:MUTED);tabLines[i].setBackgroundColor(i==page?MINT:Color.TRANSPARENT);}
    }
    @Override protected void onMeasure(int width,int height){
        int available=MeasureSpec.getSize(width),dpWidth=(int)(available/getResources().getDisplayMetrics().density);
        if(available!=lastWidth){
            lastWidth=available;wide=AssemblyUiState.wide(dpWidth);workContent.setOrientation(wide?HORIZONTAL:VERTICAL);
            LayoutParams task=(LayoutParams)taskColumn.getLayoutParams();
            task.width=wide?0:-1;task.height=-2;task.weight=wide?1:0;taskColumn.setLayoutParams(task);
            LayoutParams camera=(LayoutParams)cameraColumn.getLayoutParams();
            camera.width=wide?0:-1;camera.height=-2;camera.weight=wide?1:0;
            camera.leftMargin=wide?dp(24):0;camera.topMargin=wide?0:dp(12);cameraColumn.setLayoutParams(camera);
        }
        super.onMeasure(width,height);
    }

    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private LinearLayout column(){LinearLayout v=new LinearLayout(getContext());v.setOrientation(VERTICAL);return v;}
    private LinearLayout row(){LinearLayout v=new LinearLayout(getContext());v.setOrientation(HORIZONTAL);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    private ScrollView scroll(){ScrollView v=new ScrollView(getContext());v.setFillViewport(true);v.setClipToPadding(false);return v;}
    private void pad(View v,int l,int t,int r,int b){v.setPadding(dp(l),dp(t),dp(r),dp(b));}
    private TextView text(String value,int sp,int color,boolean bold){
        TextView v=new TextView(getContext());v.setText(value);v.setTextColor(color);v.setTextSize(sp);v.setLetterSpacing(0);
        v.setTypeface(Typeface.create(bold?"sans-serif-medium":"sans-serif",Typeface.NORMAL));v.setIncludeFontPadding(false);
        v.setBreakStrategy(android.graphics.text.LineBreaker.BREAK_STRATEGY_HIGH_QUALITY);return v;
    }
    private GradientDrawable shape(int fill,int border,int radius){
        GradientDrawable d=new GradientDrawable();d.setColor(fill);d.setCornerRadius(dp(radius));if(border!=0)d.setStroke(dp(1),border);return d;
    }
    private View rule(){View v=new View(getContext());v.setBackgroundColor(LINE);return v;}
    private void separator(LinearLayout parent){LayoutParams p=new LayoutParams(-1,dp(1));p.topMargin=dp(24);p.bottomMargin=dp(20);parent.addView(rule(),p);}
    private void section(LinearLayout parent,String title,int icon){
        TextView v=text(title,16,INK,true);var image=getContext().getDrawable(icon).mutate();image.setTint(MUTED);image.setBounds(0,0,dp(20),dp(20));
        v.setCompoundDrawablesRelative(image,null,null,null);v.setCompoundDrawablePadding(dp(10));parent.addView(v);
    }
    private Button button(String title,int icon,boolean primary){
        Button v=new Button(getContext());v.setText(title);v.setAllCaps(false);v.setLetterSpacing(0);v.setTextSize(15);v.setMinHeight(dp(56));
        v.setMinimumWidth(0);v.setMinWidth(0);pad(v,12,12,12,12);v.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));v.setMaxLines(2);
        int[][] states={{-android.R.attr.state_enabled},{}};
        v.setTextColor(new ColorStateList(states,new int[]{0xff7c8a84,primary?BG:INK}));
        var background=shape(primary?MINT:SURFACE,primary?0:LINE,8);
        background.setColor(new ColorStateList(states,new int[]{SURFACE,primary?MINT:SURFACE}));
        v.setBackground(new RippleDrawable(ColorStateList.valueOf(0x3379d6bb),background,null));v.setStateListAnimator(null);
        var image=getContext().getDrawable(icon).mutate();image.setTintList(new ColorStateList(states,new int[]{0xff7c8a84,primary?BG:MUTED}));
        image.setBounds(0,0,dp(18),dp(18));v.setCompoundDrawablesRelative(image,null,null,null);v.setCompoundDrawablePadding(dp(8));return v;
    }
    private ImageButton icon(int resource,String description){
        ImageButton v=new ImageButton(getContext());v.setImageResource(resource);v.setColorFilter(MUTED);v.setContentDescription(description);v.setTooltipText(description);
        v.setBackground(new RippleDrawable(ColorStateList.valueOf(0x3379d6bb),shape(BG,0,8),null));pad(v,12,12,12,12);return v;
    }
}
