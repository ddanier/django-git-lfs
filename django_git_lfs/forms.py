from django import forms
from .models import LfsObject


class LfsObjectForm(forms.ModelForm):
    class Meta:
        model = LfsObject
        fields = ('oid', 'file', 'size')
