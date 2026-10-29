import {$,esc,title,date,icon,badge,api,toast,dialog,basePath} from './ui.js';
import * as V from './views.js';
import {VoiceSession} from './voice-session.js';
import {mountRequestReview} from './request-review.js';
import {editAgent,editContact,editWorkflow} from './forms.js';
let data,page='overview',currentCall=null,selectedAgent='agent-sales',query='',filter='all',busy=false;
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
const liveVoice=new VoiceSession({
 basePath,api,
 onCall:call=>{if(currentCall?.id===call.id){currentCall=call;render();}},
 onStatus:message=>{const el=$('#voice-live-status');if(el)el.textContent=message;},
 onError:message=>toast(message),
});
async function startVoiceSession(){await liveVoice.start(currentCall,data.settings);}
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
  try{const mode=$('#studio-mode').value;selectedAgent=$('#studio-agent').value;currentCall=await api('/calls','POST',{agent_id:selectedAgent,contact_id:$('#studio-contact').value,mode,request_id:crypto.randomUUID()});await refresh();if(mode==='browser')await startVoiceSession()}catch(e){await liveVoice.close();if(currentCall?.status==='in_progress')currentCall=await api('/calls/'+currentCall.id+'/end','POST');await refresh();throw e}finally{busy=false}
 }
 if(name==='toggle-voice')return liveVoice.toggle();
 if(name==='replay-opening')return liveVoice.replayOpening();
 if(name==='end-call'&&currentCall){await liveVoice.close();currentCall=await api('/calls/'+currentCall.id+'/end','POST');await refresh();toast('Conversation ended');await showCall(currentCall.id)}
 if(name==='logout'){await liveVoice.close();await api('/logout','POST');currentCall=null;data=null;await init()}
}
async function reply(text){
 if(busy||!currentCall||currentCall.status!=='in_progress'||!text.trim())return;
 busy=true;document.querySelectorAll('.quick,.composer button,.composer input').forEach(x=>x.disabled=true);
 try{currentCall=await api('/calls/'+currentCall.id+'/turn','POST',{text,request_id:crypto.randomUUID()});await refresh();if(currentCall.status==='completed')toast('Outcome saved. Your dashboard is up to date.')}finally{busy=false;render();$('#reply-form input')?.focus()}
}
async function showCall(id){
 const [c,requestInfo]=await Promise.all([api('/calls/'+id),api('/calls/'+id+'/request')]);
 const outcomeLabel=c.mode==='demo'&&c.outcome==='confirmed'?'Simulated confirmation':c.outcome||c.status;
 const d=dialog(`<h2>Conversation details</h2><p class="subtitle">${esc(c.contact_snapshot.name)} with ${esc(c.agent_snapshot.name)} · ${date(c.started_at)}</p><div class="call-meta">${badge(c.mode==='browser'?'Browser voice':'Simulated')}${badge(c.source==='seed'?'Seeded example':c.source)}${badge(outcomeLabel,c.outcome||'')}</div><div class="call-summary"><strong>${esc(c.summary||'Conversation in progress.')}</strong><p>Next step: ${esc(c.next_action||'Continue the simulation')}</p></div><div id="request-review"></div><h3 class="section-space">Conversation transcript</h3><div class="transcript">${V.transcript(c)}</div><div class="actions"><a class="button" href="${basePath}/api/calls/${c.id}/export" download>${icon('download')}Export transcript</a> <button class="button" id="play-transcript">${icon('volume')}Listen locally</button>${c.status==='in_progress'?` <button class="button primary" id="resume-call">Resume</button>`:''}</div><p class="form-help" id="voice-status">Optional on-device browser voice. No recorded audio or live call.</p><details class="snapshot"><summary>Session memory · customer-provided notes</summary><ol>${(c.memory?.customer_notes||[]).map(n=>`<li>${esc(n.text)}</li>`).join('')||'<li>No customer details recorded yet.</li>'}</ol></details><details class="snapshot"><summary>Agent configuration at the time of this call</summary><pre>${esc('Use case: '+title(c.agent_snapshot.use_case)+'\n\nSystem prompt (stored, not interpreted in offline demo):\n'+c.agent_snapshot.prompt+'\n\nBusiness context:\n'+c.agent_snapshot.context)}</pre></details>`);
 mountRequestReview($('#request-review',d),c,requestInfo,api,()=>{refresh().catch(e=>toast(e.message));});
 if($('#resume-call',d))$('#resume-call',d).onclick=()=>safely(async()=>{await liveVoice.close();currentCall=c;selectedAgent=c.agent_id;d.close();navigate('studio');if(c.mode==='browser')await liveVoice.start(c,data.settings,true);});
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
window.addEventListener('pagehide',()=>{liveVoice.close();});
if('speechSynthesis' in window)speechSynthesis.getVoices();
init();
