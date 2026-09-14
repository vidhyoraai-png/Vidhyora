from django.db import migrations

# Seeds EduTrellis Light's knowledge base with core, already-known facts
# (founder/CEO, company background, services, site pages, contact info, and
# the AI's own model lineup) so a basic company question gets an instant,
# authoritative answer instead of Light falling back to a live (paid, and
# potentially off-topic) web search for something the system prompt already
# knows. Every fact here is drawn directly from ai_chat.SYSTEM_PROMPT and
# ai_chat.MODELS — nothing invented. Deliberately no "packages/pricing"
# numbers are seeded, since none are defined anywhere in the codebase to
# draw from; that entry instead points people to a real quote/consultation
# rather than making up figures.
ENTRIES = [
    (
        'EduTrellis founder and CEO',
        "EduTrellis was founded in 2020 by Vijay Tiwari, who is the company's "
        "Founder & CEO. EduTrellis is a website development and digital "
        "growth company based in Lucknow, Uttar Pradesh, India.",
    ),
    (
        'EduTrellis team',
        "Vijay Tiwari is EduTrellis's Founder & CEO. The EduTrellis AI chat "
        "assistant (a separate feature from the company itself) was built "
        "by Rudra Narayan Tiwari. For other team or staff inquiries, "
        "contact support@edutrellis.in.",
    ),
    (
        'EduTrellis AI creator',
        "The EduTrellis AI chat feature (this assistant) was built by Rudra "
        "Narayan Tiwari. This is separate from the company itself, which "
        "was founded by Vijay Tiwari.",
    ),
    (
        'EduTrellis company overview and services',
        "EduTrellis is a website development and digital growth company "
        "based in Lucknow, Uttar Pradesh, India, founded in 2020. Services "
        "include: website design & development, website management, SEO, "
        "Meta Ads, Google Business Profile setup, WordPress and Django "
        "development, logo/banner design, social media handle setup, and "
        "digital marketing services.",
    ),
    (
        'EduTrellis website pages',
        "edutrellis.in (homepage) is the main business site. "
        "edutrellis.in/websitecreation is a dedicated page for getting a "
        "custom website built — from single-page static business sites to "
        "full dynamic e-commerce stores and large custom web apps — with a "
        "free consultation, strategy, build, and ongoing growth process. "
        "edutrellis.in/store is EduTrellis Store, the company's own online "
        "gadget store selling earbuds, headphones, smartwatches, keyboards, "
        "power banks, chargers, and smart home devices across India, with "
        "Razorpay/COD payment options and order tracking. edutrellis.in/AI "
        "is this AI chat assistant.",
    ),
    (
        'EduTrellis contact information',
        "Contact EduTrellis at support@edutrellis.in, or WhatsApp/call "
        "+91 96959 53183. Office: P-109, Prembagh, Shahpur, Chinhat, "
        "Lucknow, Uttar Pradesh 226028.",
    ),
    (
        'EduTrellis packages and pricing',
        "EduTrellis doesn't publish fixed package prices online — website "
        "and service pricing depends on the specific project's scope and "
        "requirements. For an actual quote, contact EduTrellis via "
        "support@edutrellis.in or WhatsApp/call +91 96959 53183, or use "
        "the free consultation on edutrellis.in/websitecreation.",
    ),
    (
        'EduTrellis AI models available',
        "EduTrellis AI offers several modes, switchable from the model "
        "picker in the chat: EduTrellis Ultra (most capable, best for "
        "detailed or complex questions), EduTrellis Quick (fast and "
        "lightweight, best for short simple questions), EduTrellis Light "
        "(fastest — answers from EduTrellis's saved knowledge first, and "
        "searches the web if the answer isn't there), EduTrellis Code "
        "(tuned for coding, debugging, and technical questions), and "
        "EduTrellis Vision (understands images, used automatically when "
        "one is attached).",
    ),
]


def seed_knowledge_base(apps, schema_editor):
    # Historical models from apps.get_model() don't carry over class-level
    # constants like KnowledgeEntry.SOURCE_MANUAL (only fields survive) —
    # 'manual' is that same value, just written literally here instead.
    KnowledgeEntry = apps.get_model('myapp', 'KnowledgeEntry')
    for topic, content in ENTRIES:
        KnowledgeEntry.objects.get_or_create(
            topic=topic,
            defaults={'content': content, 'source': 'manual'},
        )


def unseed_knowledge_base(apps, schema_editor):
    KnowledgeEntry = apps.get_model('myapp', 'KnowledgeEntry')
    KnowledgeEntry.objects.filter(topic__in=[topic for topic, _ in ENTRIES], source='manual', user__isnull=True, session_key='').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0029_knowledgeentry_session_key_knowledgeentry_user'),
    ]

    operations = [
        migrations.RunPython(seed_knowledge_base, unseed_knowledge_base),
    ]
