from datetime import timedelta
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import F
from django.utils import timezone


class ContactLead(models.Model):
    """Persists every contact / lead-form submission.

    Saving to the database happens *before* the email is attempted, so
    no inquiry is ever lost even if SMTP is unavailable.
    """
    SOURCE_EDUTRELLIS = 'edutrellis'
    SOURCE_STORE = 'store'
    SOURCE_WEBSITECREATION = 'websitecreation'
    SOURCE_CHOICES = [
        (SOURCE_EDUTRELLIS, 'edutrellis.in'),
        (SOURCE_STORE, 'edutrellis.in/store'),
        (SOURCE_WEBSITECREATION, 'edutrellis.in/websitecreation'),
    ]

    name       = models.CharField(max_length=120)
    phone      = models.CharField(max_length=20)
    email      = models.EmailField()
    service    = models.CharField(max_length=200, blank=True)
    message    = models.TextField(blank=True)
    source     = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_EDUTRELLIS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name      = 'Contact Lead'
        verbose_name_plural = 'Contact Leads'

    def __str__(self):
        return f"{self.name} — {self.phone} ({timezone.localtime(self.created_at):%d %b %Y %H:%M})"


class StoreProfile(models.Model):
    """Extra store-specific fields for a Django auth User (E-Store signups)."""
    LOCATION_UNKNOWN = 'unknown'
    LOCATION_GRANTED = 'granted'
    LOCATION_DENIED = 'denied'
    LOCATION_CONSENT_CHOICES = [
        (LOCATION_UNKNOWN, 'Not asked'),
        (LOCATION_GRANTED, 'Enabled'),
        (LOCATION_DENIED, 'Declined'),
    ]

    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='store_profile')
    phone          = models.CharField(max_length=20, blank=True)
    avatar         = models.ImageField(upload_to='avatars/', blank=True, null=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    manual_amount_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Amount manually recorded as paid when staff creates or edits this customer.',
    )
    email_verified = models.BooleanField(default=False)  # unused — verification moved to phone/SMS, see phone_verified
    phone_verified = models.BooleanField(default=False)
    location_consent = models.CharField(
        max_length=10, choices=LOCATION_CONSENT_CHOICES, default=LOCATION_UNKNOWN,
        help_text='Whether the user allowed a one-time browser location request.',
    )
    location_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    # Vidhyora AI subscription — buying the AI plan product (see
    # AI_SUBSCRIPTION_PRODUCT_SLUG below) extends this instead of granting
    # a boolean flag, so back-to-back renewals stack cleanly. Staff accounts
    # bypass both the cap and this field entirely (see views._ai_profile_gate)
    # rather than being modeled as a permanent subscription here.
    ai_subscription_until = models.DateTimeField(null=True, blank=True, help_text="Vidhyora AI access is unlimited until this time. Blank/past = free tier.")
    ai_free_messages_used = models.PositiveIntegerField(default=0, help_text="Free-tier Vidhyora AI messages sent so far (resets on each new subscription purchase).")

    # First-time AI chat onboarding — asked once, on this account's first
    # real AI reply, then captured from whatever they say next (see
    # views.ai_chat_send and ai_chat.extract_onboarding_fields). Values are
    # saved only if the user actually volunteers them; never required.
    ai_onboarded = models.BooleanField(default=False, help_text="Already asked the first-time name/location/Instagram question (or the account predates this feature) — never ask again.")
    ai_onboarding_pending = models.BooleanField(default=False, help_text="The question was just asked; the user's next message will be parsed for an answer.")
    ai_display_name = models.CharField(max_length=100, blank=True, help_text="Name the user gave the AI chat, if any.")
    ai_location = models.CharField(max_length=150, blank=True, help_text="Location the user gave the AI chat, if any.")
    ai_instagram_handle = models.CharField(max_length=60, blank=True, help_text="Instagram handle the user gave the AI chat, if any (no leading @).")

    class Meta:
        verbose_name = 'Store Customer Profile'
        verbose_name_plural = 'Store Customer Profiles'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.phone})"

    @property
    def is_ai_subscribed(self):
        return bool(self.ai_subscription_until and self.ai_subscription_until > timezone.now())


