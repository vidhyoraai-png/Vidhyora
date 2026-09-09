from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.text import slugify

from myapp.models import Order, StoreProfile, PaymentSettings, DropboxSettings, EmailSettings, PWASettings, SiteCustomization


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
        max_length=120, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Optional — defaults to Admin'}),
        help_text='Leave blank to use Admin.',
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
    payment_received_at = forms.DateTimeField(
        label='Payment received date and time', required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'},
        ),
        help_text='Leave blank to use the current date and time.',
    )
    password = forms.CharField(
        max_length=128, required=False,
        error_messages={'min_length': 'Password must be at least 6 characters.'},
        widget=forms.TextInput(attrs={'placeholder': 'Default: admin54321'}),
        help_text='Leave blank to use admin54321.',
    )
    ai_access_days = forms.ChoiceField(
        label='Give AI premium access for', required=False, initial='365',
        choices=(('30', '1 month'), ('180', '6 months'), ('365', '1 year')),
        widget=forms.RadioSelect,
    )

    def clean_name(self):
        return self.cleaned_data.get('name', '').strip() or 'Admin'

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        existing = User.objects.filter(email__iexact=email).select_related('store_profile').first()
        if existing:
            joined = existing.date_joined.strftime('%d %b %Y')
            role = 'Superuser' if existing.is_superuser else ('Staff' if existing.is_staff else 'Customer')
            name = (f'{existing.first_name} {existing.last_name}'.strip()) or existing.username
            phone = getattr(existing.store_profile, 'phone', '') or 'not on file'
            raise forms.ValidationError(
                f'An account with "{email}" already exists — {name}, {role.lower()}, '
                f'phone {phone}, joined {joined}. Edit that account instead of creating a new one.'
            )
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
        fields = [
            'favicon', 'social_preview_title', 'social_preview_description',
            'social_preview_image',
        ]
        widgets = {
            'social_preview_description': forms.Textarea(attrs={'rows': 3}),
        }




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
