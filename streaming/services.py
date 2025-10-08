"""Domain services used by the streaming application."""
from __future__ import annotations

import random
import string
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from . import models


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
        message = "درخواست پرداخت با موفقیت ثبت شد."
        return PaymentRequestResult(success=True, authority=authority, message=message)

    def verify_payment(self, authority: str) -> PaymentVerificationResult:
        success = True if self.success_rate >= 1 else random.random() <= self.success_rate
        if success:
            reference = self._generate_code(length=20)
            return PaymentVerificationResult(success=True, reference=reference, message="پرداخت با موفقیت تایید شد")
        return PaymentVerificationResult(success=False, reference=None, message="پرداخت توسط بانک تایید نشد")


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
