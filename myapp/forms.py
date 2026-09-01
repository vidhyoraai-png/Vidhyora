from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.text import slugify

from myapp.models import (
    Category, Order, Product, ProductImage, ProductColor, StoreProfile,
    AboutUsContent, PolicyPage, PaymentSettings, DropboxSettings, EmailSettings, PWASettings, FeeSettings,
    SiteCustomization,
)


class GrantAISubscriptionForm(forms.Form):
    """Dashboard tool (AI Management) for staff to manually grant a
    customer Vidhyora AI premium access — the same ai_subscription_until
    field a real Order.maybe_grant_ai_subscription() purchase sets, just
    driven by an admin instead of a payment. Looked up by email/username
    rather than a dropdown since the store can have dozens of accounts."""
    identifier = forms.CharField(
        max_length=254, label='Customer email or username',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. customer@example.com'}),
    )
    days = forms.IntegerField(
        label='Access duration (days)', min_value=1, max_value=3650, initial=365,
        help_text='365 = 1 year, 30 = 1 month.',
    )

    def clean_identifier(self):
        identifier = self.cleaned_data['identifier'].strip()
        self.matched_user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        if not self.matched_user:
            raise forms.ValidationError(f'No account found for "{identifier}".')
        return identifier


class AddUserForm(forms.Form):
    """Dashboard tool (used from both Signups and AI Management) for staff
    to manually create a customer account — e.g. someone who signed up over
    phone/WhatsApp, or so AI Management has an account to grant premium
    access to without the customer self-registering first."""
    name = forms.CharField(
        max_length=120, required=True,
        error_messages={'required': "Enter the customer's full name."},
        widget=forms.TextInput(attrs={'placeholder': 'Full name'}),
    )
    email = forms.EmailField(
        required=True,
        error_messages={'required': 'Enter an email address.', 'invalid': 'Enter a valid email address.'},
        widget=forms.EmailInput(attrs={'placeholder': 'customer@example.com'}),
    )
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional'}))
    amount_paid = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Optional', 'step': '0.01', 'min': '0'}),
        help_text='Optional amount already paid by this customer.',
    )
    password = forms.CharField(
        max_length=128, required=False,
        error_messages={'min_length': 'Password must be at least 6 characters.'},
        widget=forms.TextInput(attrs={'placeholder': 'Leave blank to auto-generate'}),
        help_text='Leave blank to auto-generate a random password.',
    )

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError("Enter the customer's full name.")
        return name

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if phone:
            digits = ''.join(ch for ch in phone if ch.isdigit())
            if len(digits) < 10:
                raise forms.ValidationError('Enter a valid phone number.')
            if StoreProfile.objects.filter(phone=phone).exists():
                raise forms.ValidationError('An account with this phone number already exists.')
        return phone

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        if password and len(password) < 6:
            raise forms.ValidationError('Password must be at least 6 characters.')
        return password

    def clean_amount_paid(self):
        return self.cleaned_data.get('amount_paid') or 0


class AISignupForm(forms.Form):
    name     = forms.CharField(max_length=120, required=True, error_messages={'required': 'Enter your full name.'})
    phone    = forms.CharField(max_length=20, required=True, error_messages={'required': 'Enter your phone number.'})
    email    = forms.EmailField(required=True, error_messages={'required': 'Enter your email address.', 'invalid': 'Enter a valid email address.'})
    password = forms.CharField(min_length=6, required=True, error_messages={'required': 'Create a password.', 'min_length': 'Password must be at least 6 characters.'})

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Enter your full name.')
        return name

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError('Enter a valid phone number.')
        if StoreProfile.objects.filter(phone=phone).exists():
            raise forms.ValidationError('An account with this phone number already exists — try logging in.')
        return phone

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists — try logging in.')
        return email


class PhoneVerifyForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6, required=True, error_messages={
        'required': 'Enter the code we texted you.', 'min_length': 'Enter the full 6-digit code.',
    })

    def clean_otp(self):
        otp = self.cleaned_data['otp'].strip()
        if not otp.isdigit():
            raise forms.ValidationError('Enter the full 6-digit code.')
        return otp


