import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.location={pathname:'/'};
const {requestPanel}=await import('../static/request-review.js');
const call={status:'completed',transcript:[{role:'customer',text:'Saturday at two'}]};
const info={request:{revision:1,status:'needs_review',fields:{service:'<script>alert(1)</script>',preferred_day:'Saturday',preferred_time:'two'},owner:'',notes:'',evidence:{preferred_day:{quote:'Saturday at two',turn_index:0}},audit:[]},lead:null};

test('request panel shows evidence and unknowns without claiming a booking',()=>{
 const html=requestPanel(call,info);
 assert.match(html,/Calendar · Not connected/);
 assert.match(html,/CRM · Not connected/);
 assert.match(html,/No appointment has been booked/);
 assert.match(html,/Saturday at two/);
 assert.doesNotMatch(html,/<script>/);
 assert.match(html,/id="request-follow-up"[^>]*disabled/);
});
test('active conversations and previous lead revisions cannot imply current follow-up',()=>{
 assert.match(requestPanel({...call,status:'in_progress'},info),/fieldset disabled/);
 const stale={...info,request:{...info.request,status:'reviewed'},lead:{id:'lead-1',request_revision:0,owner:'Service desk'}};
 assert.match(requestPanel(call,stale),/earlier revision/);
});
