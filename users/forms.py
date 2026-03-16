from django import forms
from django.contrib.auth.forms import UserCreationForm
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox


class SignupForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Required. A verification link will be sent to this address.",
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ("email",)
