import test from 'node:test';
import assert from 'node:assert/strict';
import {VoiceSession} from '../static/voice-session.js';

function setup(fetchImpl=async()=>{throw new Error('Unexpected request');}){
 const calls=[],statuses=[],created=[];
 const session=new VoiceSession({api:async(...args)=>calls.push(args),onStatus:x=>statuses.push(x),fetchImpl});
 session.closed=false;session.call={id:'call-one'};session.streaming=true;session.paused=false;
 session.context={currentTime:1,destination:{},close:async()=>{},
  createBuffer:(_,size,rate)=>({duration:size/rate,getChannelData:()=>new Float32Array(size)}),
  createBufferSource:()=>{const source={connect(){},start(){},stop(){source.stopped=true;}};created.push(source);return source;},
 };
 session.socket={readyState:1,send(){},close(){}};
 return {session,calls,statuses,created};
}
const audio=Buffer.from([1,0,2,0]).toString('base64');

test('Silero speech event immediately stops queued audio and aborts the old response',async()=>{
 const {session,calls,created}=setup();
 session.epoch=3;session.activeId='old-response';session.processing=true;
 const controller=new AbortController();session.controller=controller;
 session.schedule(audio,24000,3);
 session.receive({type:'vad_speech_start',engine:'silero-v5'});
 assert.equal(controller.signal.aborted,true);
 assert.equal(created[0].stopped,true);
 assert.equal(session.sources.size,0);
 assert.equal(session.processing,false);
 await session.interruptAck;
 assert.equal(calls[0][0],'/calls/call-one/voice/interrupt');
 assert.equal(calls[0][2].request_id,'old-response');
 // A late chunk / onended from the abandoned generation cannot restart audio.
 session.schedule(audio,24000,3);
 created[0].onended();
 assert.equal(created.length,1);
 await session.close();
});

test('speech can interrupt the opening while the AI voice is playing',async()=>{
 const {session,calls}=setup();let paused=false;
 session.activeId='opening:call-one';session.player={pause(){paused=true;},src:'blob:test'};
 session.receive({type:'vad_speech_start'});
 assert.equal(paused,true);
 assert.equal(session.player,null);
 await session.interruptAck;
 assert.equal(calls[0][2].request_id,'opening:call-one');
 await session.close();
});

test('recognized interruption words become the next request after cancellation acknowledgment',async()=>{
 const requests=[];
 const {session}=setup(async(url,options)=>{
  requests.push({url,body:JSON.parse(options.body)});
  const events=[{type:'reply',call:{id:'call-one',transcript:[]}},{type:'audio',audio,sample_rate:24000},{type:'complete'}];
  return new Response(events.map(x=>JSON.stringify(x)+'\n').join(''),{status:200});
 });
 let release;
 session.api=()=>new Promise(resolve=>release=resolve);
 session.activeId='old-response';session.processing=true;
 session.receive({type:'vad_speech_start'});
 session.receive({type:'Turn',transcript:'Actually Friday at eleven',end_of_turn:true,turn_order:'segment-2'});
 await new Promise(resolve=>setTimeout(resolve,100));
 assert.equal(requests.length,0);
 release();
 await new Promise(resolve=>setTimeout(resolve,30));
 assert.equal(requests.length,1);
 assert.equal(requests[0].body.text,'Actually Friday at eleven');
 assert.notEqual(requests[0].body.request_id,'old-response');
 await session.close();
});

test('duplicate final transcripts do not create duplicate AI replies',async()=>{
 let requests=0;
 const {session}=setup(async()=>{requests++;return new Response('{"type":"complete"}\n');});
 const message={type:'Turn',transcript:'Yes please',end_of_turn:true,turn_order:'same-segment'};
 session.receive(message);session.receive(message);
 await new Promise(resolve=>setTimeout(resolve,120));
 assert.equal(requests,1);
 await session.close();
});

test('pause suppresses new turns and teardown stops microphone tracks',async()=>{
 const {session}=setup();let stopped=false;
 session.media={getTracks:()=>[{stop(){stopped=true;}}]};
 await session.toggle();
 session.receive({type:'Turn',transcript:'background words',end_of_turn:true});
 assert.equal(session.queue.length,0);
 await session.close();assert.equal(stopped,true);assert.equal(session.socket,null);
});

test('reconnected speech streams can reuse provider turn numbers',async()=>{
 let requests=0;
 const {session}=setup(async()=>{requests++;return new Response('{"type":"complete"}\n');});
 const previousSocket=globalThis.WebSocket,previousLocation=globalThis.location;
 try{
  globalThis.location={protocol:'https:',host:'demo.example'};
  globalThis.WebSocket=class{
   readyState=1;
   constructor(){queueMicrotask(()=>this.onmessage({data:'{"type":"ready"}'}));}
   send(){} close(){}
  };
  session.receive({type:'Turn',transcript:'First preference',end_of_turn:true,turn_order:1});
  await new Promise(resolve=>setTimeout(resolve,120));
  await session.connect();
  session.socket.onmessage({data:JSON.stringify({type:'Turn',transcript:'Corrected preference',end_of_turn:true,turn_order:1})});
  await new Promise(resolve=>setTimeout(resolve,120));
  assert.equal(requests,2);
 }finally{
  await session.close();globalThis.WebSocket=previousSocket;globalThis.location=previousLocation;
 }
});
