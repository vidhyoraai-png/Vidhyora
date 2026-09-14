"""Durable gallery for AI-generated images.

The "My Images" gallery used to read straight from AIMessage.image_data, so
deleting a conversation destroyed every image generated inside it. AIUserImage
holds them independently. The backfill copies across everything that still
exists, so no one loses the images they already have when this ships.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_existing_images(apps, schema_editor):
    AIMessage = apps.get_model('myapp', 'AIMessage')
    AIUserImage = apps.get_model('myapp', 'AIUserImage')

    existing = set(AIUserImage.objects.values_list('url', flat=True))
    rows = []
    messages = (
        AIMessage.objects
        .filter(role='assistant')
        .exclude(image_data='')
        .select_related('conversation')
        .order_by('created_at')
    )
    for message in messages.iterator(chunk_size=500):
        url = (message.image_data or '').strip()
        # Assistant image_data is always a stored media URL. Skip anything that
        # isn't (a legacy data: URI would bloat this table for no benefit).
        if not url or url.startswith('data:') or url in existing:
            continue
        existing.add(url)
        conversation = message.conversation
        rows.append(AIUserImage(
            user_id=conversation.user_id if conversation else None,
            session_key=(conversation.session_key or '') if conversation else '',
            conversation_id=message.conversation_id,
            url=url,
            prompt='',
            model_key=message.model_key or '',
            created_at=message.created_at,
        ))
        if len(rows) >= 500:
            AIUserImage.objects.bulk_create(rows)
            rows = []
    if rows:
        AIUserImage.objects.bulk_create(rows)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('myapp', '0052_aireport_image_evidence_and_backfill'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIUserImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=40)),
                ('url', models.TextField()),
                ('prompt', models.TextField(blank=True)),
                ('model_key', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_images', to='myapp.aiconversation')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ai_images', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'AI Generated Image',
                'verbose_name_plural': 'AI Generated Images',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='aiuserimage',
            index=models.Index(fields=['user', '-created_at'], name='myapp_aiuse_user_id_505be7_idx'),
        ),
        migrations.RunPython(backfill_existing_images, migrations.RunPython.noop),
    ]
