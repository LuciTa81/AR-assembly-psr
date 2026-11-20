using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace ARAssembly
{
    public sealed class DisplayBootstrap : MonoBehaviour
    {
        public bool Ready { get; private set; }
        private IEnumerator Start()
        {
            Application.runInBackground = true;
            Application.targetFrameRate = 60;
            QualitySettings.vSyncCount = 1;
            var displays = new List<DisplayInfo>();
            Screen.GetDisplayLayout(displays);
            foreach (var display in displays)
                Debug.Log("[DISPLAY] available=" + display.name + " "
                    + display.width + "x" + display.height);

            string requested = Argument("--display-name");
            SbsGuidanceOptions options;
            try { options = SbsGuidanceOptions.Parse(Environment.GetCommandLineArgs()); }
            catch (ArgumentException exc) {
                Debug.LogError("[DISPLAY] " + exc.Message);
                Application.Quit(2);
                yield break;
            }
            if (options.PreviewPath != null)
            {
                var laptop = displays.FindAll(d => d.name.IndexOf("VITURE", StringComparison.OrdinalIgnoreCase) < 0);
                if (laptop.Count == 0) {
                    Debug.LogError("[DISPLAY] Synthetic preview requires a non-VITURE display.");
                    Application.Quit(2);
                    yield break;
                }
                Screen.SetResolution(1536, 432, FullScreenMode.Windowed);
                yield return null;
                yield return Screen.MoveMainWindowTo(laptop[0], new Vector2Int(40, 40));
                double deadline = Time.realtimeSinceStartupAsDouble + 5;
                while (Time.realtimeSinceStartupAsDouble < deadline
                    && (Screen.width != 1536 || Screen.height != 432 || Screen.fullScreenMode != FullScreenMode.Windowed))
                    yield return null;
                if (Screen.width != 1536 || Screen.height != 432 || Screen.fullScreenMode != FullScreenMode.Windowed
                    || Screen.mainWindowDisplayInfo.name != laptop[0].name) {
                    Debug.LogError("[DISPLAY] Laptop preview output was not applied.");
                    Application.Quit(2);
                    yield break;
                }
            }
            if (requested != null)
            {
                var matches = displays.FindAll(d => d.name.IndexOf(requested,
                    StringComparison.OrdinalIgnoreCase) >= 0);
                if (matches.Count != 1)
                {
                    Debug.LogError("[DISPLAY] Expected one matching display; found " + matches.Count);
                    Application.Quit(2);
                    yield break;
                }
                if (options.Enabled && (matches[0].width != 3840 || matches[0].height != 1080)) {
                    Debug.LogError("[DISPLAY] SBS guidance requires native 3840x1080 output.");
                    Application.Quit(2);
                    yield break;
                }
                Screen.SetResolution(1280, 720, FullScreenMode.Windowed);
                yield return null;
                yield return Screen.MoveMainWindowTo(matches[0], Vector2Int.zero);
                Screen.SetResolution(matches[0].width, matches[0].height, FullScreenMode.FullScreenWindow);
                double deadline = Time.realtimeSinceStartupAsDouble + 5;
                while (Time.realtimeSinceStartupAsDouble < deadline &&
                    (Screen.width != matches[0].width || Screen.height != matches[0].height
                     || Screen.fullScreenMode != FullScreenMode.FullScreenWindow))
                    yield return null;
                if (Screen.width != matches[0].width || Screen.height != matches[0].height
                    || Screen.fullScreenMode != FullScreenMode.FullScreenWindow
                    || Screen.mainWindowDisplayInfo.name != matches[0].name)
                {
                    Debug.LogError("[DISPLAY] Requested display mode was not applied.");
                    Application.Quit(2);
                    yield break;
                }
            }
            Debug.Log("[DISPLAY] selected=" + Screen.mainWindowDisplayInfo.name
                + " render=" + Screen.width + "x" + Screen.height
                + " mode=" + Screen.fullScreenMode + " unity_dpi=" + Screen.dpi
                + " native_tracking_mode=UNVERIFIED calibration=NONE");
            Ready = true;
        }

        private static string Argument(string name)
        {
            string[] args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, name);
            return index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
        }
    }
}
