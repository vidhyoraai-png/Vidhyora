from django.db import migrations, models


def backfill_report_context(apps, schema_editor):
    """Recover the exact reported turn for reports created before snapshots."""
    AIReport = apps.get_model('myapp', 'AIReport')
    AIMessage = apps.get_model('myapp', 'AIMessage')

    for report in AIReport.objects.exclude(conversation_id=None).iterator():
        message = None
        if report.message_id:
            message = AIMessage.objects.filter(
                pk=report.message_id,
                conversation_id=report.conversation_id,
                role='assistant',
                created_at__lte=report.created_at,
            ).first()
        if message is None and report.reported_reply:
            message = AIMessage.objects.filter(
                conversation_id=report.conversation_id,
                role='assistant',
                content=report.reported_reply,
                created_at__lte=report.created_at,
            ).order_by('-created_at', '-pk').first()

        updates = []
        if message is not None:
            if not report.reported_reply:
                report.reported_reply = message.content
                updates.append('reported_reply')
            if message.image_data:
                report.reported_image = message.image_data
                updates.append('reported_image')

        preceding = AIMessage.objects.filter(
            conversation_id=report.conversation_id,
            role='user',
            created_at__lte=report.created_at,
        )
        if message is not None:
            preceding = preceding.filter(created_at__lt=message.created_at)
        user_message = preceding.order_by('-created_at', '-pk').first()
        if user_message is not None:
            if not report.user_prompt:
                report.user_prompt = user_message.content
                updates.append('user_prompt')
            if user_message.image_data:
                report.user_image = user_message.image_data
                updates.append('user_image')
            if user_message.document_name:
                report.user_document_name = user_message.document_name
                updates.append('user_document_name')
            if user_message.document_text:
                report.user_document_excerpt = user_message.document_text[:8000]
                updates.append('user_document_excerpt')

        if updates:
            report.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0051_aireport_user_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='aireport',
            name='reported_image',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aireport',
            name='user_image',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aireport',
            name='user_document_excerpt',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='aireport',
            name='user_document_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(backfill_report_context, migrations.RunPython.noop),
    ]
