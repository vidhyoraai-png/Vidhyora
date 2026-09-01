from django.db import migrations

SEED_POLICIES = [
    {
        'key': 'privacy',
        'title': 'Privacy Policy',
        'content': (
            "EduTrellis Private Limited (\"EduTrellis\", \"we\", \"us\") operates the EduTrellis Store. "
            "This policy explains what information we collect when you use the store and how we use it.\n\n"
            "We collect the information you give us directly — your name, phone number, email address, "
            "delivery address and order history — when you create an account, place an order or contact "
            "our support team. We also store basic technical data such as your IP address and browser type "
            "for fraud prevention and to keep the site working correctly.\n\n"
            "We use this information to process and deliver your orders, send order and delivery updates, "
            "respond to support requests, and improve the store. We do not sell your personal information "
            "to third parties. We share order details only with the delivery partners and payment gateway "
            "(Razorpay) needed to fulfil and process your order, and with authorities where required by law.\n\n"
            "Payment details such as card or UPI numbers are handled directly by our payment gateway partner "
            "and are never stored on EduTrellis servers.\n\n"
            "You can request a copy of the personal data we hold about you, ask us to correct it, or ask us "
            "to delete your account by writing to support@edutrellis.in. We retain order records for as long "
            "as required for accounting and legal purposes.\n\n"
            "We may update this policy from time to time; the latest version will always be available on "
            "this page. If you have questions about this policy, contact us at support@edutrellis.in."
        ),
    },
    {
        'key': 'terms',
        'title': 'Terms & Conditions',
        'content': (
            "These terms govern your use of the EduTrellis Store, operated by EduTrellis Private Limited, "
            "Lucknow, Uttar Pradesh. By creating an account or placing an order, you agree to these terms.\n\n"
            "Product listings, prices and stock availability shown on the store are updated regularly but "
            "may change without prior notice. We make reasonable efforts to display accurate specifications, "
            "images and pricing, and we reserve the right to cancel and fully refund an order placed at an "
            "incorrect price due to a technical or listing error.\n\n"
            "Orders are confirmed once payment is received (or, for Cash on Delivery, once the order is "
            "placed) and are subject to stock availability. We reserve the right to refuse or cancel an "
            "order at our discretion, including in cases of suspected fraud, abuse of offers, or incorrect "
            "pricing — in which case any payment already made will be refunded in full.\n\n"
            "Wallet credit earned through promotional offers has no cash value, cannot be transferred or "
            "redeemed for cash, and can only be used towards future purchases on this store.\n\n"
            "All content on this store — including text, images, logos and the EduTrellis name — is the "
            "property of EduTrellis Private Limited and may not be reproduced without permission.\n\n"
            "These terms are governed by the laws of India, and any disputes are subject to the exclusive "
            "jurisdiction of the courts in Lucknow, Uttar Pradesh."
        ),
    },
    {
        'key': 'refund',
        'title': 'Refund Policy',
        'content': (
            "We want you to be happy with what you order. This policy explains how refunds work at the "
            "EduTrellis Store.\n\n"
            "If an order is cancelled before it has been dispatched, or if we are unable to fulfil it, any "
            "amount paid online (via Razorpay, UPI or card) is refunded in full to the original payment "
            "method, typically within 5–7 business days depending on your bank.\n\n"
            "If an item arrives damaged, defective, or different from what you ordered, contact us at "
            "support@edutrellis.in within 48 hours of delivery with your order number and photos of the "
            "item. Once we verify the issue, we will offer a free replacement where stock allows, or a full "
            "refund to your original payment method or as EduTrellis Store wallet credit, whichever you "
            "prefer.\n\n"
            "Refunds for Cash on Delivery orders are issued as EduTrellis Store wallet credit or via bank "
            "transfer/UPI, since no online payment was collected at the time of purchase.\n\n"
            "Refunds are not offered for change-of-mind on items outside a reported delivery issue, or once "
            "a product has been used beyond simple inspection. Wallet credit issued as part of a refund or "
            "promotional offer is non-transferable and has no cash value.\n\n"
            "For any refund status query, email support@edutrellis.in with your order number — we usually "
            "respond within one business day."
        ),
    },
    {
        'key': 'shipping',
        'title': 'Shipping & Delivery',
        'content': (
            "All orders are packed and dispatched from our warehouse in Lucknow, Uttar Pradesh.\n\n"
            "In-stock orders are dispatched within 24 hours of being placed (excluding Sundays and public "
            "holidays). Once dispatched, you will receive a tracking update by email and, where a phone "
            "number is on file, by WhatsApp.\n\n"
            "Typical delivery times are 2–4 business days for major cities and 4–7 business days for other "
            "locations across India, depending on the courier partner and destination pincode. Delivery "
            "timelines can occasionally be affected by weather, regional restrictions or courier delays "
            "outside our control.\n\n"
            "We offer both prepaid (Razorpay — UPI, cards, net banking) and Cash on Delivery options at "
            "checkout, subject to availability for your pincode. Delivery charges, when applicable, are "
            "shown at checkout before you confirm your order.\n\n"
            "Please ensure your delivery address and phone number are accurate and reachable — orders "
            "returned due to an incorrect address or repeated failed delivery attempts may be subject to "
            "re-shipping charges.\n\n"
            "For any shipping question, write to support@edutrellis.in with your order number."
        ),
    },
]


def seed_policies(apps, schema_editor):
    PolicyPage = apps.get_model('myapp', 'PolicyPage')
    for data in SEED_POLICIES:
        PolicyPage.objects.get_or_create(key=data['key'], defaults={
            'title': data['title'],
            'content': data['content'],
        })


def unseed_policies(apps, schema_editor):
    PolicyPage = apps.get_model('myapp', 'PolicyPage')
    PolicyPage.objects.filter(key__in=[d['key'] for d in SEED_POLICIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0009_seed_products'),
    ]

    operations = [
        migrations.RunPython(seed_policies, unseed_policies),
    ]
