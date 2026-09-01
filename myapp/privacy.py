"""Remove common personal identifiers before text is sent to an LLM."""
import re

from django.conf import settings


_FALLBACK_PATTERNS = (
    (re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'), '<EMAIL>'),
    (re.compile(r'(?<!\d)(?:\+?91[- ]?)?[6-9]\d{9}(?!\d)'), '<PHONE>'),
    (re.compile(r'\b(?:\d[ -]*?){13,19}\b'), '<PAYMENT_NUMBER>'),
)
_analyzer = _anonymizer = None
_presidio_unavailable = False


def _fallback_redact(text):
    for pattern, replacement in _FALLBACK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact(text):
    if not text:
        return text

    # Presidio initializes spaCy and its NLP model on first use. Doing that
    # in the ordinary chat request path creates a very large cold start and
    # can exhaust memory on small Railway containers. The fast regex path
    # covers the identifiers this app promises to remove. Full Presidio is
    # still available as an opt-in for deployments with enough memory.
    if not getattr(settings, 'AI_USE_PRESIDIO', False):
        return _fallback_redact(text)

    global _analyzer, _anonymizer, _presidio_unavailable
    try:
        if _presidio_unavailable:
            raise RuntimeError('Presidio unavailable')
        if _analyzer is None:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            _analyzer, _anonymizer = AnalyzerEngine(), AnonymizerEngine()
        findings = _analyzer.analyze(text=text, language='en')
        return _anonymizer.anonymize(text=text, analyzer_results=findings).text
    except Exception:
        _presidio_unavailable = True
        return _fallback_redact(text)
