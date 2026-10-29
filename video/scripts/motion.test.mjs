import test from 'node:test';import assert from 'node:assert/strict';
import {cursorAt,ease} from '../src/motion.mjs';
test('cursor holds before a move and lands exactly at its target',()=>{
 const m={initial:{x:10,y:20},events:[{type:'move',at:1,duration:1,from:{x:10,y:20},to:{x:600,y:400}}]};
 assert.deepEqual(cursorAt(m,.5),m.initial);assert.deepEqual(cursorAt(m,2),{x:600,y:400});
});
test('60 fps cursor movement has no discontinuities or overshoot',()=>{
 const m={initial:{x:0,y:0},events:[{type:'move',at:0,duration:1,from:{x:0,y:0},to:{x:600,y:0}}]};
 const points=Array.from({length:61},(_,f)=>cursorAt(m,f/60).x);
 assert.ok(points.every((x,i)=>x>=0&&x<=600&&(!i||x>=points[i-1])));
 assert.ok(Math.max(...points.slice(1).map((x,i)=>x-points[i]))<19);
 assert.ok(points[1]<.03);assert.equal(ease(0),0);assert.equal(ease(1),1);
});
