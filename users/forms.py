from django import forms
from .models import User


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label='メールアドレス',
        widget=forms.EmailInput(
            attrs={'placeholder': 'your-email@example.com',
                   'class': 'form-control'})
    )


class UserSettingsForm(forms.ModelForm):
    """
    ユーザー設定を更新するためのフォーム
    """
    LANGUAGE_CHOICES = [
        ('Japanese', 'Japanese'),
        ('English', 'English'),
        ('Chinese', 'Chinese'),
        ('Korean', 'Korean'),
    ]

    preferred_language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        label='優先言語',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['preferred_language']
