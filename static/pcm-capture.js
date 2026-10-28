// Produce exact 512-sample / 32 ms frames off the main UI thread.
class PcmCapture extends AudioWorkletProcessor {
 constructor(){super();this.samples=new Float32Array(512);this.offset=0;this.phase=0;this.sum=0;this.count=0;}
 process(inputs,outputs){
  const input=inputs[0]?.[0];
  if(!input)return true;
  const ratio=sampleRate/16000;
  for(let i=0;i<input.length;i++){
   this.phase+=1;
   this.sum+=input[i];this.count++;
   if(this.phase<ratio)continue;
   this.phase-=ratio;
   this.samples[this.offset++]=this.sum/this.count;this.sum=0;this.count=0;
   if(this.offset===512){
    const buffer=new ArrayBuffer(1024),view=new DataView(buffer);
    for(let j=0;j<512;j++){const x=Math.max(-1,Math.min(1,this.samples[j]));view.setInt16(j*2,x<0?x*32768:x*32767,true);}
    this.port.postMessage(buffer,[buffer]);this.offset=0;
   }
  }
  return true;
 }
}
registerProcessor('pcm-capture',PcmCapture);
