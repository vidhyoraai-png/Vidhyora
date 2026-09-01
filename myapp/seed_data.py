"""Seeds demo buyer accounts + reviews so the storefront doesn't launch with
zero social proof. Each seeded reviewer gets a real Delivered order for the
product they "review", so they pass the same purchase-verification gate
(_user_can_review in views.py) as a genuine customer — these show up marked
"Verified purchase" exactly like real reviews. Safe to re-run: accounts and
reviews are upserted, never duplicated.

Used by both `python manage.py seed_reviews` and the dashboard's
"Seed demo reviews" button (dashboard_seed_reviews in views.py).
"""
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from myapp.models import AI_SUBSCRIPTION_PRODUCT_SLUG, Order, OrderItem, Payment, Product, Review, StoreProfile

DEMO_PASSWORD = '123456'

REVIEWERS = [
    ('Ankit', 'Sharma'), ('Priya', 'Verma'), ('Rohit', 'Singh'), ('Neha', 'Gupta'),
    ('Saurabh', 'Yadav'), ('Kavita', 'Nair'), ('Arjun', 'Mehta'), ('Simran', 'Kaur'),
    ('Vikas', 'Reddy'), ('Pooja', 'Iyer'), ('Rahul', 'Kapoor'), ('Anjali', 'Joshi'),
    ('Manish', 'Chauhan'), ('Divya', 'Menon'), ('Suresh', 'Pillai'), ('Ritu', 'Malhotra'),
    ('Karan', 'Bhatt'), ('Sneha', 'Rao'), ('Aditya', 'Kulkarni'), ('Meera', 'Desai'),
    ('Varun', 'Chopra'), ('Shreya', 'Agarwal'), ('Nikhil', 'Bansal'), ('Swati', 'Deshmukh'),
    ('Gaurav', 'Saxena'), ('Isha', 'Thakur'), ('Deepak', 'Mishra'), ('Anushka', 'Bhatia'),
    ('Sandeep', 'Rana'), ('Kirti', 'Sinha'), ('Abhishek', 'Trivedi'), ('Ritika', 'Chandra'),
    ('Mohit', 'Arora'), ('Preeti', 'Nagpal'), ('Yash', 'Vora'), ('Tanvi', 'Shah'),
    ('Harsh', 'Goyal'), ('Namrata', 'Pandey'), ('Siddharth', 'Rathi'), ('Bhavna', 'Sood'),
    ('Ashwin', 'Krishnan'), ('Ramya', 'Subramanian'), ('Pankaj', 'Tiwari'), ('Alisha', 'Khanna'),
    ('Nitin', 'Chawla'), ('Sunita', 'Kohli'), ('Rajesh', 'Ghosh'), ('Komal', 'Dutta'),
    ('Vivek', 'Nambiar'), ('Anita', 'Chatterjee'), ('Sameer', 'Qureshi'), ('Farah', 'Sheikh'),
    ('Imran', 'Ansari'), ('Zainab', 'Malik'), ('Rakesh', 'Bhalla'), ('Tanya', 'Oberoi'),
]

