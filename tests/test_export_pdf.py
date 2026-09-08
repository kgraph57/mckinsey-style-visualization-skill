import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('export_pdf',ROOT/'scripts/export_pdf.py')
pdf=importlib.util.module_from_spec(spec);spec.loader.exec_module(pdf)

class PDFTests(unittest.TestCase):
    def test_rejects_remote_or_non_html_input(self):
        with self.assertRaises(pdf.PDFExportError):pdf.export_pdf('https://example.com','x.pdf')
    def test_failed_export_preserves_existing_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);src=p/'input.html';src.write_text('<p>Hi</p>');out=p/'out.pdf';out.write_bytes(b'original')
            with patch.object(pdf,'find_browser',return_value='/browser'),patch.object(pdf,'render_html_pdf',side_effect=pdf.PDFExportError('Render failed')):
                with self.assertRaises(pdf.PDFExportError):pdf.export_pdf(src,out)
            self.assertEqual(out.read_bytes(),b'original')
    def test_export_promotes_complete_pdf_atomically(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);src=p/'input with space.html';src.write_text('<p>Hi</p>');out=p/'out.pdf'
            def render(source,target,executable):
                self.assertEqual(source,src.resolve())
                self.assertEqual(executable,'/browser')
                target.write_bytes(b'%PDF-1.7\n'+b'0'*150)
            with patch.object(pdf,'find_browser',return_value='/browser'),patch.object(pdf,'render_html_pdf',side_effect=render):pdf.export_pdf(src,out)
            self.assertTrue(out.read_bytes().startswith(b'%PDF-'))