class ActiveUserSession(models.Model):
    """The one browser session currently allowed to use a user account."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='active_login_session',
    )
    session_key = models.CharField(max_length=40, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Active User Session'
        verbose_name_plural = 'Active User Sessions'

    def __str__(self):
        return f'{self.user.username} — {self.session_key}'


class Category(models.Model):
    """A storefront category shown on the homepage's 'Shop by Category' rail
    and used as a filter tab on the shop grid. Replaces the old hardcoded
    icon-based categories with an admin-managed list backed by an image."""
    name        = models.CharField(max_length=80)
    slug        = models.SlugField(max_length=80, unique=True, help_text="Used to match product filter tags, e.g. 'audio'.")
    description = models.CharField(max_length=200, blank=True)
    image       = models.ImageField(upload_to='categories/', blank=True, null=True)
    order       = models.PositiveIntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Store Category'
        verbose_name_plural = 'Store Categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    """A storefront product. Replaces the old hardcoded PRODUCTS array in
    estore.html with an admin-managed catalogue backed by the database."""
    category          = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    slug              = models.SlugField(max_length=40, unique=True, help_text="Used as the product ID in the cart/orders — keep it stable once orders exist.")
    brand             = models.CharField(max_length=80)
    name              = models.CharField(max_length=200)
    short_description = models.CharField(max_length=300, help_text="Shown on the product card.")
    description       = models.TextField(blank=True, help_text="Longer description shown when a shopper opens the product detail view.")
    specs             = models.TextField(blank=True, help_text="One spec per line, formatted as 'Label: Value' — shown on the product detail view.")
    price             = models.DecimalField(max_digits=10, decimal_places=2)
    mrp               = models.DecimalField(max_digits=10, decimal_places=2)
    image             = models.ImageField(upload_to='products/', blank=True, null=True, help_text="Cover image. Falls back to the icon + gradient tile below when left blank. Add more angles under 'Product images' below (up to 5 total).")
    video             = models.FileField(upload_to='products/videos/', blank=True, null=True, help_text="Optional MP4 product video, shown as a slide in the detail page gallery.")
    icon              = models.CharField(max_length=60, default='fa-box', help_text="Font Awesome icon class shown when no image is set, e.g. 'fa-headphones'.")
    gradient          = models.CharField(max_length=200, default='linear-gradient(135deg,#e8001e,#c0001a)', help_text="CSS background used behind the icon when no image is set.")
    flag              = models.CharField(max_length=40, blank=True, help_text="Small badge on the card, e.g. 'Bestseller'.")
    stock_status      = models.CharField(max_length=40, default='In stock', help_text="e.g. 'In stock', 'Only 4 left'.")
    tags              = models.CharField(max_length=200, blank=True, help_text="Comma-separated, e.g. 'ANC, 40h battery, IPX5'.")
    rating            = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    reviews_count     = models.PositiveIntegerField(default=0)
    is_active         = models.BooleanField(default=True)
    is_digital        = models.BooleanField(default=False, help_text="Digital/subscription product — nothing physically ships, so checkout hides Cash on Delivery for it.")
    order             = models.PositiveIntegerField(default=0)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Store Product'
        verbose_name_plural = 'Store Products'

    def __str__(self):
        return self.name

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def spec_list(self):
        items = []
        for line in self.specs.splitlines():
            label, sep, value = line.partition(':')
            if not label.strip():
                continue
            items.append((label.strip(), value.strip() if sep else ''))
        return items

    @property
    def discount_pct(self):
        if not self.mrp:
            return 0
        return round((1 - float(self.price) / float(self.mrp)) * 100)

    @property
    def review_stats(self):
        """Blends the manually-set `rating`/`reviews_count` (the store's
        starting/base figures) with real Review rows, so the displayed
        average updates honestly as genuine reviews come in instead of
        either ignoring them or discarding the base numbers outright."""
        real = list(self.reviews.all())
        real_count = len(real)
        total_count = self.reviews_count + real_count
        if total_count == 0:
            return (0.0, 0)
        points = float(self.rating) * self.reviews_count + sum(r.rating for r in real)
        return (round(points / total_count, 1), total_count)

class ProductImage(models.Model):
    """One extra gallery photo for a Product's detail-page slider. Capped at
    5 per product by the admin form (ProductImageFormSet)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image   = models.ImageField(upload_to='products/gallery/')
    order   = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductColor(models.Model):
    """A selectable colour variant shown as a swatch on the product detail
    page. Purely presentational — it doesn't split stock or pricing."""
    product   = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='colors')
    name      = models.CharField(max_length=60, help_text="e.g. 'Midnight Black'.")
    hex_code  = models.CharField(max_length=7, default='#1c2333', help_text="e.g. #1c2333 — used for the swatch colour.")
    image     = models.ImageField(upload_to='products/colors/', blank=True, null=True, help_text="Optional — the gallery switches to this image when the shopper picks this colour.")
    order     = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Product Color'
        verbose_name_plural = 'Product Colors'

    def __str__(self):
        return f"{self.name} ({self.product.name})"


