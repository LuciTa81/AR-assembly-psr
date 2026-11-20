using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace ARAssembly.Editor
{
    public static class AssemblyGuideBuilder
    {
        private const string ScenePath = "Assets/Scenes/AssemblyGuide.unity";

        [MenuItem("AR Assembly/Create P1 Scene")]
        public static void CreateScene()
        {
            if (!Application.isBatchMode && !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                return;
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Main Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.cullingMask = 0;
            var guide = new GameObject("Assembly Guide");
            guide.AddComponent<DisplayBootstrap>();
            guide.AddComponent<GuidanceReceiver>();
            guide.AddComponent<GuidancePresenter>();
            Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
        }

        public static void BuildWindows()
        {
            CreateScene();
            PlayerSettings.companyName = "ARAssembly";
            PlayerSettings.productName = "Beast Assembly Guide";
            PlayerSettings.runInBackground = true;
            PlayerSettings.defaultScreenWidth = 1280;
            PlayerSettings.defaultScreenHeight = 720;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.insecureHttpOption = InsecureHttpOption.AlwaysAllowed;
            string output = Path.GetFullPath("../outputs/unity_p1/BeastAssemblyGuide.exe");
            var args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "-guideBuildPath");
            if (index >= 0 && index + 1 < args.Length) output = Path.GetFullPath(args[index + 1]);
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { ScenePath }, locationPathName = output,
                target = BuildTarget.StandaloneWindows64, options = BuildOptions.None
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new BuildFailedException("P1 build failed: " + report.summary.result);
            Debug.Log("[P1 BUILD] " + output);
        }
    }
}