REVIEW_TEMPLATES = [
    (5, "Genuinely happy with this purchase. Build quality feels premium and it works exactly as described. Delivery was quick too."),
    (5, "Was a bit skeptical ordering from a smaller store but this exceeded expectations. Packaging was solid, no damage, works perfectly."),
    (4, "Good product overall. Does what it says. Only reason I'm not giving 5 stars is the box was a little worn, but the item itself is fine."),
    (5, "Using it daily for almost 2 weeks now, zero issues. Battery backup is better than I expected. Would recommend."),
    (4, "Decent quality for the price. Setup was easy. Wish the manual had a bit more detail but figured it out quickly."),
    (5, "Ordered COD, got it in 3 days, well packed. Product matches the photos and description exactly. Very satisfied."),
    (3, "It's okay, does the job but nothing extraordinary. Expected slightly better finishing for this price point."),
    (5, "Excellent! My second order from this store and both times the quality has been consistent. Support replied quickly when I had a question."),
    (4, "Works well, comfortable to use daily. Shipping took a couple of days longer than expected but the product itself is solid."),
    (5, "Really impressed. Feels durable, performs well, and arrived earlier than the estimated delivery date."),
    (5, "Bought this for my parents and they're really happy with it. Easy to use, no complicated setup. Good buy."),
    (4, "Solid product for daily use. Not much else to say — it just works, and that's what I wanted."),
    (5, "Better than similar products I've used from bigger brands, honestly. Glad I took a chance on this store."),
    (3, "Average experience. Product is fine but delivery tracking wasn't updated properly, had to call to check status."),
    (5, "Third time ordering from EduTrellis Store and they haven't disappointed yet. Consistent quality, fair pricing."),
    (4, "Value for money. A couple of minor niggles but nothing that affects how well it works day to day."),
    (5, "Super happy with the purchase. Arrived well before the expected date and exactly as shown in the pictures."),
    (2, "Had an issue with the first unit but customer support replaced it quickly without any hassle. Works fine now."),
    (5, "Sound/build quality (whichever applies) is genuinely impressive for this price bracket. Highly recommend."),
    (4, "Good purchase overall. Packaging could be sturdier but the product itself arrived undamaged and works well."),
    (5, "Exactly what I needed. Simple, reliable, does the job without any fuss. Would buy again."),
    (4, "Happy with the quality. Took about 4 days to arrive which was a bit longer than expected but worth the wait."),
    (5, "Very satisfied — this is my go-to store now for gadgets. Prices are fair and the products are genuine."),
    (3, "It's decent for the price but I expected slightly better finishing. Functionally it works as advertised though."),
    (5, "Excellent build quality and fast COD delivery. No complaints at all, will be ordering more from here."),
    (4, "Works as expected. Customer support was responsive when I had a question about the warranty."),
    (5, "Really pleased with this — feels premium, works reliably, and the price was fair for what you get."),
]


