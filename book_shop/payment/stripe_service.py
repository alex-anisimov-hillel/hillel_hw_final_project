import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from decimal import Decimal
from typing import Dict, Optional, Tuple


from payment.models import Payment

User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_version = "2026-08-26.dahlia"


class StripePayment:
    @staticmethod
    @transaction.atomic
    def create_payment_intent(
        user,
        amount: Decimal,
        currency: str = "usd",
        description: str = "",
        metadata: Optional[Dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[Payment, stripe.PaymentIntent]:
        if amount < Decimal("0.50"):
            raise ValueError("Minimal amount for the transaction is 0.50")
        stripe_amount = int(amount * 100)
        payment_metadata = metadata or {}
        payment_metadata["user_id"] = str(user.id)
        payment_intent_parameters = {
            "amount": stripe_amount,
            "currency": currency.lower(),
            "description": description,
            "metadata": payment_metadata,
            "automatic_payment_methods": {"enabled": True},
        }
        if idempotency_key:
            payment_intent = stripe.PaymentIntent.create(
                **payment_intent_parameters, idempotency_key=idempotency_key
            )
        else:
            payment_intent = stripe.PaymentIntent.create(**payment_intent_parameters)
        payment = Payment.objects.create(
            user=user,
            amount=amount,
            stripe_payment_intent_id=payment_intent.id,
            currency=currency.upper(),
            description=description,
            metadata=payment_metadata,
            status=Payment.Status.PENDING,
        )
        return payment, payment_intent

    @staticmethod
    @transaction.atomic
    def confirm_payment(payment_id: str, stripe_payment_intent_id: str) -> Payment:
        payment = Payment.objects.select_for_update().get(
            id=payment_id, stripe_payment_intent_id=stripe_payment_intent_id
        )
        if payment.is_success:
            return payment
        try:
            payment_intent = stripe.PaymentIntent.retrieve(stripe_payment_intent_id)
            if payment_intent.status == "succeeded":
                payment.status = Payment.Status.SUCCESS
                payment.stripe_charge_id = payment_intent.latest_charge
                payment.save(update_fields=["status", "stripe_charge_id"])
            else:
                payment.status = Payment.Status.FAILED
                payment.error = f"Payment intent status: {payment_intent.status}"
                payment.save(update_fields=["status", "error"])
            return payment
        except stripe.StripeError as exception:
            payment.status = Payment.Status.FAILED
            payment.error = str(exception)
            payment.save(update_fields=["status", "error"])
            raise
