using System;
using System.Collections;
using System.IO;
using UnityEngine;

namespace ARAssembly
{
    // Opt-in P1 harness: captures only this player's rendered UI, never the desktop/camera.
    public sealed class GuidanceCaptureProbe : MonoBehaviour
    {
        private string directory;
        private string lastStatus;
        private GuidanceReceiver receiver;
        private double nextSbsCapture;
        private int sbsCaptures;
        private const int MaxSbsCaptures = 72;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Install()
        {
            var args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "--capture-ui");
            if (index < 0 || index + 1 >= args.Length) return;
            var probe = new GameObject("P1 UI Capture").AddComponent<GuidanceCaptureProbe>();
            probe.directory = Path.GetFullPath(args[index + 1]);
            Directory.CreateDirectory(probe.directory);
            probe.receiver = FindFirstObjectByType<GuidanceReceiver>();
        }

        private void Update()
        {
            if (receiver == null) return;
            var args = Environment.GetCommandLineArgs();
            var stereo = receiver.GetComponent<StereoAlignmentProbe>();
            var sbs = receiver.GetComponent<SbsGuidancePresenter>();
            string status = StereoAlignmentState.Requested(args)
                ? (stereo == null ? "SBS_STARTING" : stereo.CaptureStatus)
                : ManualAlignmentState.Requested(args)
                ? receiver.GetComponent<GuidancePresenter>().ManualProbeStatus
                : sbs != null ? sbs.CaptureStatus : receiver.GetComponent<GuidancePresenter>().CaptureStatus;
            bool periodic = sbs != null && sbsCaptures < MaxSbsCaptures && Time.realtimeSinceStartupAsDouble >= nextSbsCapture;
            if (sbs != null && sbsCaptures >= MaxSbsCaptures) return;
            if (status == lastStatus && !periodic) return;
            if (sbs != null) { nextSbsCapture = Time.realtimeSinceStartupAsDouble + 1; sbsCaptures++; }
            lastStatus = status;
            StartCoroutine(Capture(status));
        }

        private IEnumerator Capture(string status)
        {
            yield return new WaitForEndOfFrame();
            var sbs = receiver.GetComponent<SbsGuidancePresenter>();
            if (sbs != null && sbs.CaptureStatus != status) yield break;
            string path = Path.Combine(directory, Time.frameCount + "-" + status + ".png");
            ScreenCapture.CaptureScreenshot(path);
            Debug.Log("[P1 UI CAPTURE] " + path);
        }
    }
}
