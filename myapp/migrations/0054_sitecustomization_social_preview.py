from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0053_aiuserimage_and_backfill'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitecustomization',
            name='social_preview_description',
            field=models.CharField(
                default='Chat with Vidhyora AI for product help, quick answers and learning support — free, right from your browser.',
                help_text='Short description shown below the preview heading.',
                max_length=300,
            ),
        ),
        migrations.AddField(
            model_name='sitecustomization',
            name='social_preview_image',
            field=models.ImageField(
                blank=True,
                help_text='Large preview image. 1200×630px is recommended. Leave blank to use the default cover.',
                null=True,
                upload_to='branding/social/',
            ),
        ),
        migrations.AddField(
            model_name='sitecustomization',
            name='social_preview_title',
            field=models.CharField(
                default='Vidhyora AI — Free AI Chat Assistant',
                help_text='Heading shown in WhatsApp and social link previews.',
                max_length=120,
            ),
        ),
        migrations.AlterField(
            model_name='pwasettings',
            name='is_enabled',
            field=models.BooleanField(
                default=False,
                help_text="Show the 'Install App' option on the homepage. Uses the default Vidhyora icon when no custom icon is uploaded.",
            ),
        ),
    ]
