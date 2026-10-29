"""Generate fictional demo configuration and Gnani narration with server-only keys."""
import asyncio,json,sys,wave,subprocess,os
from dataclasses import replace
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=False)
from app.gnani import GnaniVoiceEngine
from app.store import Store
from app.seed import seed
from app.engine import DemoProvider,now
from app.memory import update_memory
AUDIO=ROOT/'video/public/audio';AUDIO.mkdir(parents=True,exist_ok=True)
if '--narration-only' not in sys.argv:
    STORE=Store(ROOT/'runtime/hackathon-video.sqlite');seed(STORE)
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date()
    friday=today+timedelta(days=(4-today.weekday())%7)
    saturday=today+timedelta(days=(5-today.weekday())%7)
    calendar_facts=f' Calendar facts: the upcoming Friday is {friday.isoformat()}; the upcoming Saturday is {saturday.isoformat()}. Use weekday and spoken time only in replies; never add a numerical calendar date.'
    with STORE.transaction() as db:
        # Replace only the fixed recording fixtures; no activity is invented as live.
        agent=Store.get(db,'agents','demo-booking')
        agent.update(name='Nisha',language='English',role='Appointment intake for Meridian Auto',industry='Automobile service',delivery='warm',
          opening="Hi Riya, I'm Nisha, an AI assistant at Meridian Auto. Which service and time would you prefer?",
          question='What time would suit you?',
          context='Fictional demo business: Meridian Auto, a car service centre in Pune. Routine servicing and vehicle inspections. Hours Monday to Saturday, nine in the morning to six in the evening. All appointment times use Asia/Kolkata. No calendar connection: record a request only; the team must confirm availability. Customer Riya wants a routine car service.'+calendar_facts,
          prompt='Disclose AI in the opening. Collect service, date and time, then read back the request. Keep each response under twenty-five words. Prefer the latest correction. Do not repeat questions already answered. Read back only the weekday and time, such as Friday at eleven or Saturday at two. Do not add a calendar date or numerical date. Never claim a confirmed booking: the team checks availability. Do not ask for payment or private identifiers.')
        Store.put(db,'agents',agent)
        names=['Riya Shah','Kabir Mehta','Ananya Rao','Arjun Nair','Meera Iyer','Dev Kapoor']
        for i,name in enumerate(names):
          Store.put(db,'contacts',dict(id=f'video-contact-{i}',name=name,company='Meridian Auto · demo',phone=f'+1202555010{i}',email=f'guest{i}@example.com',segment='Service enquiries',consent=True,do_not_call=False,notes='Fictional recording participant. Not a real customer.',created_at=now()))
        # Genuine offline engine outputs, visibly labelled as typed simulations.
        provider=DemoProvider()
        for i in range(1,5):
          contact=Store.get(db,'contacts',f'video-contact-{i}')
          a=Store.get(db,'agents',['demo-sales','demo-helper','demo-cx','demo-booking'][i-1])
          c=dict(id=f'video-simulation-{i}',mode='demo',source='interactive',status='in_progress',outcome=None,agent_id=a['id'],contact_id=contact['id'],agent_snapshot=a,contact_snapshot=contact,started_at=now(),ended_at=None,step=0,transcript=provider.start(a,contact),summary='',next_action='',workflow_id=None)
          for words in ['I would like more information','We need help with customer enquiries','Yes please']:
            provider.turn(c,words)
          update_memory(c);Store.put(db,'calls',c)
clips={
'intro':'Every enquiry needs a response. Relay Voice turns your business context into an AI voice conversation.',
'configure':'Choose a workflow. Set the language, instructions, and business facts. Here, Nisha handles vehicle service requests.',
'liveintro':'Now, a live conversation. Watch the time change.',
'review':'The latest correction stays in memory. Review the transcript and follow-up request, without losing the context.',
'outro':'Powered by Gnani speech, Relay Voice brings natural AI conversations to sales, customer support, and appointment intake. Try the demo.',
'customer-one':'Routine car service, this Friday at eleven please.',
'customer-two':'Actually, Saturday at two instead.',
}
previous=json.loads((AUDIO/'script.json').read_text()) if (AUDIO/'script.json').exists() else {}
cast_path=AUDIO/'voices.json'
previous_cast=json.loads(cast_path.read_text()) if cast_path.exists() else {}
async def main():
    voice=GnaniVoiceEngine();voice.require_ready()
    narrator=GnaniVoiceEngine(gnani_config=replace(voice.gnani,voice=os.getenv('VIDEO_NARRATOR_VOICE','Yashraj'),speed=1.05))
    cast=dict(previous_cast)
    for name,text in clips.items():
      customer=name.startswith('customer-')
      if customer and '--narration-only' in sys.argv:continue
      selected=voice if customer else narrator
      identity={'voice':selected.gnani.voice,'model':selected.gnani.tts_model,'speed':selected.gnani.speed}
      changed=previous_cast.get(name)!=identity if not customer else previous_cast.get(name) not in (None,identity)
      target=AUDIO/(name+'.wav')
      if not target.exists() or previous.get(name)!=text or changed:
        target.write_bytes(await selected.speak(text,'English','warm'))
      cast[name]=identity
      # Gnani's streaming WAV header advertises an unknown payload length.
      normalized=target.with_suffix('.normalized.wav')
      subprocess.run(['ffmpeg','-v','error','-y','-i',str(target),'-af','loudnorm=I=-17:TP=-2:LRA=7','-ar','24000','-ac','1',str(normalized)],check=True)
      normalized.replace(target)
      with wave.open(str(target),'rb') as f: duration=f.getnframes()/f.getframerate()
      print(f'{name}: {identity["voice"]}, {duration:.2f}s')
    (ROOT/'video/public/audio/script.json').write_text(json.dumps(clips,indent=2))
    cast_path.write_text(json.dumps(cast,indent=2))
asyncio.run(main())
