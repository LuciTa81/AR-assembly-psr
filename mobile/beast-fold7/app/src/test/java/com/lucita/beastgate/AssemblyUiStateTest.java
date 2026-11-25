package com.lucita.beastgate;

import org.junit.Test;
import static org.junit.Assert.*;

public class AssemblyUiStateTest {
    @Test public void titlesNeverInventACompletedTask() {
        assertEquals("작업 준비", AssemblyUiState.title(-1));
        assertEquals("상자 배치", AssemblyUiState.title(0));
        assertEquals("나사 A", AssemblyUiState.title(2));
        assertEquals("최종 검사", AssemblyUiState.title(6));
        assertEquals("작업 준비", AssemblyUiState.title(99));
    }
    @Test public void phaseNamesDescribeCurrentAction() {
        assertEquals("위치 맞추기", AssemblyUiState.phase("APPROACH"));
        assertEquals("조이는 중", AssemblyUiState.phase("WORKING"));
        assertEquals("다음 작업 준비", AssemblyUiState.phase("RELEASE"));
        assertEquals("안내 대기", AssemblyUiState.phase("unknown"));
    }
    @Test public void layoutSwitchesAtFoldWidthAndElapsedIsBounded() {
        assertFalse(AssemblyUiState.wide(360));assertFalse(AssemblyUiState.wide(599));
        assertTrue(AssemblyUiState.wide(600));assertTrue(AssemblyUiState.wide(690));
        assertEquals("00:00", AssemblyUiState.elapsed(-100));
        assertEquals("02:05", AssemblyUiState.elapsed(125000));
    }
    @Test public void onlyDiagnosticFrameSuffixIsRemoved() {
        assertEquals("USB 연결 종료", AssemblyUiState.message("USB 연결 종료 | frames=123"));
        assertEquals("카메라 권한 확인 중", AssemblyUiState.message("카메라 권한 확인 중"));
    }
    @Test public void routineLoadingMessagesStayInDiagnosticsButFailuresRemainVisible() {
        assertEquals("", AssemblyUiState.message("도구 인식 준비 중"));
        assertEquals("", AssemblyUiState.message("인식 준비 완료"));
        assertEquals("도구 인식 로딩 실패", AssemblyUiState.message("도구 인식 로딩 실패"));
        assertEquals("작업을 종료했어요", AssemblyUiState.message("작업을 종료했어요 | frames=10"));
    }
}
