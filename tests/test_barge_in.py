import hashlib
import asyncio
from concurrent.futures import CancelledError, ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import wave
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from app.main import create_app
from app.memory import history_context, memory_context, update_memory
from app.vad import SileroVad
from test_gnani import FakeStreamingVoice


class BargeInTests(unittest.TestCase):
    def test_interrupt_cancels_inflight_model_and_allows_new_turn(self):
        started=threading.Event()
        class DelayedVoice(FakeStreamingVoice):
            async def reply(self,call):
                if call['transcript'][-1]['text']=='Initial question':
                    started.set()
                    await asyncio.sleep(20)
                return 'Responding to the latest correction.'
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'APP_ENV':'local','DEMO_PASSWORD':''}):
            with TestClient(create_app(temp+'/db.sqlite',voice_engine=DelayedVoice())) as c,ThreadPoolExecutor(max_workers=1) as pool:
                call=c.post('/api/calls',json={'agent_id':'demo-sales','contact_id':'contact-1','mode':'browser'}).json()
                route='/api/calls/'+call['id']
                old=pool.submit(c.post,route+'/voice/respond/stream',json={'text':'Initial question','request_id':'slow'})
                self.assertTrue(started.wait(3))
                self.assertEqual(c.post(route+'/voice/interrupt',json={'request_id':'slow'}).status_code,200)
                new=c.post(route+'/voice/respond/stream',json={'text':'Correction, Friday instead','request_id':'new'})
                self.assertEqual(new.status_code,200)
                try: old.result(timeout=3)
                except CancelledError: pass
                saved=c.get(route).json()
                self.assertFalse(any(t.get('response_id')=='slow' and t['role']=='agent' for t in saved['transcript']))
                self.assertIn('Friday',memory_context(saved))

    def test_bundled_model_matches_pinned_upstream(self):
        model = Path(__file__).parent.parent / "app/models/silero_vad_v5.onnx"
        self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(), "2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f")

    def test_real_silero_rejects_silence_and_seeded_noise(self):
        vad = SileroVad()
        for _ in range(50):
            self.assertIsNone(vad.process(bytes(1024), playback=True))
        noise = (np.random.default_rng(7).normal(0, .02, 32000) * 32767).astype('<i2').tobytes()
        for i in range(0, len(noise), 1024):
            self.assertIsNone(vad.process(noise[i:i+1024].ljust(1024,b'\0'), playback=True))
        # Short loud impulses approximate taps/clicks, not spoken syllables.
        clicks=np.zeros(32000,dtype='<i2')
        clicks[::1600]=25000
        vad=SileroVad()
        for i in range(0,len(clicks)*2,1024):
            self.assertIsNone(vad.process(clicks.tobytes()[i:i+1024].ljust(1024,b'\0'),playback=True))

    def test_real_silero_detects_speech_during_playback_and_has_isolated_state(self):
        a, b = SileroVad(), SileroVad()
        self.assertIs(a.session, b.session)
        with wave.open(str(Path(__file__).parent / 'fixtures/synthetic-speech.wav'),'rb') as f:
            pcm = f.readframes(f.getnframes())
        events=[]
        for i in range(0,len(pcm),1024):
            event=a.process(pcm[i:i+1024].ljust(1024,b'\0'),playback=True)
            if event: events.append(event)
        self.assertTrue(any(e['type']=='vad_speech_start' for e in events))
        self.assertTrue(np.array_equal(b.state,np.zeros((2,1,128),dtype=np.float32)))
        self.assertIsNone(b.process(bytes(1024)))

    def test_memory_keeps_earlier_details_and_later_corrections(self):
        call={'transcript':[{'role':'customer','text':'My dealership receives fifty leads weekly.'}]}
        for i in range(15):
            call['transcript'] += [{'role':'agent','text':'Tell me more.'},{'role':'customer','text':f'Additional context {i}.'}]
        call['transcript'].append({'role':'customer','text':'Correction: make the visit Friday, not Monday.'})
        update_memory(call)
        self.assertIn('fifty leads',memory_context(call))
        self.assertIn('Friday, not Monday',memory_context(call))
        self.assertNotIn('fifty leads',json.dumps(list(history_context(call))))
        call['transcript'].append({'role':'agent','text':'SECRET UNHEARD ENDING','delivery_status':'interrupted'})
        self.assertNotIn('SECRET UNHEARD ENDING',json.dumps(list(history_context(call))))

    def test_interruption_annotates_history_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'APP_ENV':'local','DEMO_PASSWORD':''}):
            path=temp+'/db.sqlite'
            with TestClient(create_app(path,voice_engine=FakeStreamingVoice())) as c:
                call=c.post('/api/calls',json={'agent_id':'demo-booking','contact_id':'contact-1','mode':'browser'}).json()
                route='/api/calls/'+call['id']
                response=c.post(route+'/voice/respond/stream',json={'text':'Monday at ten','request_id':'first-response'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(c.post(route+'/voice/interrupt',json={'request_id':'first-response','played_ms':420}).status_code,200)
                call=c.get(route).json()
                self.assertEqual(call['transcript'][-1]['delivery_status'],'interrupted')
                self.assertEqual(call['transcript'][-1]['played_ms'],420)
                c.post(route+'/voice/respond/stream',json={'text':'Actually Friday at eleven instead','request_id':'correction'})
                self.assertEqual(c.post(route+'/voice/respond/stream',json={'text':'duplicate','request_id':'correction'}).status_code,409)
                second=c.post('/api/calls',json={'agent_id':'demo-booking','contact_id':'contact-1','mode':'browser'}).json()
                self.assertEqual(second['memory']['customer_notes'],[])
            with TestClient(create_app(path,voice_engine=FakeStreamingVoice())) as c:
                call=c.get(route).json()
                self.assertIn('Friday',memory_context(call))
                self.assertEqual(call['interruptions'],1)

    def test_opening_can_be_interrupted_and_cancelled_response_cannot_start_late(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'APP_ENV':'local','DEMO_PASSWORD':''}):
            with TestClient(create_app(temp+'/db.sqlite',voice_engine=FakeStreamingVoice())) as c:
                call=c.post('/api/calls',json={'agent_id':'demo-sales','contact_id':'contact-1','mode':'browser'}).json()
                route='/api/calls/'+call['id']
                c.post(route+'/voice/interrupt',json={'request_id':'opening:'+call['id']})
                self.assertEqual(c.get(route).json()['transcript'][0]['delivery_status'],'interrupted')
                c.post(route+'/voice/interrupt',json={'request_id':'cancelled-before-start','customer_text':'I need a service visit Monday'})
                self.assertEqual(c.post(route+'/voice/respond/stream',json={'text':'too late','request_id':'cancelled-before-start'}).status_code,409)
                self.assertIn('service visit Monday',memory_context(c.get(route).json()))
