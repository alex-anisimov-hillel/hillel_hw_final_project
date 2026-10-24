import pytest
from decimal import Decimal

from payment.models import Payment


@pytest.mark.django_db
def test_payment_str_representation(payment):
    assert str(payment) == f"{payment}"


@pytest.mark.django_db
def test_payment_str_matches_expected_format(payment_factory):
    # Generated with AI, reviewed and modified
    payment = payment_factory(
        amount=Decimal("25.00"), currency="USD", status=Payment.Status.PENDING
    )
    assert (
        str(payment) == f"Payment {payment.id} - {payment.amount} {payment.currency} "
        f"({payment.status})"
    )


@pytest.mark.django_db
def test_payment_is_success_true_when_status_is_success(payment_factory):
    # Generated with AI, reviewed and modified
    payment = payment_factory(status=Payment.Status.SUCCESS)
    assert payment.is_success is True


@pytest.mark.django_db
def test_payment_is_success_false_for_non_success_status(payment_factory):
    # Generated with AI, reviewed and modified
    payment = payment_factory(status=Payment.Status.PENDING)
    assert payment.is_success is False


@pytest.mark.django_db
def test_payment_can_be_refunded_when_successful_and_not_fully_refunded(
    payment_factory,
):
    # Generated with AI, reviewed and modified
    payment = payment_factory(
        status=Payment.Status.SUCCESS,
        amount=Decimal("10.00"),
        refund_amount=Decimal("0.00"),
    )
    assert payment.can_be_refunded is True


@pytest.mark.django_db
def test_payment_can_be_refunded_false_when_payment_not_successful(payment_factory):
    # Generated with AI, reviewed and modified
    payment = payment_factory(
        status=Payment.Status.FAILED,
        amount=Decimal("10.00"),
        refund_amount=Decimal("0.00"),
    )
    assert payment.can_be_refunded is False


@pytest.mark.django_db
def test_payment_can_be_refunded_false_when_already_fully_refunded(payment_factory):
    # Generated with AI, reviewed and modified
    payment = payment_factory(
        status=Payment.Status.SUCCESS,
        amount=Decimal("10.00"),
        refund_amount=Decimal("15.00"),
    )
    assert payment.can_be_refunded is False


@pytest.mark.django_db
def test_payment_remaining_amount_subtracts_refund_from_total(payment_factory):
    # Generated with AI, reviewed and modified
    payment = payment_factory(amount=Decimal("10.00"), refund_amount=Decimal("4.00"))
    assert payment.remaining_amount == Decimal("6.00")


@pytest.mark.django_db
def test_payment_for_valid(payment_factory):
    payment = payment_factory(status="PENDING")
    assert payment.status == "PENDING"


@pytest.mark.django_db
def test_multiple_payments_users(payment_factory):
    payment1 = payment_factory()
    payment2 = payment_factory()
    assert payment1.user != payment2.user


@pytest.mark.django_db
def test_multiple_payments_same_users(payment_factory, user):
    payment1 = payment_factory(user=user)
    payment2 = payment_factory(user=user)
    assert payment1.user == payment2.user
