using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class PreviewBuilder
{
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var camera = new GameObject("Main Camera").AddComponent<Camera>();
        camera.tag = "MainCamera";
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = Color.black;
        camera.cullingMask = 0;
        new GameObject("Pamphlet Overlay Preview").AddComponent<OverlayPreview>();
        Directory.CreateDirectory("Assets/Scenes");
        const string scenePath = "Assets/Scenes/Preview.unity";
        EditorSceneManager.SaveScene(scene, scenePath);
        PlayerSettings.companyName = "ARAssembly";
        PlayerSettings.productName = "Pamphlet Overlay Preview";
        PlayerSettings.runInBackground = true;
        PlayerSettings.colorSpace = ColorSpace.Gamma;
        PlayerSettings.defaultScreenWidth = 1530;
        PlayerSettings.defaultScreenHeight = 1020;
        PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
        PlayerSettings.resizableWindow = false;
        PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
        AssetDatabase.SaveAssets();
        string output = Path.GetFullPath("../unity-overlay-player-v11/Preview.exe");
        string[] args = Environment.GetCommandLineArgs();
        int index = Array.IndexOf(args,"-previewBuildPath");
        if (index >= 0 && index + 1 < args.Length) output = Path.GetFullPath(args[index+1]);
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[]{scenePath}, locationPathName = output,
            target = BuildTarget.StandaloneWindows64, options = BuildOptions.None
        });
        if (report.summary.result != BuildResult.Succeeded) throw new BuildFailedException(report.summary.result.ToString());
        Debug.Log("Preview build complete: " + output);
    }
}
