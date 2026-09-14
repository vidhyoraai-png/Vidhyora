from django.db import migrations

SEED_CATEGORIES = [
    {'name': 'Audio', 'slug': 'audio', 'description': 'Earbuds, headphones, speakers', 'order': 1},
    {'name': 'Wearables', 'slug': 'wearables', 'description': 'Smartwatches & bands', 'order': 2},
    {'name': 'Power', 'slug': 'power', 'description': 'Chargers, cables, banks', 'order': 3},
    {'name': 'Computing', 'slug': 'computing', 'description': 'Keyboards, mice, hubs', 'order': 4},
    {'name': 'Smart Home', 'slug': 'smart', 'description': 'Bulbs, plugs, cameras', 'order': 5},
    {'name': 'Mobile', 'slug': 'mobile', 'description': 'Gimbals, mounts, tripods', 'order': 6},
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('myapp', 'Category')
    for data in SEED_CATEGORIES:
        Category.objects.get_or_create(slug=data['slug'], defaults=data)


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('myapp', 'Category')
    Category.objects.filter(slug__in=[d['slug'] for d in SEED_CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0005_category'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
