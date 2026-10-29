import tempfile
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
from tests.test_voice import FakeVoiceEngine


class Extractor:
    async def __call__(self, call):
        return {'service':{'value':'car service','quote':'Routine car service, Friday at eleven.','turn_index':1},
                'preferred_day':{'value':'Saturday','quote':'Actually Saturday at two instead.','turn_index':3},
                'preferred_time':{'value':'two','quote':'Actually Saturday at two instead.','turn_index':3}}


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=self.tmp.name+'/test.sqlite'
        self.client=TestClient(create_app(self.path,voice_engine=FakeVoiceEngine(),request_extractor=Extractor()))
        self.client.__enter__()
        self.call=self.client.post('/api/calls',json={'agent_id':'demo-booking','contact_id':'contact-1','mode':'browser'}).json()
        self.id=self.call['id'];self.url=f'/api/calls/{self.id}/request'
        with Store(self.path).transaction() as db:
            call=Store.get(db,'calls',self.id)
            call['transcript'] += [
                {'role':'customer','text':'Routine car service, Friday at eleven.'},
                {'role':'agent','text':'I have booked Friday at eleven.'},
                {'role':'customer','text':'Actually Saturday at two instead.'}]
            Store.put(db,'calls',call)
        self.client.post(f'/api/calls/{self.id}/end')

    def tearDown(self):
        self.client.__exit__(None,None,None);self.tmp.cleanup()

    def extract(self):
        return self.client.post(self.url+'/extract',json={'revision':0})

    def review(self,revision=0):
        return self.client.put(self.url,json={'revision':revision,'fields':{'service':'car service','preferred_day':'Saturday','preferred_time':'two'},'owner':'Service desk','notes':'Check availability; time of day needs clarification.'})

    def test_correction_is_suggested_not_booked_and_requires_review(self):
        r=self.extract();self.assertEqual(r.status_code,200,r.text)
        result=r.json();self.assertEqual(result['request']['fields']['preferred_day'],'Saturday')
        self.assertEqual(result['request']['fields']['preferred_time'],'two')
        self.assertEqual(result['request']['fields']['timezone'],'')
        self.assertEqual(result['request']['status'],'needs_review')
        self.assertEqual(result['integrations']['calendar']['status'],'disabled')
        self.assertEqual(self.client.post(self.url+'/follow-up',json={'revision':1}).status_code,409)
        self.assertEqual(self.client.get(f'/api/calls/{self.id}').json()['outcome'],'follow_up')

    def test_review_and_followup_idempotency_persist_after_restart(self):
        self.assertEqual(self.review().status_code,200)
        a=self.client.post(self.url+'/follow-up',json={'revision':1});self.assertEqual(a.status_code,200,a.text)
        b=self.client.post(self.url+'/follow-up',json={'revision':1})
        self.assertEqual(a.json()['lead']['id'],b.json()['lead']['id'])
        with Store(self.path).transaction() as db:
            self.assertEqual(len(Store.all(db,'leads')),1)
            self.assertEqual(len(Store.all(db,'tasks')),1)
        with TestClient(create_app(self.path)) as restarted:
            result=restarted.get(self.url).json()
            self.assertEqual(result['lead']['sync_status'],'not_connected')
            self.assertEqual(result['request']['fields']['preferred_day'],'Saturday')
            self.assertEqual(len(result['request']['audit']),2)

    def test_stale_edits_and_unexpected_external_fields_are_rejected(self):
        self.assertEqual(self.review().status_code,200)
        self.assertEqual(self.review().status_code,409)
        self.assertEqual(self.client.put(self.url,json={'revision':1,'fields':{},'booking_status':'confirmed'}).status_code,422)
        self.assertEqual(self.client.post(self.url+'/extract',json={'revision':0}).status_code,409)

    def test_opt_out_after_review_blocks_followup(self):
        self.review()
        with Store(self.path).transaction() as db:
            contact=Store.get(db,'contacts','contact-1');contact['do_not_call']=True;Store.put(db,'contacts',contact)
        self.assertEqual(self.client.post(self.url+'/follow-up',json={'revision':1}).status_code,409)

    def test_open_calls_cannot_be_reviewed_and_bad_timezone_is_rejected(self):
        other=self.client.post('/api/calls',json={'agent_id':'demo-booking','contact_id':'contact-1'}).json()
        self.assertEqual(self.client.put(f"/api/calls/{other['id']}/request",json={'revision':0,'fields':{'service':'Repair'}}).status_code,409)
        self.assertEqual(self.client.put(self.url,json={'revision':0,'fields':{'service':'Repair','timezone':'made-up'}}).status_code,422)

    def test_failed_model_keeps_operator_review_and_hides_provider_error(self):
        self.review()
        before=self.client.get(self.url).json()
        async def broken(call):
            raise RuntimeError('private-provider-token')
        with TestClient(create_app(self.path,request_extractor=broken)) as client:
            response=client.post(self.url+'/extract',json={'revision':1})
            self.assertEqual(response.status_code,503)
            self.assertNotIn('private-provider-token',response.text)
            self.assertEqual(client.get(self.url).json(),before)

    def test_slow_extraction_cannot_overwrite_an_intervening_review(self):
        async def concurrent(call):
            self.assertEqual(self.review().status_code,200)
            return await Extractor()(call)
        with TestClient(create_app(self.path,request_extractor=concurrent)) as client:
            response=client.post(self.url+'/extract',json={'revision':0})
            self.assertEqual(response.status_code,409)
            self.assertEqual(client.get(self.url).json()['request']['source'],'operator')

    def test_later_review_updates_same_lead_and_marks_old_lead_revision(self):
        self.review()
        lead=self.client.post(self.url+'/follow-up',json={'revision':1}).json()['lead']
        reviewed=self.client.put(self.url,json={'revision':1,'fields':{'service':'car service','preferred_day':'Sunday'},'owner':'Service desk'}).json()
        self.assertNotEqual(reviewed['request']['revision'],reviewed['lead']['request_revision'])
        updated=self.client.post(self.url+'/follow-up',json={'revision':2}).json()['lead']
        self.assertEqual(updated['id'],lead['id'])
        self.assertEqual(updated['created_at'],lead['created_at'])
        self.assertEqual(updated['fields']['preferred_day'],'Sunday')



