package com.lucita.beastgate;

import java.util.Locale;

/** Phone presentation only. Never used to advance assembly or place overlays. */
final class AssemblyUiState {
    private static final String[] TITLES={"상자 배치","뚜껑 닫기","나사 A","나사 B","나사 C","나사 D","최종 검사"};
    static String title(int stage){return stage>=0&&stage<TITLES.length?TITLES[stage]:"작업 준비";}
    static String phase(String phase){
        return switch(phase){
            case "APPROACH" -> "위치 맞추기";
            case "WORKING" -> "조이는 중";
            case "RELEASE" -> "다음 작업 준비";
            case "INSPECTION" -> "최종 검사";
            case "PREPARATION" -> "준비 단계";
            default -> "안내 대기";
        };
    }
    static boolean wide(int widthDp){return widthDp>=600;}
    static String elapsed(long millis){long seconds=Math.max(0,millis)/1000;return String.format(Locale.ROOT,"%02d:%02d",seconds/60,seconds%60);}
    static String message(String raw){
        if(raw.equals("도구 인식 준비 중")||raw.equals("인식 준비 완료"))return "";
        int suffix=raw.indexOf(" | frames=");return suffix<0?raw:raw.substring(0,suffix);
    }
}
