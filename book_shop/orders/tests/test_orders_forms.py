from orders.forms import OrderCreateForm


def test_order_form_valid_with_full_data():
    form = OrderCreateForm(
        data={
            "email": "test@example.com",
            "phone_number": "0123456789",
            "address": "Some address",
            "city": "Some city",
        }
    )
    assert form.is_valid()


def test_order_form_invalid_email():
    form = OrderCreateForm(
        data={
            "email": "wrong email",
            "phone_number": "0123456789",
            "address": "Some address",
            "city": "Some city",
        }
    )
    assert not form.is_valid()
    assert "email" in form.errors


def test_order_form_allows_blank_fields():
    form = OrderCreateForm(data={})
    assert form.is_valid()
