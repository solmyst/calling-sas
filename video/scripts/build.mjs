import {spawn} from 'node:child_process';
import {setTimeout as wait} from 'node:timers/promises';
const python=process.env.VIDEO_PYTHON||'../.venv/bin/python';
const run=(command,args)=>new Promise((resolve,reject)=>{const p=spawn(command,args,{stdio:'inherit'});p.once('error',reject);p.once('exit',code=>code===0?resolve():reject(new Error(`${command} exited ${code}`)));});
const reuse=process.argv.includes('--reuse-capture');let server;
process.once('SIGINT',()=>{server?.kill('SIGINT');process.exit(130);});
process.once('SIGTERM',()=>{server?.kill('SIGINT');process.exit(143);});
try{
 if(!reuse){
  await run(python,['scripts/prepare.py']);
  // Fail on occupied recording ports rather than connect to or stop another app.
  try{await fetch('http://127.0.0.1:8792/health');throw new Error('Port 8792 is occupied. Stop the recording server you started before building.');}catch(e){if(e.message.startsWith('Port'))throw e;}
  server=spawn(python,['scripts/server.py'],{stdio:'inherit'});
  let ready=false;for(let i=0;i<50;i++){try{const r=await fetch('http://127.0.0.1:8792/health');if(r.ok){ready=true;break;}}catch{}await wait(200);}
  if(!ready)throw new Error('Isolated recording server did not start.');
  await run('node',['scripts/capture.mjs']);
 }
 await run('node',['--test','scripts/motion.test.mjs']);
 await run(python,['scripts/edit.py']);
 await run('node',['scripts/render.mjs']);
 await run(python,['scripts/review.py']);
 console.log('Ready: out/giani-hackathon-demo.mp4');
}finally{server?.kill('SIGINT');}