RC_PLANE_REVIEW_TEMPLATES = [
    (5, "Bought this for my son's birthday and he hasn't put it down since. Flies smoothly and the foam body has already survived a good number of crash landings without a scratch."),
    (5, "The LED lights are a nice touch — my kids fly it in the backyard after dark now and it looks amazing. Genuinely well thought out for the price."),
    (4, "Easy to fly straight out of the box, barely any assembly needed. Only wish the battery lasted a bit longer per charge, but it's still great value."),
    (5, "Sturdy propellers held up even after a few rough landings on the terrace. My nephew is obsessed with this thing."),
    (5, "Wasn't expecting much at this price but it flies really well and feels solid. The foam body clearly takes a beating and keeps going."),
    (4, "Good flyer once you get the hang of the controls. Took my son a couple of tries but now he's flying it like a pro."),
    (5, "This was a birthday gift and it was a massive hit. Flies straight, lights up nicely at night, and hasn't broken despite a few crashes already."),
    (5, "Really impressed with the build quality — didn't expect the propellers to be this sturdy. Flew it in the park all weekend."),
    (3, "Flies okay but the range felt a bit limited compared to what I expected. Kids still enjoy it though, especially the lights."),
    (5, "My daughter loves flying this in the evening because of the LED lights. Controller response is smooth and it's held up well so far."),
    (4, "Solid little plane for the price. Assembly took two minutes and it was airborne. A couple of hard landings and it's still intact."),
    (5, "Great gift idea — my kid's friends all want one now after seeing him fly it in the park. Foam body is tougher than it looks."),
    (5, "Genuinely surprised by how well this flies for something in this price range. No assembly hassle, charges fast, kids are thrilled."),
    (4, "Works well and the lights make evening flying fun. Only minor gripe is charging takes a little longer than I'd like."),
    (5, "Bought two — one for my son and one for his cousin. Both fly great and have survived plenty of crash landings already."),
    (5, "The night flying with the LEDs on is honestly the best part. Kids call it the 'star fighter' and fly it every evening now."),
    (3, "Decent plane, does the job, but I expected the controller range to be a bit better. Still, my son enjoys flying it in the garden."),
    (5, "Excellent purchase. Flies smooth and straight, easy for a beginner to control, and the foam body shrugs off crashes."),
    (4, "Good value for money. Took a minute to figure out the controls but after that it was smooth flying every time."),
    (5, "This has been my son's favorite toy since it arrived. Durable, flies well, and the lights make it look really cool at dusk."),
    (5, "Was skeptical about a plane in this price range but it's held up brilliantly — several crashes and not a single crack."),
    (4, "Flies nicely and looks great with the LEDs on. Setup was quick, just needed the battery charged before the first flight."),
    (5, "Bought it as a surprise gift and my nephew was over the moon. Easy to fly, sturdy, and the night-flying feature is a big hit."),
    (5, "Really well made for the price point. Foam body is tougher than expected, propellers haven't chipped despite regular use."),
    (2, "Had trouble getting the remote to sync properly the first day, but once it worked it flew fine. Wish setup instructions were clearer."),
    (5, "My kids fight over whose turn it is to fly this thing. Great build, smooth flight, and the lights are a nice bonus for evening flying."),
    (4, "Solid buy — flies straight, controller feels responsive, and it survived being dropped a few times already without issue."),
    (5, "Perfect gift for a curious 8-year-old. Easy to fly right away, no complicated assembly, and it's held up to daily use for weeks now."),
    (5, "The durability is what surprised me most. Expected it to break on the first crash but it's taken several hits and keeps flying."),
    (4, "Flies well once you're used to the controls. LED lights are a great feature for evening flying sessions in the park."),
    (5, "Bought this after seeing a neighbor's kid fly one — glad I did. Smooth flight, sturdy build, and the lights make it extra fun at night."),
    (5, "Great little plane. Minimal assembly, flies straight out of the box, and the propellers are much sturdier than I anticipated."),
    (3, "It's fine for casual backyard flying but not the fastest or most agile. Kids still enjoy it, especially with the lights on."),
    (5, "This has become our go-to evening activity — flying it in the park with the LEDs glowing. Very happy with the purchase."),
    (4, "Good build quality for the price. A couple of hard landings on concrete and it's still flying fine."),
    (5, "My son received this as a gift and it's easily his favorite toy right now. Tough foam body, smooth controls, looks great lit up at night."),
    (5, "Impressed with how well this survives crashes — my kid isn't the most careful pilot and it's still in one piece."),
    (4, "Flies smoothly and the setup was quick. Only wish the charging cable was a bit longer, but that's a minor complaint."),
    (5, "Bought for my daughter's birthday and she loves it. Easy to control, sturdy build, and the night flying with lights is the best part."),
    (5, "Genuinely good quality for a toy plane at this price. Propellers are sturdy, body is durable, and it flies straight and steady."),
]


