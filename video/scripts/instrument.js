// Recording-only instrumentation: real app audio, virtual customer mic, visible cursor.
// No provider responses, transcripts, UI components or API state are mocked.
(() => {
 const NativeContext=window.AudioContext, connect=AudioNode.prototype.connect;
 let mic,recorder,mix,recordContext,chunks=[],startTime=0;
 const mirrors=new WeakMap();
 const ensure=async()=>{
  if(recordContext)return;
  recordContext=new NativeContext({sampleRate:48000});await recordContext.resume();
  mix=recordContext.createMediaStreamDestination();
  mic=recordContext.createMediaStreamDestination();
  const customer=recordContext.createMediaStreamSource(mic.stream);
  connect.call(customer,mix);
 };
 navigator.mediaDevices.getUserMedia=async()=>{await ensure();return mic.stream;};
 AudioNode.prototype.connect=function(destination,...args){
  const result=connect.call(this,destination,...args);
  if(destination instanceof AudioDestinationNode && this.context!==recordContext){
   let mirror=mirrors.get(this.context);
   if(!mirror){mirror=this.context.createMediaStreamDestination();mirrors.set(this.context,mirror);const source=recordContext.createMediaStreamSource(mirror.stream);connect.call(source,mix);}
   connect.call(this,mirror);
  }
  return result;
 };
 const originalPlay=HTMLMediaElement.prototype.play;
 const observed=new WeakSet();
 HTMLMediaElement.prototype.play=function(){
  if(this instanceof HTMLAudioElement&&!observed.has(this)){
   const context=new NativeContext();context.resume();
   const source=context.createMediaElementSource(this);source.connect(context.destination);observed.add(this);
  }
  return originalPlay.call(this);
 };
 window.__demo={
  events:[],
  async begin(){await ensure();chunks=[];startTime=performance.now();recorder=new MediaRecorder(mix.stream,{mimeType:'audio/webm;codecs=opus',audioBitsPerSecond:192000});recorder.ondataavailable=e=>chunks.push(e.data);recorder.start(100);return Date.now();},
  async speak(name){
   await ensure();const wav=await(await fetch('/video-audio/'+name+'.wav')).arrayBuffer();
   const buffer=await recordContext.decodeAudioData(wav),source=recordContext.createBufferSource();source.buffer=buffer;source.connect(mic);
   this.events.push({type:'customer',name,at:(performance.now()-startTime)/1000});
   source.start();await new Promise(resolve=>source.onended=resolve);
  },
  async finish(){
   const data=await new Promise(resolve=>{recorder.onstop=async()=>{const blob=new Blob(chunks,{type:recorder.mimeType});const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';for(const b of bytes)binary+=String.fromCharCode(b);resolve(btoa(binary));};recorder.stop();});
   return {data,events:this.events};
  }
 };
 addEventListener('DOMContentLoaded',()=>{
  const cursor=document.createElement('div');cursor.id='demo-cursor';
  cursor.innerHTML='<svg width="36" height="44" viewBox="0 0 24 30"><path d="M2 2 L2 25 L8 19 L12 28 L16 26 L12 17 L21 17 Z" fill="#204e40" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>';
  Object.assign(cursor.style,{position:'fixed',left:'0',top:'0',zIndex:'2147483647',pointerEvents:'none',filter:'drop-shadow(0 3px 6px #0006)',transform:'translate(120px,100px)',transition:'transform 700ms cubic-bezier(.22,.61,.36,1)'});document.body.append(cursor);
  window.__demo.move=(x,y)=>cursor.style.transform=`translate(${x}px,${y}px)`;
  window.__demo.click=()=>{
   const ring=document.createElement('span');Object.assign(ring.style,{position:'absolute',left:'-14px',top:'-14px',width:'38px',height:'38px',borderRadius:'50%',border:'3px solid #87ac72',background:'#cce4b944'});cursor.append(ring);
   ring.animate([{transform:'scale(.5)',opacity:1},{transform:'scale(1.8)',opacity:0}],{duration:550,fill:'forwards'});setTimeout(()=>ring.remove(),600);
  };
 });
})();
