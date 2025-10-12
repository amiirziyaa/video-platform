"""Seed the database with demo data for quick exploration."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from streaming.models import (
    Payment,
    Subscription,
    SubscriptionPlan,
    Video,
    VideoCategory,
    WatchHistory,
)


class Command(BaseCommand):
    """Populate the database with opinionated demo data."""

    help = "Create a demo user, plans, videos and watch history entries."

    def handle(self, *args, **options) -> None:  # type: ignore[override]
        with transaction.atomic():
            demo_user = self._ensure_demo_user()
            plans = self._ensure_plans()
            categories = self._ensure_categories()
            videos = self._ensure_videos(demo_user, categories)
            subscription = self._ensure_subscription(demo_user, plans["premium"])
            self._ensure_watch_history(demo_user, videos, subscription.payment)

        self.stdout.write(self.style.SUCCESS("Demo data ready!"))
        self.stdout.write("Log in with username 'demo' and password 'demo1234'.")

    def _ensure_demo_user(self):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@example.com",
                "first_name": "فیلم",
                "last_name": "دوست",
                "is_staff": True,
            },
        )
        if created:
            user.set_password("demo1234")
            user.save(update_fields=["password"])
            self.stdout.write("Created demo user.")
        return user

    def _ensure_plans(self) -> dict[str, SubscriptionPlan]:
        plans: dict[str, SubscriptionPlan] = {}
        plan_definitions = [
            {
                "key": "basic",
                "name": "Basic",
                "price": 99000,
                "level": 1,
                "duration_days": 30,
                "description": "کیفیت SD و دسترسی به آرشیو عمومی.",
            },
            {
                "key": "standard",
                "name": "Standard",
                "price": 149000,
                "level": 2,
                "duration_days": 30,
                "description": "کیفیت HD به همراه دانلود آفلاین.",
            },
            {
                "key": "premium",
                "name": "Premium",
                "price": 199000,
                "level": 3,
                "duration_days": 30,
                "description": "کیفیت 4K و تماشای همزمان روی چند دستگاه.",
            },
        ]

        for data in plan_definitions:
            plan, created = SubscriptionPlan.objects.get_or_create(
                slug=data["key"],
                defaults={
                    "name": data["name"],
                    "price": data["price"],
                    "level": data["level"],
                    "duration_days": data["duration_days"],
                    "description": data["description"],
                },
            )
            if created:
                self.stdout.write(f"Created plan {plan.name}.")
            else:
                updated = False
                for field in ("name", "price", "level", "duration_days", "description"):
                    if getattr(plan, field) != data[field]:
                        setattr(plan, field, data[field])
                        updated = True
                if updated:
                    plan.save()
                    self.stdout.write(f"Updated plan {plan.name}.")
            plans[data["key"]] = plan
        return plans

    def _ensure_categories(self) -> dict[str, VideoCategory]:
        categories: dict[str, VideoCategory] = {}
        category_definitions = [
            ("drama", "درام"),
            ("documentary", "مستند"),
            ("comedy", "کمدی"),
        ]
        for slug, name in category_definitions:
            category, created = VideoCategory.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            if created:
                self.stdout.write(f"Created category {name}.")
            elif category.name != name:
                category.name = name
                category.save(update_fields=["name"])
                self.stdout.write(f"Updated category {name}.")
            categories[slug] = category
        return categories

    def _ensure_videos(self, user, categories) -> dict[str, Video]:
        videos: dict[str, Video] = {}
        video_definitions = [
            {
                "slug": "behind-the-scenes",
                "title": "پشت صحنه تولید یک سریال محبوب",
                "category": categories["documentary"],
                "duration_seconds": 1800,
                "stream_url": "https://cdn.example.com/videos/behind-the-scenes.m3u8",
                "thumbnail_url": "https://cdn.example.com/thumbs/behind-the-scenes.jpg",
                "is_premium": False,
                "min_subscription_level": 0,
            },
            {
                "slug": "family-drama",
                "title": "درام خانوادگی",
                "category": categories["drama"],
                "duration_seconds": 5400,
                "stream_url": "https://cdn.example.com/videos/family-drama.m3u8",
                "thumbnail_url": "https://cdn.example.com/thumbs/family-drama.jpg",
                "min_subscription_level": 2,
            },
            {
                "slug": "standup-night",
                "title": "شب استندآپ",
                "category": categories["comedy"],
                "duration_seconds": 3600,
                "stream_url": "https://cdn.example.com/videos/standup-night.m3u8",
                "thumbnail_url": "https://cdn.example.com/thumbs/standup-night.jpg",
                "min_subscription_level": 1,
            },
        ]
        for data in video_definitions:
            defaults = {
                "title": data["title"],
                "description": "نمونه محتوای ویدیویی برای شروع کار.",
                "category": data["category"],
                "duration_seconds": data["duration_seconds"],
                "trailer_url": data.get("trailer_url", ""),
                "stream_url": data["stream_url"],
                "thumbnail_url": data["thumbnail_url"],
                "status": Video.Status.PUBLISHED,
                "published_at": timezone.now(),
                "created_by": user,
                "is_premium": data.get("is_premium", True),
                "min_subscription_level": data.get("min_subscription_level", 1),
            }
            video, created = Video.objects.get_or_create(
                slug=data["slug"],
                defaults=defaults,
            )
            if created:
                self.stdout.write(f"Created video {video.title}.")
            else:
                # ensure metadata stays up to date if we modify defaults later
                for field, value in defaults.items():
                    setattr(video, field, value)
                video.save()
            videos[data["slug"]] = video
        return videos

    def _ensure_subscription(self, user, plan: SubscriptionPlan) -> Subscription:
        subscription = user.subscriptions.filter(status=Subscription.Status.ACTIVE).first()
        if subscription:
            return subscription

        payment, _ = Payment.objects.get_or_create(
            user=user,
            plan=plan,
            status=Payment.Status.SUCCESS,
            amount=plan.price,
            currency=plan.currency,
            defaults={
                "authority_code": "AUTH-DEMO",
                "reference_code": "REF-DEMO",
                "processed_at": timezone.now(),
            },
        )
        start = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            payment=payment,
            status=Subscription.Status.ACTIVE,
            start_date=start,
            end_date=start + timedelta(days=plan.duration_days),
        )
        self.stdout.write("Created demo subscription.")
        return subscription

    def _ensure_watch_history(self, user, videos, payment) -> None:
        watch_entries = [
            {
                "video": videos["behind-the-scenes"],
                "progress": 1200,
                "completed": True,
                "rating": 4,
                "review": "خیلی آموزنده بود!",
            },
            {
                "video": videos["family-drama"],
                "progress": 2400,
                "completed": False,
            },
            {
                "video": videos["standup-night"],
                "progress": 3500,
                "completed": True,
                "rating": 5,
                "review": "واقعا خنده دار بود!",
            },
        ]
        for data in watch_entries:
            WatchHistory.objects.update_or_create(
                user=user,
                video=data["video"],
                defaults={
                    "watched_at": timezone.now(),
                    "progress": data.get("progress", 0),
                    "completed": data.get("completed", False),
                    "rating": data.get("rating"),
                    "review": data.get("review", ""),
                    "payment": payment,
                },
            )
        self.stdout.write("Seeded watch history.")
