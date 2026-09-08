#!/usr/bin/env python3
"""Export a local, self-contained HTML deck or report to PDF with Chromium.

Requires Python playwright and installed Google Chrome or Chromium.
The HTML's print CSS owns page size and pagination. No Office conversion.
Usage: python3 scripts/export_pdf.py report.html -o report.pdf
"""
import argparse
import os
from pathlib import Path
import shutil
import tempfile


class PDFExportError(ValueError):
    pass


def find_browser(explicit=None):
    if explicit:
        candidate = shutil.which(explicit) or explicit
        if Path(candidate).is_file():
            return str(Path(candidate).resolve())
        raise PDFExportError('Browser executable not found: '+explicit)
    candidates = [shutil.which(name) for name in ('google-chrome', 'chromium', 'chromium-browser')]
    candidates += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                   '/Applications/Chromium.app/Contents/MacOS/Chromium']
    for base in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        if os.environ.get(base):
            candidates.append(str(Path(os.environ[base])/'Google/Chrome/Application/chrome.exe'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise PDFExportError('Install Google Chrome/Chromium, or pass --browser /path/to/executable')



def render_html_pdf(source, target, executable):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PDFExportError('Install the optional PDF dependency: python3 -m pip install playwright') from exc
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=executable, headless=True)
            try:
                page = browser.new_page(viewport={"width":1280,"height":720})
                page.set_default_timeout(30000)
                page.goto(source.as_uri(), wait_until='load', timeout=30000)
                page.emulate_media(media='print')
                page.evaluate('document.fonts.ready')
                page.pdf(path=str(target), prefer_css_page_size=True, print_background=True,
                         display_header_footer=False)
            finally:
                browser.close()
    except Exception as exc:
        raise PDFExportError('Chromium PDF export failed: '+str(exc)) from exc

def export_pdf(input_path, output_path, browser=None):
    source = Path(input_path).resolve()
    output = Path(output_path).resolve()
    if not source.is_file() or source.suffix.lower() not in ('.html', '.htm'):
        raise PDFExportError('Input must be an existing local HTML report or deck')
    if output.suffix.lower() != '.pdf':
        raise PDFExportError('Output must use the .pdf extension')
    if not output.parent.is_dir():
        raise PDFExportError('Output directory does not exist')
    executable = find_browser(browser)
    with tempfile.TemporaryDirectory(prefix='consulting-pdf-') as td:
        target = Path(td)/'export.pdf'
        render_html_pdf(source, target, executable)
        if not target.is_file():
            raise PDFExportError('Chromium did not produce a PDF')
        payload = target.read_bytes()
        if not payload.startswith(b'%PDF-') or len(payload) < 100:
            raise PDFExportError('Browser output is not a valid PDF file')
        # Preserve an existing destination until a complete export exists.
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False, suffix='.tmp') as f:
            temporary = Path(f.name)
            f.write(payload)
        try:
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('--browser', help='Chrome or Chromium executable')
    args = parser.parse_args()
    try:
        print('OK: exported', export_pdf(args.input,args.output,args.browser))
    except PDFExportError as exc:
        parser.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
