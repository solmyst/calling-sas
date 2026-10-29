// Isolated real-UI check. --live-model opts into one paid extraction request.
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {mkdtempSync,mkdirSync,writeFileSync,rmSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'..');
const require=createRequire(path.join(root,'video/package.json'));
const {chromium}=require('playwright');
const live=process.argv.includes('--live-model');
const temporary=mkdtempSync(path.join(os.tmpdir(),'relay-request-check-'));
const listener=net.createServer();await new Promise(resolve=>listener.listen(0,'127.0.0.1',resolve));
const port=listener.address().port;await new Promise(resolve=>listener.close(resolve));
const origin='http://127.0.0.1:'+port;
const output=path.join(root,'runtime/request-browser-check');mkdirSync(output,{recursive:true});
const server=spawn(path.join(root,'.venv/bin/python'),['run.py'],{cwd:root,env:{...process.env,APP_ENV:'local',DEMO_PASSWORD:'',DATABASE_PATH:path.join(temporary,'check.sqlite'),PORT:String(port),PUBLIC_ORIGIN:origin},stdio:'ignore'});
let browser;
try{
 let ready=false;
 for(let i=0;i<80;i++){
  if(server.exitCode!==null)throw new Error('Validation server exited before startup');
  try{if((await fetch(origin+'/health')).ok){ready=true;break}}catch{}
  await new Promise(resolve=>setTimeout(resolve,100));
 }
 assert.ok(ready,'Validation server ready');
 browser=await chromium.launch({headless:true,...(process.env.BROWSER_PATH?{executablePath:process.env.BROWSER_PATH}:{channel:'chrome'})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/#workflows');
 await page.getByRole('button',{name:'Create workflow'}).click();
 await page.getByLabel('Workflow name',{exact:true}).fill('Service follow-up check');
 await page.getByRole('button',{name:'Save changes'}).click();
 await page.waitForFunction(()=>!document.querySelector('#modal').open);
 await page.getByRole('button',{name:'Edit',exact:true}).first().click();
 await page.getByRole('button',{name:'Cancel',exact:true}).click();
 await page.goto(origin+'/#studio');
 await page.locator('#studio-agent').selectOption('demo-booking');
 await page.getByRole('button',{name:'Start conversation'}).click();
 for(const text of ['Routine car service, this Friday at eleven please.','Actually, Saturday at two instead.','Yes, please proceed.']){
  await page.getByRole('textbox',{name:'Customer response'}).fill(text);
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/turn')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send',exact:true}).click()]);
 }
 await page.getByRole('button',{name:/View full details/}).click();
 await page.getByRole('heading',{name:'Customer request',exact:true}).waitFor();
 const panel=page.locator('#request-review');
 assert.match(await panel.innerText(),/No appointment has been booked/);
 if(live){
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/request/extract'),{timeout:45000}),page.getByRole('button',{name:'Extract from transcript'}).click()]);
  await page.waitForFunction(()=>!document.querySelector('#request-review fieldset').disabled);
  assert.match(await page.getByLabel('Preferred day / date',{exact:true}).inputValue(),/Saturday/i);
  assert.match(await page.getByLabel('Preferred time · as spoken',{exact:true}).inputValue(),/two/i);
  await page.getByText('Why these details? Customer evidence',{exact:true}).click();
  assert.match(await panel.innerText(),/Saturday at two/);
 }
 await page.getByLabel('Requested service',{exact:true}).fill('Routine car service');
 await page.getByLabel('Preferred day / date',{exact:true}).fill('Saturday');
 await page.getByLabel('Preferred time · as spoken',{exact:true}).fill('two · AM/PM to clarify');
 await page.getByLabel('Timezone · IANA name',{exact:true}).fill('Asia/Kolkata');
 await page.getByLabel('Assigned team / owner',{exact:true}).fill('Service desk');
 await page.getByLabel('Operator notes',{exact:true}).fill('Check availability and clarify time before confirming.');
 await page.getByRole('button',{name:'Save reviewed request'}).click();
 await page.getByRole('button',{name:'Create local follow-up'}).waitFor();
 await page.getByRole('button',{name:'Create local follow-up'}).click();
 await page.getByText('Local lead and follow-up saved',{exact:true}).waitFor();
 await Promise.all([page.waitForResponse(r=>r.url().endsWith('/request/follow-up')),page.getByRole('button',{name:'Update local follow-up'}).click()]);
 await page.locator('#modal').evaluate(el=>el.scrollTop=0);
 await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
 // Persisted history survives a full browser reload.
 await page.goto(origin+'/#history');
 await page.reload();
 await page.locator('[data-call]').first().click();
 await page.getByText('Local lead and follow-up saved',{exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 await page.locator('#modal').evaluate(el=>el.scrollTop=0);
 await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
 const overflow=await page.locator('#modal').evaluate(el=>({width:el.clientWidth,scroll:el.scrollWidth}));
 assert.ok(overflow.scroll<=overflow.width+1,'No horizontal modal overflow on mobile');
 assert.deepEqual(errors,[]);
 const report={passed:true,live_model_extraction:live,workflow_create_edit:true,review_followup_reload:true,mobile_no_horizontal_overflow:true,page_errors:errors,scope:'Temporary database; no external actions or phone calls'};
 writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
}finally{
 await browser?.close();server.kill('SIGTERM');
 await new Promise(resolve=>{if(server.exitCode!==null)resolve();else server.once('exit',resolve)});
 rmSync(temporary,{recursive:true,force:true});
}
