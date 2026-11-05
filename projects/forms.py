import time

from django import forms
from django.core import signing

# Spam checks: a hidden "website" field (honeypot) that people never see but
# bots fill in, and a signed timestamp from when the page was loaded, since
# bots usually post within a second or two. Both are invisible to visitors.
MIN_SECONDS_TO_SUBMIT = 3
MAX_FORM_AGE_SECONDS = 24 * 60 * 60
_TS_SALT = 'contact-form-ts'


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': 'Name',
        'id': 'name'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': 'Email',
        'id': 'email'
    }))
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={
        'placeholder': 'Subject',
        'id': 'subject'
    }))
    message = forms.CharField(widget=forms.Textarea(attrs={
        'placeholder': 'Message',
        'id': 'message'
    }))
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'id': 'website',
        'tabindex': '-1',
        'autocomplete': 'off',
    }))
    form_ts = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields['form_ts'].initial = signing.dumps(time.time(), salt=_TS_SALT)

    def is_expired(self):
        """The page was loaded more than a day ago (likely a real person who left the tab open)."""
        try:
            signing.loads(self.cleaned_data.get('form_ts') or '', salt=_TS_SALT, max_age=MAX_FORM_AGE_SECONDS)
        except signing.SignatureExpired:
            return True
        except signing.BadSignature:
            pass
        return False

    def spam_reason(self):
        """Why this (valid) submission looks automated, or None if it looks human."""
        if self.cleaned_data.get('website'):
            return 'honeypot filled'
        try:
            loaded_at = signing.loads(self.cleaned_data.get('form_ts') or '', salt=_TS_SALT,
                                      max_age=MAX_FORM_AGE_SECONDS)
        except signing.BadSignature:  # also covers expired or missing
            return 'missing, forged or expired timestamp'
        if time.time() - float(loaded_at) < MIN_SECONDS_TO_SUBMIT:
            return 'submitted too fast'
        return None
