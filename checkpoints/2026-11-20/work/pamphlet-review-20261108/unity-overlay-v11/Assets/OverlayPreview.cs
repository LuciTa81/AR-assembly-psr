using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

public sealed class OverlayPreview : MonoBehaviour
{
    const int Width = 1530, Height = 1020;
    Texture2D ring, line;
    Font font, instructionFont;
    bool greenGuide, softHud, uniformRim;
    Color edgeColor = new Color(0.24f, 0.92f, 0.80f, 0.57f);
    Color activeColor = new Color(0.38f, 1f, 0.67f, 1f);
    readonly List<TextMesh> labels = new List<TextMesh>();
    // Editorial correspondences on the archived photo, not headset calibration.
    readonly Vector2[] rim = {
        new Vector2(600,249), new Vector2(1027,224), new Vector2(1060,226),
        new Vector2(1076,242), new Vector2(1081,270), new Vector2(1145,573),
        new Vector2(1150,604), new Vector2(1143,625), new Vector2(1123,639),
        new Vector2(590,668), new Vector2(568,657), new Vector2(557,636),
        new Vector2(555,609), new Vector2(564,290), new Vector2(569,267),
        new Vector2(583,254), new Vector2(600,249)
    };

    IEnumerator Start()
    {
        Application.runInBackground = true;
        string[] args = Environment.GetCommandLineArgs();
        int index = Array.IndexOf(args, "--output");
        if (index < 0 || index + 1 >= args.Length) throw new ArgumentException("--output required");
        string output = System.IO.Path.GetFullPath(args[index+1]);
        Directory.CreateDirectory(output);
        font = Resources.Load<Font>("Fonts/NotoSansKR-SemiBold");
        if (font == null) throw new InvalidOperationException("Noto Sans KR SemiBold font missing");
        greenGuide = Array.IndexOf(args, "--green-bold") >= 0;
        softHud = Array.IndexOf(args, "--soft-hud") >= 0;
        uniformRim = Array.IndexOf(args, "--uniform-rim") >= 0;
        instructionFont = greenGuide && !softHud ? Resources.Load<Font>("Fonts/NotoSansKR-Bold") : font;
        if (instructionFont == null) throw new InvalidOperationException("Instruction font missing");
        if (softHud) {
            activeColor = new Color(118/255f,1,131/255f);
            edgeColor = new Color(activeColor.r,1,activeColor.b,0.44f);
        }
        Debug.Log("Preview font: Noto Sans KR, title 600, instruction " + (softHud ? "600 soft green HUD" : greenGuide ? "700 green" : "600 white"));
        ring = new Texture2D(256, 256, TextureFormat.RGBA32, false);
        Color[] pixels = new Color[256 * 256];
        for (int y = 0; y < 256; y++) for (int x = 0; x < 256; x++) {
            float distance = new Vector2(x - 127.5f, y - 127.5f).magnitude;
            pixels[y * 256 + x] = new Color(1, 1, 1, Mathf.Clamp01(8.5f - Mathf.Abs(distance - 115)));
        }
        ring.SetPixels(pixels);
        ring.Apply();
        line = new Texture2D(1, 32, TextureFormat.RGBA32, false);
        for (int y = 0; y < 32; y++) line.SetPixel(0, y, new Color(1, 1, 1, Mathf.Clamp01(Mathf.Min(y, 31-y) / 3f)));
        line.Apply();
        BuildOverlay();
        yield return null;
        yield return null;
        foreach (var label in labels) {
            float wantedHeight = label.text.StartsWith("나사 B ·") ? (softHud ? 55 : 44) : 66;
            var renderer = label.GetComponent<MeshRenderer>();
            if (renderer.bounds.size.y <= 0) throw new InvalidOperationException("Empty text mesh");
            label.transform.localScale *= wantedHeight / renderer.bounds.size.y;
            if (renderer.bounds.size.x > 1260) throw new InvalidOperationException("Text exceeds image width");
            if (renderer.sortingOrder == 21) Debug.Log("Text bounds: " + label.text + " " + renderer.bounds.size);
        }
        yield return null;
        var camera = Camera.main;
        camera.transform.position = new Vector3(Width/2f, -Height/2f, -10);
        camera.orthographic = true;
        camera.orthographicSize = Height/2f;
        camera.aspect = Width/(float)Height;
        camera.cullingMask = -1;
        camera.clearFlags = CameraClearFlags.SolidColor;
        var target = new RenderTexture(Width, Height, 24, RenderTextureFormat.ARGB32);
        target.antiAliasing = 4;
        target.Create();
        camera.targetTexture = target;
        for (int pass = 0; pass < 2; pass++) {
            camera.backgroundColor = pass == 0 ? Color.black : Color.white;
            camera.Render();
            RenderTexture.active = target;
            var capture = new Texture2D(Width, Height, TextureFormat.RGB24, false);
            capture.ReadPixels(new Rect(0,0,Width,Height),0,0);
            capture.Apply();
            File.WriteAllBytes(System.IO.Path.Combine(output,pass == 0 ? "black.png" : "white.png"),capture.EncodeToPNG());
            Destroy(capture);
        }
        RenderTexture.active = null;
        camera.targetTexture = null;
        target.Release();
        Debug.Log("Offscreen overlay capture complete: " + Width + "x" + Height);
        Application.Quit();
    }