class AboutUsContent(models.Model):
    """Singleton content block backing the storefront's About Us section."""
    photo          = models.ImageField(upload_to='about/', blank=True, null=True)
    badge_title    = models.CharField(max_length=120, default='Working since 2020')
    badge_subtitle = models.CharField(max_length=200, default='Websites & technical services · store launched 2026')

    founder_name     = models.CharField(max_length=120, default='Vijay Tiwari')
    founder_title    = models.CharField(max_length=120, default='Founder & CEO')
    founder_email    = models.EmailField(default='ceo@edutrellis.in')
    founder_linkedin = models.URLField(blank=True, default='https://www.linkedin.com/in/vijaytiwariii/')
    founder_photo    = models.ImageField(upload_to='about/', blank=True, null=True)

    stat1_value = models.CharField(max_length=20, default='2020')
    stat1_label = models.CharField(max_length=40, default='Founded')
    stat2_value = models.CharField(max_length=20, default='1200+')
    stat2_label = models.CharField(max_length=40, default='Clients')
    stat3_value = models.CharField(max_length=20, default='500+')
    stat3_label = models.CharField(max_length=40, default='Projects')
    stat4_value = models.CharField(max_length=20, default='98%')
    stat4_label = models.CharField(max_length=40, default='Satisfaction')

    heading    = models.CharField(max_length=200, default='A gadget store run by a tech company')
    paragraph1 = models.TextField(default=(
        "EduTrellis Private Limited has been working since 2020 — building and selling websites, "
        "and running the technical services around them: hosting, SEO, digital marketing and Google "
        "Business, for clients across India from our base in Lucknow."
    ))
    paragraph2 = models.TextField(default=(
        "Along the way we bought a lot of gear for our own team and for clients, and got tired of spec "
        "sheets that didn't match reality. So this year we launched the store. Everything listed here is "
        "stock we keep, unbox and test before it ships, sold at a fixed price."
    ))

    list_heading   = models.CharField(max_length=150, default='What you get with every order')
    bullet_points  = models.TextField(default=(
        "Sealed, genuine units, tested before dispatch\n"
        "Specs listed honestly — real battery and charging numbers\n"
        "Dispatch within 24 hours, tracking sent on WhatsApp\n"
        "GST invoice on request for business purchases\n"
        "A human who actually answers your messages"
    ), help_text="One point per line.")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'About Us Content'
        verbose_name_plural = 'About Us Content'

    def __str__(self):
        return 'About Us content'

    @property
    def bullet_list(self):
        return [b.strip() for b in self.bullet_points.splitlines() if b.strip()]

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PolicyPage(models.Model):
    """Admin-editable legal/policy pages linked from the storefront footer."""
    PRIVACY  = 'privacy'
    TERMS    = 'terms'
    REFUND   = 'refund'
    SHIPPING = 'shipping'
    KEY_CHOICES = [
        (PRIVACY, 'Privacy Policy'),
        (TERMS, 'Terms & Conditions'),
        (REFUND, 'Refund Policy'),
        (SHIPPING, 'Shipping & Delivery'),
    ]
    key        = models.CharField(max_length=20, choices=KEY_CHOICES, unique=True)
    title      = models.CharField(max_length=150)
    content    = models.TextField(help_text="Plain text — a blank line starts a new paragraph.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Policy Page'
        verbose_name_plural = 'Policy Pages'

    def __str__(self):
        return self.title

    @property
    def paragraphs(self):
        return [p.strip() for p in self.content.split('\n\n') if p.strip()]


class PaymentSettings(models.Model):
    """Singleton Razorpay configuration, managed from the store dashboard."""
    razorpay_key_id     = models.CharField(max_length=100, blank=True)
    razorpay_key_secret = models.CharField(max_length=100, blank=True)
    is_razorpay_enabled = models.BooleanField(default=False)
    is_test_mode        = models.BooleanField(default=True)
    cod_enabled         = models.BooleanField(default=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment Settings'
        verbose_name_plural = 'Payment Settings'

    def __str__(self):
        return 'Payment settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def razorpay_ready(self):
        return bool(self.is_razorpay_enabled and self.razorpay_key_id and self.razorpay_key_secret)


class EmailSettings(models.Model):
    """Singleton SMTP configuration, managed from the store dashboard. This is
    the only source of SMTP credentials for every email the app sends (order
    confirmations, contact leads) — there is no fallback in settings.py. If
    left disabled or incomplete, no email is sent."""
    is_enabled     = models.BooleanField(default=False, help_text='Turn on to send emails using the SMTP details below. If off (or incomplete), no email is sent.')
    smtp_host      = models.CharField(max_length=200, blank=True, default='smtp.gmail.com')
    smtp_port      = models.PositiveIntegerField(default=587)
    smtp_username  = models.CharField(max_length=200, blank=True)
    smtp_password  = models.CharField(max_length=200, blank=True)
    use_tls        = models.BooleanField(default=True)
    use_ssl        = models.BooleanField(default=False)
    from_email     = models.CharField(max_length=200, blank=True, help_text='e.g. "EduTrellis <support@edutrellis.in>". Defaults to the SMTP username if left blank.')
    notify_email   = models.EmailField(blank=True, help_text='Where new-order and contact-lead notifications are sent. Defaults to the support email if left blank.')
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Email (SMTP) Settings'
        verbose_name_plural = 'Email (SMTP) Settings'

    def __str__(self):
        return 'Email settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def ready(self):
        return bool(self.is_enabled and self.smtp_host and self.smtp_username and self.smtp_password)


class Cart(models.Model):
    """A shopping cart tied to a logged-in store user or an anonymous session."""
    user        = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Store Cart'
        verbose_name_plural = 'Store Carts'

    def __str__(self):
        owner = self.user.username if self.user else f"session:{self.session_key[:8]}"
        return f"Cart #{self.pk} — {owner}"


class CartItem(models.Model):
    """A single product line inside a Cart. Product data is snapshotted here
    since the storefront catalogue lives in the template, not the database."""
    cart         = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_id   = models.CharField(max_length=40)
    product_name = models.CharField(max_length=200)
    price        = models.DecimalField(max_digits=10, decimal_places=2)
    quantity     = models.PositiveIntegerField(default=1)
    added_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product_id')
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.price * self.quantity


# Product id (matches Product.slug) whose first delivered order
# triggers the ₹100 wallet-credit welcome offer.
WALLET_OFFER_PRODUCT_ID = 'aud-metal'
WALLET_OFFER_CREDIT = 100

# Product id (matches Product.slug) for the Vidhyora AI monthly plan —
# seeded automatically by migration 0034_seed_ai_subscription_product.
# Buying it (see Order.maybe_grant_ai_subscription) extends the buyer's
# StoreProfile.ai_subscription_until by this many days.
AI_SUBSCRIPTION_PRODUCT_SLUG = 'edutrellis-ai-monthly'
AI_SUBSCRIPTION_DAYS = 30


class Order(models.Model):
    """A placed order, created from the cart at checkout. Product data is
    snapshotted onto OrderItem the same way CartItem snapshots it, since the
    catalogue lives in the template, not the database."""
    STATUS_PLACED     = 'placed'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED    = 'shipped'
    STATUS_DELIVERED  = 'delivered'
    STATUS_CANCELLED  = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PLACED, 'Placed'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    user                   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    status                 = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLACED)
    subtotal               = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wallet_discount        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    handling_fee           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total                  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wallet_credit_applied  = models.BooleanField(default=False)
    ai_subscription_granted = models.BooleanField(default=False)

    # Delivery address — snapshotted at checkout the same way OrderItem
    # snapshots product data, so a later profile edit never changes where an
    # already-placed order was meant to ship.
    recipient_name  = models.CharField(max_length=120, blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    address_line1   = models.CharField(max_length=200, blank=True)
    address_line2   = models.CharField(max_length=200, blank=True)
    city            = models.CharField(max_length=100, blank=True)
    state           = models.CharField(max_length=100, blank=True)
    pincode         = models.CharField(max_length=10, blank=True)

    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Store Order'
        verbose_name_plural = 'Store Orders'

    def __str__(self):
        return f"Order #{self.pk} — {self.user.username} ({self.get_status_display()})"

    @property
    def full_address(self):
        lines = [self.address_line1, self.address_line2, self.city, self.state, self.pincode]
        return ', '.join(line for line in lines if line)

    @property
    def latest_payment(self):
        """The most recent Payment attempt for this order (COD or Razorpay,
        whatever its status). payments is ordered newest-first
        (Payment.Meta.ordering), and when the caller has
        .prefetch_related('payments') this hits that cache instead of a
        fresh query per order."""
        return self.payments.first()

    @property
    def payment_label(self):
        """'COD — pay on delivery', 'COD — Paid', 'Online — Paid',
        'Online — Pending', 'Online — Failed', etc. — shown in the
        dashboard Orders/Delivery pages so staff can see COD vs Online at
        a glance, and whether it's actually been paid."""
        payment = self.latest_payment
        if not payment:
            return None
        if payment.method == payment.METHOD_COD:
            if payment.status == payment.STATUS_COD_PENDING:
                return payment.get_status_display()
            return f'COD — {payment.get_status_display()}'
        return f'Online — {payment.get_status_display()}'

    def maybe_credit_wallet(self):
        """Credits the ₹100 welcome offer once this order is Delivered, if
        it's the customer's first order and contains the Metal Bluetooth
        Speaker. Idempotent via wallet_credit_applied — guarded with an
        atomic compare-and-swap UPDATE so two concurrent calls (e.g. a
        double-click on "Mark Delivered") can't both pass the check and
        double-credit the wallet."""
        if self.wallet_credit_applied or self.status != self.STATUS_DELIVERED:
            return
        claimed = Order.objects.filter(pk=self.pk, wallet_credit_applied=False).update(wallet_credit_applied=True)
        if not claimed:
            return
        self.wallet_credit_applied = True
        is_first_order = not Order.objects.filter(user=self.user).exclude(pk=self.pk).exists()
        has_offer_product = self.items.filter(product_id=WALLET_OFFER_PRODUCT_ID).exists()
        if is_first_order and has_offer_product:
            StoreProfile.objects.filter(user=self.user).update(wallet_balance=F('wallet_balance') + WALLET_OFFER_CREDIT)

    def maybe_grant_ai_subscription(self):
        """Extends the buyer's Vidhyora AI subscription once this order's
        AI-plan item (AI_SUBSCRIPTION_PRODUCT_SLUG) is actually paid for —
        either an online payment that's cleared, or a COD order the admin
        has marked Delivered (COD's own "paid" signal elsewhere in this
        codebase, e.g. maybe_credit_wallet above). Extends from whichever is
        later, now or the current expiry, so renewing early stacks instead
        of wasting remaining days. Idempotent the same way as
        maybe_credit_wallet — an atomic compare-and-swap on
        ai_subscription_granted means a re-saved order status or a repeated
        webhook call can't extend the subscription twice for one order."""
        if self.ai_subscription_granted:
            return
        if not self.items.filter(product_id=AI_SUBSCRIPTION_PRODUCT_SLUG).exists():
            return
        payment = self.latest_payment
        if not payment:
            return
        paid = payment.status == Payment.STATUS_PAID or (
            payment.method == Payment.METHOD_COD and self.status == self.STATUS_DELIVERED
        )
        if not paid:
            return
        claimed = Order.objects.filter(pk=self.pk, ai_subscription_granted=False).update(ai_subscription_granted=True)
        if not claimed:
            return
        self.ai_subscription_granted = True
        profile, _ = StoreProfile.objects.get_or_create(user=self.user)
        now = timezone.now()
        base = profile.ai_subscription_until if profile.ai_subscription_until and profile.ai_subscription_until > now else now
        profile.ai_subscription_until = base + timedelta(days=AI_SUBSCRIPTION_DAYS)
        profile.ai_free_messages_used = 0
        profile.save(update_fields=['ai_subscription_until', 'ai_free_messages_used'])


class OrderItem(models.Model):
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_id   = models.CharField(max_length=40)
    product_name = models.CharField(max_length=200)
    price        = models.DecimalField(max_digits=10, decimal_places=2)
    quantity     = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.price * self.quantity


class Payment(models.Model):
    """A payment attempt/record for an Order — either Cash on Delivery or a
    Razorpay transaction. One Order can have multiple Payment rows if a
    Razorpay attempt fails and the shopper retries."""
    METHOD_COD      = 'cod'
    METHOD_RAZORPAY = 'razorpay'
    METHOD_CHOICES = [
        (METHOD_COD, 'Cash on Delivery'),
        (METHOD_RAZORPAY, 'Razorpay'),
    ]

    STATUS_PENDING     = 'pending'
    STATUS_PAID        = 'paid'
    STATUS_FAILED      = 'failed'
    STATUS_REFUNDED    = 'refunded'
    STATUS_COD_PENDING = 'cod_pending'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
        (STATUS_COD_PENDING, 'COD — pay on delivery'),
    ]

    order                = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    method               = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_COD)
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount               = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    razorpay_order_id    = models.CharField(max_length=80, blank=True)
    razorpay_payment_id  = models.CharField(max_length=80, blank=True)
    razorpay_signature   = models.CharField(max_length=200, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"Payment for Order #{self.order_id} — {self.get_method_display()} ({self.get_status_display()})"


class DropboxSettings(models.Model):
    """Singleton Dropbox App credentials used to back up/restore db.sqlite3,
    managed from the store dashboard."""
    app_key       = models.CharField(max_length=200, blank=True)
    app_secret    = models.CharField(max_length=200, blank=True)
    refresh_token = models.CharField(max_length=400, blank=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dropbox Backup Settings'
        verbose_name_plural = 'Dropbox Backup Settings'

    def __str__(self):
        return 'Dropbox backup settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_configured(self):
        return bool(self.app_key and self.app_secret and self.refresh_token)


class PWASettings(models.Model):
    """Singleton PWA (Progressive Web App) configuration, managed from the
    store dashboard. When enabled (and an icon is set), the storefront
    exposes a manifest + service worker and shows an 'Install App' button
    to shoppers on supporting browsers."""
    is_enabled        = models.BooleanField(default=False, help_text="Show the 'Install App' option on the storefront. Needs an icon set below to actually work.")
    app_name          = models.CharField(max_length=100, default='EduTrellis Store', help_text='Full name shown during install and on the splash screen.')
    short_name        = models.CharField(max_length=40, default='EduTrellis', help_text='Short name shown under the home-screen icon.')
    description       = models.CharField(max_length=200, blank=True, default="Shop gadgets from EduTrellis — audio, wearables, charging and more.")
    icon              = models.ImageField(upload_to='pwa/', blank=True, null=True, help_text='Square logo, ideally 512×512px or larger — used as the installed app icon.')
    theme_color       = models.CharField(max_length=7, default='#e8001e', help_text='Hex color, e.g. #e8001e — used for the browser/app toolbar.')
    background_color  = models.CharField(max_length=7, default='#ffffff', help_text='Hex color shown behind the splash screen while the app loads.')
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'PWA (Install App) Settings'
        verbose_name_plural = 'PWA (Install App) Settings'

    def __str__(self):
        return 'PWA settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def ready(self):
        return bool(self.is_enabled and self.icon)


class FeeSettings(models.Model):
    """Singleton delivery/handling fee configuration, managed from the store
    dashboard. Any field left at 0 simply isn't charged."""
    delivery_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, help_text='Flat delivery fee per order. Leave 0 for free delivery.')
    free_delivery_over = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, help_text='Orders at or above this subtotal skip the delivery fee above, even if one is set. Leave 0 to always charge it (if set).')
    handling_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, help_text='Flat handling fee per order. Leave 0 for no handling fee.')
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delivery & Handling Fees'
        verbose_name_plural = 'Delivery & Handling Fees'

    def __str__(self):
        return 'Delivery & handling fees'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class EmailVerification(models.Model):
    """A pending email-verification OTP for an already-logged-in store user.
    Signup itself is never blocked on this — the account exists and is
    usable regardless of whether/when the shopper verifies. Sending the
    email is always best-effort from the caller's side."""
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    otp           = models.CharField(max_length=6)
    attempts      = models.PositiveSmallIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    last_sent_at  = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField()

    class Meta:
        verbose_name = 'Pending Email Verification'
        verbose_name_plural = 'Pending Email Verifications'

    def __str__(self):
        return f"{self.user.email} (expires {timezone.localtime(self.expires_at):%d %b %H:%M})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class PhoneVerification(models.Model):
    """A pending phone-verification OTP, sent and checked via the 2Factor
    SMS API — the actual OTP digits live at 2Factor against `session_id`,
    we never generate or store them ourselves. Signup itself is never
    blocked on this — the account exists and is usable regardless of
    whether/when the shopper verifies."""
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='phone_verification')
    session_id    = models.CharField(max_length=100)
    phone         = models.CharField(max_length=20)
    attempts      = models.PositiveSmallIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    last_sent_at  = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField()

    class Meta:
        verbose_name = 'Pending Phone Verification'
        verbose_name_plural = 'Pending Phone Verifications'

    def __str__(self):
        return f"{self.phone} (expires {timezone.localtime(self.expires_at):%d %b %H:%M})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class Review(models.Model):
    """A shopper's rating/comment on a Product. Every row here is a verified
    purchase — creating one is gated (see views._user_can_review) on the
    shopper having a Delivered order containing this product, so there's no
    separate 'verified' flag to track."""
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')
    rating     = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('product', 'user')
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'

    def __str__(self):
        return f"{self.user.username} → {self.product.name} ({self.rating}★)"


