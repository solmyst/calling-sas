import {bundle} from '@remotion/bundler';
import {ensureBrowser,renderStill} from '@remotion/renderer';
const serveUrl=await bundle({entryPoint:process.cwd()+'/src/index.jsx',publicDir:process.cwd()+'/public'});
const browser=await ensureBrowser({chromeMode:'headless-shell'});
const composition={id:'RelayHackathon',width:1920,height:1080,fps:60,durationInFrames:3600};
for(const frame of [180,600,1500,2900]){
 await renderStill({serveUrl,composition,browserExecutable:browser.path,chromiumOptions:{gl:'swangle'},imageFormat:'png',frame,output:process.cwd()+`/out/revision-preview-${frame}.png`});
 console.log('Preview',frame);
}
