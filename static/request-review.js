import {esc,field,area,badge,date} from './ui.js';
const fields=[['Requested service','service'],['Preferred day / date','preferred_day'],['Preferred time · as spoken','preferred_time'],['Timezone · IANA name','timezone'],['Business need','business_need'],['Callback window','callback_window']];

export function requestPanel(call,info){
 const r=info.request,active=call.status==='in_progress',reviewed=r.status==='reviewed';
 const evidence=Object.entries(r.evidence||{});
 const lead=info.lead;
 const current=lead&&lead.request_revision===r.revision;
 return `<section class="request-summary" aria-labelledby="request-heading">
 <div class="request-heading"><div><p class="eyebrow">CONVERSATION → NEXT STEP</p><h3 id="request-heading">Customer request</h3></div>${badge(r.status==='reviewed'?'Reviewed':'Needs review',r.status==='reviewed'?'active':'')}</div>
 <p class="request-intro">Capture the details, check the latest correction, and assign a local follow-up. No appointment has been booked.</p>
 <div class="integration-status"><span>Calendar · Not connected</span><span>CRM · Not connected</span><span>Follow-up · Local workspace</span></div>
 ${active?'<p class="notice">End the conversation to extract, review and save its request.</p>':''}
 ${reviewed?`<dl class="request-values">${fields.map(([label,key])=>`<div><dt>${esc(label)}</dt><dd>${esc(r.fields[key]||'Not provided')}</dd></div>`).join('')}</dl><p class="request-owner">Assigned to ${esc(r.owner||'No owner yet')}</p>${r.notes?`<p class="request-intro">${esc(r.notes)}</p>`:''}`:''}
 <details class="request-editor" ${reviewed?'':'open'}><summary>${reviewed?'Edit reviewed request':'Review request details'}</summary><form id="request-review-form"><fieldset ${active?'disabled':''}><legend class="sr-only">Review customer preferences</legend><div class="form-grid">${fields.map(([label,key])=>field(label,key,r.fields[key]||'','text',`maxlength="200" placeholder="${key==='timezone'?'Unknown · e.g. Asia/Kolkata':'Not provided'}"`)).join('')}${field('Assigned team / owner','owner',r.owner,'text','maxlength="80" placeholder="e.g. Service desk"')}</div>
 <p class="form-help">Keep unclear dates, AM/PM and timezone unresolved until clarified. These fields are preferences, not available slots.</p>
 ${area('Operator notes','notes',r.notes,'maxlength="1000" placeholder="What should the team verify?"')}
 <p id="request-feedback" class="form-error" role="status" aria-live="polite"></p>
 <div class="request-actions"><button type="submit" class="button primary">Save reviewed request</button><button type="button" id="request-extract" class="button" ${!call.transcript.some(t=>t.role==='customer')?'disabled':''}>Extract from transcript</button></div>
 <p class="form-help">Extraction uses the configured AI model and may incur usage charges. Review suggestions before saving. You can also enter the details yourself.</p></fieldset></form></details>
 <div class="request-actions"><button type="button" id="request-follow-up" class="button primary" ${active||!reviewed||!r.owner?'disabled':''}>${lead?'Update':'Create'} local follow-up</button></div>
 ${evidence.length?`<details class="request-evidence"><summary>Why these details? Customer evidence</summary>${evidence.map(([key,e])=>`<blockquote><strong>${esc(fields.find(f=>f[1]===key)?.[0]||key)} · turn ${e.turn_index+1}</strong><p>“${esc(e.statement||e.quote)}”</p></blockquote>`).join('')}</details>`:''}
 ${lead?`<div class="local-lead"><strong>${current?'Local lead and follow-up saved':'Local lead uses an earlier revision'}</strong><p>Owner: ${esc(lead.owner)} · External CRM: not connected</p><small>${esc(lead.id)}${current?'':'. Update the local follow-up after reviewing your changes.'}</small></div>`:''}
 ${r.audit?.length?`<details class="request-evidence"><summary>Request activity</summary><ol>${r.audit.map(e=>`<li>${esc(e.action)} · ${esc(date(e.at))}</li>`).join('')}</ol></details>`:''}
 </section>`;
}

export function mountRequestReview(root,call,initial,api,onSaved=()=>{}){
 let info=initial;
 function render(){
  root.innerHTML=requestPanel(call,info);
  const form=root.querySelector('form'),fieldset=form.querySelector('fieldset');
  const feedback=root.querySelector('#request-feedback'),extract=root.querySelector('#request-extract'),follow=root.querySelector('#request-follow-up');
  let pending=false;
  form.addEventListener('input',()=>{follow.disabled=true;extract.disabled=true;feedback.textContent='Unsaved changes. Save the reviewed request before continuing.';});
  async function run(path,method,body){
   if(pending)return;
   pending=true;fieldset.disabled=true;follow.disabled=true;feedback.textContent='Saving…';
   try{
    info=await api('/calls/'+call.id+'/request'+path,method,body);
    onSaved(info);render();
   }catch(e){feedback.textContent=e.message;fieldset.disabled=call.status==='in_progress';follow.disabled=true;root.querySelector('.request-editor').open=true;}
   finally{pending=false;}
  }
  form.onsubmit=e=>{
   e.preventDefault();const values=Object.fromEntries(new FormData(form));
   run('','PUT',{revision:info.request.revision,fields:Object.fromEntries(fields.map(([,key])=>[key,values[key]||''])),owner:values.owner||'',notes:values.notes||''});
  };
  extract.onclick=()=>run('/extract','POST',{revision:info.request.revision});
  follow.onclick=()=>run('/follow-up','POST',{revision:info.request.revision});
 }
 render();
}
