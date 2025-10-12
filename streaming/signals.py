"""Signal handlers for keeping models in sync."""
from __future__ import annotations
from django.db.models.signals import post_save
from django.dispatch import receiver
from . import models


@receiver(post_save, sender=models.Subscription)
def ensure_subscription_status(sender, instance: models.Subscription, created: bool, **kwargs) -> None:
    """Refresh the subscription status when saved."""

    if created:
        instance.refresh_status()


@receiver(post_save, sender=models.Video)
def update_video_publish_timestamp(sender, instance: models.Video, created: bool, **kwargs) -> None:
    """Ensure the published timestamp is set for published videos."""

    if instance.status == models.Video.Status.PUBLISHED and instance.published_at is None:
        instance.published_at = instance.updated_at
        instance.save(update_fields=["published_at"])
