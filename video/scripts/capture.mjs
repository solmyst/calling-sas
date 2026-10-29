import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const BASE='http://127.0.0.1:8792',OUT=path.resolve('public/capture');
await fs.mkdir(OUT,{recursive:true});
const browser=await chromium.launch({channel:process.env.VIDEO_BROWSER_CHANNEL||undefined,headless:true,args:['--autoplay-policy=no-user-gesture-required','--disable-background-timer-throttling']});
const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
await page.addInitScript({path:'scripts/instrument.js'});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')errors.push(m.text().replace(/https?:\/\/\S+/g,'[URL]'));});
await page.goto(BASE+'/#demos');await page.locator('h1').waitFor();
const pause=ms=>page.waitForTimeout(ms);
async function move(locator){await locator.scrollIntoViewIfNeeded();const b=await locator.boundingBox();await page.evaluate(({x,y})=>window.__demo.move(x,y),{x:b.x+b.width/2,y:b.y+b.height/2});await pause(750);}
async function click(locator){await move(locator);await page.evaluate(()=>window.__demo.click());await locator.click();await pause(450);}
async function nav(label){await click(page.getByRole('link',{name:label,exact:true}));}
const chapters=[];let audioWallClock;
async function record(name,actions){
 const dir=path.join(OUT,name);await fs.rm(dir,{recursive:true,force:true});await fs.mkdir(dir,{recursive:true});
 const cdp=await page.context().newCDPSession(page);let frames=[],pending=[],index=0;
 cdp.on('Page.screencastFrame',event=>{
  const n=index++,file=`${String(n).padStart(6,'0')}.jpg`;
  frames.push({file,t:event.metadata.timestamp});pending.push(fs.writeFile(path.join(dir,file),Buffer.from(event.data,'base64')));
  cdp.send('Page.screencastFrameAck',{sessionId:event.sessionId}).catch(()=>{});
 });
 await cdp.send('Page.startScreencast',{format:'jpeg',quality:96,maxWidth:1440,maxHeight:900,everyNthFrame:1});
 const start=Date.now();await pause(150);await actions();await pause(300);
 await cdp.send('Page.stopScreencast');await Promise.all(pending);await cdp.detach();
 const duration=(Date.now()-start)/1000;
 if(frames.length<2)throw new Error('No capture frames: '+name);
 let concat='';for(let i=0;i<frames.length;i++){concat+=`file '${frames[i].file}'\nduration ${i+1<frames.length?Math.max(.001,frames[i+1].t-frames[i].t):.3}\n`;}
 concat+=`file '${frames.at(-1).file}'\n`;await fs.writeFile(path.join(dir,'frames.txt'),concat);
 execFileSync('ffmpeg',['-v','error','-y','-f','concat','-safe','0','-i',path.join(dir,'frames.txt'),'-vf','fps=30','-c:v','libx264','-crf','15','-pix_fmt','yuv420p','-an',path.join(OUT,name+'.mp4')]);
 await page.screenshot({path:path.join(OUT,name+'-last.png')});
 const probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','json',path.join(OUT,name+'.mp4')]));
 chapters.push({name,duration:Number(probe.format.duration),frames:frames.length,...(name==='conversation'?{audioOffset:audioWallClock/1000-frames[0].t}:{})});
 console.log(name,chapters.at(-1));
}
try{
 await record('choose',async()=>{
  await pause(1600);await page.mouse.wheel(0,365);await pause(800);
  await move(page.locator('[data-test-agent="demo-sales"]'));await pause(650);
  await move(page.locator('[data-edit-agent="demo-booking"]'));await pause(600);
 });
 await record('configure',async()=>{
  await click(page.locator('[data-edit-agent="demo-booking"]'));
  await move(page.locator('#editor [name="language"]'));await pause(600);
  await move(page.locator('#editor [name="context"]'));await pause(800);
  await click(page.getByRole('button',{name:'Save changes',exact:true}));await pause(650);
  await click(page.locator('[data-test-agent="demo-booking"]'));
  await page.locator('#studio-contact').selectOption('video-contact-0');
  await click(page.locator('#studio-mode'));await page.locator('#studio-mode').selectOption('browser');await page.keyboard.press('Escape');await pause(700);
 });
 let callId,transcript;
 await record('conversation',async()=>{
  audioWallClock=await page.evaluate(()=>window.__demo.begin());
  await click(page.getByRole('button',{name:'Start conversation',exact:true}));
  await page.waitForFunction(()=>document.querySelector('#voice-live-status')?.textContent?.startsWith('AI is speaking'),{},{timeout:30000});
  await page.waitForFunction(()=>document.querySelector('#voice-live-status')?.textContent==='Listening… speak naturally.',{},{timeout:30000});
  await pause(250);await page.evaluate(()=>window.__demo.speak('customer-one'));
  await page.waitForFunction(()=>document.querySelectorAll('.turn.agent').length>=2,{},{timeout:30000});
  await page.waitForFunction(()=>document.querySelector('#voice-live-status')?.textContent?.startsWith('AI is speaking'),{},{timeout:30000});
  await pause(1900);await page.evaluate(()=>window.__demo.speak('customer-two'));
  await page.waitForFunction(()=>document.querySelectorAll('.turn.agent').length>=3,{},{timeout:30000});
  await page.waitForFunction(()=>document.querySelector('#voice-live-status')?.textContent==='Listening… speak naturally.',{},{timeout:30000});
  await pause(700);
  const audio=await page.evaluate(()=>window.__demo.finish());await fs.writeFile('public/audio/conversation.webm',Buffer.from(audio.data,'base64'));
  await fs.writeFile(path.join(OUT,'voice-events.json'),JSON.stringify(audio.events,null,2));
  await click(page.getByRole('button',{name:'End session',exact:true}));
  const state=await(await page.request.get(BASE+'/api/state')).json();
  const call=state.calls.find(c=>c.contact_id==='video-contact-0'&&c.mode==='browser');callId=call.id;transcript=call;
  if(call.transcript.filter(t=>t.delivery_status==='interrupted').length<1)throw new Error('The real barge-in was not observed.');
  if(!/Saturday|शनिवार/i.test(call.transcript.at(-1).text))throw new Error('Latest correction was not used.');
 });
 await record('memory',async()=>{
  await nav('Call history');await click(page.locator(`[data-call="${callId}"]`).first());
  await page.locator('#modal .transcript').evaluate(el=>el.scrollTop=el.scrollHeight);await pause(1100);
  await click(page.getByText('Session memory · customer-provided notes',{exact:true}));await pause(1500);
 });
 await page.getByRole('button',{name:'Close dialog',exact:true}).click();
 await record('analytics',async()=>{await nav('Analytics');await pause(1400);await move(page.getByRole('heading',{name:'Agent performance',exact:true}));await pause(900);});
 await nav('Demo experiences');
 await record('outro',async()=>{await pause(1400);await page.mouse.wheel(0,370);await pause(1200);await move(page.locator('[data-test-agent="demo-booking"]'));await pause(1000);});
 await fs.writeFile('public/manifest.json',JSON.stringify({chapters,callId,transcript,errors,width:1440,height:900,provider:'Gnani Prisma / Bifrost / Gnani Timbre',fictionalData:true},null,2));
 if(errors.length)throw new Error('Browser errors: '+errors.join('; '));
 console.log('Capture complete. Real API transcript saved.');
}finally{await browser.close();}
