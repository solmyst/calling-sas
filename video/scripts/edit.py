"""Make editorial cuts from real app capture. Only silent waits are shortened."""
import json,re,subprocess,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
CAP=ROOT/'public/capture';AUDIO=ROOT/'public/audio'
def run(args):subprocess.run(args,check=True)
def duration(file):return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(file)]))
motions={}
def ui(name,seconds):
    original=CAP/(name+'.mp4')
    start=.9 if name=='memory' else 0
    active=seconds-2.5 if name=='memory' else seconds
    rate=max(1,(duration(original)-start)/active)
    motion=json.loads((CAP/(name+'-motion.json')).read_text())
    for e in motion['events']:
        e['at']=(e['at']-start)/rate
        if 'duration' in e:e['duration']/=rate
    motions[name]=motion
    run(['ffmpeg','-v','error','-y','-ss',str(start),'-i',str(original),'-vf',f'setpts=PTS/{rate},fps=60,tpad=stop_mode=clone:stop_duration={seconds}', '-t',str(seconds),'-an','-c:v','libx264','-crf','15','-pix_fmt','yuv420p',str(CAP/(name+'-edit.mp4'))])
for name,seconds in [('choose',7),('configure',9),('memory',7),('analytics',4),('outro',5)]:ui(name,seconds)
m=json.loads((ROOT/'public/manifest.json').read_text());offset=next(c for c in m['chapters'] if c['name']=='conversation')['audioOffset']
raw=AUDIO/'conversation-source.wav'
run(['ffmpeg','-v','error','-y','-i',str(AUDIO/'conversation.webm'),'-ar','48000','-ac','2',str(raw)])
total=duration(raw)
process=subprocess.run(['ffmpeg','-hide_banner','-i',str(raw),'-af','silencedetect=noise=-36dB:d=0.7','-f','null','-'],capture_output=True,text=True,check=True)
starts=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',process.stderr)]
ends=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',process.stderr)]
if len(starts)>len(ends):ends.append(total)
# Keep 0.36s per long pause. No speech samples are removed, including overlap.
cuts=[]
for start,end in zip(starts,ends):
    if end-start>.7:cuts.append((max(1.8,start+.18) if start<.05 else start+.18,end-.18))
keep=[];pos=0
for start,end in cuts:
    if start>pos:keep.append((pos,start))
    pos=end
if pos<total:keep.append((pos,total))
kept=sum(b-a for a,b in keep);tempo=max(1,kept/24)
if tempo>1.12:raise RuntimeError(f'Speech take is too long ({kept:.2f}s). Re-record a shorter conversation.')
filters=[]
for i,(a,b) in enumerate(keep):
    filters += [f'[0:v]trim=start={a+offset}:end={b+offset},setpts=PTS-STARTPTS[v{i}]',f'[1:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]']
filters.append(''.join(f'[v{i}][a{i}]' for i in range(len(keep)))+f'concat=n={len(keep)}:v=1:a=1[v][a]')
filters += [f'[v]setpts=PTS/{tempo},fps=60,tpad=stop_mode=clone:stop_duration=24[video]',f'[a]atempo={tempo},loudnorm=I=-17:TP=-2:LRA=7,apad[audio]']
run(['ffmpeg','-v','error','-y','-i',str(CAP/'conversation.mp4'),'-i',str(raw),'-filter_complex',';'.join(filters),'-map','[video]','-map','[audio]','-t','24','-c:v','libx264','-crf','15','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(CAP/'conversation-edit.mp4')])
run(['ffmpeg','-v','error','-y','-i',str(CAP/'conversation-edit.mp4'),'-vn','-ar','48000','-ac','2',str(AUDIO/'conversation-edit.wav')])
motion=json.loads((CAP/'conversation-motion.json').read_text())
def edited_time(raw_time):
    return sum(max(0,min(b,raw_time-offset)-a) for a,b in keep)/tempo
for e in motion['events']:
    e['at']=edited_time(e['at'])
    if 'duration' in e:e['duration']/=tempo
motions['conversation']=motion
(ROOT/'public/motion.json').write_text(json.dumps(motions,indent=2))
# Original quiet synth bed: no stock track, licence dependency, or external music.
sr=48000;t=np.arange(60*sr)/sr;signal=np.zeros_like(t)
for freq in [130.8128,164.8138,195.9977,261.6256]:signal+=.09*np.sin(2*np.pi*freq*t)*(0.65+0.35*np.sin(2*np.pi*t/12))
signal*=np.minimum(t/2,1)*np.minimum((60-t)/2,1)
with wave.open(str(AUDIO/'bed.wav'),'wb') as w:
    w.setparams((1,2,sr,0,'NONE','not compressed'));w.writeframes((np.clip(signal,-1,1)*32767).astype('<i2').tobytes())
(ROOT/'out/edit-report.json').write_text(json.dumps(dict(audioOffset=offset,rawAudioDuration=total,silenceCuts=cuts,keptRanges=keep,speechTempo=tempo,editedDuration=24),indent=2))
print('Edit prepared:',round(kept,2),'seconds of speech and short pauses; tempo',round(tempo,3))
