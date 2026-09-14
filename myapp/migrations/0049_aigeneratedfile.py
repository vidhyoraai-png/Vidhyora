import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0048_sitecustomization'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIGeneratedFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=40)),
                ('file_name', models.CharField(max_length=120)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ai_generated_files', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'AI Generated File',
                'verbose_name_plural': 'AI Generated Files',
                'ordering': ['-created_at'],
            },
        ),
    ]
