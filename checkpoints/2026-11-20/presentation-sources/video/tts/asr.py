import sys, json, subprocess, numpy as np
from faster_whisper import WhisperModel
f=sys.argv[1]
b=subprocess.run(['ffmpeg','-v','error','-i',f,'-f','f32le','-ac','1','-ar','16000','-'],capture_output=True,check=True).stdout
audio=np.frombuffer(b,np.float32)
m=WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=2)
segs,info=m.transcribe(audio, language='ko', word_timestamps=True, beam_size=1, vad_filter=False, condition_on_previous_text=False)
W=[]
for s in segs:
    for w in s.words: W.append([round(w.start,3),round(w.end,3),w.word])
json.dump(W,open(f.replace('.mp3','_words.json'),'w'),ensure_ascii=False)
print('words',len(W))
