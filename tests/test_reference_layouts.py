import importlib.util
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    s=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
r=load('render_slide_spec'); report=load('build_html_report')

def spec():
    return {'pattern':'distribution','theme':'executive','layout':'analytical','headline':'Delivery capacity trails commitments','subline':'Monthly projects, illustrative planning case','exhibit_label':'Exhibit 1','source':'Source: illustrative data.','bins':[{'label':'Capacity','value':6},{'label':'Committed','value':10}], 'highlight':1}

class ReferenceLayouts(unittest.TestCase):
    def test_executive_columns_are_slim_and_keep_value_proportions(self):
        root=ET.fromstring(r.render(spec()));ns={'s':'http://www.w3.org/2000/svg'}
        bars=[e for e in root.findall('s:rect',ns) if e.get('fill') in ['#D1D5DB','#15296B']]
        self.assertEqual(len(bars),2)
        self.assertTrue(all(float(e.get('width'))<=88 for e in bars))
        self.assertAlmostEqual(float(bars[0].get('height'))/float(bars[1].get('height')),.6,places=2)

    def test_analytical_header_and_palette(self):
        s=spec();s['palette']='red';svg=r.render(s)
        self.assertIn('Exhibit 1',svg);self.assertIn('#B4232D',svg)
        ET.fromstring(svg)
    def test_sidebar_preserves_data_scale_and_separates_text(self):
        s=spec();s['commentary']={'title':'Decision required','points':['Add capacity before signing more work.']}
        root=ET.fromstring(r.render(s));ns={'s':'http://www.w3.org/2000/svg'}
        bars=[x for x in root.findall('s:rect',ns) if x.get('fill') in ['#D1D5DB','#15296B']]
        self.assertEqual(len(bars),2)
        self.assertAlmostEqual(float(bars[0].get('height'))/float(bars[1].get('height')),.6,places=2)
        self.assertTrue(all(float(x.get('x'))+float(x.get('width'))<=828 for x in bars))
    def test_compact_exhibit_omits_slide_chrome(self):
        s=spec();s['page_number']=91
        svg=r.render_exhibit(s)
        self.assertNotIn(s['headline'],svg);self.assertNotIn(s['source'],svg)
        self.assertIn('viewBox="40 180 1200 432"',svg)
    def test_report_compact_exhibit_keeps_semantic_caption_and_source(self):
        import json,tempfile
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'chart.json').write_text(json.dumps(spec()))
            html=report.build_report('---\ntitle: Review\nreport_style: briefing\nexhibit_mode: compact\n---\n## Recommendation\n\n![Delivery gap](spec:chart.json)',p)
        self.assertIn('report-briefing',html);self.assertIn('Source: illustrative data.',html)
        self.assertIn('exhibit-subline',html);self.assertNotIn('Delivery capacity trails commitments</text>',html)
    def test_briefing_has_no_hidden_toc_grid(self):
        html=report.build_report('---\nreport_style: briefing\n---\n## Decision\n\nProse.',ROOT)
        self.assertNotIn('<nav class="toc"',html)

    def test_compact_commentary_is_editable_prose(self):
        import json,tempfile
        s=spec();s['commentary']={'title':'Operating gate','points':['Confirm staffing first.']}
        self.assertNotIn('Confirm staffing first.',r.render_exhibit(s))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'c.json').write_text(json.dumps(s))
            html=report.build_report('---\nexhibit_mode: compact\n---\n![Gap](spec:c.json)',p)
        self.assertIn('<p class="exhibit-commentary">Confirm staffing first.</p>',html)

    def test_word_sample_has_native_tables_and_vector_fallback(self):
        import zipfile
        with zipfile.ZipFile(ROOT/'templates/reference-layouts/decision-brief.docx') as z:
            doc=ET.fromstring(z.read('word/document.xml'))
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            self.assertGreater(len(doc.findall('.//w:tbl',ns)),0)
            self.assertIn('Recommendation',''.join(doc.itertext()))
            self.assertTrue(any(x.endswith('.svg') for x in z.namelist()))
            self.assertTrue(any(x.endswith('.png') for x in z.namelist()))
            self.assertIn('Heading1',z.read('word/styles.xml').decode())

    def test_invalid_profiles_and_dense_content_fail(self):
        for change in [{'palette':'oops'},{'layout':'oops'},{'headline':'word '*80},{'commentary':{'title':'Decision','points':['word '*120]}},{'bins':[{'label':'Negative','value':-1}]}]:
            s=spec();s.update(change)
            with self.assertRaises(r.RenderSpecError):r.render(s)
        with self.assertRaises(report.ReportBuildError):report.build_report('---\nreport_style: unknown\n---\nBody',ROOT)

if __name__=='__main__':unittest.main()
