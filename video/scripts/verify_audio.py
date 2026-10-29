"""Optional paid intelligibility check: transcribe the final mix through Gnani."""
import asyncio,json,subprocess,sys,re,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from app.gnani import GnaniVoiceEngine
from websockets.asyncio.client import connect
parser=argparse.ArgumentParser()
parser.add_argument('--video',type=Path,default=ROOT/'video/out/giani-hackathon-demo.mp4')
parser.add_argument('--report',type=Path,default=ROOT/'video/out/audio-intelligibility.json')
parser.add_argument('--review-cached',action='store_true')
args=parser.parse_args()
async def main():
    report=args.report
    if args.review_cached:
      cached=json.loads(report.read_text())
      return assess(cached['transcript'],report,cached.get('pcm_sha256'))
    voice=GnaniVoiceEngine();voice.require_ready()
    pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(args.video),'-vn','-ar','16000','-ac','1','-f','s16le','-'])
    transcripts=[]
    async with connect(voice.streaming_stt_url,additional_headers=voice.streaming_headers('English'),compression=None,open_timeout=15) as upstream:
      async def receive():
        async for message in upstream:
          event=voice.stream_event(message)
          if event and event.get('transcript'):transcripts.append(event['transcript'])
      reader=asyncio.create_task(receive())
      for i in range(0,len(pcm),1024):
        await upstream.send(pcm[i:i+1024].ljust(1024,b'\0'));await asyncio.sleep(.024)
      for _ in range(60):await upstream.send(bytes(1024));await asyncio.sleep(.024)
      await asyncio.sleep(2);reader.cancel();await asyncio.gather(reader,return_exceptions=True)
    assess(transcripts,report,hashlib.sha256(pcm).hexdigest())

def assess(transcripts,report,pcm_hash=None):
    text=' '.join(transcripts).lower()
    checks={name:phrase in text for name,phrase in [('product','relay'),('workflow','workflow'),('correction','saturday'),('context','context')]}
    # STT formats spoken numbers as digits and may transliterate proper names.
    checks['preferred_time']=bool(re.search(r'\bsaturday\b.{0,30}\b(?:two|2)\b',text))
    checks['removed_name_absent']=not bool(re.search(r'bi[fv]rost|byfrost|by frost|brifort|bifort',text))
    result={'passed':all(checks.values()),'checks':checks,'transcript':transcripts,'pcm_sha256':pcm_hash,'method':'Final rendered mix → real Gnani STT; no physical microphone'}
    report.write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'checks':checks}))
    if not result['passed']:raise RuntimeError('Review the final audio transcript.')
asyncio.run(main())
