using System;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace ARAssembly
{
    [RequireComponent(typeof(GuidanceReceiver))]
    public sealed class GuidancePresenter : MonoBehaviour
    {
        [SerializeField] private bool enableTestRing;
        private GuidanceReceiver receiver;
        private Texture2D ring;
        private GUIStyle titleStyle;
        private GUIStyle actionStyle;
        private GUIStyle statusStyle;
        private string lastStatus;
        private bool lastRing;
        private bool manualRequested;
        private ManualAlignmentState manual;
        private string manualDisplay;
        private string manualDirectory;
        private string manualExitReason = "user_exit";
        private double manualSeconds = 180;

        public string ManualProbeStatus => manual == null ? "MANUAL_STARTING" :
            manual.MarkedCount == 0 ? "MANUAL_READY" : "MANUAL_MARKED_" + manual.MarkedCount;
        public string CaptureStatus {
            get {
                var view = receiver.State.Presentation(Time.realtimeSinceStartupAsDouble);
                return receiver.State.LastSnapshot?.guidance == null ? view.Status
                    : "GUIDANCE_" + view.Status + "_" + receiver.State.LastSnapshot.target
                        + (view.Acknowledgement.Length > 0 ? "_ACK" : "");
            }
        }

        private void Awake()
        {
            receiver = GetComponent<GuidanceReceiver>();
            var args = Environment.GetCommandLineArgs();
            SbsGuidanceOptions options;
            try { options = SbsGuidanceOptions.Parse(args); }
            catch (ArgumentException exc)
            {
                Debug.LogError("[GUIDANCE] " + exc.Message);
                enabled = false;
                Application.Quit(2);
                return;
            }
            // Awake ordering between components is not guaranteed.
            if (options.Enabled)
            {
                gameObject.AddComponent<SbsGuidancePresenter>();
                enabled = false;
                return;
            }
            if (StereoAlignmentState.Requested(args))
            {
                if (ManualAlignmentState.Requested(args) || Array.IndexOf(args, "--test-ring") >= 0)
                {
                    Debug.LogError("[STEREO PROBE] Choose only one probe mode.");
                    Application.Quit(2);
                }
                else gameObject.AddComponent<StereoAlignmentProbe>();
                enabled = false;
                return;
            }
            manualRequested = ManualAlignmentState.Requested(args);
            int durationIndex = Array.IndexOf(args, "--probe-seconds");
            if (manualRequested && durationIndex >= 0 && (durationIndex + 1 >= args.Length
                || !double.TryParse(args[durationIndex + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out manualSeconds)
                || double.IsNaN(manualSeconds) || manualSeconds < 1 || manualSeconds > 300))
            {
                Debug.LogError("[MANUAL PROBE] --probe-seconds must be 1-300");
                enabled = false;
                Application.Quit(2);
                return;
            }
            enableTestRing |= Array.IndexOf(Environment.GetCommandLineArgs(), "--test-ring") >= 0;
            ring = new Texture2D(128, 128, TextureFormat.RGBA32, false);
            var pixels = new Color[128 * 128];
            for (int y = 0; y < 128; y++)
                for (int x = 0; x < 128; x++)
                {
                    float distance = new Vector2(x - 63.5f, y - 63.5f).magnitude;
                    float alpha = Mathf.Clamp01(2.5f - Mathf.Abs(distance - 56));
                    pixels[y * 128 + x] = new Color(0.35f, 1, 0.75f, alpha);
                }
            ring.SetPixels(pixels);
            ring.Apply(false, true);
        }

        private void Update()
        {
            double now = Time.realtimeSinceStartupAsDouble;
            if (manualRequested)
            {
                UpdateManualProbe(now);
                return;
            }
            string status = receiver.State.Presentation(now).Status;
            bool visible = receiver.State.ShowTestRing(now, enableTestRing);
            if (status != lastStatus || visible != lastRing)
            {
                Debug.Log("[GUIDANCE] status=" + status + " test_ring=" + visible
                    + " state=" + (receiver.State.LastSnapshot?.current_state ?? "none"));
                lastStatus = status;
                lastRing = visible;
            }
        }

        private void OnGUI()
        {
            if (manualRequested)
            {
                DrawManualProbe();
                return;
            }
            if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.Escape)
                Application.Quit();
            if (titleStyle == null)
            {
                titleStyle = MakeStyle(28, TextAnchor.MiddleCenter, Color.white);
                actionStyle = MakeStyle(36, TextAnchor.MiddleCenter, Color.white);
                statusStyle = MakeStyle(20, TextAnchor.MiddleCenter, new Color(0.75f, 0.82f, 0.82f));
            }

            Matrix4x4 previous = GUI.matrix;
            float scale = Mathf.Min(Screen.width / 1280f, Screen.height / 720f);
            var origin = new Vector3((Screen.width - 1280 * scale) / 2,
                (Screen.height - 720 * scale) / 2, 0);
            GUI.matrix = Matrix4x4.TRS(origin, Quaternion.identity, Vector3.one * scale);

            double now = Time.realtimeSinceStartupAsDouble;
            var snapshot = receiver.State.LastSnapshot;
            var view = receiver.State.Presentation(now);
            string status = view.Status;
            GUI.Label(new Rect(140, 38, 1000, 44),
                snapshot == null ? "Assembly guide" :
                (view.IsReference ? "Last: " : "") + snapshot.current_state + "  |  " + snapshot.current_label, titleStyle);
            GUI.Label(new Rect(140, 88, 1000, 36), status.Replace('_', ' '), statusStyle);
            if (receiver.State.ShowTestRing(now, enableTestRing))
                GUI.DrawTexture(new Rect(576, 296, 128, 128), ring);
            GUI.Label(new Rect(140, 475, 1000, 40), view.Acknowledgement, statusStyle);
            GUI.Label(new Rect(140, 532, 1000, 96),
                view.Instruction, actionStyle);
            GUI.Label(new Rect(140, 653, 1000, 30),
                enableTestRing ? "DISPLAY TEST  |  NOT CALIBRATED" : "NOT CALIBRATED", statusStyle);
            GUI.matrix = previous;
        }

        private void UpdateManualProbe(double now)
        {
            if (manual == null)
            {
                var display = GetComponent<DisplayBootstrap>();
                if (display == null || !display.Ready)
                {
                    if (now > 20) Application.Quit(2);
                    return;
                }
                try
                {
                    manual = new ManualAlignmentState(Screen.width, Screen.height, now, manualSeconds);
                    manualDisplay = Screen.mainWindowDisplayInfo.name;
                    manualDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        "ARAssembly", "beast-mvp", "display_probe", "manual-" + DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ")
                        + "-" + Guid.NewGuid().ToString("N").Substring(0, 8));
                    Directory.CreateDirectory(manualDirectory);
                    Debug.Log("[MANUAL PROBE] ready display=" + manualDisplay + " size=" + Screen.width + "x" + Screen.height
                        + " seconds=" + manualSeconds + " directory=" + manualDirectory);
                }
                catch (Exception exc)
                {
                    Debug.LogError("[MANUAL PROBE] " + exc.Message);
                    enabled = false;
                    Application.Quit(2);
                }
                return;
            }
            if (!ManualVisible(now))
            {
                manualExitReason = "deadline_or_display_changed";
                Application.Quit();
            }
        }

        private bool ManualVisible(double now)
        {
            return manual != null && Screen.mainWindowDisplayInfo.name == manualDisplay
                && manual.Visible(now, Screen.width, Screen.height);
        }

        private void DrawManualProbe()
        {
            double now = Time.realtimeSinceStartupAsDouble;
            if (!ManualVisible(now)) return;
            Event key = Event.current;
            if (key.type == EventType.KeyDown)
            {
                double step = key.shift ? 20 : 2;
                switch (key.keyCode)
                {
                    case KeyCode.LeftArrow: manual.Move(-step, 0, now); break;
                    case KeyCode.RightArrow: manual.Move(step, 0, now); break;
                    case KeyCode.UpArrow: manual.Move(0, -step, now); break;
                    case KeyCode.DownArrow: manual.Move(0, step, now); break;
                    case KeyCode.R: manual.Reset(now); break;
                    case KeyCode.Return:
                    case KeyCode.KeypadEnter: SaveManualPoint(now); break;
                    case KeyCode.Escape:
                    case KeyCode.Q: Application.Quit(); break;
                    default: return;
                }
                key.Use();
            }
            float x = (float)manual.X, y = (float)manual.Y;
            GUI.DrawTexture(new Rect(x - 24, y - 24, 48, 48), ring);
            Color previous = GUI.color;
            GUI.color = new Color(.35f, 1, .75f);
            GUI.DrawTexture(new Rect(x - 5, y - 1, 10, 2), Texture2D.whiteTexture);
            GUI.DrawTexture(new Rect(x - 1, y - 5, 2, 10), Texture2D.whiteTexture);
            GUI.color = previous;
            if (statusStyle == null) statusStyle = MakeStyle(20, TextAnchor.MiddleCenter, Color.white);
            GUI.Label(new Rect(Mathf.Clamp(x - 14, 0, Screen.width - 28), Mathf.Max(0, y - 54), 28, 28), "A", statusStyle);
            GUI.Label(new Rect(0, Screen.height - 60, Screen.width, 30), "MANUAL  |  NOT CALIBRATED", statusStyle);
        }

        private void SaveManualPoint(double now)
        {
            try
            {
                var point = manual.Mark(now);
                string path = Path.Combine(manualDirectory, "point-" + point.point_index.ToString("D3") + ".json");
                using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
                using (var writer = new StreamWriter(stream)) writer.Write(JsonUtility.ToJson(point, true));
                Debug.Log("[MANUAL PROBE] marked point=" + point.point_index + " x=" + point.x + " y=" + point.y
                    + " display=" + manualDisplay + " calibration_valid=false path=" + path);
            }
            catch (Exception exc)
            {
                Debug.LogError("[MANUAL PROBE] Could not save point: " + exc.Message);
                enabled = false;
                Application.Quit(2);
            }
        }

        private static GUIStyle MakeStyle(int size, TextAnchor alignment, Color color)
        {
            var style = new GUIStyle(GUI.skin.label) {
                fontSize = size, alignment = alignment, wordWrap = true, richText = false
            };
            style.normal.textColor = color;
            return style;
        }

        private void OnDestroy()
        {
            if (manualRequested) Debug.Log("[MANUAL PROBE] stopped reason=" + manualExitReason
                + " marked=" + (manual == null ? 0 : manual.MarkedCount));
            if (ring != null) Destroy(ring);
        }
    }
}
