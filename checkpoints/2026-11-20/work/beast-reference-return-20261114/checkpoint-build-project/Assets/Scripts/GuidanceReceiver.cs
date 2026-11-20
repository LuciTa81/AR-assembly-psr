using System;
using System.Collections;
using System.IO;
using System.Runtime.Serialization.Json;
using System.Text;
using System.Xml;
using UnityEngine;
using UnityEngine.Networking;

namespace ARAssembly
{
    public sealed class GuidanceReceiver : MonoBehaviour
    {
        private const string Endpoint = "http://127.0.0.1:8765/state.json";
        public GuidanceState State { get; private set; } = new GuidanceState();
        public bool SbsEnabled { get; private set; }
        public bool SyntheticPreview => preview != null;
        public double PreviewDuration => preview == null ? 0 : preview.duration_seconds;
        public double LastRoundTripMs { get; private set; }
        private SpatialPreviewConfig preview;
        private string endpoint = Endpoint;
        private UnityWebRequest activeRequest;

        private void Awake()
        {
            try {
                var options = SbsGuidanceOptions.Parse(Environment.GetCommandLineArgs());
                SbsEnabled = options.Enabled;
                endpoint = options.StateUrl;
                if (options.PreviewPath == null) return;
                string path = Path.GetFullPath(options.PreviewPath);
                if (path.StartsWith(@"\\") || new FileInfo(path).Length > 65536)
                    throw new ArgumentException("Preview config must be a small local file");
                preview = new SpatialPreviewConfig();
                JsonUtility.FromJsonOverwrite(File.ReadAllText(path), preview);
                preview = preview.ValidatedCopy();
                State = new GuidanceState(preview);
                endpoint = preview.state_url;
            } catch (Exception exc) {
                Debug.LogError("[SBS GUIDANCE] " + exc.Message);
                enabled = false;
                Application.Quit(2);
            }
        }

        public static GuidanceSnapshot ParseSnapshot(string json)
        {
            if (string.IsNullOrWhiteSpace(json) || Encoding.UTF8.GetByteCount(json) > 65536)
                throw new ArgumentException("Invalid snapshot size");
            var snapshot = new GuidanceSnapshot();
            JsonUtility.FromJsonOverwrite(json, snapshot);
            // JsonUtility creates inline objects even for absent/null fields.
            // Inspect presence structurally so an explicit empty object stays invalid.
            bool guidanceObject = false, seenGuidance = false;
            byte[] bytes = Encoding.UTF8.GetBytes(json);
            try {
                using (var reader = JsonReaderWriterFactory.CreateJsonReader(bytes, new XmlDictionaryReaderQuotas {
                    MaxDepth = 32, MaxStringContentLength = 65536, MaxArrayLength = 65536,
                    MaxBytesPerRead = 4096, MaxNameTableCharCount = 65536
                })) {
                    while (reader.Read()) {
                        if (reader.NodeType != XmlNodeType.Element || reader.Depth != 1 || reader.LocalName != "guidance") continue;
                        if (seenGuidance) throw new ArgumentException("Duplicate guidance field");
                        seenGuidance = true;
                        string kind = reader.GetAttribute("type");
                        if (kind != "object" && kind != "null") throw new ArgumentException("Invalid guidance type");
                        guidanceObject = kind == "object";
                    }
                }
            } catch (XmlException exc) { throw new ArgumentException("Invalid snapshot JSON", exc); }
            if (!guidanceObject) snapshot.guidance = null;
            return snapshot;
        }

        private void OnEnable()
        {
            var args = Environment.GetCommandLineArgs();
            if (ManualAlignmentState.Requested(args) || StereoAlignmentState.Requested(args)) return;
            StartCoroutine(Poll());
        }

        private IEnumerator Poll()
        {
            while (true)
            {
                double started = Time.realtimeSinceStartupAsDouble;
                var download = new BoundedDownload();
                activeRequest = new UnityWebRequest(endpoint, "GET", download, null);
                activeRequest.timeout = 1;
                activeRequest.redirectLimit = 0;
                activeRequest.SetRequestHeader("Cache-Control", "no-cache");
                yield return activeRequest.SendWebRequest();
                LastRoundTripMs = (Time.realtimeSinceStartupAsDouble - started) * 1000;
                using (var response = activeRequest)
                {
                    activeRequest = null;
                    if (response.result != UnityWebRequest.Result.Success)
                        State.Disconnect();
                    else
                    {
                        try
                        {
                            var snapshot = ParseSnapshot(download.Text);
                            State.Apply(snapshot, started, Time.realtimeSinceStartupAsDouble);
                        }
                        catch (ArgumentException)
                        {
                            State.InvalidResponse();
                        }
                    }
                }
                // Pose has a150ms budget; the older500ms text loop can poll less often.
                if (SbsEnabled) yield return null;
                else yield return new WaitForSecondsRealtime(0.05f);
            }
        }

        private sealed class BoundedDownload : DownloadHandlerScript
        {
            private readonly MemoryStream buffer = new MemoryStream();
            public BoundedDownload() : base(new byte[4096]) { }
            public string Text => Encoding.UTF8.GetString(buffer.ToArray());
            protected override bool ReceiveData(byte[] data, int length)
            {
                if (data == null || length < 0 || buffer.Length + length > 65536) return false;
                buffer.Write(data, 0, length);
                return true;
            }
        }

        private void OnDisable()
        {
            StopAllCoroutines();
            if (activeRequest != null)
            {
                activeRequest.Abort();
                activeRequest.Dispose();
                activeRequest = null;
            }
            State.Disconnect();
        }
    }
}
