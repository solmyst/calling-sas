import React from 'react';
import {registerRoot,Composition,AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,Freeze,staticFile,useCurrentFrame,interpolate,Easing} from 'remotion';
import motion from '../public/motion.json';
import {cursorAt} from './motion.mjs';
const FPS=60,DISSOLVE=18;
const chapters=[
 {start:0,end:7,clip:'choose',step:'01 / CHOOSE A WORKFLOW',title:'Business context. Real voice conversations.',caption:'Sales · Business helper · Customer care · Appointment intake'},
 {start:7,end:16,clip:'configure',step:'02 / CONFIGURE THE AGENT',title:'Your instructions. Your business context.',caption:'Language, delivery, opening message, and approved business facts.'},
 {start:16,end:20,image:'configure-last.png',step:'03 / START IN THE BROWSER',title:'Microphone in. Natural speech out.',caption:'Gnani speech recognition → AI agent → Gnani voice'},
 {start:20,end:44,clip:'conversation',step:'04 / LIVE VOICE EXCHANGE',title:'Speak over the AI. It listens.',caption:'Automatic barge-in · Silero VAD · Latest correction remembered'},
 {start:44,end:51,clip:'memory',step:'05 / REVIEW THE CONTEXT',title:'The correction survives the conversation.',caption:'Saved transcript · Interruption markers · Session memory'},
 {start:51,end:55,clip:'analytics',step:'06 / SEE THE OUTCOME',title:'Conversations you can trace and review.',caption:'Browser sessions and typed simulations stay separately labelled.'},
 {start:55,end:60,clip:'outro',step:'RELAY VOICE / GNANI HACKATHON',title:'One workspace. Four practical use cases.',caption:'Explore the demo → solmyst.github.io/calling-sas'},
];
function Cursor({name}){
 const time=useCurrentFrame()/FPS,m=motion[name];
 if(!m||name==='conversation'&&time>2)return null;
 const p=cursorAt(m,time),click=m.events.filter(e=>e.type==='click'&&time>=e.at&&time<e.at+.5).at(-1);
 return <div style={{position:'absolute',left:p.x,top:p.y,width:36,height:44,pointerEvents:'none',filter:'drop-shadow(0 3px 5px #0004)'}}>
  {click&&<div style={{position:'absolute',left:-14,top:-14,width:38,height:38,border:'2px solid #87ac72',borderRadius:'50%',opacity:1-(time-click.at)*2,transform:`scale(${.5+(time-click.at)*2})`}}/>}
  <Img src={staticFile('cursor.svg')} style={{width:36,height:44}}/>
 </div>;
}
function Footage({c}){
 return <div style={{position:'absolute',left:240,top:170,width:1440,height:834,borderRadius:14,overflow:'hidden',border:'1px solid #b8c7b533',boxShadow:'0 20px 60px #0003',background:'#f7f8f5'}}>
  <div style={{height:24,background:'#e7ece4',display:'flex',alignItems:'center',paddingLeft:14,gap:5,borderBottom:'1px solid #d6dfd1'}}>{['#9bac97','#b6c5aa','#ccd6c4'].map((color,i)=><span key={i} style={{width:6,height:6,borderRadius:'50%',background:color}}/>)}<span style={{marginLeft:15,fontSize:11,color:'#66765d'}}>Relay Voice · real application · fictional demo workspace</span></div>
  <div style={{position:'relative',width:1440,height:810,overflow:'hidden'}}>
   {c.image?<Img src={staticFile('capture/'+c.image)} style={{width:1440,height:810}}/>:<OffthreadVideo muted src={staticFile('capture/'+c.clip+'-edit.mp4')} style={{width:1440,height:810}}/>}
   {!c.image&&<Cursor name={c.clip}/>}
  </div>
 </div>;
}
function Scene({c}){
 const frame=useCurrentFrame(),alpha=interpolate(frame,[0,DISSOLVE],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.inOut(Easing.cubic)});
 return <AbsoluteFill style={{opacity:alpha,background:'#122f27'}}>
  <div style={{position:'absolute',left:240,top:78,color:'#95aa8c',fontSize:14,fontWeight:600,letterSpacing:1.8}}>{c.step}</div>
  <div style={{position:'absolute',left:240,top:104,fontSize:36,fontWeight:650,letterSpacing:-1.1,color:'#eaf2e4',lineHeight:1.12}}>{c.title}</div>
  <Freeze frame={Math.min(frame,(c.end-c.start)*FPS-1)}><Footage c={c}/></Freeze>
  <div style={{position:'absolute',left:240,right:240,top:1028,display:'flex',justifyContent:'space-between',alignItems:'center',gap:18,color:'#dce8d2',fontSize:20,fontWeight:500}}><span>{c.caption}</span><span style={{fontSize:10,letterSpacing:.8,color:'#92a48b',whiteSpace:'nowrap'}}>{c.clip==='conversation'?'RECORDED LIVE · WAITING TIME SHORTENED':'REAL APP · DEMO DATA'}</span></div>
 </AbsoluteFill>;
}
function Film(){
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#122f27',fontFamily:'Arial, sans-serif'}}>
  {chapters.map(c=><Sequence key={c.start} from={c.start*FPS} durationInFrames={(c.end-c.start)*FPS+(c.end<60?DISSOLVE:0)}><Scene c={c}/></Sequence>)}
  <div style={{position:'absolute',left:240,top:26,display:'flex',alignItems:'center',gap:10}}><Img src={staticFile('brand.svg')} style={{width:32,height:32}}/><span style={{fontSize:26,fontWeight:700,letterSpacing:-1,color:'#f3f5ee'}}>relay.<span style={{fontWeight:400,color:'#b1c0a9'}}>voice</span></span></div>
  <div style={{position:'absolute',right:240,top:35,color:'#bed6ab',fontSize:14,letterSpacing:1.5,fontWeight:600}}>GNANI HACKATHON / PRODUCT DEMO</div>
  {[['intro',0],['configure',7],['liveintro',16],['review',44],['outro',51]].map(([name,at])=><Sequence key={name} from={at*FPS}><Audio src={staticFile('audio/'+name+'.wav')} volume={.95}/></Sequence>)}
  <Sequence from={20*FPS} durationInFrames={24*FPS}><Audio src={staticFile('audio/conversation-edit.wav')} volume={.95}/></Sequence>
  <Audio src={staticFile('audio/bed.wav')} volume={f>=20*FPS&&f<44*FPS?.035:.06}/>
  <div style={{position:'absolute',left:0,bottom:0,width:interpolate(f,[0,3599],[0,1920]),height:3,background:'#b9d98e'}}/>
  <div style={{position:'absolute',inset:0,background:'#122f27',opacity:interpolate(f,[3580,3599],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}/>
 </AbsoluteFill>;
}
registerRoot(()=> <Composition id="RelayHackathon" component={Film} durationInFrames={3600} fps={FPS} width={1920} height={1080}/>);
