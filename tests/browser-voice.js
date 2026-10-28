import {VoiceSession} from '/static/voice-session.js';
const status=document.querySelector('#status'),result=document.querySelector('#result');
async function api(path,method='GET',body){
 const response=await fetch('/api'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 if(!response.ok)throw new Error('API request failed: '+response.status);
 return response.json();
}
document.querySelector('#start').onclick=async()=>{
 document.querySelector('#start').disabled=true;
 let session,context,timeout,call,injections=0,replies=0,scheduled=false,awaitingVad=false,injectionAt=0;
 const cutoffs=[],seenResponses=new Set();
 try{
  context=new AudioContext();await context.resume();
  const microphone=context.createMediaStreamDestination();
  const corrections=[];
  for(const name of ['correction.wav','second-correction.wav']){
   const bytes=await (await fetch('/test-assets/fixtures/'+name)).arrayBuffer();
   corrections.push(await context.decodeAudioData(bytes));
  }
  session=new VoiceSession({api,getMicrophone:async()=>microphone.stream,
   onStatus:message=>{
    status.textContent=message;
    if(message==='Listening… go ahead.'&&awaitingVad){cutoffs.push(Math.round(performance.now()-injectionAt));awaitingVad=false;}
    if(message.startsWith('AI is speaking')&&injections===replies&&injections<2&&!scheduled){
     scheduled=true;setTimeout(()=>{const source=context.createBufferSource();source.buffer=corrections[injections++];source.connect(microphone);injectionAt=performance.now();awaitingVad=true;source.start();scheduled=false;},650);
    }
   },
   onCall:async value=>{
    const responseId=value.transcript.at(-1)?.response_id;
    if(responseId&&!seenResponses.has(responseId)&&value.transcript.some(t=>t.role==='customer')){
     seenResponses.add(responseId);replies++;
     if(replies<2)return;
     const saved=await api('/calls/'+call.id);
     const interrupted=saved.transcript[0].delivery_status==='interrupted';
     const streamedInterrupted=saved.transcript.filter(t=>t.role==='agent'&&t.delivery_status==='interrupted').length>=2;
     result.textContent=JSON.stringify({passed:cutoffs.length>=2&&interrupted&&streamedInterrupted&&saved.memory.customer_notes.length>=2,silero_speech_events:cutoffs.length,opening_interrupted:interrupted,streamed_reply_interrupted:streamedInterrupted,cutoff_from_synthetic_speech_ms:cutoffs,customer_words:saved.transcript.filter(t=>t.role==='customer').map(t=>t.text),memory_notes:saved.memory.customer_notes.length,reply:saved.transcript.at(-1).text},null,2);
     clearTimeout(timeout);
     setTimeout(async()=>{await session.close();await api('/calls/'+call.id+'/end','POST');await context.close();status.textContent='Validation complete';},2000);
    }
   },onError:message=>{status.textContent=message;result.textContent='FAILED: '+message;},
  });
  call=await api('/calls','POST',{agent_id:'demo-booking',contact_id:'contact-1',mode:'browser'});
  const settings=(await api('/state')).settings;
  timeout=setTimeout(async()=>{result.textContent='FAILED: timed out';await session.close();await context.close();},45000);
  await session.start(call,settings);
 }catch(error){clearTimeout(timeout);result.textContent='FAILED: '+error.message;await session?.close();if(context&&context.state!=='closed')await context.close();}
};