class EvidenceTests(unittest.TestCase):
    def test_agent_claims_guesses_and_unknown_fields_are_rejected(self):
        from app.requests import grounded_fields
        call={'transcript':[{'role':'customer','text':'Saturday at two'}, {'role':'agent','text':'Confirmed booking'}]}
        for raw in [
            {'preferred_time':{'value':'14:00','quote':'Saturday at two','turn_index':0}},
            {'service':{'value':'booking','quote':'Confirmed booking','turn_index':1}},
            {'preferred_day':{'value':'Friday','quote':'Friday','turn_index':0}},
            {'confirmed':True},
        ]:
            with self.assertRaises(ValueError):grounded_fields(raw,call)

    def test_hindi_evidence_is_preserved_without_inventing_timezone(self):
        from app.requests import grounded_fields
        quote='नहीं, शनिवार को दो बजे चाहिए।'
        fields,evidence=grounded_fields({'preferred_day':{'value':'शनिवार','quote':quote,'turn_index':0},'preferred_time':{'value':'दो बजे','quote':quote,'turn_index':0}}, {'transcript':[{'role':'customer','text':quote}]})
        self.assertEqual(fields['preferred_day'],'शनिवार');self.assertEqual(fields['timezone'],'')
        self.assertEqual(evidence['preferred_time']['quote'],quote)

    def test_real_model_adapter_uses_existing_authenticated_endpoint(self):
        import asyncio,json,httpx
        from app.voice import VoiceEngine,VoiceConfig
        from app.requests import grounded_fields
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json={'choices':[{'message':{'content':'{"preferred_day":{"value":"Saturday","quote":"Saturday at two","turn_index":1}}'}}]})
        config=VoiceConfig('','test-key','https://gateway.example/v1','test-model','','','')
        async def check():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                engine=VoiceEngine(config=config,client=client)
                call={'transcript':[{'role':'agent','text':'Booked Friday'}, {'role':'customer','text':'Saturday at two'}]}
                raw=await engine.extract_request(call)
                self.assertEqual(grounded_fields(raw,call)[0]['preferred_day'],'Saturday')
        asyncio.run(check())
        self.assertEqual(calls[0].url.path,'/v1/chat/completions')
        self.assertEqual(calls[0].headers['x-bf-vk'],'test-key')
        payload=json.loads(calls[0].content)
        self.assertNotIn('Booked Friday',payload['messages'][1]['content'])
