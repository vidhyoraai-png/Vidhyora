from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('myapp', '0039_instagramdownloadjob_youtube_quality')]

    operations = [
        migrations.DeleteModel(name='InstagramDownloadJob'),
    ]
