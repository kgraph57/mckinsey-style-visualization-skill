#!/usr/bin/env node
/** Optional Word report exporter. Requires Node.js, docx and sharp; Python 3 for chart rendering.
 * Usage: node scripts/build_briefing_docx.cjs report.json -o report.docx
 * See references/reference-reproduction.md for the input contract and limits.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {Document,Packer,Paragraph,TextRun,HeadingLevel,Table,TableRow,TableCell,
    WidthType,BorderStyle,ShadingType,Header,Footer,AlignmentType,PageNumber,ImageRun} = require('docx');
const sharp = require('sharp');
const WIDTH = 9638; // A4 minus two 20mm margins, in twips.
const INK = '202124', MUTED = '62666B', RULE = 'C7CBCF';
const border = {style:BorderStyle.SINGLE,size:4,color:RULE};
const noBorder = {style:BorderStyle.NONE,size:0,color:'FFFFFF'};
const text = (value,options={}) => new TextRun({text:String(value ?? ''),...options});
const para = (value,options={}) => new Paragraph({children:[text(value)],...options});
function validate(data) {
    if (!data || typeof data.title !== 'string' || !Array.isArray(data.blocks)) throw Error('Report needs title and blocks');
    if (data.blocks.length>150) throw Error('Split reports with more than 150 blocks');
    for (const b of data.blocks) {
        if (!b || !['paragraph','heading','table','exhibit'].includes(b.type)) throw Error('Unsupported report block type');
        if (['paragraph','heading'].includes(b.type) && typeof b.text !== 'string') throw Error('Text block needs text');
        if (b.type==='table' && (!Array.isArray(b.headers) || b.headers.length<1 || b.headers.length>6 || !Array.isArray(b.rows) || b.rows.some(r=>!Array.isArray(r)||r.length!==b.headers.length))) throw Error('Table needs 1–6 headers and equally sized rows');
        if (b.type==='exhibit' && (typeof b.spec !== 'string' || typeof b.caption !== 'string')) throw Error('Exhibit needs spec path and caption');
    }
}
function table(block) {
    const widths=block.headers.map((_,i)=>Math.floor(WIDTH/block.headers.length)+(i===0?WIDTH%block.headers.length:0));
    const rows=[block.headers,...block.rows].map((row,i)=>new TableRow({tableHeader:i===0,cantSplit:true,children:row.map((cell,j)=>new TableCell({
        width:{size:widths[j],type:WidthType.DXA}, margins:{top:110,bottom:110,left:90,right:90},
        shading:{type:ShadingType.CLEAR,fill:'FFFFFF'},borders:{top:noBorder,left:noBorder,right:noBorder,bottom:border},
        children:[para(cell,{children:[text(cell,{bold:i===0,color:i===0?INK:MUTED,size:18})],spacing:{after:0}})]
    }))}));
    return new Table({width:{size:WIDTH,type:WidthType.DXA},columnWidths:widths,rows,borders:{top:border,bottom:border,left:noBorder,right:noBorder,insideVertical:noBorder,insideHorizontal:border}});
}
async function build(data,base) {
    validate(data);
    const children=[para(data.classification || 'Decision brief',{children:[text(data.classification || 'Decision brief',{size:16,color:MUTED})]}),
        para(data.title,{heading:HeadingLevel.TITLE,spacing:{after:180}}),
        para(data.subtitle || '',{spacing:{after:120}}),
        para([data.author,data.date].filter(Boolean).join(' · '),{children:[text([data.author,data.date].filter(Boolean).join(' · '),{size:16,color:MUTED})],border:{bottom:border},spacing:{after:240}})];
    let exhibit=0;
    for (const block of data.blocks) {
        if(block.type==='heading') children.push(para(block.text,{heading:HeadingLevel.HEADING_1,keepNext:true,spacing:{before:240,after:120}}));
        if(block.type==='paragraph') children.push(para(block.text,{spacing:{after:120,line:280},widowControl:true}));
        if(block.type==='table') children.push(table(block),para('',{spacing:{after:80}}));
        if(block.type==='exhibit') {
            const specPath=path.resolve(base,block.spec), spec=JSON.parse(fs.readFileSync(specPath,'utf8'));
            // No temporary files; render directly to stdout through the existing stdlib renderer.
            const result=spawnSync(process.env.PYTHON || 'python3',['-c',
                'import sys,json;sys.path.insert(0,sys.argv[1]);from render_slide_spec import render_exhibit;print(render_exhibit(json.load(open(sys.argv[2]))))',
                __dirname,specPath],{encoding:'utf8',maxBuffer:8*1024*1024});
            if(result.status!==0) throw Error(`Exhibit failed: ${block.spec}: ${result.stderr || result.error}`);
            const svg=Buffer.from(result.stdout), png=await sharp(svg,{density:160}).png().toBuffer();
            children.push(para(`Exhibit ${++exhibit}. ${block.caption}`,{children:[text(`Exhibit ${exhibit}. ${block.caption}`,{bold:true,size:22})],keepNext:true,spacing:{before:200,after:80}}));
            if(spec.subline) children.push(para(spec.subline,{children:[text(spec.subline,{size:17,color:MUTED})],keepNext:true,spacing:{after:60}}));
            children.push(new Paragraph({children:[new ImageRun({type:'svg',data:svg,transformation:{width:642,height:231.12},fallback:{type:'png',data:png},altText:{title:block.caption,description:spec.subline||block.caption,name:`Exhibit ${exhibit}`}})],keepNext:true}));
            for(const note of [...(spec.footnotes||[]),spec.source].filter(Boolean)) children.push(para(note,{children:[text(note,{size:15,color:MUTED})],spacing:{after:60}}));
            if(spec.commentary) {
                children.push(para(spec.commentary.title,{children:[text(spec.commentary.title,{bold:true,size:20})],keepNext:true,spacing:{before:120,after:60}}));
                for(const point of spec.commentary.points) children.push(para(point));
            }
            if(spec.annotation) children.push(para(spec.annotation,{children:[text(spec.annotation,{bold:true})]}));
        }
    }
    return new Document({creator:data.author || 'Strategy Office',title:data.title,description:'Editable briefing with source-linked exhibits',styles:{default:{document:{run:{font:'Arial',size:20,color:INK},paragraph:{spacing:{after:120}}}},paragraphStyles:[
        {id:'Title',name:'Title',basedOn:'Normal',run:{font:'Arial',size:48,bold:true,color:INK}},
        {id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',quickFormat:true,paragraph:{outlineLevel:0,keepNext:true},run:{font:'Arial',size:26,bold:true,color:INK}}
    ]},sections:[{properties:{page:{size:{width:11906,height:16838},margin:{top:1134,bottom:1134,left:1134,right:1134,header:567,footer:567}}},headers:{default:new Header({children:[para(data.running_title || data.title,{children:[text(data.running_title || data.title,{size:15,color:MUTED})],border:{bottom:border}})]})},footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[text('Page ',{size:15,color:MUTED}),new TextRun({children:[PageNumber.CURRENT],size:15,color:MUTED})]})]})},children}]});
}
async function main() {
    const args=process.argv.slice(2),o=args.indexOf('-o');
    if(args.length!==3||o!==1) throw Error('Usage: node scripts/build_briefing_docx.cjs report.json -o report.docx');
    const input=path.resolve(args[0]),data=JSON.parse(fs.readFileSync(input,'utf8'));
    const doc=await build(data,path.dirname(input));fs.writeFileSync(args[2],await Packer.toBuffer(doc));
    console.log(`OK: built ${args[2]}`);
}
if(require.main===module) main().catch(e=>{console.error(`ERROR: ${e.message}`);process.exitCode=1;});
module.exports={build,validate};
