export const ease=t=>{t=Math.max(0,Math.min(1,t));return t*t*t*(t*(t*6-15)+10);};
export function cursorAt(motion,time){
 let point=motion.initial;
 for(const e of motion.events){
  if(e.type!=='move'||e.at>time)continue;
  const t=ease((time-e.at)/e.duration);
  point={x:e.from.x+(e.to.x-e.from.x)*t,y:e.from.y+(e.to.y-e.from.y)*t};
 }
 return point;
}
