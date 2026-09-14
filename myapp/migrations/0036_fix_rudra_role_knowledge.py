from django.db import migrations

# Corrects the seeded "authoritative" facts about Rudra Narayan Tiwari:
# he is the Team Leader of EduTrellis's Sales Team and Tech Team, NOT the
# founder (that's Vijay Tiwari), and he personally/fully developed the
# EduTrellis AI chat feature himself. Matches the corresponding
# SYSTEM_PROMPT correction in ai_chat.py.
TOPIC_UPDATES = {
    'EduTrellis team': (
        "Vijay Tiwari is EduTrellis's Founder & CEO. Rudra Narayan Tiwari "
        "is the Team Leader of EduTrellis's Sales Team and Tech Team — he "
        "is NOT the founder. Rudra personally and fully developed the "
        "EduTrellis AI chat assistant (a separate feature from the company "
        "itself) himself. For other team or staff inquiries, contact "
        "support@edutrellis.in."
    ),
    'EduTrellis AI creator': (
        "The EduTrellis AI chat feature (this assistant) was fully "
        "developed by Rudra Narayan Tiwari, who is the Team Leader of "
        "EduTrellis's Sales Team and Tech Team — NOT the founder of "
        "EduTrellis. The company itself was founded by Vijay Tiwari, "
        "EduTrellis's Founder & CEO."
    ),
}

# Old real chat replies that predate this correction — harmless ("built by
# Rudra Narayan Tiwari" is still true, just incomplete now) but redundant
# with the corrected entries above and worth clearing so a future retrieval
# can't surface the stale, less-accurate version instead.
STALE_SELF_INTRO_TOPICS = [
    'WHO ARE BYOU?', 'Hi are you edutrellis code?', 'Hello which model yopu are?',
    'Hi which model you have?', 'im new to this ai', 'wh oare you?>', 'who are you?',
]

# This one isn't just stale, it's actively wrong on two counts: it calls
# Rudra "the founder and owner" (he isn't), and it invents an unverified
# job title for Sumudrika — exactly the kind of fabrication SYSTEM_PROMPT
# explicitly tells the model never to do when asked about her. Deleted
# rather than corrected, since there's no real information to replace it
# with.
WRONG_FACT_TOPIC = 'Who is Sumudrika? Is she related to Rudra?'


def fix_rudra_role(apps, schema_editor):
    KnowledgeEntry = apps.get_model('myapp', 'KnowledgeEntry')
    shared = {'user__isnull': True, 'session_key': ''}
    for topic, content in TOPIC_UPDATES.items():
        KnowledgeEntry.objects.filter(topic=topic, source='manual', **shared).update(content=content)
    KnowledgeEntry.objects.filter(topic__in=STALE_SELF_INTRO_TOPICS, source='chat', **shared).delete()
    KnowledgeEntry.objects.filter(topic=WRONG_FACT_TOPIC, source='chat', **shared).delete()


def noop_reverse(apps, schema_editor):
    # Deliberately no-op — the corrected/removed content was wrong, so
    # there's nothing worth restoring on a reverse migration.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0035_product_is_digital'),
    ]

    operations = [
        migrations.RunPython(fix_rudra_role, noop_reverse),
    ]
