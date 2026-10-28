import {$,esc,title,date,icon,badge,api,toast,dialog,basePath} from './ui.js';
import * as V from './views.js';
import {editAgent,editContact,editWorkflow} from './forms.js';
let data,page='overview',currentCall=null,selectedAgent='agent-sales',query='',filter='all',busy=false;
let mediaStream=null,audioPlayer=null,lastAudio=null,audioContext=null,micPaused=false,sttSocket=null,processor=null,streamMuted=true,handledTurns=new Set();
let responseAbort=null,pcmSources=new Set(),pcmUntil=0,voiceGeneration=0;
const find=(kind,id)=>data[kind].find(x=>x.id===id);
async function refresh(){data=await api('/state');render()}
function render(){
 const renderers={demos:()=>V.demos(data),overview:()=>V.overview(data),agents:()=>V.agents(data),contacts:()=>V.contacts(data,query),studio:()=>V.studio(data,currentCall,selectedAgent),workflows:()=>V.workflows(data),history:()=>V.history(data,query,filter),analytics:()=>V.analytics(data),settings:()=>V.settings(data)};
 $('#app').innerHTML=V.shell(page,renderers[page]());bind();
 document.querySelectorAll('#app a[href^="/api/"]').forEach(a=>a.setAttribute('href',basePath+a.getAttribute('href')));
 if(page==='studio'&&currentCall){const el=$('.transcript');if(el)el.scrollTop=el.scrollHeight;}
}
function navigate(next){if(location.hash==='#'+next){page=next;render()}else location.hash=next}
window.addEventListener('hashchange',()=>{if(location.hash==='#main'){$('#main')?.focus();return}window.scrollTo(0,0);page=V.nav.some(x=>x[0]===location.hash.slice(1))?location.hash.slice(1):'overview';query='';filter='all';if(data)render()});
async function safely(fn,button){if(button)button.disabled=true;try{await fn()}catch(e){toast(e.message)}finally{if(button)button.disabled=false}}
function voiceStatus(message){const el=$('#voice-live-status');if(el)el.textContent=message}
function audioFromBase64(value,type='audio/mpeg'){
 const bytes=Uint8Array.from(atob(value),c=>c.charCodeAt(0));
 return new Blob([bytes],{type});
}
async function playVoice(value,type='audio/mpeg'){
 if(audioPlayer){audioPlayer.pause();audioPlayer=null}
 lastAudio={value,type};
 const url=URL.createObjectURL(audioFromBase64(value,type));
 audioPlayer=new Audio(url);
 audioPlayer.onended=()=>{URL.revokeObjectURL(url);audioPlayer=null;if(currentCall?.mode==='browser'&&currentCall.status==='in_progress'&&!micPaused){streamMuted=false;voiceStatus('Listening… just speak.')}else voiceStatus('Ready.')};
 audioPlayer.onerror=()=>{URL.revokeObjectURL(url);audioPlayer=null;voiceStatus('Audio playback failed. The reply is still saved in the transcript.')};
 try{voiceStatus('AI is speaking…');await audioPlayer.play()}catch{voiceStatus('Playback was blocked. Press Replay last AI reply.')}
}
async function playOpening(){
 if(!currentCall||currentCall.mode!=='browser')return;
 voiceStatus('Preparing the AI voice…');
 const r=await api('/calls/'+currentCall.id+'/voice/opening','POST');
 await playVoice(r.audio,r.content_type);
}
async function sendStreamingTurn(text){
 if(busy||!text.trim())return;busy=true;streamMuted=true;voiceStatus('Thinking…');
 const generation=voiceGeneration;
 if(data.settings.streaming_audio){try{await streamReply(text)}catch(e){if(generation===voiceGeneration){for(const source of pcmSources){try{source.stop()}catch{}}pcmSources.clear();pcmUntil=0;voiceStatus(e.message);toast(e.message)}}finally{if(generation===voiceGeneration){busy=false;if(!pcmSources.size)streamMuted=micPaused;}}return}
 try{const body=await api('/calls/'+currentCall.id+'/voice/respond','POST',{text});currentCall=body.call;await refresh();await playVoice(body.audio,body.content_type)}
 catch(e){voiceStatus(e.message);toast(e.message);streamMuted=false}finally{busy=false}
}
async function streamReply(text){
 const generation=voiceGeneration;
 responseAbort=new AbortController();
 const r=await fetch(`${basePath}/api/calls/${currentCall.id}/voice/respond/stream`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text}),signal:responseAbort.signal});
 if(!r.ok)throw new Error('The voice session could not respond. Check provider configuration.');
 const reader=r.body.getReader(),decoder=new TextDecoder();let pending='',completed=false;
 try{while(true){const {value,done}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done});const lines=pending.split('\n');pending=lines.pop();for(const line of lines){if(!line.trim())continue;const event=JSON.parse(line);if(generation!==voiceGeneration)return;
  if(event.type==='reply'){currentCall=event.call;render();voiceStatus('Preparing voice…');}
  if(event.type==='audio'){const bytes=Uint8Array.from(atob(event.audio),c=>c.charCodeAt(0)),view=new DataView(bytes.buffer);const buffer=audioContext.createBuffer(1,bytes.length/2,event.sample_rate);const channel=buffer.getChannelData(0);for(let i=0;i<channel.length;i++)channel[i]=view.getInt16(i*2,true)/32768;const source=audioContext.createBufferSource();source.buffer=buffer;source.connect(audioContext.destination);pcmUntil=Math.max(audioContext.currentTime+0.04,pcmUntil);source.start(pcmUntil);pcmUntil+=buffer.duration;pcmSources.add(source);source.onended=()=>{pcmSources.delete(source);if(!pcmSources.size&&completed&&generation===voiceGeneration&&!micPaused){streamMuted=false;voiceStatus('Listening… just speak.')}};voiceStatus('AI is speaking…');}
  if(event.type==='complete'){completed=true;voiceStatus(`Reply ready · first audio ${event.first_audio_ms??'—'} ms`);}
  if(event.type==='error')throw new Error(event.message);
 }if(done)break;}if(!completed)throw new Error('The voice stream ended early. Please restart the session.');}
 finally{reader.releaseLock();responseAbort=null;}
}
async function releaseVoice(){
 voiceGeneration++;responseAbort?.abort();responseAbort=null;
 for(const source of pcmSources){try{source.stop()}catch{}}pcmSources.clear();pcmUntil=0;
 micPaused=true;streamMuted=true;sttSocket?.close();sttSocket=null;processor?.disconnect();processor=null;
 audioPlayer?.pause();audioPlayer=null;mediaStream?.getTracks().forEach(t=>t.stop());mediaStream=null;
 if(audioContext)await audioContext.close();audioContext=null;
}
function pcm16(input,inputRate){
 const ratio=inputRate/16000,length=Math.floor(input.length/ratio),out=new Int16Array(length);
 for(let i=0;i<length;i++){const start=Math.floor(i*ratio),end=Math.min(input.length,Math.floor((i+1)*ratio));let sum=0;for(let j=start;j<end;j++)sum+=input[j];const sample=Math.max(-1,Math.min(1,sum/Math.max(1,end-start)));out[i]=sample<0?sample*32768:sample*32767}
 return out.buffer;
}
async function ensureStreaming(){
 if(sttSocket?.readyState===WebSocket.OPEN)return;
 const scheme=location.protocol==='https:'?'wss':'ws';sttSocket=new WebSocket(`${scheme}://${location.host}${basePath}/api/calls/${currentCall.id}/voice/stream`);sttSocket.binaryType='arraybuffer';
 await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>{sttSocket?.close();reject(new Error('Speech recognition timed out. Check provider access.'))},15000);
 sttSocket.onmessage=e=>{const msg=JSON.parse(e.data);if(msg.type==='ready'){clearTimeout(timeout);resolve();return}if(msg.type==='processing'&&!streamMuted)voiceStatus('Understanding…');if(msg.type!=='Turn'||streamMuted||micPaused)return;const text=(msg.transcript||'').trim();if(text&&!msg.end_of_turn)voiceStatus('Hearing: '+text);if(msg.end_of_turn&&text){const key=String(msg.turn_order??text);if(handledTurns.has(key))return;handledTurns.add(key);sendStreamingTurn(text)}};
 sttSocket.onerror=()=>{clearTimeout(timeout);reject(new Error('Realtime transcription could not connect.'))};
 sttSocket.onclose=()=>{clearTimeout(timeout);streamMuted=true;voiceStatus('Speech recognition disconnected. End and restart the session.');reject(new Error('Realtime transcription disconnected.'))};});
 await audioContext.audioWorklet.addModule(`${basePath}/static/pcm-capture.js`);
 processor=new AudioWorkletNode(audioContext,'pcm-capture');const source=audioContext.createMediaStreamSource(mediaStream);source.connect(processor);processor.connect(audioContext.destination);
 processor.port.onmessage=e=>{if(sttSocket?.readyState===WebSocket.OPEN){if(sttSocket.bufferedAmount>64000){streamMuted=true;voiceStatus('Connection is too slow. Restart the session.');sttSocket.close();return}sttSocket.send(streamMuted||micPaused?new ArrayBuffer(1024):e.data)}};
}
async function ensureMicrophone(){
 if(!navigator.mediaDevices?.getUserMedia||!window.AudioContext)throw new Error('This browser does not support realtime microphone audio.');
 if(!mediaStream)mediaStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
 if(!audioContext)audioContext=new AudioContext();
 await audioContext.resume();
}
async function beginListening(){
 if(micPaused||audioPlayer||!currentCall)return;
 await ensureMicrophone();await ensureStreaming();streamMuted=false;voiceStatus('Listening… just speak.');
}
async function toggleVoice(){
 micPaused=!micPaused;
 if(micPaused){streamMuted=true;voiceStatus('Microphone paused.');return}
 await beginListening();
}
async function startVoiceSession(){micPaused=false;streamMuted=true;handledTurns.clear();await ensureMicrophone();await ensureStreaming();await playOpening();
}
function search(input,type){const pos=input.selectionStart;query=input.value;render();const el=$('#'+type+'-search');el.focus();el.setSelectionRange(pos,pos)}
function bind(){
 document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>safely(()=>action(b.dataset.action),b));
 document.querySelectorAll('[data-edit-agent]').forEach(b=>b.onclick=()=>editAgent(find('agents',b.dataset.editAgent),refresh));
 document.querySelectorAll('[data-test-agent]').forEach(b=>b.onclick=()=>{if(currentCall?.status==='in_progress'){toast('End the current simulation before switching agents.');navigate('studio');return}selectedAgent=b.dataset.testAgent;currentCall=null;navigate('studio')});
 document.querySelectorAll('[data-edit-contact]').forEach(b=>b.onclick=()=>editContact(find('contacts',b.dataset.editContact),refresh));
 document.querySelectorAll('[data-edit-workflow]').forEach(b=>b.onclick=()=>editWorkflow(find('workflows',b.dataset.editWorkflow),data,refresh));
 document.querySelectorAll('[data-run-workflow]').forEach(b=>b.onclick=()=>safely(async()=>{const r=await api('/workflows/'+b.dataset.runWorkflow+'/run','POST',{request_id:crypto.randomUUID()});await refresh();toast(`${r.created} simulated calls completed. ${r.skipped} ineligible contacts skipped.`)},b));
 document.querySelectorAll('[data-complete-task]').forEach(b=>b.onclick=()=>safely(async()=>{await api('/tasks/'+b.dataset.completeTask+'/complete','POST');await refresh();toast('Task marked done')},b));
 document.querySelectorAll('[data-call]').forEach(b=>b.onclick=()=>safely(()=>showCall(b.dataset.call),b));
 document.querySelectorAll('[data-reply]').forEach(b=>b.onclick=()=>safely(()=>reply(b.dataset.reply),b));
 if($('#contact-search'))$('#contact-search').oninput=e=>search(e.target,'contact');
 if($('#history-search'))$('#history-search').oninput=e=>search(e.target,'history');
 if($('#history-filter'))$('#history-filter').onchange=e=>{filter=e.target.value;render()};
 if($('#studio-agent'))$('#studio-agent').onchange=e=>selectedAgent=e.target.value;
 if($('#reply-form'))$('#reply-form').onsubmit=e=>{e.preventDefault();const text=new FormData(e.target).get('text');safely(()=>reply(text),$('[type=submit]',e.target))};
}
async function action(name){
 if(V.nav.some(x=>x[0]===name)){navigate(name);return}
 if(name==='new-agent')return editAgent(null,refresh);
 if(name==='new-contact')return editContact(null,refresh);
 if(name==='new-workflow')return editWorkflow(null,data,refresh);
 if(name==='start-call'){
  if(busy||currentCall?.status==='in_progress')return;busy=true;
  try{const mode=$('#studio-mode').value;selectedAgent=$('#studio-agent').value;currentCall=await api('/calls','POST',{agent_id:selectedAgent,contact_id:$('#studio-contact').value,mode,request_id:crypto.randomUUID()});await refresh();if(mode==='browser')await startVoiceSession()}catch(e){await releaseVoice();if(currentCall?.status==='in_progress')currentCall=await api('/calls/'+currentCall.id+'/end','POST');await refresh();throw e}finally{busy=false}
 }
 if(name==='toggle-voice')return toggleVoice();
 if(name==='interrupt-voice'){
  voiceGeneration++;responseAbort?.abort();responseAbort=null;
  for(const source of pcmSources){try{source.stop()}catch{}}pcmSources.clear();pcmUntil=0;
  audioPlayer?.pause();audioPlayer=null;busy=false;micPaused=false;streamMuted=false;
  voiceStatus('Listening… tell me what you need.');return;
 }
 if(name==='replay-opening'){if(lastAudio)return playVoice(lastAudio.value,lastAudio.type);return playOpening()}
 if(name==='end-call'&&currentCall){await releaseVoice();currentCall=await api('/calls/'+currentCall.id+'/end','POST');await refresh();toast('Conversation ended')}
 if(name==='logout'){await releaseVoice();await api('/logout','POST');currentCall=null;data=null;await init()}
}
async function reply(text){
 if(busy||!currentCall||currentCall.status!=='in_progress'||!text.trim())return;
 busy=true;document.querySelectorAll('.quick,.composer button,.composer input').forEach(x=>x.disabled=true);
 try{currentCall=await api('/calls/'+currentCall.id+'/turn','POST',{text,request_id:crypto.randomUUID()});await refresh();if(currentCall.status==='completed')toast('Outcome saved. Your dashboard is up to date.')}finally{busy=false;render();$('#reply-form input')?.focus()}
}
async function showCall(id){
 const c=await api('/calls/'+id);
 const d=dialog(`<h2>Conversation details</h2><p class="subtitle">${esc(c.contact_snapshot.name)} with ${esc(c.agent_snapshot.name)} · ${date(c.started_at)}</p><div class="call-meta">${badge(c.mode==='browser'?'Browser voice':'Simulated')}${badge(c.source==='seed'?'Seeded example':c.source)}${badge(c.outcome||c.status,c.outcome||'')}</div><div class="call-summary"><strong>${esc(c.summary||'Conversation in progress.')}</strong><p>Next step: ${esc(c.next_action||'Continue the simulation')}</p></div><div class="transcript">${V.transcript(c)}</div><div class="actions"><a class="button" href="${basePath}/api/calls/${c.id}/export" download>${icon('download')}Export transcript</a> <button class="button" id="play-transcript">${icon('volume')}Listen locally</button>${c.status==='in_progress'?` <button class="button primary" id="resume-call">Resume</button>`:''}</div><p class="form-help" id="voice-status">Optional on-device browser voice. No recorded audio or live call.</p><details class="snapshot"><summary>Agent configuration at the time of this call</summary><pre>${esc('Use case: '+title(c.agent_snapshot.use_case)+'\n\nSystem prompt (stored, not interpreted in offline demo):\n'+c.agent_snapshot.prompt+'\n\nBusiness context:\n'+c.agent_snapshot.context)}</pre></details>`);
 if($('#resume-call',d))$('#resume-call',d).onclick=()=>{currentCall=c;selectedAgent=c.agent_id;d.close();navigate('studio')};
 let speaking=false;
 $('#play-transcript',d).onclick=()=>{
  if(!('speechSynthesis' in window)){$('#voice-status').textContent='This browser does not support voice playback.';return}
  if(speaking){speechSynthesis.cancel();speaking=false;$('#voice-status').textContent='Playback stopped.';return}
  const voice=speechSynthesis.getVoices().find(v=>v.localService&&v.lang.startsWith('en'));
  if(!voice){$('#voice-status').textContent='No local English voice is available in this browser. The full transcript remains available above.';return}
  speechSynthesis.cancel();speaking=true;$('#voice-status').textContent='Playing with an on-device voice. Click Listen locally again to stop.';
  const utterance=new SpeechSynthesisUtterance(c.transcript.map(t=>(t.role==='agent'?c.agent_snapshot.name:'Customer')+'. '+t.text).join('\n'));
  utterance.voice=voice;utterance.rate=1;utterance.onend=()=>{speaking=false;$('#voice-status').textContent='Playback complete.'};utterance.onerror=()=>{speaking=false;$('#voice-status').textContent='Playback is unavailable. Please use the transcript.'};speechSynthesis.speak(utterance);
 };
 d.addEventListener('close',()=>{if('speechSynthesis' in window)speechSynthesis.cancel()},{once:true});
}
async function init(){
 try{
  const session=await api('/session');
  if(!session.authenticated){$('#app').innerHTML=`<main class="login"><section class="card"><div class="brand"><span class="brand-mark">${icon('chart')}</span>relay. voice</div><h1>Your workspace awaits.</h1><p>Enter your demo workspace password to continue.</p><form id="login"><label>Workspace password<input name="password" type="password" required autocomplete="current-password"></label><p class="form-error" role="alert"></p><button class="button primary" type="submit">Sign in ${icon('arrow')}</button></form></section></main>`;$('#login').onsubmit=async e=>{e.preventDefault();try{await api('/login','POST',{password:new FormData(e.target).get('password')});await init()}catch(err){$('.form-error').textContent=err.message}};return}
  page=V.nav.some(x=>x[0]===location.hash.slice(1))?location.hash.slice(1):'overview';await refresh();
 }catch(e){$('#app').innerHTML=`<div class="error-box"><h1>Workspace unavailable</h1><p>${esc(e.message)}</p><button class="button" id="retry">Try again</button></div>`;$('#retry').onclick=init}
}
window.addEventListener('pagehide',()=>{releaseVoice();});
if('speechSynthesis' in window)speechSynthesis.getVoices();
init();
