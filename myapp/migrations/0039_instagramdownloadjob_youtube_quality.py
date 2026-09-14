import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('myapp', '0038_youtubedownloadjob')]

    operations = [
        migrations.AddField(
            model_name='youtubedownloadjob', name='quality',
            field=models.CharField(default='1080', max_length=10),
        ),
        migrations.CreateModel(
            name='InstagramDownloadJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('source_url', models.URLField(max_length=500)),
                ('option', models.CharField(max_length=20)),
                ('username', models.CharField(blank=True, max_length=150)),
                ('title', models.CharField(blank=True, max_length=300)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('working', 'Working'), ('ready', 'Ready'), ('failed', 'Failed')], default='pending', max_length=12)),
                ('progress', models.PositiveSmallIntegerField(default=0)),
                ('archive_path', models.CharField(blank=True, max_length=500)),
                ('error', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instagram_downloads', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
