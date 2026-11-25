package com.lucita.beastgate;

import org.junit.Test;
import static org.junit.Assert.*;

public class SessionLimitsTest {
    @Test public void standaloneSurvivesFiveMinutesAndEndsAtTen() {
        assertFalse(SessionLimits.expired(300_000L, true, true, true));
        assertFalse(SessionLimits.expired(599_999L, true, true, true));
        assertTrue(SessionLimits.expired(600_000L, true, true, true));
        assertTrue(SessionLimits.expired(600_001L, true, true, true));
    }
    @Test public void diagnosticDurationsStayUnchanged() {
        assertEquals(300_000L, SessionLimits.limitMs(false, true, true));
        assertEquals(90_000L, SessionLimits.limitMs(false, false, true));
        assertEquals(30_000L, SessionLimits.limitMs(false, false, false));
    }
}
