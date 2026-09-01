from django.db import migrations

# Matches models.AI_SUBSCRIPTION_PRODUCT_SLUG — kept as a literal here since
# historical models from apps.get_model() don't carry over module-level
# constants, only fields (same reasoning as 0030_seed_knowledge_base.py).
AI_CATEGORY_SLUG = 'ai'
AI_PRODUCT_SLUG = 'edutrellis-ai-monthly'

AI_PRODUCT_DESCRIPTION = (
    "Unlock unlimited access to every EduTrellis AI model — Ultra, Quick, "
    "Light, Code and Vision — for a full month. Free accounts get 20 "
    "EduTrellis AI messages; this plan removes that cap entirely for 30 "
    "days from purchase, and stacks if you renew before it runs out."
)

AI_PRODUCT_SPECS = (
    "Included: Unlimited messages across every EduTrellis AI model\n"
    "Included: EduTrellis Ultra — most capable, best for detailed or complex questions\n"
    "Included: EduTrellis Code — tuned for coding and debugging\n"
    "Included: EduTrellis Vision — image understanding\n"
    "Included: EduTrellis Light — instant answers with live web search\n"
    "Duration: 30 days from activation, stacks on renewal\n"
    "Delivery: Instant — activates automatically once payment is confirmed"
)


def seed_ai_subscription_product(apps, schema_editor):
    Category = apps.get_model('myapp', 'Category')
    Product = apps.get_model('myapp', 'Product')

    category, _ = Category.objects.get_or_create(
        slug=AI_CATEGORY_SLUG,
        defaults={
            'name': 'AI',
            'description': 'EduTrellis AI subscription plans',
            'order': 0,
            'is_active': True,
        },
    )

    Product.objects.get_or_create(
        slug=AI_PRODUCT_SLUG,
        defaults={
            'category': category,
            'brand': 'EduTrellis',
            'name': 'EduTrellis AI — 1 Month',
            'short_description': 'Unlimited messages on every EduTrellis AI model for 30 days.',
            'description': AI_PRODUCT_DESCRIPTION,
            'specs': AI_PRODUCT_SPECS,
            'price': 99,
            'mrp': 99,
            'icon': 'fa-robot',
            'gradient': 'linear-gradient(135deg,#e8001e,#c0001a)',
            'flag': 'Unlimited AI',
            'stock_status': 'In stock',
            'tags': 'AI, subscription, unlimited, monthly',
            'rating': 4.8,
            'reviews_count': 0,
            'is_active': True,
            'order': 0,
        },
    )


def unseed_ai_subscription_product(apps, schema_editor):
    Product = apps.get_model('myapp', 'Product')
    Category = apps.get_model('myapp', 'Category')
    Product.objects.filter(slug=AI_PRODUCT_SLUG).delete()
    Category.objects.filter(slug=AI_CATEGORY_SLUG, products__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0033_order_ai_subscription_granted_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_ai_subscription_product, unseed_ai_subscription_product),
    ]
