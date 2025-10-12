"""Domain services used by the streaming application."""
from __future__ import annotations
import random
import string
import requests
import json
from dataclasses import dataclass
from typing import Any
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone
from . import models
from django.conf import settings
from django.urls import reverse_lazy


@dataclass
class PaymentRequestResult:
    success: bool
    authority: str | None = None
    message: str = ""


@dataclass
class PaymentVerificationResult:
    success: bool
    reference: str | None = None
    message: str = ""


class MockBankGateway:
    """A fake payment gateway that emulates a banking provider."""

    def __init__(self, success_rate: float = 1.0) -> None:
        self.success_rate = success_rate

    def _generate_code(self, length: int = 16) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))

    def initiate_payment(self, amount: float, user: models.User, **metadata: Any) -> PaymentRequestResult:
        authority = self._generate_code()
        message = "The payment request was successfully submitted."
        return PaymentRequestResult(success=True, authority=authority, message=message)

    def verify_payment(self, authority: str) -> PaymentVerificationResult:
        success = True if self.success_rate >= 1 else random.random() <= self.success_rate
        if success:
            reference = self._generate_code(length=20)
            return PaymentVerificationResult(success=True, reference=reference, message="Payment successfully confirmed")
        return PaymentVerificationResult(success=False, reference=None, message="Payment not confirmed by bank")


class SubscriptionService:
    """High level operations for managing subscriptions."""

    def __init__(self, gateway: MockBankGateway | None = None) -> None:
        self.gateway = gateway or MockBankGateway()

    @transaction.atomic
    def start_subscription(self, user: models.User, plan: models.SubscriptionPlan) -> models.Subscription:
        payment = models.Payment.objects.create(user=user, plan=plan, amount=plan.price, currency=plan.currency)
        request_result = self.gateway.initiate_payment(plan.price, user=user, plan=plan.slug)
        if not request_result.success:
            payment.mark_failed(request_result.message)
            raise ValueError(request_result.message)
        payment.authority_code = request_result.authority or ""
        payment.metadata.update({"gateway_message": request_result.message})
        payment.save(update_fields=["authority_code", "metadata"])

        verification = self.gateway.verify_payment(payment.authority_code)
        if not verification.success:
            payment.mark_failed(verification.message)
            raise ValueError(verification.message)

        payment.mark_success(verification.reference or "")

        existing = user.active_subscription
        if existing:
            existing.extend(plan.duration_days)
            existing.payment = payment
            existing.save(update_fields=["end_date", "payment", "status"])
            return existing

        subscription = models.Subscription.create_for_plan(user=user, plan=plan, payment=payment)
        return subscription

    @transaction.atomic
    def cancel_subscription(self, subscription: models.Subscription) -> models.Subscription:
        subscription.cancel()
        return subscription

    @transaction.atomic
    def renew_subscription(self, subscription: models.Subscription) -> models.Subscription:
        plan = subscription.plan
        subscription.extend(plan.duration_days)
        return subscription
    
    @transaction.atomic
    def start_payment_process(self, user: models.User, plan: models.SubscriptionPlan, request) -> tuple[models.Payment, str | None]:
        """Initiates a payment and returns the payment URL."""
        gateway = ZarinpalGateway()
        callback_url = request.build_absolute_uri(reverse_lazy("payment_callback"))
        amount_in_toman = int(plan.price)

        payment = models.Payment.objects.create(user=user, plan=plan, amount=plan.price, currency=plan.currency)

        request_result = gateway.initiate_payment(amount_in_toman, user=user, callback_url=callback_url)

        if not request_result.success:
            payment.mark_failed(request_result.message)
            raise ValueError(request_result.message)

        payment.authority_code = request_result.authority
        payment.save()
        return payment, request_result.message


class VideoAnalyticsService:
    """Aggregate analytics related to videos for live dashboards."""

    @staticmethod
    def live_status(video: models.Video) -> dict[str, Any]:
        watch_qs = video.watch_history.all()
        ratings = watch_qs.exclude(rating__isnull=True)
        comments = video.comments.select_related("user").all()[:10]
        return {
            "video_id": video.pk,
            "views": watch_qs.count(),
            "average_rating": float(ratings.aggregate(Avg("rating"))["rating__avg"] or 0.0),
            "recent_comments": [
                {
                    "user": comment.user.get_full_name() or comment.user.username,
                    "comment": comment.comment,
                    "created_at": timezone.localtime(comment.created_at).isoformat(),
                }
                for comment in comments
            ],
        }
    
    
# FINAL Sandbox URLs
ZP_API_REQUEST = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZP_API_VERIFY = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
ZP_API_STARTPAY = "https://sandbox.zarinpal.com/pg/StartPay/{authority}"

class ZarinpalGateway:
    """Gateway for connecting to Zarinpal's payment API directly."""

    def __init__(self) -> None:
        self.merchant_id = settings.ZARINPAL_MERCHANT_ID

    def initiate_payment(
        self, amount: int, user: models.User, callback_url: str, **metadata: Any
    ) -> PaymentRequestResult:
        description = metadata.get("description", "Payment for subscription purchase")
        
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "description": description,
            "callback_url": callback_url,
            "metadata": {
                "email": user.email or "",
                "mobile": user.phone_number or ""
            },
            "currency": "IRR"
        }
        
        headers = {'content-type': 'application/json'}
        
        try:
            response = requests.post(
                ZP_API_REQUEST, data=json.dumps(payload), headers=headers, timeout=10
            )
            response_json = response.json()
            
            if response.status_code == 200 and response_json.get("data") and response_json["data"].get("code") == 100:
                authority = response_json["data"]["authority"]
                payment_url = ZP_API_STARTPAY.format(authority=authority)
                return PaymentRequestResult(success=True, authority=authority, message=payment_url)
            else:
                error_message = response_json.get("errors", {"message": "Unspecified error"})
                return PaymentRequestResult(success=False, message=str(error_message))

        except requests.exceptions.RequestException as e:
            return PaymentRequestResult(success=False, message=f"Error connecting to the gateway server: {e}")

    def verify_payment(self, amount: int, authority: str) -> PaymentVerificationResult:
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "authority": authority,
        }
        
        headers = {'content-type': 'application/json'}

        try:
            response = requests.post(
                ZP_API_VERIFY, data=json.dumps(payload), headers=headers, timeout=10
            )
            response_json = response.json()
            
            if response.status_code == 200 and response_json.get("data") and response_json["data"].get("code") in [100, 101]:
                data = response_json["data"]
                reference = data.get("ref_id")
                return PaymentVerificationResult(success=True, reference=str(reference))
            else:
                error_message = response_json.get("errors", {"message": "Payment confirmation failed."})
                return PaymentVerificationResult(success=False, message=str(error_message))

        except requests.exceptions.RequestException as e:
            return PaymentVerificationResult(success=False, message=f"Error connecting to the gateway server: {e}")



