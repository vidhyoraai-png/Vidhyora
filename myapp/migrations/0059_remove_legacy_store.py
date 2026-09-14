from django.db import migrations


def remove_store_orders(apps, schema_editor):
    Order = apps.get_model('myapp', 'Order')
    # Retain AI subscriptions and ambiguous records. Remove only orders with
    # identifiable merchandise items and no AI subscription entitlement.
    Order.objects.using(schema_editor.connection.alias).filter(
        items__isnull=False, ai_subscription_granted=False,
    ).exclude(items__product_id='edutrellis-ai-monthly').delete()


class Migration(migrations.Migration):
    dependencies = [('myapp', '0058_aiaccountmessagesettings')]
    operations = [migrations.RunPython(remove_store_orders, migrations.RunPython.noop)] + [
        migrations.DeleteModel(name=name)
        for name in ('Review', 'ProductImage', 'ProductColor', 'Product', 'Category',
                     'CartItem', 'Cart', 'ContactLead', 'AboutUsContent', 'PolicyPage', 'FeeSettings')
    ]
