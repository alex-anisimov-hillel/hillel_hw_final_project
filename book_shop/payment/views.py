import logging

from django.core.mail import send_mail
from django.shortcuts import render, get_object_or_404
from decimal import Decimal
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from payment.models import Payment
from payment.stripe_service import StripePayment
from payment.serializers import PaymentSerializer, PaymentCreateSerializer
from orders.models import Order
from payment.tasks import send_order_confirmation_email_task

logger = logging.getLogger(__name__)

STRIPE_PUBLIC_KEY = settings.STRIPE_PUBLIC_KEY


def checkout_view(request, order_id=None):
    """Render the Stripe checkout page for an (optional) existing order.

    If ``order_id`` is provided the matching :class:`~orders.models.Order`
    is loaded and passed to the template so its total price can be
    pre-filled; a missing order returns a 404. The Stripe publishable key
    is always included so the frontend can initialize Stripe.js.
    """
    order = None
    if order_id:
        order = get_object_or_404(Order, id=order_id)
    return render(
        request,
        "payment/checkout.html",
        {"stripe_public_key": STRIPE_PUBLIC_KEY, "order": order},
    )


async def send_order_confirmation_email(email, order_id):
    """Send a simple order-confirmation email, or do nothing if ``email`` is falsy.

    Kept as a coroutine (rather than a plain function) so it matches the
    async call site in :meth:`PaymentViewSet.confirm_payment` and the
    existing test suite, which patches/awaits it as an async callable.
    """
    if not email:
        return
    send_mail(
        subject="Order confirmation",
        message=f"The payment for our order #{order_id} was successful!",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


class PaymentViewSet(viewsets.ModelViewSet):
    """CRUD + payment-flow endpoints for the authenticated user's Stripe payments.

    Only the requesting user's own payments are ever visible or actionable
    (see :meth:`get_queryset`), and the whole viewset requires
    authentication so a payment can never be created, listed, or confirmed
    on behalf of an anonymous user.
    """

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Restrict every action to payments owned by the current user."""
        return Payment.objects.filter(user=self.request.user).select_related("user")

    def get_serializer_class(self):
        """Use the stricter creation serializer only for ``create_payment_intent``."""
        if self.action == "create_payment_intent":
            return PaymentCreateSerializer
        return PaymentSerializer

    @action(detail=False, methods=["POST"])
    def create_payment_intent(self, request):
        """Create a Stripe PaymentIntent (and local Payment) for the current user.

        Validates the request body with :class:`PaymentCreateSerializer`,
        then delegates to :meth:`StripePayment.create_payment_intent`.
        Returns 400 for invalid amounts/currency and 500 for unexpected
        Stripe/API errors, surfacing the error message either way instead
        of leaking a raw traceback.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment, payment_intent = StripePayment.create_payment_intent(
                user=request.user,
                amount=Decimal(serializer.validated_data["amount"]),
                currency=serializer.validated_data["currency"],
                description=serializer.validated_data["description"],
                metadata=serializer.validated_data.get("metadata", {}),
            )
            return Response(
                {
                    "payment_id": str(payment.id),
                    "client_secret": payment_intent.client_secret,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "status": payment.status,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as exception:
            return Response(
                {"Value error": str(exception)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exception:
            return Response(
                {"Error": str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["POST"])
    def confirm_payment(self, request, pk):
        """Confirm a Stripe PaymentIntent, attach it to an order, email the customer.

        Looks up the order given in ``order_id``, links it to this payment,
        asks Stripe for the current status via
        :meth:`StripePayment.confirm_payment`, and - when the order has an
        email on file - sends a confirmation email. Uses ``order.email``
        rather than ``order.user.email`` because ``order.user`` is optional
        (guest checkout), so this never raises on a userless order.
        """
        payment = self.get_object()
        order_id = request.data.get("order_id")
        order = get_object_or_404(Order, id=order_id)
        order.payment_method = payment
        order.save()
        try:
            payment = StripePayment.confirm_payment(
                payment_id=str(payment.id),
                stripe_payment_intent_id=payment.stripe_payment_intent_id,
            )
            if payment.is_success:
                # Mark the order paid; this also confirms the warehouse reservation
                # (see warehouse.signals).
                order.status = Order.OrderStatus.PAID
                order.save(update_fields=["status"])
            if order.email:
                try:
                    send_order_confirmation_email_task.delay(order.email, order_id)
                except Exception:
                    logger.exception(
                        "Could not send a confirmation email for order %s", order_id
                    )

            serializer = self.get_serializer(payment)
            return Response(serializer.data)
        except Exception as exception:
            return Response(
                {"Error": str(exception)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