    void BuildOverlay()
    {
        if (uniformRim) ClosedPath(rim,3.4f,edgeColor);
        else Path(rim,3.4f,edgeColor);
        if (!uniformRim) {
        Color corner = softHud ? new Color(activeColor.r,1,activeColor.b,0.68f) : new Color(0.35f, 1, 0.83f, 0.84f);
        Path(new[]{new Vector2(566,328),new Vector2(564,290),new Vector2(569,267),new Vector2(583,254),new Vector2(600,249),new Vector2(653,246)},5,corner);
        Path(new[]{new Vector2(557,573),new Vector2(555,609),new Vector2(557,636),new Vector2(568,657),new Vector2(590,668),new Vector2(643,665)},5,corner);
        Path(new[]{new Vector2(1138,541),new Vector2(1145,573),new Vector2(1150,604),new Vector2(1143,625),new Vector2(1123,639),new Vector2(1067,642)},5,corner);
        }
        Vector2 b = new Vector2(1042.3f,248);
        Quad(new[]{b+new Vector2(-45,45),b+new Vector2(45,45),b+new Vector2(45,-45),b+new Vector2(-45,-45)},ring,activeColor,12);
        Segment(new Vector2(b.x,127),new Vector2(b.x,190),7,activeColor);
        Segment(new Vector2(b.x-17,172),new Vector2(b.x,190),7,activeColor);
        Segment(new Vector2(b.x+17,172),new Vector2(b.x,190),7,activeColor);
        Label(new Vector2(765,softHud ? 42 : 34),"나사 B · 2/4");
        Label(new Vector2(765,923),"나사 B를 조여주세요.");
    }

    void Path(Vector2[] points,float width,Color color)
    {
        for(int i=1;i<points.Length;i++) Segment(points[i-1],points[i],width,color);
    }

