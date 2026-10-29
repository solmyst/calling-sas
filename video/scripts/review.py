"""Review every decoded frame, overlay OCR, audio levels, and cursor tracking."""
import json,math,re,subprocess,sys,shutil,hashlib
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'out';VIDEO=OUT/'giani-hackathon-demo.mp4'
FRAMES=OUT/'review-frames';FRAMES.mkdir(exist_ok=True)
for old in FRAMES.glob('*.jpg'):old.unlink()
def run(args,**kwargs):return subprocess.run(args,check=True,**kwargs)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(VIDEO)]))
v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
assert v['width']==1920 and v['height']==1080 and v['r_frame_rate']=='60/1'
assert v['codec_name']=='h264' and a['codec_name']=='aac' and v['pix_fmt']=='yuv420p'
assert abs(float(probe['format']['duration'])-60)<.05
run(['ffmpeg','-v','error','-y','-i',str(VIDEO),'-vf','scale=960:540','-q:v','3',str(FRAMES/'%04d.jpg')])
files=sorted(FRAMES.glob('*.jpg')); assert len(files)==3600,len(files)
# Reuse exactly the SVG cursor used by the capture, never a guessed UI marker.
run(['node','scripts/cursor-template.mjs'],cwd=ROOT)
template=cv2.imread(str(OUT/'cursor-template.png'),cv2.IMREAD_UNCHANGED)
template=cv2.resize(template,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
mask=(template[:,:,3]>128).astype('uint8')*255
cursor=[];black=[];differences=[];previous=None;low_contrast=[];tiled=[];cursor_point=None;overlay_changes=[]
logo=cv2.imread(str(files[180]))[13:30,120:137]
scene_starts=[0,420,960,1200,2640,3060,3300]
references={start:cv2.imread(str(files[start+60]),0) for start in scene_starts}
for i,file in enumerate(files):
    frame=cv2.imread(str(file));gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    if gray.mean()<3 and i<3580:black.append(i)
    if previous is not None:differences.append(float(np.mean(np.abs(gray.astype(float)-previous))))
    previous=gray.astype(float)
    transitioning=any(start<=i<start+20 for start in scene_starts)
    if not transitioning and i<3580 and gray[52:74,120:840].std()<8:low_contrast.append(i)
    if not transitioning and i<3580:
      reference=references[max(start for start in scene_starts if start<=i)]
      delta=max(np.mean(np.abs(gray[38:76].astype(float)-reference[38:76])),np.mean(np.abs(gray[513:532].astype(float)-reference[513:532])))
      if delta>2:overlay_changes.append(i)
    brands=cv2.matchTemplate(frame,logo,cv2.TM_CCOEFF_NORMED)
    brands[0:48,90:170]=0
    if cv2.minMaxLoc(brands)[1]>.9:tiled.append(i)
    if cursor_point or i%10==0:
      x,y=cursor_point or (0,0)
      x0,y0=(max(0,x-65),max(0,y-65)) if cursor_point else (0,0)
      roi=frame[y0:min(540,y+100),x0:min(960,x+100)] if cursor_point else frame
      match=cv2.matchTemplate(roi,template[:,:,:3],cv2.TM_CCORR_NORMED,mask=mask)
      _,score,_,point=cv2.minMaxLoc(match)
      if score>.965:
        cursor_point=(point[0]+x0,point[1]+y0)
        cursor.append({'frame':i,'x':cursor_point[0],'y':cursor_point[1],'score':round(score,4)})
      else:cursor_point=None
    if i%300==0:print(f'Pixel/cursor review: {i}/3600',flush=True)
assert not black, 'Unexpected black frames: '+str(black)
assert not low_contrast,'Unreadable title band: '+str(low_contrast[:20])
assert not tiled,'Repeated/tiling artifact frames: '+str(tiled)
assert not overlay_changes,'Unexpected title/caption changes: '+str(overlay_changes)
assert len(cursor)>100 and len({(p['x'],p['y']) for p in cursor})>20,'Cursor motion was not verified.'
# Contact sheets cover all 3600 frames, 180 frames / sheet, without sampling gaps.
for batch in range(20):
    sheet=Image.new('RGB',(2880,12*122),(18,47,39));draw=ImageDraw.Draw(sheet)
    for j,file in enumerate(files[batch*180:(batch+1)*180]):
      image=Image.open(file).resize((192,108));x=(j%15)*192;y=(j//15)*122
      sheet.paste(image,(x,y));draw.text((x+4,y+109),f'{(batch*180+j)/60:05.2f}s',fill='#d6edb9')
    sheet.save(OUT/f'contact-sheet-{batch+1:02}.jpg',quality=90)
# Full-size frames at all transitions and moments used to inspect reading size.
keyframes=[30,180,419,438,600,959,978,1199,1218,1440,1800,2160,2639,2658,2880,3059,3078,3299,3318,3540,3579]
for frame in keyframes:
    run(['ffmpeg','-v','error','-y','-i',str(VIDEO),'-vf',f'select=eq(n\\,{frame})','-frames:v','1',str(OUT/f'keyframe-{frame:04}.png')])
# OCR validates each distinct overlay. Every other stable frame is compared to
# that validated reference above, rather than repeatedly OCRing identical text.
ocr_dir=OUT/'ocr-reference';ocr_dir.mkdir(exist_ok=True)
for old in ocr_dir.glob('*.jpg'):old.unlink()
for start in scene_starts:shutil.copy(files[start+60],ocr_dir/files[start+60].name)
run(['swiftc',str(ROOT/'scripts/ocr.swift'),'-o',str(OUT/'ocr-review')])
run([str(OUT/'ocr-review'),str(ocr_dir),str(OUT/'ocr.json')])
ocr=json.loads((OUT/'ocr.json').read_text())
assert len(ocr)==7
expected=[(0,420,'business context'),(420,960,'your instructions'),(960,1200,'microphone in'),(1200,2640,'speak over'),(2640,3060,'correction survives'),(3060,3300,'conversations you'),(3300,3600,'one workspace')]
ocr_failures=[]
for index,(start,end,phrase) in enumerate(expected):
    text=' '.join(ocr[index]['text']).lower()
    if not all(word in text for word in phrase.split()):ocr_failures.append(start+60)
assert not ocr_failures,'Overlay OCR failures: '+str(ocr_failures)
audio=run(['ffmpeg','-hide_banner','-i',str(VIDEO),'-af','loudnorm=I=-16:TP=-1:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True)
levels=json.loads(re.findall(r'\{\s*"input_i".*?\}',audio.stderr,re.S)[-1]);assert float(levels['input_tp'])<-.1,levels
report={'passed':True,'duration_seconds':float(probe['format']['duration']),'frames_decoded':len(files),'overlay_reference_ocr_images':len(ocr),'overlay_ocr_failures':ocr_failures,'unexpected_overlay_changes':overlay_changes,'unexpected_black_frames':black,'unreadable_title_frames':low_contrast,'tiling_artifact_frames':tiled,'cursor_detections':len(cursor),'unique_cursor_positions':len({(p['x'],p['y']) for p in cursor}),'audio':levels,'video_codec':v['codec_name'],'audio_codec':a['codec_name'],'resolution':[v['width'],v['height']],'file_megabytes':round(VIDEO.stat().st_size/1e6,2),'visual_contact_sheets':20,'keyframes':keyframes}
report['sha256']=hashlib.sha256(VIDEO.read_bytes()).hexdigest()
(OUT/'review-report.json').write_text(json.dumps(report,indent=2));(OUT/'cursor-tracking.json').write_text(json.dumps(cursor))
print(json.dumps(report,indent=2))