class AIConversation(models.Model):
    """One saved chat thread on /AI/, ChatGPT-style. A guest (not logged in)
    can chat for a few messages before being asked to log in — their
    conversation is kept here tied to session_key (user is null) and gets
    handed over to their account (user set, session_key cleared) the moment
    they log in or sign up, the same way an anonymous cart is merged in."""
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_conversations', null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    title       = models.CharField(max_length=80, blank=True)
    # Captured once at creation from the same IP-detection the chat rate
    # limiter already uses — lets staff (see dashboard AI Activity) spot a
    # repeat spammer across guest sessions/accounts sharing one connection,
    # not just within one rate-limit window. Null when the request's IP
    # couldn't be determined at all (never set to the literal 'unknown').
    ip_address  = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'AI Conversation'
        verbose_name_plural = 'AI Conversations'

    def __str__(self):
        return self.title or f"Conversation #{self.pk}"


class AIBlock(models.Model):
    """Staff-issued block against a repeat spammer on /AI/, checked on every
    ai_chat_send call before anything else runs. Blocks by IP (works
    against a guest, and stops a logged-out spammer from just signing up
    again from the same connection) and/or by account (still works if their
    IP changes) — either or both can be set; see dashboard AI Activity for
    where these get created."""
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='ai_blocks')
    reason     = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Block'
        verbose_name_plural = 'AI Blocks'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ip_address__isnull=False) | models.Q(user__isnull=False),
                name='aiblock_ip_or_user_required',
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f'Blocked account: {self.user.email or self.user.username}'
        return f'Blocked IP: {self.ip_address}'