AI_REVIEW_TEMPLATES = [
    (5, "Been using this daily for debugging Python and JS — it catches mistakes I'd have spent an hour hunting down myself. Genuinely worth the Rs 99."),
    (5, "Switched from a free chatbot to this mainly for the coding mode and it's been a massive upgrade. Explains errors clearly instead of just dumping a fix."),
    (4, "Good for regular office work too — drafting emails, summarizing long documents, planning my week. Not just for developers."),
    (5, "I write a lot of SQL queries for reports and this has saved me so much time. Rarely gets stuck on syntax issues."),
    (5, "Unlimited messages is the real selling point — I was hitting the free limit every single day before subscribing."),
    (4, "Solid for day-to-day coding help. Occasionally needs a follow-up question to get exactly what I want, but overall very reliable."),
    (5, "Uploaded a screenshot of a broken layout and it spotted the CSS issue instantly. Vision mode is surprisingly accurate."),
    (5, "Using it for both work and personal coding projects — from fixing bugs to explaining unfamiliar codebases. Worth subscribing."),
    (3, "Decent for regular tasks but sometimes takes a couple of tries to get complex code right. Still better than most free tools I've tried."),
    (5, "My go-to for regular work now — meeting notes, quick calculations, drafting messages. Feels like having an assistant on call."),
    (5, "As a student learning to code, this has been incredibly patient explaining concepts step by step instead of just giving me the answer."),
    (4, "Handles routine office tasks well — spreadsheet formulas, email drafts, quick research. Good value for the price."),
    (5, "Debugged a tricky React state issue for me in minutes that I'd been stuck on for an hour. Subscribing was worth it just for that."),
    (5, "I use it for everything from writing scripts to organizing my daily task list. The unlimited access makes it actually usable for work."),
    (4, "Good coding assistant overall. Sometimes I have to double check the output but it gets me 90% of the way there quickly."),
    (5, "Freelance developer here — this has basically become part of my workflow for reviewing code and writing documentation."),
    (5, "Cheaper than other AI subscriptions I've tried and handles both my coding questions and regular admin work equally well."),
    (5, "Great for quick regular work stuff — summarizing PDFs, replying to emails, planning my schedule — not just coding."),
    (3, "Works well most of the time for coding help, with the occasional hiccup on very niche libraries, but support for common languages is solid."),
    (5, "Been using EduTrellis Code mode for backend work — it remembers context from earlier in the conversation which saves a lot of re-explaining."),
    (5, "Genuinely useful day to day — from debugging to writing quick reports for work. The subscription pays for itself within a week of regular use."),
    (4, "Reliable for everyday coding and office tasks. Response time is quick even during work hours which matters when you're on a deadline."),
    (5, "Best Rs 99 I spend every month. Between coding help and regular work tasks I probably send 50+ messages a day now without worrying about limits."),
]


def _spread_datetime(base_now, max_days_back=150):
    """A realistic, non-sequential timestamp somewhere in the last
    `max_days_back` days, at a random hour/minute — so a batch of reviews
    lands on different days and times rather than a mechanical pattern."""
    return base_now - timedelta(
        days=random.randint(1, max_days_back), hours=random.randint(7, 23), minutes=random.randint(0, 59),
    )


def seed_product_reviews(product_id, count=56):
    """Seeds `count` reviews on a single product, one per existing/created
    demo reviewer account (see REVIEWERS above), each with its own real
    Delivered order for that product so it passes the same purchase-
    verification gate as a genuine review. Dates are spread randomly across
    the last few months instead of all landing today. Safe to re-run —
    accounts and reviews are upserted, never duplicated."""
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return f"No product with id {product_id} found."

    count = min(count, len(REVIEWERS))
    reviewers = REVIEWERS[:count]
    if product.slug == AI_SUBSCRIPTION_PRODUCT_SLUG:
        templates = AI_REVIEW_TEMPLATES
    elif 'plane' in product.name.lower():
        templates = RC_PLANE_REVIEW_TEMPLATES
    else:
        templates = REVIEW_TEMPLATES
    shuffled_templates = templates[:]
    random.shuffle(shuffled_templates)

    now = timezone.now()
    accounts_made = 0
    reviews_made = 0

    for i, (first, last) in enumerate(reviewers):
        review_date = _spread_datetime(now)
        order_date = review_date - timedelta(days=random.randint(2, 6))
        email = f"{first.lower()}.{last.lower()}.demo@example.com"
        user, made = User.objects.get_or_create(
            username=email, defaults={'email': email, 'first_name': first, 'last_name': last},
        )
        if made:
            user.set_password(DEMO_PASSWORD)
            user.save()
            accounts_made += 1

        profile, _ = StoreProfile.objects.get_or_create(
            user=user, defaults={'phone': f'9{random.randint(100000000, 999999999)}'},
        )

        rating, comment = shuffled_templates[i % len(shuffled_templates)]

        has_delivered_order = OrderItem.objects.filter(
            order__user=user, order__status=Order.STATUS_DELIVERED, product_id=product.slug,
        ).exists()
        if not has_delivered_order:
            order = Order.objects.create(
                user=user, status=Order.STATUS_DELIVERED,
                subtotal=product.price, total=product.price,
                recipient_name=f"{first} {last}", recipient_phone=profile.phone,
                address_line1='Demo delivery address', city='Lucknow', state='Uttar Pradesh', pincode='226001',
            )
            OrderItem.objects.create(
                order=order, product_id=product.slug, product_name=product.name,
                price=product.price, quantity=1,
            )
            Payment.objects.create(order=order, method=Payment.METHOD_COD, status=Payment.STATUS_PAID, amount=product.price)
            Order.objects.filter(pk=order.pk).update(created_at=order_date, updated_at=review_date)

        review, created = Review.objects.update_or_create(
            product=product, user=user, defaults={'rating': rating, 'comment': comment},
        )
        Review.objects.filter(pk=review.pk).update(created_at=review_date)
        if created:
            reviews_made += 1

    return (
        f"Seeded {accounts_made} new demo accounts (password: {DEMO_PASSWORD}) and "
        f"{reviews_made} new reviews on \"{product.name}\"."
    )


