import re

from django.db import migrations

# EduTrellis AI's public identity/contact story changed: the assistant must
# never name any individual (previously "Rudra Narayan Tiwari") as its
# creator — only "EduTrellis" — and must never state the physical office
# address in a chat reply (contact should be email/WhatsApp/call only).
# Matches the corresponding ai_chat.py/company_knowledge.py prompt changes.
# See 0036_fix_rudra_role_knowledge.py for the same pattern used previously.
TOPIC_UPDATES = {
    'EduTrellis team': (
        "Vijay Tiwari is EduTrellis's Founder & CEO. The EduTrellis AI chat "
        "assistant (a separate feature from the company itself) was built "
        "by EduTrellis. For other team or staff inquiries, contact "
        "support@edutrellis.in."
    ),
    'EduTrellis AI creator': (
        "The EduTrellis AI chat feature (this assistant) was built by "
        "EduTrellis. The company itself was founded by Vijay Tiwari, "
        "EduTrellis's Founder & CEO."
    ),
    'EduTrellis contact information': (
        "Contact EduTrellis at support@edutrellis.in, or WhatsApp/call "
        "+91 96959 53183."
    ),
}

# Any older auto-learned ("chat"/"web_search" sourced) entry that leaked a
# personal name or the physical address into a cached reply — same
# reasoning as 0042_purge_fake_contact_knowledge.py's purge of fabricated
# contact details: harmless when written, but now stale/wrong policy, and
# worth clearing so a future retrieval can't surface it.
_STALE_INFO_RE = re.compile(r"Rudra|Prembagh|Shahpur|Chinhat|226028", re.IGNORECASE)


def fix_identity_and_address(apps, schema_editor):
    KnowledgeEntry = apps.get_model('myapp', 'KnowledgeEntry')
    shared = {'user__isnull': True, 'session_key': ''}
    for topic, content in TOPIC_UPDATES.items():
        KnowledgeEntry.objects.filter(topic=topic, source='manual', **shared).update(content=content)
    stale_ids = [
        entry.pk for entry in KnowledgeEntry.objects.exclude(source='manual')
        if _STALE_INFO_RE.search(entry.topic) or _STALE_INFO_RE.search(entry.content)
    ]
    if stale_ids:
        KnowledgeEntry.objects.filter(pk__in=stale_ids).delete()


def noop_reverse(apps, schema_editor):
    # Deliberately no-op — the previous content is no longer correct policy,
    # so there's nothing worth restoring on a reverse migration.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0043_storeprofile_ai_display_name_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_identity_and_address, noop_reverse),
    ]