class GitHubConnection(models.Model):
    """A user's personal-access-token connection to GitHub, used by
    /AI/'s GitHub mode to read files from and push commits to a chosen repo
    on their instruction. One per user, isolated by the user relation, and
    the token itself is never sent back to the browser once saved."""
    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='github_connection')
    access_token    = models.CharField(max_length=255)
    github_username = models.CharField(max_length=120, blank=True)
    repo_full_name  = models.CharField(max_length=200, blank=True, help_text="owner/repo this connection reads/writes, e.g. 'boosternotes/EduTrellis'.")
    default_branch  = models.CharField(max_length=100, blank=True, default='main')
    connected_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'GitHub Connection'
        verbose_name_plural = 'GitHub Connections'

    def __str__(self):
        return f"{self.github_username or self.user.username} → {self.repo_full_name or '(no repo set)'}"


class KnowledgeEntry(models.Model):
    """A saved fact/answer EduTrellis Light checks before anything else.
    Seeded manually from the admin, and grown automatically three ways: a
    live web search fallback saves its top result; every real chat Q&A
    (any model) saves the pair; and a Q&A that involved an uploaded file/
    image, or a logged-in user's own account details, is saved too — but
    scoped private to that one user/guest session (see user/session_key
    below) instead of shared, since that content can be personal or
    proprietary. A blank user AND blank session_key means shared with
    everyone; either one set means only that person's own future Light
    questions can retrieve it. See light_mode.save_from_chat/
    search_knowledge_base for exactly how this is decided and enforced."""
    SOURCE_MANUAL = 'manual'
    SOURCE_WEB = 'web_search'
    SOURCE_CHAT = 'chat'
    SOURCE_CHOICES = [(SOURCE_MANUAL, 'Manual'), (SOURCE_WEB, 'Web search'), (SOURCE_CHAT, 'Chat')]

    topic       = models.CharField(max_length=200, help_text="Short label/question this answers, e.g. 'refund policy' or 'GST registration steps'.")
    content     = models.TextField(help_text='The saved text EduTrellis Light will answer from.')
    source      = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    source_url  = models.URLField(blank=True, help_text='Where this was found, if saved from a web search.')
    user        = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='knowledge_entries', help_text='Set only for an entry private to one logged-in person (from a file/image upload, or their own account details). Blank = visible to everyone.')
    session_key = models.CharField(max_length=40, blank=True, db_index=True, help_text='Same idea as user, for a private entry saved from a guest (not logged in) session.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Knowledge Entry'
        verbose_name_plural = 'Knowledge Entries (EduTrellis Light)'

    def __str__(self):
        return self.topic


class YouTubeDownloadJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_WORKING = 'working'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_WORKING, 'Working'),
        (STATUS_READY, 'Ready'), (STATUS_FAILED, 'Failed'),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='youtube_downloads')
    source_url = models.URLField(max_length=500)
    quality = models.CharField(max_length=10, default='1080')
    title = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    progress = models.PositiveSmallIntegerField(default=0)
    video_path = models.CharField(max_length=500, blank=True)
    audio_path = models.CharField(max_length=500, blank=True)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']


