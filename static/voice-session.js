// One owner for microphone, reply generation, playback and interruption lifecycle.
export class VoiceSession {
 constructor({basePath='',api,onCall=()=>{},onStatus=()=>{},onError=()=>{},fetchImpl=globalThis.fetch.bind(globalThis),getMicrophone=null}){
  Object.assign(this,{basePath,api,onCall,onStatus,onError,fetchImpl,getMicrophone});
  this.epoch=0;this.closed=true;this.sources=new Set();this.seen=new Set();
  this.queue=[];this.interruptAck=Promise.resolve();this.nextAudioTime=0;
 }
 status(text){this.onStatus(text)}
 isCurrent(epoch){return !this.closed&&this.epoch===epoch}
 control(active){
  this.playing=active;
  if(this.socket?.readyState===1)this.socket.send(JSON.stringify({type:'playback',active}));
 }
 async start(call,settings,resume=false){
  await this.close();this.closed=false;this.call=call;this.streaming=settings.streaming_audio;
  this.paused=false;this.queue=[];this.seen.clear();this.reconnects=0;this.interruptAck=Promise.resolve();
  if(!navigator.mediaDevices?.getUserMedia||!globalThis.AudioWorkletNode)throw new Error('Use a current browser with microphone and AudioWorklet support.');
  try{
   const constraints={audio:{echoCancellation:{ideal:true},noiseSuppression:{ideal:true},autoGainControl:{ideal:true},channelCount:{ideal:1}}};
   this.media=this.getMicrophone?await this.getMicrophone(constraints):await navigator.mediaDevices.getUserMedia(constraints);
   this.context=new AudioContext();await this.context.resume();
   await this.context.audioWorklet.addModule(`${this.basePath}/static/pcm-capture.js`);
   this.processor=new AudioWorkletNode(this.context,'pcm-capture');
   this.input=this.context.createMediaStreamSource(this.media);
   this.highpass=this.context.createBiquadFilter();this.highpass.type='highpass';this.highpass.frequency.value=85;
   this.input.connect(this.highpass);this.highpass.connect(this.processor);this.processor.connect(this.context.destination);
   this.processor.port.onmessage=event=>{
    if(this.socket?.readyState!==1)return;
    if(this.socket.bufferedAmount>64000){this.socket.close();return;}
    // Keep real microphone audio flowing during AI speech: AEC/NS clean it,
    // Silero confirms speech, and Gnani keeps the beginning of the utterance.
    this.socket.send(this.paused?new ArrayBuffer(1024):event.data);
   };
   await this.connect();if(resume)this.status('Conversation restored. Listening…');else await this.opening();
  }catch(error){await this.close();throw error;}
 }
 async connect(){
  const scheme=location.protocol==='https:'?'wss':'ws';
  const socket=new WebSocket(`${scheme}://${location.host}${this.basePath}/api/calls/${this.call.id}/voice/stream`);
  this.socket=socket;socket.binaryType='arraybuffer';
  await new Promise((resolve,reject)=>{
   const timeout=setTimeout(()=>{socket.close();reject(new Error('Speech recognition did not become ready.'));},15000);
   let ready=false;
   socket.onmessage=event=>{
    if(this.socket!==socket||this.closed)return;
    try{const message=JSON.parse(event.data);
     if(message.type==='ready'){clearTimeout(timeout);ready=true;this.reconnects=0;this.seen.clear();this.control(!!this.playing);resolve();return;}
     this.receive(message);
    }catch{this.status('Speech recognition sent an invalid event. Please restart the session.');}
   };
   socket.onerror=()=>{if(!ready){clearTimeout(timeout);reject(new Error('Speech recognition could not connect.'));}};
   socket.onclose=()=>{
    clearTimeout(timeout);
    if(!ready)reject(new Error('Speech recognition disconnected.'));
    if(this.socket===socket&&!this.closed){this.status('Reconnecting microphone…');this.retryConnection();}
   };
  });
 }
 retryConnection(){
  if(this.closed||this.reconnectTimer)return;
  if(this.reconnects>=2){this.status('Speech recognition disconnected. End and restart the session.');return;}
  const delay=500*2**this.reconnects++;
  this.reconnectTimer=setTimeout(async()=>{
   this.reconnectTimer=null;if(this.closed)return;
   try{await this.connect();this.status('Reconnected. Please repeat anything said while reconnecting.');}
   catch{this.retryConnection();}
  },delay);
 }
 receive(message){
  if(this.closed||this.paused)return;
  if(message.type==='vad_speech_start'){
   this.interrupt();this.status('Listening… go ahead.');return;
  }
  if(message.type==='processing'){if(!this.playing)this.status('Understanding…');return;}
  if(message.type!=='Turn')return;
  const text=(message.transcript||'').trim();
  if(!text||!message.end_of_turn)return;
  const key=String(message.turn_order??text);
  if(this.seen.has(key))return;
  this.seen.add(key);if(this.seen.size>128)this.seen.delete(this.seen.values().next().value);
  // Even a short word below the VAD duration threshold can be a real correction.
  this.interrupt();this.queue.push(text);
  clearTimeout(this.turnTimer);this.turnTimer=setTimeout(()=>this.drain(),80);
 }
 stopPlayback(){
  if(this.player){this.player.onended=null;this.player.onerror=null;this.player.pause();this.player.src='';this.player=null;}
  if(this.audioURL){URL.revokeObjectURL(this.audioURL);this.audioURL=null;}
  for(const source of this.sources){try{source.stop();}catch{}}
  this.sources.clear();this.nextAudioTime=0;this.control(false);
 }
 interrupt(){
  const requestId=this.activeId;
  if(!requestId)return this.interruptAck;
  const playedMs=this.playStarted?Math.max(0,Math.round((this.context?.currentTime-this.playStarted)*1000)):0;
  this.epoch++;this.activeId=null;this.processing=false;
  this.controller?.abort();this.controller=null;this.stopPlayback();
  const customerText=this.currentInput||'';this.currentInput='';
  const ack=this.api(`/calls/${this.call.id}/voice/interrupt`,'POST',{request_id:requestId,played_ms:Math.min(900000,playedMs),customer_text:customerText},true);
  this.interruptAck=Promise.all([this.interruptAck.catch(()=>{}),ack]);
  this.interruptAck.catch(()=>this.status('Could not save interruption. Check the connection before continuing.'));
  return this.interruptAck;
 }
 async opening(){
  const epoch=++this.epoch;this.activeId=`opening:${this.call.id}`;this.processing=true;this.currentInput='';
  const controller=new AbortController();this.controller=controller;
  this.status('Preparing the opening…');
  try{
   const response=await this.fetchImpl(`${this.basePath}/api/calls/${this.call.id}/voice/opening`,{method:'POST',signal:controller.signal});
   if(!response.ok)throw new Error('The opening voice could not be generated.');
   const value=await response.json();if(!this.isCurrent(epoch))return;
   await this.playFile(value.audio,value.content_type,epoch);
  }catch(error){if(this.isCurrent(epoch)&&error.name!=='AbortError')throw error;}
  finally{if(this.isCurrent(epoch)){this.processing=false;this.controller=null;}}
 }
 async playFile(audio,type,epoch){
  const bytes=Uint8Array.from(atob(audio),c=>c.charCodeAt(0));
  this.audioURL=URL.createObjectURL(new Blob([bytes],{type}));
  const player=new Audio(this.audioURL);this.player=player;
  player.onended=()=>{if(this.isCurrent(epoch)){this.stopPlayback();this.activeId=null;this.status('Listening… speak naturally.');}};
  player.onerror=()=>{if(this.isCurrent(epoch)){this.stopPlayback();this.activeId=null;this.status('Audio playback failed. The transcript remains available.');}};
  this.playStarted=this.context.currentTime;this.control(true);this.status('AI is speaking · you can interrupt');
  try{await player.play();}catch{this.stopPlayback();throw new Error('Audio playback was blocked. Click Resume microphone and try again.');}
 }
 async drain(){
  if(this.closed||this.paused||this.processing||!this.queue.length)return;
  try{await this.interruptAck;}catch{this.onError('Could not synchronize the interrupted reply. Please restart the session.');return;}
  if(this.closed||this.paused||this.processing||!this.queue.length)return;
  const text=this.queue.splice(0).join(' ').slice(0,2000);
  const epoch=++this.epoch,requestId=crypto.randomUUID();
  this.activeId=requestId;this.processing=true;this.playStarted=0;this.finished=false;this.currentInput=text;
  const controller=new AbortController();this.controller=controller;
  this.status('Thinking…');
  try{
   const response=await this.fetchImpl(`${this.basePath}/api/calls/${this.call.id}/voice/respond${this.streaming?'/stream':''}`,{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,request_id:requestId}),signal:controller.signal,
   });
   if(!response.ok)throw new Error('The AI could not respond. Please retry or restart the session.');
   if(this.streaming)await this.readStream(response,epoch);
   else{const value=await response.json();if(this.isCurrent(epoch)){this.call=value.call;this.onCall(value.call);await this.playFile(value.audio,value.content_type,epoch);}}
  }catch(error){
   if(this.isCurrent(epoch)&&error.name!=='AbortError'){
    this.interrupt();this.status(error.message);this.onError(error.message);
   }
  }finally{
   if(this.isCurrent(epoch)){this.processing=false;this.controller=null;if(this.streaming&&!this.sources.size){this.control(false);this.activeId=null;this.status('Listening… speak naturally.');}}
  }
 }
 async readStream(response,epoch){
  const reader=response.body.getReader(),decoder=new TextDecoder();let pending='';
  try{
   while(true){
    const {value,done}=await reader.read();
    pending+=decoder.decode(value||new Uint8Array(),{stream:!done});
    const lines=pending.split('\n');pending=lines.pop();
    for(const line of lines){
     if(!line.trim())continue;if(!this.isCurrent(epoch))return;
     const event=JSON.parse(line);
     if(event.type==='reply'){this.call=event.call;this.onCall(event.call);this.status('Preparing voice…');}
     if(event.type==='audio')this.schedule(event.audio,event.sample_rate,epoch);
     if(event.type==='complete')this.finished=true;
     if(event.type==='error')throw new Error(event.message);
    }
    if(done)break;
   }
   if(!this.finished)throw new Error('The voice stream ended early. Please retry.');
  }finally{reader.releaseLock();}
 }
 schedule(audio,sampleRate,epoch){
  if(!this.isCurrent(epoch))return;
  const bytes=Uint8Array.from(atob(audio),c=>c.charCodeAt(0)),view=new DataView(bytes.buffer);
  const buffer=this.context.createBuffer(1,bytes.length/2,sampleRate),channel=buffer.getChannelData(0);
  for(let i=0;i<channel.length;i++)channel[i]=view.getInt16(i*2,true)/32768;
  const source=this.context.createBufferSource();source.buffer=buffer;source.connect(this.context.destination);
  this.nextAudioTime=Math.max(this.context.currentTime+0.04,this.nextAudioTime);
  if(!this.playStarted)this.playStarted=this.nextAudioTime;
  this.sources.add(source);source.start(this.nextAudioTime);this.nextAudioTime+=buffer.duration;
  this.control(true);this.status('AI is speaking · you can interrupt');
  source.onended=()=>{
   this.sources.delete(source);
   if(this.isCurrent(epoch)&&!this.sources.size&&this.finished){this.control(false);this.activeId=null;this.status('Listening… speak naturally.');}
  };
 }
 async toggle(){
  this.paused=!this.paused;
  if(this.paused){this.interrupt();this.status('Microphone paused.');}
  else{await this.context?.resume();this.status('Listening… speak naturally.');this.drain();}
 }
 async replayOpening(){this.interrupt();await this.interruptAck;await this.opening();}
 async close(){
  this.closed=true;if(this.activeId)this.interrupt();this.epoch++;this.activeId=null;this.processing=false;
  clearTimeout(this.turnTimer);clearTimeout(this.reconnectTimer);this.reconnectTimer=null;
  this.controller?.abort();this.controller=null;this.stopPlayback();this.socket?.close();this.socket=null;
  this.processor?.disconnect();this.processor=null;this.input?.disconnect();this.highpass?.disconnect();
  this.media?.getTracks().forEach(track=>track.stop());this.media=null;
  const context=this.context;this.context=null;if(context&&context.state!=='closed')await context.close();
 }
}
