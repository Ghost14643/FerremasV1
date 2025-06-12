# ferremasApp/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        
        widgets = {
            'password': forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
            'password2': forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        }