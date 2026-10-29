import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.location={pathname:'/'};
const {editWorkflow}=await import('../static/forms.js');

test('new and existing workflow editors open without borrowing agent fields',()=>{
 let content='';
 const form={},cancel={},close={};
 const dialog={set innerHTML(value){content=value},querySelector(s){return s==='h2'?{textContent:'Workflow'}:s==='#editor'?form:s==='[data-cancel]'?cancel:close},setAttribute(){},showModal(){},close(){}};
 globalThis.document={querySelector:()=>dialog};
 const agents=[{id:'agent-sales',name:'Sales'}];
 editWorkflow(null,{agents},async()=>{});
 assert.match(content,/Create a workflow/);
 assert.doesNotMatch(content,/name="delivery"/);
 editWorkflow({id:'w',name:'Follow up',agent_id:'agent-sales',segment:'Leads',action:'Create follow-up task',status:'active'},{agents},async()=>{});
 assert.match(content,/Edit workflow/);
 assert.equal(typeof form.onsubmit,'function');
});