class AILoginForm(forms.Form):
    identifier = forms.CharField(max_length=150, required=True, error_messages={'required': 'Enter your email or phone number.'})
    password   = forms.CharField(required=True, error_messages={'required': 'Enter your password.'})


class AIProfileEditForm(forms.Form):
    name   = forms.CharField(max_length=120, required=True, error_messages={'required': 'Enter your full name.'})
    phone  = forms.CharField(max_length=20, required=True, error_messages={'required': 'Enter your phone number.'})
    # Optional keeps the existing store profile form backwards-compatible;
    # the AI account modal supplies it so customers can change their login.
    email  = forms.EmailField(required=False, error_messages={'invalid': 'Enter a valid email address.'})
    avatar = forms.ImageField(required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Enter your full name.')
        return name

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError('Enter a valid phone number.')
        existing = StoreProfile.objects.filter(phone=phone)
        if self.user:
            existing = existing.exclude(user=self.user)
        if existing.exists():
            raise forms.ValidationError('An account with this phone number already exists.')
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            return ''
        existing = User.objects.filter(email__iexact=email)
        if self.user:
            existing = existing.exclude(pk=self.user.pk)
        if existing.exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and avatar.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Profile image must be 5 MB or smaller.')
        return avatar


class AIPasswordChangeForm(forms.Form):
    current_password = forms.CharField(required=True, error_messages={'required': 'Enter your current password.'})
    new_password      = forms.CharField(min_length=6, required=True, error_messages={'required': 'Enter a new password.', 'min_length': 'New password must be at least 6 characters.'})


class SignupEditForm(forms.ModelForm):
    phone = forms.CharField(max_length=20, required=False)
    wallet_balance = forms.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    amount_paid = forms.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email

    def clean_wallet_balance(self):
        return self.cleaned_data.get('wallet_balance') or 0

    def clean_amount_paid(self):
        return self.cleaned_data.get('amount_paid') or 0


class CategoryForm(forms.ModelForm):
    slug = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'auto-generated if left blank'}),
    )

    class Meta:
        model = Category
        fields = ['name', 'slug', 'description', 'image', 'order', 'is_active']

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Category name must be at least 2 characters long.')
        return name

    def clean_slug(self):
        slug = slugify(self.cleaned_data.get('slug') or self.cleaned_data.get('name', ''))
        if not slug:
            raise forms.ValidationError('Could not derive a slug — enter one manually.')
        qs = Category.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A category with this slug already exists.')
        return slug


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']


class ProductForm(forms.ModelForm):
    slug = forms.CharField(
        max_length=40, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'auto-generated if left blank'}),
    )

    class Meta:
        model = Product
        # 'name' must precede 'slug' — clean_slug() reads self.cleaned_data['name'],
        # and Django's _clean_fields() populates cleaned_data in this field order.
        fields = [
            'category', 'brand', 'name', 'slug', 'short_description', 'description', 'specs',
            'price', 'mrp', 'image', 'video', 'icon', 'gradient', 'flag', 'stock_status', 'tags',
            'rating', 'reviews_count', 'order', 'is_active',
        ]
        widgets = {
            'short_description': forms.TextInput(),
            'description': forms.Textarea(attrs={'rows': 4}),
            'specs': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Battery: 40 hours\nConnectivity: Bluetooth 5.3'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Product name must be at least 2 characters long.')
        return name

    def clean_slug(self):
        slug = slugify(self.cleaned_data.get('slug') or self.cleaned_data.get('name', ''))
        if not slug:
            raise forms.ValidationError('Could not derive a slug — enter one manually.')
        qs = Product.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A product with this slug already exists.')
        return slug

    def clean(self):
        cleaned = super().clean()
        price, mrp = cleaned.get('price'), cleaned.get('mrp')
        if price is not None and mrp is not None and price > mrp:
            raise forms.ValidationError('Price cannot be higher than MRP.')
        return cleaned


