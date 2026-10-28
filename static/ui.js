export const $=(s,root=document)=>root.querySelector(s);
export const basePath=location.pathname.replace(/\/$/,'');
export const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const title=s=>(s||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
export const initials=s=>(s||'?').split(' ').map(x=>x[0]).slice(0,2).join('');
export const date=s=>new Date(s).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
export const duration=c=>c.ended_at?`${Math.max(0,Math.round((new Date(c.ended_at)-new Date(c.started_at))/1000))}s`:'In progress';
const paths={grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',agents:'M9 3h6m-3 0v3M5 7h14v13H5z M8 11h.1M16 11h.1M9 16h6M2 10v6m20-6v6',phone:'M7 3H3c0 10 8 18 18 18v-4l-5-2-2 2a16 16 0 0 1-7-7l2-2z',contacts:'M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3m17 0v-3a5 5 0 0 0-3-4M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm7 0a4 4 0 0 1 0 8',workflow:'M9 2h6v6H9zM2 16h6v6H2zM16 16h6v6h-6zM12 8v4M5 16v-4h14v4',chart:'M3 3v18h18M7 16v-4m5 4V7m5 9V4',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2',arrow:'M5 12h14m-5-5 5 5-5 5',plus:'M12 5v14M5 12h14',play:'m8 4 12 8-12 8z',check:'m5 12 4 4L19 6',down:'m6 9 6 6 6-6',search:'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6',close:'m6 6 12 12M6 18 18 6',shield:'m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6z m-5 10 3 3 5-5',clock:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18m0 4v5l3 2',download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',volume:'m11 4-6 5H2v6h3l6 5z m4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14',spark:'m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3z',edit:'m15 3 6 6-12 12H3v-6zM12 6l6 6',logout:'M9 3H3v18h6m4-14 5 5-5 5m-5-5h10'};
export const icon=(name,cls='')=>`<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name]||paths.spark}"/></svg>`;
export const badge=(label,kind='')=>`<span class="badge ${kind}">${esc(title(label))}</span>`;
export const avatar=(name,color='mint')=>`<span class="avatar ${esc(color)}">${esc(initials(name))}</span>`;
export const empty=(heading,detail)=>`<div class="empty">${icon('phone')}<h3>${esc(heading)}</h3><p>${esc(detail)}</p></div>`;
export function chart(days){
 const max=Math.max(5,...days.map(d=>d.calls));
 return `<svg class="chart" viewBox="0 0 650 180" role="img" aria-label="Simulated call volume over the last seven days">${[0,1,2,3].map(i=>`<line x1="32" x2="640" y1="${20+i*42}" y2="${20+i*42}" class="gridline"/><text x="5" y="${24+i*42}">${Math.round(max*(1-i/3))}</text>`).join('')}${days.map((d,i)=>{const x=50+i*85,h=d.calls/max*125,s=d.successful/max*125;return `<rect x="${x}" y="${146-h}" width="32" height="${h}" rx="5" class="bar-total"><title>${esc(d.label)}: ${d.calls} calls</title></rect><rect x="${x+35}" y="${146-s}" width="13" height="${s}" rx="4" class="bar-success"/><text x="${x+22}" y="172" text-anchor="middle">${esc(d.label)}</text>`}).join('')}</svg>`;
}
export async function api(path,method='GET',body,keepalive=false){
 const r=await fetch(basePath+'/api'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,keepalive});
 const data=await r.json();if(!r.ok)throw new Error(Array.isArray(data.detail)?data.detail.map(x=>`${x.loc.at(-1)}: ${x.msg}`).join('; '):data.detail||'Request failed');return data;
}
export function toast(text){const el=$('#toast');el.textContent=text;el.classList.add('show');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>el.classList.remove('show'),4500)}
export function dialog(html){const d=$('#modal');d.innerHTML=`<button class="icon-btn close-modal" aria-label="Close dialog">${icon('close')}</button>${html}`;$('.close-modal',d).onclick=()=>d.close();d.setAttribute('aria-label',d.querySelector('h2')?.textContent||'Details');d.showModal();return d;}
export const field=(label,name,value='',type='text',extra='')=>`<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
export const area=(label,name,value='',extra='')=>`<label>${esc(label)}<textarea name="${name}" ${extra}>${esc(value)}</textarea></label>`;
export const select=(label,name,options,value)=>`<label>${esc(label)}<select name="${name}">${options.map(o=>{const [v,t]=Array.isArray(o)?o:[o,title(o)];return `<option value="${esc(v)}" ${value===v?'selected':''}>${esc(t)}</option>`}).join('')}</select></label>`;
