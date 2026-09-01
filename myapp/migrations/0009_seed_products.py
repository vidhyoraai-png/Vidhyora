from django.db import migrations

# Mirrors the PRODUCTS array that used to be hardcoded in estore.html —
# migrated into the database so the storefront and dashboard can manage it.
SEED_PRODUCTS = [
    {'slug': 'aud-anc', 'cat': 'audio', 'brand': 'SoundCore', 'name': 'ANC Wireless Earbuds Pro', 'desc': 'Active noise cancellation, 40h total playback with the case and low-latency game mode.', 'price': 2799, 'mrp': 4499, 'icon': 'fa-headphones-simple', 'grad': 'linear-gradient(135deg,#e8001e,#c0001a)', 'flag': 'Bestseller', 'stock': 'In stock', 'tags': 'ANC, 40h battery, IPX5', 'rating': 4.8, 'reviews': 412, 'order': 1},
    {'slug': 'aud-over', 'cat': 'audio', 'brand': 'Vertex', 'name': 'Over-Ear Studio Headphones', 'desc': '40mm drivers, memory-foam cups and a detachable cable for wired studio use.', 'price': 3499, 'mrp': 5999, 'icon': 'fa-headphones', 'grad': 'linear-gradient(135deg,#1c2333,#2c3e50)', 'flag': '', 'stock': 'In stock', 'tags': '40mm drivers, 60h battery, Foldable', 'rating': 4.7, 'reviews': 186, 'order': 2},
    {'slug': 'aud-spk', 'cat': 'audio', 'brand': 'BoomBox', 'name': 'Portable Party Speaker 20W', 'desc': '20W output, IPX7 waterproofing and 24 hours of playback on a single charge.', 'price': 2199, 'mrp': 3499, 'icon': 'fa-volume-high', 'grad': 'linear-gradient(135deg,#f59e0b,#b45309)', 'flag': 'Hot', 'stock': 'Only 6 left', 'tags': '20W, IPX7, 24h', 'rating': 4.6, 'reviews': 243, 'order': 3},
    {'slug': 'aud-neck', 'cat': 'audio', 'brand': 'SoundCore', 'name': 'Bluetooth Neckband', 'desc': 'Magnetic earbuds, quick-charge for 10 hours of playback from a 10-minute top-up.', 'price': 999, 'mrp': 1799, 'icon': 'fa-music', 'grad': 'linear-gradient(135deg,#8b5cf6,#6d28d9)', 'flag': 'Under ₹1000', 'stock': 'In stock', 'tags': 'Quick charge, Magnetic, 30h', 'rating': 4.4, 'reviews': 308, 'order': 4},
    {'slug': 'aud-metal', 'cat': 'audio', 'brand': 'BoomBox', 'name': 'Metal Bluetooth Speaker', 'desc': 'Solid metal shell, 360° sound and 18 hours of playback — plus ₹100 wallet credit on your first order once it’s delivered.', 'price': 1799, 'mrp': 2999, 'icon': 'fa-volume-high', 'grad': 'linear-gradient(135deg,#334155,#0f172a)', 'flag': 'Welcome offer', 'stock': 'In stock', 'tags': 'Metal body, 360° sound, 18h battery', 'rating': 4.7, 'reviews': 64, 'order': 5},

    {'slug': 'wear-amo', 'cat': 'wearables', 'brand': 'Pulse', 'name': 'AMOLED Smartwatch Series 5', 'desc': '1.85-inch AMOLED display, Bluetooth calling, SpO2 and 100+ sport modes.', 'price': 2999, 'mrp': 5999, 'icon': 'fa-stopwatch', 'grad': 'linear-gradient(135deg,#0ea5e9,#0369a1)', 'flag': 'Top rated', 'stock': 'In stock', 'tags': 'AMOLED, BT calling, SpO2', 'rating': 4.7, 'reviews': 521, 'order': 1},
    {'slug': 'wear-band', 'cat': 'wearables', 'brand': 'Pulse', 'name': 'Fitness Band Lite', 'desc': 'Heart-rate and sleep tracking with a 14-day battery and a strap you can actually wash.', 'price': 1299, 'mrp': 2299, 'icon': 'fa-heart-pulse', 'grad': 'linear-gradient(135deg,#10b981,#047857)', 'flag': '', 'stock': 'In stock', 'tags': '14-day battery, HR tracking, 5ATM', 'rating': 4.5, 'reviews': 274, 'order': 2},
    {'slug': 'wear-rug', 'cat': 'wearables', 'brand': 'Vertex', 'name': 'Rugged Outdoor Smartwatch', 'desc': 'Metal bezel, built-in GPS and a 10-day battery for anyone outdoors more than indoors.', 'price': 4499, 'mrp': 7999, 'icon': 'fa-compass', 'grad': 'linear-gradient(135deg,#64748b,#334155)', 'flag': 'New', 'stock': 'Only 4 left', 'tags': 'GPS, 10-day battery, Metal body', 'rating': 4.8, 'reviews': 97, 'order': 3},

    {'slug': 'pow-gan', 'cat': 'power', 'brand': 'VoltEdge', 'name': '65W GaN Fast Charger', 'desc': 'Three ports, GaN cooling and enough headroom to charge a laptop and phone together.', 'price': 1799, 'mrp': 2999, 'icon': 'fa-bolt', 'grad': 'linear-gradient(135deg,#ef4444,#991b1b)', 'flag': 'Bestseller', 'stock': 'In stock', 'tags': '65W, 3 ports, GaN', 'rating': 4.9, 'reviews': 389, 'order': 1},
    {'slug': 'pow-bank', 'cat': 'power', 'brand': 'VoltEdge', 'name': '20000mAh Power Bank', 'desc': '22.5W fast output, digital charge display and pass-through charging while it refills.', 'price': 1999, 'mrp': 3299, 'icon': 'fa-battery-full', 'grad': 'linear-gradient(135deg,#3b82f6,#1d4ed8)', 'flag': '', 'stock': 'In stock', 'tags': '20000mAh, 22.5W, Display', 'rating': 4.7, 'reviews': 452, 'order': 2},
    {'slug': 'pow-cable', 'cat': 'power', 'brand': 'VoltEdge', 'name': 'Braided 100W USB-C Cable', 'desc': 'Nylon-braided 1.5m cable rated for 100W charging and 480Mbps data transfer.', 'price': 499, 'mrp': 899, 'icon': 'fa-plug', 'grad': 'linear-gradient(135deg,#14b8a6,#0f766e)', 'flag': 'Value pick', 'stock': 'In stock', 'tags': '100W, 1.5m, Braided', 'rating': 4.6, 'reviews': 611, 'order': 3},
    {'slug': 'pow-mag', 'cat': 'power', 'brand': 'VoltEdge', 'name': 'Magnetic Wireless Power Bank', 'desc': 'Snaps to the back of your phone, 10000mAh with 15W magnetic wireless charging.', 'price': 2499, 'mrp': 3999, 'icon': 'fa-magnet', 'grad': 'linear-gradient(135deg,#ec4899,#9d174d)', 'flag': 'New', 'stock': 'Only 9 left', 'tags': '10000mAh, 15W wireless, Magnetic', 'rating': 4.5, 'reviews': 118, 'order': 4},

    {'slug': 'com-mech', 'cat': 'computing', 'brand': 'KeyForge', 'name': '65% Mechanical Keyboard', 'desc': 'Hot-swappable switches, RGB per key and tri-mode connection over USB-C, BT and 2.4G.', 'price': 3299, 'mrp': 5499, 'icon': 'fa-keyboard', 'grad': 'linear-gradient(135deg,#7c3aed,#4c1d95)', 'flag': 'Enthusiast', 'stock': 'In stock', 'tags': 'Hot-swap, Tri-mode, RGB', 'rating': 4.9, 'reviews': 203, 'order': 1},
    {'slug': 'com-mouse', 'cat': 'computing', 'brand': 'KeyForge', 'name': 'Wireless Ergonomic Mouse', 'desc': 'Silent clicks, adjustable 800–4000 DPI and a shape that stops the wrist ache.', 'price': 1099, 'mrp': 1899, 'icon': 'fa-computer-mouse', 'grad': 'linear-gradient(135deg,#6366f1,#3730a3)', 'flag': '', 'stock': 'In stock', 'tags': 'Silent, 4000 DPI, Ergonomic', 'rating': 4.6, 'reviews': 287, 'order': 2},
    {'slug': 'com-hub', 'cat': 'computing', 'brand': 'Vertex', 'name': '7-in-1 USB-C Hub', 'desc': 'HDMI 4K, three USB ports, SD and microSD readers and 100W pass-through power.', 'price': 2299, 'mrp': 3799, 'icon': 'fa-network-wired', 'grad': 'linear-gradient(135deg,#0891b2,#155e75)', 'flag': '', 'stock': 'In stock', 'tags': '4K HDMI, 100W PD, Card reader', 'rating': 4.7, 'reviews': 164, 'order': 3},
    {'slug': 'com-stand', 'cat': 'computing', 'brand': 'Vertex', 'name': 'Aluminium Laptop Stand', 'desc': 'Adjustable height, folds flat for the bag and lifts the screen to eye level.', 'price': 1499, 'mrp': 2499, 'icon': 'fa-laptop', 'grad': 'linear-gradient(135deg,#94a3b8,#475569)', 'flag': '', 'stock': 'In stock', 'tags': 'Adjustable, Foldable, Aluminium', 'rating': 4.5, 'reviews': 141, 'order': 4},

    {'slug': 'sm-bulb', 'cat': 'smart', 'brand': 'Lumo', 'name': 'Smart RGB LED Bulb (Pack of 2)', 'desc': '16 million colours, app scheduling and voice control through Alexa and Google Home.', 'price': 1199, 'mrp': 1999, 'icon': 'fa-lightbulb', 'grad': 'linear-gradient(135deg,#f59e0b,#d97706)', 'flag': 'Pack of 2', 'stock': 'In stock', 'tags': '16M colours, Alexa, Scheduling', 'rating': 4.6, 'reviews': 329, 'order': 1},
    {'slug': 'sm-plug', 'cat': 'smart', 'brand': 'Lumo', 'name': 'Wi-Fi Smart Plug 16A', 'desc': '16A rated for heavy appliances, with energy monitoring and timer routines in the app.', 'price': 899, 'mrp': 1499, 'icon': 'fa-plug-circle-bolt', 'grad': 'linear-gradient(135deg,#22c55e,#15803d)', 'flag': '', 'stock': 'In stock', 'tags': '16A, Energy meter, Timers', 'rating': 4.7, 'reviews': 256, 'order': 2},
    {'slug': 'sm-cam', 'cat': 'smart', 'brand': 'Lumo', 'name': '360° Security Camera 3MP', 'desc': '3MP night vision, motion alerts, two-way audio and local storage on microSD.', 'price': 2299, 'mrp': 3799, 'icon': 'fa-video', 'grad': 'linear-gradient(135deg,#1e293b,#0f172a)', 'flag': 'Hot', 'stock': 'Only 7 left', 'tags': '3MP, Night vision, Two-way audio', 'rating': 4.5, 'reviews': 198, 'order': 3},

    {'slug': 'mob-gim', 'cat': 'mobile', 'brand': 'Steady', 'name': '3-Axis Phone Gimbal', 'desc': 'Three-axis stabilisation, gesture control and 12 hours of runtime for handheld shoots.', 'price': 4999, 'mrp': 7999, 'icon': 'fa-mobile-screen', 'grad': 'linear-gradient(135deg,#e8001e,#7c1020)', 'flag': 'Creator pick', 'stock': 'Only 5 left', 'tags': '3-axis, Gesture control, 12h', 'rating': 4.8, 'reviews': 86, 'order': 1},
    {'slug': 'mob-trip', 'cat': 'mobile', 'brand': 'Steady', 'name': 'Tripod with Ring Light', 'desc': 'Extends to 1.6m, dimmable ring light in three tones and a Bluetooth shutter remote.', 'price': 1599, 'mrp': 2699, 'icon': 'fa-camera', 'grad': 'linear-gradient(135deg,#a855f7,#6b21a8)', 'flag': '', 'stock': 'In stock', 'tags': '1.6m, Ring light, BT remote', 'rating': 4.6, 'reviews': 172, 'order': 2},
    {'slug': 'mob-mount', 'cat': 'mobile', 'brand': 'Steady', 'name': 'Magnetic Car Mount', 'desc': "Strong N52 magnets, 360° rotation and a vent clip that doesn't rattle on bad roads.", 'price': 699, 'mrp': 1199, 'icon': 'fa-car', 'grad': 'linear-gradient(135deg,#0d9488,#115e59)', 'flag': 'Value pick', 'stock': 'In stock', 'tags': 'N52 magnets, 360°, Vent clip', 'rating': 4.4, 'reviews': 225, 'order': 3},
]


def seed_products(apps, schema_editor):
    Product = apps.get_model('myapp', 'Product')
    Category = apps.get_model('myapp', 'Category')
    for data in SEED_PRODUCTS:
        category = Category.objects.filter(slug=data['cat']).first()
        if not category:
            continue
        Product.objects.get_or_create(
            slug=data['slug'],
            defaults={
                'category': category,
                'brand': data['brand'],
                'name': data['name'],
                'short_description': data['desc'],
                'description': data['desc'],
                'price': data['price'],
                'mrp': data['mrp'],
                'icon': data['icon'],
                'gradient': data['grad'],
                'flag': data['flag'],
                'stock_status': data['stock'],
                'tags': data['tags'],
                'rating': data['rating'],
                'reviews_count': data['reviews'],
                'order': data['order'],
            },
        )


def unseed_products(apps, schema_editor):
    Product = apps.get_model('myapp', 'Product')
    Product.objects.filter(slug__in=[d['slug'] for d in SEED_PRODUCTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0008_aboutuscontent_paymentsettings_policypage_payment_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_products, unseed_products),
    ]
