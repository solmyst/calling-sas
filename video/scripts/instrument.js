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
 const observed=new WeakSet(),playbackContexts=[];
 HTMLMediaElement.prototype.play=function(){
  if(this instanceof HTMLAudioElement&&!observed.has(this)){
   const context=new NativeContext();context.resume();
   const source=context.createMediaElementSource(this);source.connect(context.destination);observed.add(this);playbackContexts.push({context,source,element:this});
   this.addEventListener('error',()=>window.__demo.audioErrors.push({code:this.error?.code,message:this.error?.message}));
  }
  return originalPlay.call(this);
 };
 window.__demo={
  events:[],audioErrors:[],
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
 window.__demo.motion=[];
 window.__demo.point={x:120,y:100};
 window.__demo.move=(x,y)=>{
  const from={...window.__demo.point};
  window.__demo.motion.push({type:'move',wallClock:Date.now(),duration:.7,from,to:{x,y}});
  window.__demo.point={x,y};
 };
 window.__demo.click=()=>window.__demo.motion.push({type:'click',wallClock:Date.now(),...window.__demo.point});
})();