ProductImageFormSet = forms.inlineformset_factory(
    Product, ProductImage,
    fields=['image', 'order'],
    extra=8, max_num=10, validate_max=True, can_delete=True,
)

ProductColorFormSet = forms.inlineformset_factory(
    Product, ProductColor,
    fields=['name', 'hex_code', 'image', 'order'],
    extra=6, max_num=14, validate_max=True, can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={'placeholder': 'Colour name, e.g. Midnight Black'}),
        'hex_code': forms.TextInput(attrs={'type': 'color'}),
        'order': forms.NumberInput(attrs={'placeholder': 'Order'}),
    },
)


class AboutUsContentForm(forms.ModelForm):
    class Meta:
        model = AboutUsContent
        fields = [
            'photo', 'badge_title', 'badge_subtitle',
            'founder_name', 'founder_title', 'founder_email', 'founder_linkedin', 'founder_photo',
            'stat1_value', 'stat1_label', 'stat2_value', 'stat2_label',
            'stat3_value', 'stat3_label', 'stat4_value', 'stat4_label',
            'heading', 'paragraph1', 'paragraph2', 'list_heading', 'bullet_points',
        ]
        widgets = {
            'paragraph1': forms.Textarea(attrs={'rows': 4}),
            'paragraph2': forms.Textarea(attrs={'rows': 4}),
            'bullet_points': forms.Textarea(attrs={'rows': 5, 'placeholder': 'One point per line'}),
        }


class PolicyPageForm(forms.ModelForm):
    class Meta:
        model = PolicyPage
        fields = ['title', 'content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 16}),
        }


class PaymentSettingsForm(forms.ModelForm):
    razorpay_key_secret = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=True, attrs={'autocomplete': 'new-password'}),
        help_text='Found in Razorpay Dashboard → Settings → API Keys. Kept secret — never exposed to the storefront.',
    )

    class Meta:
        model = PaymentSettings
        fields = ['razorpay_key_id', 'razorpay_key_secret', 'is_razorpay_enabled', 'is_test_mode', 'cod_enabled']


class DropboxSettingsForm(forms.ModelForm):
    app_secret = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=True, attrs={'autocomplete': 'new-password'}),
        help_text='From your Dropbox App Console — kept secret, never exposed to the storefront.',
    )
    refresh_token = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=True, attrs={'autocomplete': 'new-password'}),
        help_text="A long-lived OAuth2 refresh token for your Dropbox app (doesn't expire like a short-lived access token).",
    )

    class Meta:
        model = DropboxSettings
        fields = ['app_key', 'app_secret', 'refresh_token']


class PWASettingsForm(forms.ModelForm):
    class Meta:
        model = PWASettings
        fields = ['is_enabled', 'app_name', 'short_name', 'description', 'icon', 'theme_color', 'background_color']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'theme_color': forms.TextInput(attrs={'type': 'color'}),
            'background_color': forms.TextInput(attrs={'type': 'color'}),
        }


class SiteCustomizationForm(forms.ModelForm):
    class Meta:
        model = SiteCustomization
        fields = ['favicon']


class FeeSettingsForm(forms.ModelForm):
    delivery_fee       = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0 = free delivery'}))
    free_delivery_over = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'optional'}))
    handling_fee       = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0 = no handling fee'}))

    class Meta:
        model = FeeSettings
        fields = ['delivery_fee', 'free_delivery_over', 'handling_fee']

    def clean_delivery_fee(self):
        return self.cleaned_data.get('delivery_fee') or 0

    def clean_free_delivery_over(self):
        return self.cleaned_data.get('free_delivery_over') or 0

    def clean_handling_fee(self):
        return self.cleaned_data.get('handling_fee') or 0


class EmailSettingsForm(forms.ModelForm):
    smtp_password = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=True, attrs={'autocomplete': 'new-password'}),
        help_text='For Gmail, use a 16-character App Password, not your normal login password. Kept secret — never exposed to the storefront.',
    )

    class Meta:
        model = EmailSettings
        fields = [
            'is_enabled', 'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
            'use_tls', 'use_ssl', 'from_email', 'notify_email',
        ]
