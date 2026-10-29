import React from 'react';
import {registerRoot,Composition,AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,staticFile,useCurrentFrame,interpolate,Easing} from 'remotion';
const FPS=30;
const chapters=[
 {from:0,to:210,clip:'choose-edit.mp4',step:'01 / CHOOSE A WORKFLOW',title:'Business context. Real voice conversations.',caption:'Sales · Business helper · Customer care · Appointment intake',y:440},
 {from:210,to:480,clip:'configure-edit.mp4',step:'02 / CONFIGURE THE AGENT',title:'Your instructions. Your business context.',caption:'Language, delivery, opening message, and approved business facts.',y:450},
 {from:480,to:660,image:'configure-last.png',step:'03 / START IN THE BROWSER',title:'Microphone in. Natural speech out.',caption:'Gnani Prisma → Bifrost → Gnani Timbre',y:430},
 {from:660,to:1320,clip:'conversation-edit.mp4',step:'04 / LIVE VOICE EXCHANGE',title:'Speak over the AI. It listens.',caption:'Automatic barge-in · Silero VAD · Latest correction remembered',y:500},
 {from:1320,to:1530,clip:'memory-edit.mp4',step:'05 / REVIEW THE CONTEXT',title:'The correction survives the conversation.',caption:'Saved transcript · Interruption markers · Session memory',y:535},
 {from:1530,to:1650,clip:'analytics-edit.mp4',step:'06 / SEE THE OUTCOME',title:'Conversations you can trace and review.',caption:'Browser sessions and typed simulations remain separately labelled.',y:430},
 {from:1650,to:1800,clip:'outro-edit.mp4',step:'RELAY VOICE / GNANI HACKATHON',title:'One workspace. Four practical use cases.',caption:'Explore the demo → solmyst.github.io/calling-sas',y:440},
];
function Scene({c}){
 const frame=useCurrentFrame(),progress=frame/(c.to-c.from);
 const enter=interpolate(frame,[0,10],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.out(Easing.cubic)});
 let y=c.y;
 if(c.clip==='conversation-edit.mp4')y=interpolate(progress,[0,.4,1],[430,500,570]);
 if(c.clip==='choose-edit.mp4')y=interpolate(progress,[0,.3,.52,.64,.8,1],[440,440,600,600,440,440],{easing:Easing.inOut(Easing.cubic)});
 if(c.clip==='configure-edit.mp4')y=interpolate(progress,[0,.3,.48,.6,.78,1],[450,450,570,570,450,450],{easing:Easing.inOut(Easing.cubic)});
 const scale=1.24; // Camera crops only genuine app pixels; all content comes from capture.
 return <AbsoluteFill style={{opacity:enter}}>
  <div style={{position:'absolute',left:72,top:102,display:'flex',gap:16,alignItems:'center',color:'#6b7d71',fontSize:17,fontWeight:700,letterSpacing:2.2}}>{c.step}</div>
  <div data-qa="title" style={{position:'absolute',left:72,top:136,fontSize:46,fontWeight:650,letterSpacing:-1.7,color:'#eaf2e4',lineHeight:1.1}}>{c.title}</div>
  <div style={{position:'absolute',left:72,top:218,width:1776,height:746,borderRadius:17,overflow:'hidden',border:'1px solid #b8c7b533',boxShadow:'0 22px 70px #0004',background:'#f7f8f5'}}>
   <div style={{position:'absolute',left:0,top:0,width:'100%',height:30,background:'#e7ece4',zIndex:2,display:'flex',alignItems:'center',paddingLeft:17,gap:6,borderBottom:'1px solid #d6dfd1'}}>{['#9bac97','#b6c5aa','#ccd6c4'].map((color,i)=><span key={i} style={{width:7,height:7,borderRadius:'50%',background:color}}/>)}<span style={{marginLeft:17,fontSize:12,color:'#66765d',letterSpacing:.2}}>Relay Voice · product capture · fictional demo workspace</span></div>
   <div style={{position:'absolute',top:30,width:'100%',height:716,overflow:'hidden'}}>
    <div style={{position:'absolute',width:1440,height:900,left:888-720*scale,top:358-y*scale,transform:`scale(${scale})`,transformOrigin:'top left'}}>
     {c.image?<Img src={staticFile('capture/'+c.image)} style={{width:'100%',height:'100%'}}/>:<OffthreadVideo muted src={staticFile('capture/'+c.clip)} style={{width:'100%',height:'100%'}}/>}
    </div>
   </div>
  </div>
  <div data-qa="caption" style={{position:'absolute',left:72,right:72,top:991,display:'flex',alignItems:'center',justifyContent:'space-between',color:'#dce8d2',fontSize:24,fontWeight:500}}><span>{c.caption}</span><span style={{fontSize:14,letterSpacing:1.4,color:'#92a48b'}}>{c.from===660?'RECORDED LIVE · WAITING TIME SHORTENED':'REAL APPLICATION · DEMO DATA'}</span></div>
 </AbsoluteFill>;
}
function Film(){
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#122f27',fontFamily:'Arial, sans-serif'}}>
  <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse at 70% 20%, #49674430, transparent 70%)'}}/>
  <div style={{position:'absolute',left:72,top:31,display:'flex',alignItems:'center',gap:12}}><Img src={staticFile('brand.svg')} style={{width:38,height:38}}/><span style={{fontSize:30,fontWeight:700,letterSpacing:-1.2,color:'#f3f5ee'}}>relay.<span style={{fontWeight:400,color:'#b1c0a9'}}>voice</span></span></div>
  <div style={{position:'absolute',right:72,top:41,color:'#bed6ab',fontSize:17,letterSpacing:2,fontWeight:600}}>GNANI HACKATHON / PRODUCT DEMO</div>
  {chapters.map(c=><Sequence key={c.from} from={c.from} durationInFrames={c.to-c.from}><Scene c={c}/></Sequence>)}
  {[['intro',0],['configure',210],['liveintro',480],['review',1320],['outro',1530]].map(([name,from])=><Sequence key={name} from={from}><Audio src={staticFile('audio/'+name+'.wav')} volume={.95}/></Sequence>)}
  <Sequence from={660} durationInFrames={660}><Audio src={staticFile('audio/conversation-edit.wav')} volume={.95}/></Sequence>
  <Audio src={staticFile('audio/bed.wav')} volume={f>=660&&f<1320?.045:.075}/>
  <div style={{position:'absolute',left:0,bottom:0,width:interpolate(f,[0,1799],[0,1920]),height:4,background:'#b9d98e'}}/>
  <div style={{position:'absolute',inset:0,background:'#122f27',opacity:interpolate(f,[1790,1799],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}),pointerEvents:'none'}}/>
 </AbsoluteFill>;
}
registerRoot(()=> <Composition id="RelayHackathon" component={Film} durationInFrames={1800} fps={FPS} width={1920} height={1080}/>);
