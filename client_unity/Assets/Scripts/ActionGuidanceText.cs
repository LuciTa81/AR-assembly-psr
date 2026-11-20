namespace ARAssembly
{
    public enum ActionGuidanceTone { Attention, Approach, Working, Release, Complete }

    // Display-only copy. Stage decisions, retention and the green-cue delay remain upstream.
    public struct ActionGuidanceText
    {
        public string Title, Action;
        public bool NeedsAttention;
        public ActionGuidanceTone Tone;
        public bool Retained;

        public static ActionGuidanceText From(GuidancePresentation view, GuidanceSnapshot frame,
            string positionHint = null)
        {
            string step = frame?.current_state;
            int index = step != null && step.Length == 2 && step[0] == 'S' ? step[1] - '0' : -1;
            bool screw = index >= 2 && index <= 5;
            string letter = screw ? "ABCD"[index - 2].ToString() : "";
            var result = new ActionGuidanceText {
                Title = screw ? "나사 " + letter + " · " + (index - 1) + "/4"
                    : index == 0 ? "상자 배치" : index == 1 ? "뚜껑 닫기"
                    : index == 6 ? "최종 확인" : "조립 안내",
                Action = "멈추고 관제 화면을 확인해주세요", NeedsAttention = true
            };
            switch (view.Status) {
                case "WAITING": result.Action = "작업대를 바라봐주세요"; return result;
                case "DISCONNECTED": result.Action = "멈추고 연결을 확인해주세요"; return result;
                case "DISPLAY_CHANGED": result.Action = "화면 설정을 확인해주세요"; return result;
                case "NOT_CALIBRATED": result.Action = "관제에서 위치 보정을 확인해주세요"; return result;
                case "TRACKING_LOST": case "NO_POSE":
                    result.Action = "작업대가 보이도록 바라봐주세요"; return result;
                case "STALE": case "STALE_POSE":
                    result.Action = "잠시 멈추고 작업대를 봐주세요"; return result;
                case "COMPLETED":
                    if (index == 6) {
                        result.Title = "조립 안내";
                        result.Action = "조립 안내를 마쳤습니다";
                        result.NeedsAttention = false;
                        result.Tone = ActionGuidanceTone.Complete;
                    }
                    return result;
                case "AWAITING_CONFIRMATION":
                    if (index == 6) { result.Action = "조립 상태를 확인해주세요"; result.NeedsAttention = false; }
                    return result;
                case "LIVE": case "GUIDING": case "OBSERVING": case "OBSERVED": case "PAUSED":
                    break;
                default: return result;
            }
            if (index < 0 || index > 6) return result;
            if (screw && positionHint != null) {
                result.Action = positionHint == "Return to the tested working distance"
                    ? "원래 작업 거리로 돌아와주세요"
                    : positionHint == "Display changed. Position guide paused" ? "화면 설정을 확인해주세요"
                    : positionHint == "Profile unavailable. Position guide paused" ? "관제에서 위치 보정을 확인해주세요"
                    : "잠시 멈추고 작업대를 봐주세요";
                return result;
            }
            if (view.Status == "PAUSED") {
                result.Action = "잠시 멈추고 작업대를 봐주세요";
                if (view.Instruction == "Checking input. Guidance paused.") return result;
                switch (frame?.guidance?.reason) {
                    case "tool_not_visible": case "tool_position_unknown":
                        result.Action = "드라이버가 보이도록 해주세요"; break;
                    case "multiple_tool_candidates": result.Action = "드라이버 하나만 보여주세요"; break;
                    case "marker_not_stable": result.Action = "작업대가 보이도록 바라봐주세요"; break;
                }
                return result;
            }
            result.Action = index == 0 ? "상자를 놓아주세요" : index == 1 ? "뚜껑을 덮어주세요"
                : index == 6 ? "조립 상태를 확인해주세요"
                : view.HoldProgress == "recheck" || view.Status == "GUIDING" || view.Status == "LIVE"
                    ? "드라이버 끝을 나사 " + letter + "에 맞춰주세요"
                : view.Status == "OBSERVED" ? "드라이버를 떼어주세요" : "나사 " + letter + "를 조여주세요";
            result.Tone = screw && view.HoldProgress != "recheck" && view.Status == "OBSERVED"
                ? ActionGuidanceTone.Release
                : screw && view.HoldProgress != "recheck" && view.Status == "OBSERVING"
                    ? ActionGuidanceTone.Working : ActionGuidanceTone.Approach;
            result.NeedsAttention = false;
            return result;
        }
    }

    public sealed class ActionGuidanceDisplay
    {
        private string context;
        private double lastTime = -1, lastUsableAt = -1;
        private ActionGuidanceText? lastAction;

        public ActionGuidanceText Apply(GuidancePresentation view, GuidanceSnapshot frame,
            string gate, string hint, double now)
        {
            var current = ActionGuidanceText.From(view, frame, hint);
            string scope = frame?.session_id + "|" + frame?.current_state + "|" + frame?.target;
            bool clockValid = !double.IsNaN(now) && !double.IsInfinity(now) && now >= 0 && now >= lastTime;
            if (context != scope || !clockValid) lastAction = null;
            context = scope;
            lastTime = clockValid ? now : -1;
            if (!clockValid) return current;

            bool retainableStage = frame?.current_state != null && frame.current_state.Length == 2
                && frame.current_state[0] == 'S' && frame.current_state[1] >= '0' && frame.current_state[1] <= '5'
                && !string.IsNullOrEmpty(frame.session_id);
            if (!current.NeedsAttention) {
                lastAction = retainableStage ? current : (ActionGuidanceText?)null;
                lastUsableAt = now;
                return current;
            }
            bool softState = view.Status == "PAUSED" || view.Status == "TRACKING_LOST" || view.Status == "STALE"
                || view.Status == "NO_POSE" || view.Status == "STALE_POSE" || view.Status == "WAITING"
                || view.Status == "LIVE" || view.Status == "GUIDING" || view.Status == "OBSERVING" || view.Status == "OBSERVED";
            bool softGate = gate == null || gate == "VISIBLE" || gate == "STATE WAITING"
                || gate == "STATE TRACKING_LOST" || gate == "STATE STALE" || gate == "POSE WAITING"
                || gate == "POSE STALE" || gate == "POSE NO POSE" || gate == "WAITING"
                || gate == "STAGE TARGET UNAVAILABLE"
                || gate == "NO STAGE TARGET" && (frame?.current_state == "S0" || frame?.current_state == "S1");
            // Only the display survives this brief gap. No progress, pose or green delay is advanced here.
            if (retainableStage && softState && softGate && view.HoldProgress != "recheck"
                && frame.guidance?.reason != "multiple_tool_candidates"
                && lastAction.HasValue && now - lastUsableAt < .75) {
                var retained = lastAction.Value;
                retained.Retained = true;
                return retained;
            }
            lastAction = null;
            return current;
        }
    }
}
