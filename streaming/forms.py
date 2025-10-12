"""HTML form definitions for the streaming frontend."""
from __future__ import annotations
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    """Registration form tailored for the custom user model."""

    email = forms.EmailField(label="Email Address", max_length=255)
    phone_number = forms.CharField(label="Phone Number (Optional)", max_length=32, required=False)
    marketing_opt_in = forms.BooleanField(label="Receive newsletters and offers", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "phone_number", "password1", "password2", "marketing_opt_in")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        user.phone_number = self.cleaned_data.get("phone_number", "")
        user.marketing_opt_in = self.cleaned_data.get("marketing_opt_in", False)
        if commit:
            user.save()
        return user

class CommentForm(forms.Form):
    comment = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your comment...'}),
        label=""
    )
    rating = forms.TypedChoiceField(
        choices=[('', 'Rate this video'), (5, '★★★★★'), (4, '★★★★'), (3, '★★★'), (2, '★★'), (1, '★')],
        coerce=int,
        label="",
        required=False,
        widget=forms.Select
    )
    is_spoiler = forms.BooleanField(required=False, label="This comment contains spoilers")


class UserUpdateForm(forms.ModelForm):
    """Form for updating a user's public profile information."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'bio']