def seed_demo_reviews():
    """Creates/refreshes the 54 demo buyer accounts and their reviews.
    Returns a short human-readable summary string."""
    products = list(Product.objects.filter(is_active=True))
    if not products:
        return "No active products found — add a product before seeding reviews."

    random.shuffle(products)
    accounts_made = 0
    reviews_made = 0
    now = timezone.now()

    for i, (first, last) in enumerate(REVIEWERS):
        # Spread reviews ~2 days apart going back in time (covering the last
        # few months across all 54), with a little jitter, so they don't all
        # show today's date — auto_now_add would otherwise stamp every
        # seeded review with the moment the command ran, which reads as
        # fake. QuerySet.update() below bypasses auto_now_add (it only
        # fires on Model.save()).
        review_date = now - timedelta(days=2 + i * 2 + random.randint(0, 2), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        order_date = review_date - timedelta(days=random.randint(2, 5))
        email = f"{first.lower()}.{last.lower()}.demo@example.com"
        user, made = User.objects.get_or_create(
            username=email, defaults={'email': email, 'first_name': first, 'last_name': last},
        )
        if made:
            user.set_password(DEMO_PASSWORD)
            user.save()
            accounts_made += 1

        profile, _ = StoreProfile.objects.get_or_create(
            user=user, defaults={'phone': f'9{random.randint(100000000, 999999999)}'},
        )

        product = products[i % len(products)]
        rating, comment = REVIEW_TEMPLATES[i % len(REVIEW_TEMPLATES)]

        has_delivered_order = OrderItem.objects.filter(
            order__user=user, order__status=Order.STATUS_DELIVERED, product_id=product.slug,
        ).exists()
        if not has_delivered_order:
            order = Order.objects.create(
                user=user, status=Order.STATUS_DELIVERED,
                subtotal=product.price, total=product.price,
                recipient_name=f"{first} {last}", recipient_phone=profile.phone,
                address_line1='Demo delivery address', city='Lucknow', state='Uttar Pradesh', pincode='226001',
            )
            OrderItem.objects.create(
                order=order, product_id=product.slug, product_name=product.name,
                price=product.price, quantity=1,
            )
            Payment.objects.create(order=order, method=Payment.METHOD_COD, status=Payment.STATUS_PAID, amount=product.price)
            Order.objects.filter(pk=order.pk).update(created_at=order_date, updated_at=review_date)

        review, created = Review.objects.update_or_create(
            product=product, user=user, defaults={'rating': rating, 'comment': comment},
        )
        Review.objects.filter(pk=review.pk).update(created_at=review_date)
        if created:
            reviews_made += 1

    product_count = min(len(REVIEWERS), len(products))
    return (
        f"Seeded {accounts_made} new demo accounts (password: {DEMO_PASSWORD}) and "
        f"{reviews_made} new reviews across {product_count} product{'s' if product_count != 1 else ''}."
    )
