// Re-render just the corrected real-app memory shot; keep the original audio continuous.
import {bundle} from '@remotion/bundler';
import {ensureBrowser,selectComposition,renderMedia} from '@remotion/renderer';
import {execFileSync} from 'node:child_process';import fs from 'node:fs';
const serveUrl=await bundle({entryPoint:process.cwd()+'/src/index.jsx',publicDir:process.cwd()+'/public'}),b=await ensureBrowser({chromeMode:'headless-shell'}),chromiumOptions={gl:'swangle'};
const composition=await selectComposition({serveUrl,id:'RelayHackathon',browserExecutable:b.path,chromiumOptions});
await renderMedia({serveUrl,composition,browserExecutable:b.path,chromiumOptions,imageFormat:'png',codec:'h264',audioCodec:'aac',crf:17,pixelFormat:'yuv420p',frameRange:[2640,3077],outputLocation:'out/memory-refined.mp4',concurrency:4});
const filter='[0:v]trim=start_frame=0:end_frame=2640,setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[0:v]trim=start_frame=3078:end_frame=3600,setpts=PTS-STARTPTS[c];[a][b][c]concat=n=3:v=1:a=0,scale=in_range=auto:out_range=tv:out_color_matrix=bt709[v]';
execFileSync('ffmpeg',['-v','error','-y','-i','out/master.mp4','-i','out/memory-refined.mp4','-filter_complex',filter,'-map','[v]','-map','0:a','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-af','loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000,atrim=duration=60','-c:a','aac','-b:a','192k','-t','60','-movflags','+faststart','out/giani-hackathon-demo.mp4']);
fs.copyFileSync('out/giani-hackathon-demo.mp4','out/giani-hackathon-demo-v2.mp4');
console.log('Refined memory shot, continuous audio, and 60 fps export complete.');