class AIGeneratedFile(models.Model):
    """A text/code file created from an AI chat request.

    The opaque token is used in the download URL, while the user/session
    ownership check in the download view keeps the file private.
    """
    token       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_generated_files', null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    file_name   = models.CharField(max_length=120)
    content     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Generated File'
        verbose_name_plural = 'AI Generated Files'

    def __str__(self):
        return self.file_name


class AIMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [(ROLE_USER, 'User'), (ROLE_ASSISTANT, 'Assistant')]

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name='messages')
    role         = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content      = models.TextField()
    image_data   = models.TextField(blank=True)  # data: URI of an attached image, if any (user turns only)
    document_name = models.CharField(max_length=255, blank=True)
    # Extracted text (capped by doc_extract.MAX_CHARS), persisted so
    # follow-up questions about the same document work without re-uploading
    # it — replayed on every turn within AI_CHAT_MAX_HISTORY, same tradeoff
    # as replaying an attached image.
    document_text = models.TextField(blank=True)
    model_key    = models.CharField(max_length=20, blank=True)  # which EduTrellis model answered (assistant turns only)
    # Comma-separated slugs of real EduTrellis Store products shown as cards
    # under this reply (assistant turns only) — see myapp.product_search.
    # Never AI-generated text; always resolved from the real Product table
    # so history replay shows the same real cards, not anything the model
    # claimed.
    product_slugs = models.CharField(max_length=250, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'AI Message'
        verbose_name_plural = 'AI Messages'

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class AINote(models.Model):
    """A note saved from the AI chat, Google-Keep style — created when the
    user says something like 'take this note', 'note it down', or 'save
    details' (see request_router.is_note_intent / views._ai_save_note_response).
    Owned the same dual way as AIConversation: a real account, or a guest
    tied to session_key."""
    user         = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='ai_notes')
    session_key  = models.CharField(max_length=40, blank=True, db_index=True)
    conversation = models.ForeignKey(AIConversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes')
    heading      = models.CharField(max_length=120, blank=True)
    content      = models.TextField()
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Note'
        verbose_name_plural = 'AI Notes'

    def __str__(self):
        return self.heading or f"Note #{self.pk}"


class AIReport(models.Model):
    """A user's 'this answer is wrong / abusive' report against one
    assistant reply, submitted from the Report button under every AI chat
    message. Snapshots the reported reply's text and model at submit time
    (not just a message FK) so staff can still see exactly what was flagged
    even if the message, or the whole conversation, is later deleted."""
    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [(STATUS_OPEN, 'Open'), (STATUS_RESOLVED, 'Resolved')]

    conversation   = models.ForeignKey(AIConversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    message        = models.ForeignKey(AIMessage, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    reported_reply = models.TextField(blank=True)
    model_key      = models.CharField(max_length=20, blank=True)
    explanation    = models.TextField(blank=True)
    user           = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_reports')
    session_key    = models.CharField(max_length=40, blank=True, db_index=True)
    ip_address     = models.GenericIPAddressField(null=True, blank=True)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Report'
        verbose_name_plural = 'AI Reports'

    def __str__(self):
        return f"Report #{self.pk} ({self.get_status_display()})"


class SiteCustomization(models.Model):
    """Singleton branding configuration, managed from the store dashboard's
    Customize page — currently just the favicon shown in the browser tab
    across every page (AI chat, store, policy pages, 404, dashboard). See
    myapp.views.site_customization_context, registered as a global template
    context processor in edutrellis/settings.py, for how SITE_FAVICON_URL
    reaches every template without each view needing to fetch this itself."""
    favicon    = models.ImageField(upload_to='branding/', blank=True, null=True, help_text='Browser-tab icon. Square, ideally 512×512px or smaller (PNG/ICO). Leave blank to use the default EduTrellis favicon.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Customization'
        verbose_name_plural = 'Site Customization'

    def __str__(self):
        return 'Site customization'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
