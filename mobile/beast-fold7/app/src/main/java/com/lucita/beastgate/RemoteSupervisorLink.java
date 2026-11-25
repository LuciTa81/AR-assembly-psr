package com.lucita.beastgate;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.ApplicationInfo;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.text.InputFilter;
import android.text.InputType;
import android.view.View;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import java.util.function.Supplier;

/** Separate opt-in UI. It never writes assembly state or controls the camera/LAN link. */
final class RemoteSupervisorLink {
    private final Activity activity;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Switch toggle;
    private final TextView status;
    private final RemoteSupervisorTransport transport;
    private final RemoteSupervisorSampler sampler;
    private final RemoteVideoEncoder videoEncoder;
    private volatile boolean cameraRunning;
    private final boolean debug;
    private AlertDialog dialog;
    private String endpoint = "";
    private int generation;
    private boolean changing, disposed;

    RemoteSupervisorLink(Activity activity, LinearLayout root, Supplier<String> state) {
        this.activity = activity;
        debug = (activity.getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        transport = new RemoteSupervisorTransport(RemoteSupervisorTransport.newClient(), new RemoteSupervisorCredentials(activity), debug);
        videoEncoder=new RemoteVideoEncoder(()->cameraRunning&&transport.canSendVideo(),transport::offerVideo,this::reportVideoError);
        sampler = new RemoteSupervisorSampler(state, transport::isReady, snapshot -> {
            if (snapshot == null) fail("상태를 읽지 못해 인터넷 관제를 종료했어요");
            else transport.offer(snapshot);
        });
        toggle = new Switch(activity); toggle.setText("인터넷 관제"); toggle.setTextColor(AssemblyScreen.INK); toggle.setTextSize(16);
        toggle.setMinHeight(dp(48)); root.addView(toggle, new LinearLayout.LayoutParams(-1, -2));
        status = new TextView(activity); status.setTextColor(AssemblyScreen.MUTED); status.setTextSize(15);
        status.setPadding(0, dp(8), 0, dp(8));
        status.setTextIsSelectable(true); status.setVisibility(View.GONE);
        root.addView(status, new LinearLayout.LayoutParams(-1, -2));
        toggle.setOnCheckedChangeListener((button, checked) -> {
            if (changing) return;
            if (checked) consent(); else close();
        });
        transport.loadEndpoint(saved -> main.post(() -> { if (!disposed && endpoint.isEmpty()) endpoint = saved; }));
    }

    private int dp(int value) { return (int) (value * activity.getResources().getDisplayMetrics().density); }
    private TextView label(String value) {
        TextView label = new TextView(activity); label.setText(value); label.setTextColor(Color.LTGRAY); label.setTextSize(16); return label;
    }
    private EditText field(LinearLayout form, String title, String value, int inputType) {
        TextView label = label(title); form.addView(label);
        EditText input = new EditText(activity); input.setId(View.generateViewId()); label.setLabelFor(input.getId());
        input.setInputType(inputType); input.setSingleLine(true); input.setText(value); input.setMinHeight(dp(48));
        form.addView(input, new LinearLayout.LayoutParams(-1, -2)); return input;
    }

    private void consent() {
        if (disposed || activity.isFinishing() || activity.isDestroyed()) { close(); return; }
        int token = ++generation;
        LinearLayout form = new LinearLayout(activity); form.setOrientation(LinearLayout.VERTICAL); form.setPadding(dp(24), dp(12), dp(24), dp(8));
        EditText url = field(form, "중계 서버 주소", endpoint, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        url.setHint("https://relay.example"); url.setFilters(new InputFilter[]{new InputFilter.LengthFilter(2048)});
        EditText name = field(form, "기기 이름", "Fold7", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(64)});
        CheckBox consent = new CheckBox(activity);
        consent.setText("이 서버에 작업 단계·추적 상태·진단 수치를 전송하는 데 동의합니다. 영상은 아래 항목을 선택한 경우에만 전송합니다.");
        consent.setTextColor(Color.LTGRAY); consent.setMinHeight(dp(48)); form.addView(consent);
        CheckBox videoConsent=new CheckBox(activity);
        videoConsent.setText("작업대 실시간 영상도 공유합니다. 이 서버를 거쳐 본인 관제에 표시됩니다. 음성은 전송하지 않습니다.");
        videoConsent.setTextColor(AssemblyScreen.INK);videoConsent.setMinHeight(dp(48));form.addView(videoConsent);
        CheckBox recordingConsent=new CheckBox(activity);
        recordingConsent.setText("공유한 작업 영상을 서버에 저장하는 데 동의합니다. 본인 관제에서 다운로드할 수 있으며 7일 후 삭제됩니다.");
        recordingConsent.setTextColor(AssemblyScreen.INK);recordingConsent.setMinHeight(dp(48));recordingConsent.setEnabled(false);form.addView(recordingConsent);
        videoConsent.setOnCheckedChangeListener((button,checked)->{recordingConsent.setEnabled(checked);if(!checked)recordingConsent.setChecked(false);});
        ScrollView scroll = new ScrollView(activity); scroll.addView(form);
        dialog = new AlertDialog.Builder(activity).setTitle("인터넷 관제 연결").setView(scroll)
                .setPositiveButton("연결", null).setNegativeButton("취소", (d, which) -> close())
                .setOnCancelListener(d -> close()).create();
        AlertDialog shown = dialog; shown.show();
        shown.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
        consent.setOnCheckedChangeListener((button, checked) -> shown.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(checked));
        shown.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            if (token != generation || disposed || !toggle.isChecked() || !consent.isChecked()) return;
            String destination;
            try { destination = RemoteSupervisorPolicy.endpoint(url.getText().toString(), debug); }
            catch (IllegalArgumentException invalid) { url.setError(debug ? "HTTPS 서버 주소만 입력해 주세요. 개발용 HTTP는 localhost/127.0.0.1만 허용합니다" : "경로·계정·쿼리가 없는 HTTPS 서버 주소를 입력해 주세요"); return; }
            String deviceName;
            try { deviceName = RemoteSupervisorPolicy.name(name.getText().toString()); }
            catch (IllegalArgumentException invalid) { name.setError("기기 이름을 1~64자로 입력해 주세요"); return; }
            endpoint = destination; shown.dismiss(); dialog = null;
            status.setText("연결 준비 중"); status.setVisibility(View.VISIBLE);
            transport.start(destination, deviceName, (event, code, expiry) -> main.post(() -> {
                if (token != generation || disposed || !toggle.isChecked() || activity.isDestroyed()) return;
                switch (event) {
                    case PAIRING: status.setText("연결 코드 요청 중"); break;
                    case CODE:
                        status.setText("연결 코드  " + code + "\n승인 대기 · " + android.text.format.DateFormat.format("HH:mm", expiry) + " 만료"); break;
                    case CONNECTING: status.setText("인터넷 관제 연결 중"); break;
                    case CONNECTED:
                        status.setText(recordingConsent.isChecked()?(transport.recordingAvailable()?"인터넷 관제 연결됨 · 영상 공유·저장 동의":"인터넷 관제 연결됨 · 영상 공유 · 서버 저장 꺼짐"):videoConsent.isChecked()?"인터넷 관제 연결됨 · 영상 공유 허용":"인터넷 관제 연결됨 · 상태 공유"); break;
                    case RETRYING: status.setText(code.isEmpty() ? "인터넷 관제 재연결 대기" : "연결 코드  " + code + "\n승인 확인 재시도 중"); break;
                    case PAIR_REQUIRED: fail("승인이 만료되었거나 해제됐어요. 인터넷 관제를 다시 켜 새 코드를 요청해 주세요"); break;
                    case ERROR: fail("인터넷 관제를 연결하지 못했어요. 서버 주소·인증서·보안 저장소를 확인해 주세요"); break;
                }
            }));
            transport.setVideoEnabled(videoConsent.isChecked());
            transport.setRecordingEnabled(recordingConsent.isChecked());
            sampler.start();
        });
    }

    private void fail(String message) { close(); Toast.makeText(activity, message, Toast.LENGTH_LONG).show(); }
    void close() {
        videoEncoder.clear();
        ++generation; sampler.close(); transport.close();
        if (dialog != null) { dialog.dismiss(); dialog = null; }
        changing = true; toggle.setChecked(false); changing = false;
        status.setVisibility(View.GONE);
    }
    void dispose() {
        if (disposed) return;
        close(); disposed = true; main.removeCallbacksAndMessages(null); videoEncoder.close();transport.dispose();
    }
    void cameraRunning(boolean value){cameraRunning=value;if(!value)videoEncoder.clear();}
    void offerFrame(byte[] nv21,long captured){videoEncoder.offer(nv21,captured);}
    boolean wantsFrame(long captured){return videoEncoder.wantsFrame(captured);}
    private void reportVideoError(String message){main.post(()->{if(!disposed&&toggle.isChecked())status.setText(message);});}
}
