from django import forms
from orders.models import Order


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["email", "phone_number", "address", "city"]
