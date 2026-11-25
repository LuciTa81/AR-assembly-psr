package com.lucita.beastgate;

import org.junit.Test;
import static org.junit.Assert.*;

public class PartPreviewTest {
    @Test public void partFollowsPreparationScrewsInspectionAndIdle(){
        assertEquals(0,PartPreviewView.selectPart(0,0));
        assertEquals(1,PartPreviewView.selectPart(1,0));
        for(int target=0;target<4;target++)assertEquals(2,PartPreviewView.selectPart(2,target));
        assertEquals(3,PartPreviewView.selectPart(2,4));
        assertEquals(4,PartPreviewView.selectPart(-1,-1));
    }
}
