// Optional: node --test tests/test_word_briefing.cjs (requires docx and sharp).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {validate,build}=require('../scripts/build_briefing_docx.cjs');
const {Packer}=require('docx');
test('reject inconsistent table rows before writing an unreadable document',()=>{
    assert.throws(()=>validate({title:'Review',blocks:[{type:'table',headers:['A','B'],rows:[['one']]}]}),/equally sized/);
});
test('reject unknown block types',()=>{
    assert.throws(()=>validate({title:'Review',blocks:[{type:'script',text:'x'}]}),/Unsupported/);
});
test('native text and table documents pack successfully',async()=>{
    const doc=await build({title:'Review & decision',blocks:[{type:'heading',text:'Recommendation'},{type:'paragraph',text:'Keep <values> literal.'},{type:'table',headers:['Action','Owner'],rows:[['Validate','Operations']]}]},__dirname);
    const out=await Packer.toBuffer(doc);assert.equal(out.subarray(0,2).toString(),'PK');assert.ok(out.length>5000);
});
