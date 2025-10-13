from django import forms

class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label='メールアドレス',
        widget=forms.EmailInput(attrs={'placeholder': 'your-email@example.com', 'class': 'form-control'})
    )
