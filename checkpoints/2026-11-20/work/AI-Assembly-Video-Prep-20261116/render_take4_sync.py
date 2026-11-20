import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
SRC = ROOT / 'recordings/20261116_034830_linefix-take4'
OUT = ROOT / 'edited/take4-sync'
FF = Path('C:/Users/fresh/Documents/Codex/2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin/ffmpeg.exe')
FONT = 'C:/Windows/Fonts/malgun.ttf'
BOLD = 'C:/Windows/Fonts/malgunbd.ttf'


def label(draw, xy, text, size, color='#e6eeeb', bold=False):
    draw.text(xy, text, font=ImageFont.truetype(BOLD if bold else FONT, size), fill=color)


def run(args, logfile):
    with (OUT/logfile).open('w', encoding='utf-8') as log:
        subprocess.run([str(FF), '-y', '-hide_banner', '-loglevel', 'warning', *args], stdout=log, stderr=log, check=True)


def side_by_side():
    bg = Image.new('RGB', (1920,1080), '#141c1b')
    d = ImageDraw.Draw(bg)
    label(d,(48,44),'AI Assembly Guide',28,'#69c5cf',True)
    label(d,(48,94),'실제 작업과 AR 안내',48,bold=True)
    label(d,(48,198),'작업대 카메라',27,bold=True)
    label(d,(984,198),'Unity 왼눈 출력',27,bold=True)
    d.rectangle((48,250,935,749), fill='black')
    d.rectangle((984,250,1871,749), fill='black')
    label(d,(48,794),'상자 배치   →   뚜껑 닫기   →   나사 A · B · C · D   →   최종 확인',31,bold=True)
    label(d,(48,870),'같은 작업 시간대로 정렬한 카메라 영상과 Unity 출력입니다.',25,'#adbfba')
    label(d,(48,918),'안경 렌즈를 통해 촬영한 영상은 아닙니다.',23,'#adbfba')
    bg.save(OUT/'comparison-layout.png')
    filters = '[0:v]fps=30,scale=888:500,setsar=1[c];[1:v]crop=1920:1080:0:0,scale=888:500,setsar=1[u];[2:v][c]overlay=48:250:shortest=1[b];[b][u]overlay=984:250:shortest=1,format=yuv420p[v]'
    run(['-ss','21','-i',str(SRC/'camera-preview.mp4'),'-ss','20.7','-i',str(SRC/'unity-sbs.mp4'),'-loop','1','-i',str(OUT/'comparison-layout.png'),'-filter_complex',filters,'-map','[v]','-an','-t','121.5','-r','30','-c:v','libx264','-preset','fast','-crf','19','-movflags','+faststart',str(OUT/'01-synchronized-comparison.mp4')], 'comparison-encode.log')
    print('Comparison rendered',flush=True)


def composite_sample(clean=False, full=False):
    cv2.setNumThreads(2)
    # A single plane mapping is a reconstruction, not an optical-eye recording.
    src_points = np.float32([[944,53],[1465,54],[961,497],[1548,495]])
    dst_points = np.float32([[574,328],[798,319],[566,521],[836,514]])
    H = cv2.getPerspectiveTransform(src_points,dst_points)
    cap = cv2.VideoCapture(str(SRC/'camera-preview.mp4'))
    uni = cv2.VideoCapture(str(SRC/'unity-sbs.mp4'))
    start, length, fps = (21.0,121.5,30) if full else (82.0,14.0,30)
    cap.set(cv2.CAP_PROP_POS_FRAMES,round(start*10))
    uni.set(cv2.CAP_PROP_POS_FRAMES,round((start-.3)*30))
    badge = Image.new('RGB',(1280,720),'black')
    bd=ImageDraw.Draw(badge)
    label(bd,(20,18),'카메라 시점 재구성 · Unity 실제 출력 사용',18,'#ffffff')
    badge = cv2.cvtColor(np.array(badge),cv2.COLOR_RGB2BGR)
    dest=OUT/('06-camera-composite-full.mp4' if full else '05-camera-composite-clean.mp4' if clean else '02-camera-view-reconstruction-sample.mp4')
    command=[str(FF),'-y','-hide_banner','-loglevel','warning','-f','rawvideo','-pixel_format','bgr24','-video_size','1280x720','-framerate',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
    stats=[]
    with (OUT/('full-encode.log' if full else 'clean-encode.log' if clean else 'sample-encode.log')).open('w') as log:
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
        try:
            camera=None
            for i in range(round(length*fps)):
                if i%3==0:
                    ok,camera=cap.read()
                    if not ok: raise RuntimeError('Camera ended early')
                ok,u=uni.read()
                if not ok: raise RuntimeError('Unity ended early')
                u=u[:,:1920]
                hsv=cv2.cvtColor(u,cv2.COLOR_BGR2HSV)
                geometry=np.zeros_like(u)
                mask=(hsv[:,:,1]>45)&(hsv[:,:,2]>30)
                mask[760 if full else 620:]=False
                geometry[mask]=u[mask]
                warp=cv2.warpPerspective(geometry,H,(1280,720))
                # Leave the recorded diagnostic graphics visible; do not invent hidden pixels.
                frame=cv2.add(camera,warp)
                title=np.zeros_like(u)
                title_mask=np.zeros(hsv.shape[:2],dtype=bool)
                title_mask[50:115,800:1130]=(hsv[50:115,800:1130,1]<25)&(hsv[50:115,800:1130,2]>160)
                title[title_mask]=u[title_mask]
                title=cv2.resize(title[:125],(1280,83))
                frame[48:131]=cv2.add(frame[48:131],title)
                hud=cv2.resize(u[760:960],(1280,133))
                if not clean:
                    frame[570:703]=(frame[570:703].astype(np.float32)*.42).astype(np.uint8)
                frame[570:703]=cv2.add(frame[570:703],hud)
                if not clean:
                    frame[:45]=(frame[:45].astype(np.float32)*.4).astype(np.uint8)
                    frame=cv2.add(frame,badge)
                proc.stdin.write(frame.tobytes())
                stats.append(int(np.count_nonzero(warp)))
                checks=(0,390,810,1500,2160,3030,3600) if full else (0,90,150,240,330,390)
                if i in checks:
                    prefix='full' if full else 'clean' if clean else 'reconstruction'
                    cv2.imwrite(str(OUT/f'{prefix}-{i:03}.jpg'),frame)
                if full and i % 600 == 0:
                    print(f'Rendered {i/fps:.0f}/{length:.1f} seconds',flush=True)
        finally:
            proc.stdin.close()
            cap.release()
            uni.release()
        if proc.wait()!=0: raise RuntimeError('Sample encoding failed')
    (OUT/('full-mapping.json' if full else 'clean-mapping.json' if clean else 'sample-mapping.json')).write_text(json.dumps({'camera_start_seconds':start,'unity_start_seconds':start-.3,'length_seconds':length,'unity_reference_points':src_points.tolist(),'camera_reference_points':dst_points.tolist(),'homography':H.tolist(),'frames_with_geometry':sum(s>0 for s in stats),'frames':len(stats),'method':'Fixed reference plane only; recorded camera diagnostics retained; Unity HUD positioned separately'},indent=2),encoding='utf-8')
    print('Composite sample rendered',flush=True)


if __name__=='__main__':
    composite_sample()
    side_by_side()
