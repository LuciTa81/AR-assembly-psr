package com.lucita.beastgate;

import org.opencv.core.Point;
import java.util.Map;

/** Both window sizes use the same pose, residual and sensitivity gates. */
final class MultiWindowCornerTracker {
    private final LearnedCornerTracker longer,shorter;
    MultiWindowCornerTracker(WorkspaceTracker tracker) {
        longer=new LearnedCornerTracker(tracker,8);shorter=new LearnedCornerTracker(tracker,4);
    }
    void reset(){longer.reset();shorter.reset();}
    WorkspaceTracker.Result update(long now,Map<Integer,Point[]> real) {
        var a=longer.update(now,real);var b=shorter.update(now,real);
        return a.valid?a:b.valid?b:a;
    }
}
