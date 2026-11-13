import test from 'node:test';
import assert from 'node:assert/strict';
import {VoiceSession} from '../static/voice-session.js';

function setup(fetchImpl=async()=>{throw new Error('Unexpected request');}){
 const calls=[],statuses=[],created=[];
 const session=new VoiceSession({api:async(...args)=>calls.push(args),onStatus:x=>statuses.push(x),fetchImpl});
 session.closed=false;session.call={id:'call-one'};session.paused=false;
 session.context={currentTime:1,destination:{},close:async()=>{},
  createBuffer:(_,size,rate)=>({duration:size/rate,getChannelData:()=>new Float32Array(size)}),
  createBufferSource:()=>{const source={connect(){},start(){},stop(){source.stopped=true;}};created.push(source);return source;},
 };
 session.socket={readyState:1,send(){},close(){}};
 return {session,calls,statuses,created};
}
const audio=Buffer.from([1,0,2,0]).toString('base64');

test('finishing the opening does not report an empty-source playback error',async()=>{
 const {session,statuses}=setup();
 const previousAudio=globalThis.Audio;let player;
 globalThis.Audio=class{
  constructor(){player=this;}
  async play(){} pause(){}
  set src(value){if(value==='')this.onerror?.();}
 };
 try{
  session.activeId='opening:call-one';
  await session.playFile(audio,'audio/wav',session.epoch);
  player.onended();
  assert.equal(statuses.at(-1),'Listening… speak naturally.');
  assert.equal(statuses.some(s=>s.includes('failed')),false);
  assert.equal(session.activeId,null);
 }finally{globalThis.Audio=previousAudio;await session.close();}
});

test('a recognized customer turn stops queued audio and aborts the old response',async()=>{
 const {session,calls,created}=setup();
 session.epoch=3;session.activeId='old-response';session.processing=true;session.speakingText='Which day suits you?';
 const controller=new AbortController();session.controller=controller;
 session.schedule(audio,24000,3);
 session.receive({type:'vad_speech_start',engine:'silero-v5'});
 assert.equal(controller.signal.aborted,false,'voice activity alone only lowers the volume');
 session.receive({type:'Turn',transcript:'Friday at eleven',end_of_turn:true,turn_order:'barge'});
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

test('speaker echo of the opening is ignored; real speech interrupts it',async()=>{
 const {session,calls}=setup();let paused=false;
 session.activeId='opening:call-one';session.playing=true;
 session.speakingText='नमस्ते Demo, मैं मीरा, Relay Voice की AI assistant हूँ।';
 session.player={pause(){paused=true;},src:'blob:test',volume:1};
 session.receive({type:'vad_speech_start'});
 assert.equal(session.player.volume,0.2);
 // Transcript recorded on 13 Nov when laptop speakers fed the greeting back into the mic.
 session.receive({type:'Turn',transcript:'नमस्ते demo में मेरा।',end_of_turn:true,turn_order:'echo'});
 assert.equal(paused,false);
 assert.equal(session.player.volume,1);
 assert.equal(session.queue.length,0);
 session.receive({type:'Turn',transcript:'Mujhe booking karni hai',end_of_turn:true,turn_order:'real'});
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

test('speech endpoint and provider timings are sent with the recognized turn',async()=>{
 const requests=[];
 const events=[{type:'reply',call:{id:'call-one',transcript:[]}},{type:'audio',audio,sample_rate:24000},{type:'complete'}];
 const {session}=setup(async(url,options)=>{
  requests.push(JSON.parse(options.body));
  return new Response(events.map(x=>JSON.stringify(x)+'\n').join(''),{status:200});
 });
 session.receive({type:'vad_speech_end'});
 session.receive({type:'Turn',transcript:'Thursday afternoon',end_of_turn:true,turn_order:'timed',stt_ms:284});
 await new Promise(resolve=>setTimeout(resolve,120));
 assert.equal(requests[0].stt_provider_ms,284);
 assert.equal(Number.isInteger(requests[0].asr_ms),true);
 assert.equal(requests[0].asr_ms>=0,true);
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

test('a prefetched backchannel fills a slow response gap without replacing the reply',async()=>{
 const events=[{type:'reply',call:{id:'call-one',transcript:[]}},{type:'audio',audio,sample_rate:24000},{type:'complete'}];
 const {session,created}=setup(async()=>{
  await new Promise(resolve=>setTimeout(resolve,30));
  return new Response(events.map(x=>JSON.stringify(x)+'\n').join(''),{status:200});
 });
 session.backchannel={audio,sample_rate:24000};session.backchannelDelay=5;
 session.queue.push('Please help with my appointment');
 await session.drain();
 assert.equal(created.length,2);
 assert.equal(session.backchannelTurns,1);
 await session.close();
});

test('backchannel is skipped when the customer opts out',async()=>{
 const events=[{type:'reply',call:{id:'call-one',transcript:[]}},{type:'audio',audio,sample_rate:24000},{type:'complete'}];
 const {session,created}=setup(async()=>{
  await new Promise(resolve=>setTimeout(resolve,20));
  return new Response(events.map(x=>JSON.stringify(x)+'\n').join(''),{status:200});
 });
 session.backchannel={audio,sample_rate:24000};session.backchannelDelay=5;
 session.queue.push('Stop calling me, I am not interested');
 await session.drain();
 assert.equal(created.length,1);
 assert.equal(session.backchannelTurns,0);
 await session.close();
});

test('server idle close pauses the microphone instead of reconnecting',async()=>{
 const {session,statuses}=setup();
 const previous={WebSocket:globalThis.WebSocket,location:globalThis.location};let socket;
 globalThis.location={protocol:'http:',host:'test'};
 globalThis.WebSocket=class{constructor(){socket=this;this.readyState=1;} send(){} close(){}};
 try{
  const connected=session.connect();
  socket.onmessage({data:JSON.stringify({type:'ready'})});await connected;
  socket.onclose({code:4408});
  assert.equal(session.paused,true);
  assert.equal(session.reconnectTimer,undefined);
  assert.match(statuses.at(-1),/without speech/);
 }finally{Object.assign(globalThis,previous);await session.close();}
});

test('streamed chunks play back to back after a jitter lead, and re-buffer after a gap',async()=>{
 const {session,created}=setup();
 session.epoch=1;session.activeId='reply';
 const starts=[];session.context.createBufferSource=()=>{const s={connect(){},start(t){starts.push(t);},stop(){}};created.push(s);return s;};
 session.schedule(audio,24000,1);session.schedule(audio,24000,1);
 assert.equal(starts[0],1.12);
 assert.equal(starts[1],1.12+2/24000);
 session.context.currentTime=5;session.schedule(audio,24000,1);
 assert.equal(starts[2],5.12);
 await session.close();
});