    void ClosedPath(Vector2[] points,float width,Color color)
    {
        // Shared miter joins avoid darker alpha overlaps at the corners.
        int count=points.Length-1;
        var vertices=new Vector3[(count+1)*2];
        var uv=new Vector2[vertices.Length];
        var triangles=new int[count*6];
        for(int i=0;i<=count;i++) {
            int current=i%count;
            Vector2 before=(points[current]-points[(current+count-1)%count]).normalized;
            Vector2 after=(points[(current+1)%count]-points[current]).normalized;
            Vector2 normal=new Vector2(-after.y,after.x);
            Vector2 miter=(new Vector2(-before.y,before.x)+normal).normalized;
            Vector2 offset=miter*(width/2/Vector2.Dot(miter,normal));
            Vector2 a=points[current]-offset,b=points[current]+offset;
            vertices[2*i]=new Vector3(a.x,-a.y,0);
            vertices[2*i+1]=new Vector3(b.x,-b.y,0);
            uv[2*i]=new Vector2(0,0);
            uv[2*i+1]=new Vector2(0,1);
            if(i==count) continue;
            int v=2*i,t=6*i;
            triangles[t]=v;triangles[t+1]=v+2;triangles[t+2]=v+3;
            triangles[t+3]=v;triangles[t+4]=v+3;triangles[t+5]=v+1;
        }
        var item=new GameObject("Uniform lid outline");
        var mesh=new Mesh { vertices=vertices,uv=uv,triangles=triangles };
        item.AddComponent<MeshFilter>().mesh=mesh;
        var renderer=item.AddComponent<MeshRenderer>();
        renderer.sortingOrder=10;
        var material=new Material(Shader.Find("Sprites/Default"));
        material.mainTexture=line;
        material.color=color;
        renderer.material=material;
    }

    void Segment(Vector2 a,Vector2 b,float width,Color color)
    {
        Vector2 along=(b-a).normalized;
        Vector2 side=new Vector2(-along.y,along.x)*width/2;
        Quad(new[]{a-side,b-side,b+side,a+side},line,color,10);
    }

    void Quad(Vector2[] points,Texture2D texture,Color color,int order)
    {
        var item=new GameObject("Overlay stroke");
        var mesh=new Mesh();
        mesh.vertices=Array.ConvertAll(points,p=>new Vector3(p.x,-p.y,0));
        mesh.uv=new[]{new Vector2(0,0),new Vector2(1,0),new Vector2(1,1),new Vector2(0,1)};
        mesh.triangles=new[]{0,1,2,0,2,3};
        item.AddComponent<MeshFilter>().mesh=mesh;
        var renderer=item.AddComponent<MeshRenderer>();
        renderer.sortingOrder=order;
        var material=new Material(Shader.Find("Sprites/Default"));
        material.mainTexture=texture;
        material.color=color;
        renderer.material=material;
    }

    void Label(Vector2 center,string text)
    {
        bool isInstruction = !text.StartsWith("나사 B ·");
        Font face = isInstruction ? instructionFont : font;
        Color foreground = greenGuide && isInstruction ? new Color(0.48f,1f,0.67f) : Color.white;
        if (softHud) {
            // A narrow green halo without a dark backing or blurred letter cores.
            for (int band=0;band<2;band++) for(int i=0;i<8;i++) {
                float angle=i*Mathf.PI/4;
                float radius=band==0 ? 1f : 2f;
                var offset=new Vector2(Mathf.Cos(angle),Mathf.Sin(angle))*radius;
                var glow=new Color(activeColor.r,1,activeColor.b,band==0 ? 0.025f : 0.012f);
                AddLabel(center+offset,text,face,glow,20);
            }
            AddLabel(center,text,face,new Color(activeColor.r,1,activeColor.b,0.96f),21);
            return;
        }
        for(int shadow=1;shadow>=0;shadow--) {
            AddLabel(center+new Vector2(shadow*2,shadow*3),text,face,shadow==1 ? new Color(0,0,0,0.58f) : foreground,shadow==1 ? 20 : 21);
        }
    }

    void AddLabel(Vector2 center,string text,Font face,Color color,int order)
    {
        var item=new GameObject("Guidance text");
        item.transform.position=new Vector3(center.x,-center.y,0);
        var label=item.AddComponent<TextMesh>();
        label.font=face;
        label.fontSize=124;
        label.fontStyle=FontStyle.Normal;
        label.anchor=TextAnchor.MiddleCenter;
        label.alignment=TextAlignment.Center;
        label.text=text;
        label.color=color;
        var renderer=item.GetComponent<MeshRenderer>();
        renderer.sharedMaterial=face.material;
        renderer.sortingOrder=order;
        labels.Add(label);
    }
}
