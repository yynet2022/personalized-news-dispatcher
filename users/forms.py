from django import forms

from .models import User


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label="メールアドレス",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "your-email@example.com",
                "class": "form-control",
            }
        ),
    )


class UserSettingsForm(forms.ModelForm):
    """
    ユーザー設定を更新するためのフォーム
    """

    class Meta:
        model = User
        fields = ["preferred_language"]
        widgets = {
            "preferred_language": forms.Select(
                attrs={"class": "form-control"}
            ),
        }
