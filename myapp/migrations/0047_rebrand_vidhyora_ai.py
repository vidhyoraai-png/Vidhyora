from django.db import migrations, models


OLD_NAME = 'EduTrellis AI'
NEW_NAME = 'Vidhyora AI'


def replace_name(value, old, new):
    return value.replace(old, new) if value else value


def rebrand_forward(apps, schema_editor):
    Category = apps.get_model('myapp', 'Category')
    Product = apps.get_model('myapp', 'Product')
    KnowledgeEntry = apps.get_model('myapp', 'KnowledgeEntry')

    for category in Category.objects.filter(slug='ai'):
        category.name = replace_name(category.name, OLD_NAME, NEW_NAME)
        category.description = replace_name(category.description, OLD_NAME, NEW_NAME)
        category.save(update_fields=['name', 'description'])

    for product in Product.objects.filter(slug='edutrellis-ai-monthly'):
        for field in ('name', 'short_description', 'description', 'specs'):
            setattr(product, field, replace_name(getattr(product, field), OLD_NAME, NEW_NAME))
        product.gradient = 'linear-gradient(135deg,#ff7a00,#101114)'
        product.save(update_fields=['name', 'short_description', 'description', 'specs', 'gradient'])

    for entry in KnowledgeEntry.objects.filter(topic__icontains=OLD_NAME):
        entry.topic = replace_name(entry.topic, OLD_NAME, NEW_NAME)
        entry.content = replace_name(entry.content, OLD_NAME, NEW_NAME)
        entry.save(update_fields=['topic', 'content'])
    for entry in KnowledgeEntry.objects.filter(content__icontains=OLD_NAME):
        entry.content = replace_name(entry.content, OLD_NAME, NEW_NAME)
        entry.save(update_fields=['content'])


def rebrand_backward(apps, schema_editor):
    Category = apps.get_model('myapp', 'Category')
    Product = apps.get_model('myapp', 'Product')
    KnowledgeEntry = apps.get_model('myapp', 'KnowledgeEntry')

    for category in Category.objects.filter(slug='ai'):
        category.name = replace_name(category.name, NEW_NAME, OLD_NAME)
        category.description = replace_name(category.description, NEW_NAME, OLD_NAME)
        category.save(update_fields=['name', 'description'])

    for product in Product.objects.filter(slug='edutrellis-ai-monthly'):
        for field in ('name', 'short_description', 'description', 'specs'):
            setattr(product, field, replace_name(getattr(product, field), NEW_NAME, OLD_NAME))
        product.gradient = 'linear-gradient(135deg,#e8001e,#c0001a)'
        product.save(update_fields=['name', 'short_description', 'description', 'specs', 'gradient'])

    for entry in KnowledgeEntry.objects.filter(topic__icontains=NEW_NAME):
        entry.topic = replace_name(entry.topic, NEW_NAME, OLD_NAME)
        entry.content = replace_name(entry.content, NEW_NAME, OLD_NAME)
        entry.save(update_fields=['topic', 'content'])
    for entry in KnowledgeEntry.objects.filter(content__icontains=NEW_NAME):
        entry.content = replace_name(entry.content, NEW_NAME, OLD_NAME)
        entry.save(update_fields=['content'])


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0046_storeprofile_location_consent_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storeprofile',
            name='ai_free_messages_used',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Free-tier Vidhyora AI messages sent so far (resets on each new subscription purchase).',
            ),
        ),
        migrations.AlterField(
            model_name='storeprofile',
            name='ai_subscription_until',
            field=models.DateTimeField(
                blank=True,
                help_text='Vidhyora AI access is unlimited until this time. Blank/past = free tier.',
                null=True,
            ),
        ),
        migrations.RunPython(rebrand_forward, rebrand_backward),
    ]
