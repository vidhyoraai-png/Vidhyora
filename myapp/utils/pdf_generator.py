"""Render arbitrary HTML into a real, print-quality PDF using headless Chromium.

The markdown-to-PDF path in file_convert.py is deliberately plain-text-only —
it can't reproduce a real layout (CSS grid/flexbox, custom fonts, Tailwind
utility classes) because it never runs a browser engine at all. Driving actual
Chromium through Playwright instead means anything a browser can render,
including CDN-hosted stylesheets and fonts, comes out in the PDF exactly as
it would appear on screen.
"""

import logging

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class PDFGenerationError(Exception):
    """Raised when Chromium fails to launch, load, or print the given HTML."""


def render_html_to_pdf(html_content: str) -> bytes:
    """Render a complete HTML document to PDF bytes (A4, printed backgrounds).

    ``wait_until="networkidle"`` is what actually matters here: a CDN
    stylesheet (Tailwind's play build, Google Fonts) is fetched asynchronously
    after the markup loads, and printing before those requests finish
    captures an unstyled flash of the page instead of the intended design.
    """
    html_content = (html_content or '').strip()
    if not html_content:
        raise PDFGenerationError('No HTML content was provided to render.')

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.set_content(html_content, wait_until='networkidle')
                return page.pdf(format='A4', print_background=True)
            finally:
                # Always release the browser process, whether set_content/pdf
                # succeeded or raised — an exception here must never leak a
                # headless Chromium instance.
                browser.close()
    except PDFGenerationError:
        raise
    except Exception as exc:
        logger.exception('Playwright PDF rendering failed')
        raise PDFGenerationError(f'PDF rendering failed: {exc}') from exc
