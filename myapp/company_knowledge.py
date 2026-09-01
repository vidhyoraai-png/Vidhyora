"""Verified Vidhyora AI company facts supplied to chat models."""

import re

from myapp import business_info


_BRAND_RE = re.compile(r"\b(vidhyora|edutrellis|edutrellis\.in)\b", re.IGNORECASE)
_CONTACT_KEYWORD_RE = re.compile(
    r"\b(phone|telephone|mobile|whatsapp|what.?s ?app|call(?:ing)?|e-?mail|"
    r"contact|address|location|office|sales|support|helpline|instagram|"
    r"facebook|linkedin|social(?:\s*media|\s*handles?)?|hours|timings?)\b",
    re.IGNORECASE,
)


def is_company_query(text):
    text = text or ''
    return bool(_BRAND_RE.search(text) or _CONTACT_KEYWORD_RE.search(text))


PUBLIC_SITE_CONTEXT = f"""VERIFIED VIDHYORA AI DATA (authoritative):
Use only these details for company answers. Never invent a phone number,
email, address, person, statistic, social handle, product, price, or URL.
If a requested detail is absent, say so and point to edutrellis.in or
{business_info.EMAIL_SUPPORT}.

Vidhyora AI is an AI assistant offering chat, reasoning, coding, document
help, image understanding, image generation/editing, notes, web-assisted
answers, audio transcription, YouTube downloads, and optional GitHub
repository workflows.

Official AI pages: {business_info.WEBSITE} and {business_info.WEBSITE}AI/
Support: {business_info.EMAIL_SUPPORT}
Call/WhatsApp: {business_info.PHONE_DISPLAY}
Hours: {business_info.HOURS}
Instagram: {business_info.INSTAGRAM_URL}
LinkedIn: {business_info.LINKEDIN_COMPANY_URL}
Facebook: {business_info.FACEBOOK_URL}

There is one general support email and one phone/WhatsApp number. Never
invent a separate sales line, toll-free number, international number, or
second support address. Do not provide a physical office address or name
an individual as founder, owner, CEO, or creator.
"""
