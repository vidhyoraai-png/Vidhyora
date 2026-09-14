import re

from django.db import migrations

# A "what is the sales team number?" chat exchange got auto-saved to the
# shared knowledge base with a fabricated US toll-free number and a fake
# sales@edutrellis.com address — the model invented both when asked a more
# specific question than the plain contact info it was actually given (see
# the SYSTEM_PROMPT/company_knowledge.py hardening that accompanies this
# migration, which now explicitly tells it not to). Purges any entry
# carrying either of those unambiguous wrong-info markers, not just the one
# already found, in case the same fabrication happened elsewhere.
_WRONG_INFO_RE = re.compile(r"edutrellis\.com|sales@edutrellis|1[\-‑\s]?800[\-‑\s]?555", re.IGNORECASE)


def purge_fake_contact_entries(apps, schema_editor):
    KnowledgeEntry = apps.get_model('myapp', 'KnowledgeEntry')
    bad_ids = [
        entry.pk for entry in KnowledgeEntry.objects.all()
        if _WRONG_INFO_RE.search(entry.topic) or _WRONG_INFO_RE.search(entry.content)
    ]
    if bad_ids:
        KnowledgeEntry.objects.filter(pk__in=bad_ids).delete()


def noop_reverse(apps, schema_editor):
    # Deliberately no-op — the purged content was fabricated, so there's
    # nothing worth restoring on a reverse migration.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0041_ainote_aireport'),
    ]

    operations = [
        migrations.RunPython(purge_fake_contact_entries, noop_reverse),
    ]
