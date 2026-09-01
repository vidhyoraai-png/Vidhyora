"""Single source of truth for EduTrellis's real, verified contact details.

Every place that shows or tells a user this information — the AI chat
system prompt, company_knowledge's grounding context, and the public
site's contact cards/footers (via the `business_info` context processor,
see edutrellis/settings.py) — must read it from here, not keep its own
hardcoded copy. Update it in exactly one place when a real detail changes.

There is deliberately only ONE phone/WhatsApp number and ONE general
support email. EduTrellis does not have a separate sales line, toll-free
number, or a second support address — do not add one here without it
being genuinely true, since anything added here is treated as
authoritative and handed straight to the AI model as fact.
"""

PHONE_DISPLAY = '+91 96959 53183'
PHONE_E164 = '+919695953183'           # for tel: links
WHATSAPP_DIGITS = '919695953183'       # for wa.me links (no leading +)
WHATSAPP_LINK = f'https://wa.me/{WHATSAPP_DIGITS}'

EMAIL_SUPPORT = 'support@edutrellis.in'
EMAIL_CEO = 'ceo@edutrellis.in'

WEBSITE = 'https://www.edutrellis.in/'

ADDRESS = 'P-109, Prembagh, Shahpur, Chinhat, Lucknow, Uttar Pradesh 226028'
ADDRESS_SHORT = 'P-109, Prembagh, Shahpur, Chinhat, Lucknow, UP 226028'
# Split out for schema.org/JSON-LD PostalAddress blocks (streetAddress,
# addressLocality, etc), which want the address as separate fields rather
# than one string — kept in sync with ADDRESS/ADDRESS_SHORT above.
ADDRESS_STREET = 'P-109, Prembagh, Shahpur, Chinhat'
ADDRESS_CITY = 'Lucknow'
ADDRESS_STATE = 'Uttar Pradesh'
ADDRESS_ZIP = '226028'
ADDRESS_COUNTRY = 'IN'

HOURS = 'Monday-Saturday 9 AM-8 PM; Sunday 10 AM-6 PM'

INSTAGRAM_URL = 'https://www.instagram.com/edutrellis'
LINKEDIN_COMPANY_URL = 'https://www.linkedin.com/company/edutrellis'
LINKEDIN_FOUNDER_URL = 'https://www.linkedin.com/in/vijaytiwariii/'
FACEBOOK_URL = 'https://www.facebook.com/profile.php?id=61590850943948'

# The exact reply the AI must give instead of inventing a detail it wasn't
# actually given — see ai_chat.SYSTEM_PROMPT and company_knowledge.py.
NOT_FOUND_MESSAGE = (
    "I couldn't find verified information for that. Please visit "
    "edutrellis.in or contact support@edutrellis.in."
)


def as_dict():
    return {
        'phone_display': PHONE_DISPLAY,
        'phone_e164': PHONE_E164,
        'whatsapp_link': WHATSAPP_LINK,
        'email_support': EMAIL_SUPPORT,
        'email_ceo': EMAIL_CEO,
        'website': WEBSITE,
        'address': ADDRESS,
        'address_short': ADDRESS_SHORT,
        'address_street': ADDRESS_STREET,
        'address_city': ADDRESS_CITY,
        'address_state': ADDRESS_STATE,
        'address_zip': ADDRESS_ZIP,
        'address_country': ADDRESS_COUNTRY,
        'hours': HOURS,
        'instagram_url': INSTAGRAM_URL,
        'linkedin_company_url': LINKEDIN_COMPANY_URL,
        'linkedin_founder_url': LINKEDIN_FOUNDER_URL,
        'facebook_url': FACEBOOK_URL,
    }


_CONTEXT = as_dict()


def context_processor(request):
    """Registered in edutrellis/settings.py TEMPLATES/OPTIONS/context_
    processors — exposes every value above to every template as `BIZ`
    (e.g. `{{ BIZ.phone_display }}`, `{{ BIZ.whatsapp_link }}`), so contact
    cards/footers render from this one source instead of their own
    hardcoded copy. Built once at import time since these are constants,
    not computed per-request."""
    return {'BIZ': _CONTEXT}
