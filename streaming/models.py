"""Database models for the streaming platform."""
from __future__ import annotations
from datetime import timedelta
from typing import Optional
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class User(AbstractUser):
    """Custom user model with additional profile information."""
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=32, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    preferred_language = models.CharField(max_length=8, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    REQUIRED_FIELDS = ["email"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def active_subscription(self) -> Optional["Subscription"]:
        """Return the user's active subscription if available."""

        now = timezone.now()
        return (
            self.subscriptions.filter(
                status=Subscription.Status.ACTIVE, end_date__gte=now
            )
            .select_related("plan")
            .order_by("-end_date")
            .first()
        )

    @property
    def subscription_level(self) -> int:
        """Return the level of the active subscription or zero if none."""

        subscription = self.active_subscription
        if subscription and subscription.plan:
            return subscription.plan.level
        return 0


class SubscriptionPlan(models.Model):
    """Defines the available subscription tiers for users."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="IRR")
    duration_days = models.PositiveIntegerField(default=30)
    level = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Represents a payment transaction processed via the bank gateway."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="IRR")
    authority_code = models.CharField(max_length=64, blank=True)
    reference_code = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self) -> str:
        return f"Payment {self.pk} - {self.status}"

    def mark_success(self, reference: str, metadata: Optional[dict[str, str]] = None) -> None:
        self.status = self.Status.SUCCESS
        self.reference_code = reference
        self.processed_at = timezone.now()
        if metadata:
            self.metadata.update(metadata)
        self.save(update_fields=["status", "reference_code", "processed_at", "metadata"])

    def mark_failed(self, reason: str) -> None:
        self.status = self.Status.FAILED
        self.metadata.update({"reason": reason})
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "metadata", "processed_at"])


class Subscription(models.Model):
    """Subscription of a user to a specific plan."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    payment = models.OneToOneField(
        "Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="subscription"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status__in=["pending", "active"]),
                name="unique_active_subscription_per_user",
            )
        ]


    def __str__(self) -> str:
        return f"{self.user} - {self.plan} ({self.status})"

    @property
    def is_active(self) -> bool:
        if self.status != self.Status.ACTIVE:
            return False
        return self.end_date >= timezone.now()

    def refresh_status(self) -> None:
        """Update the status based on the end date."""

        now = timezone.now()
        new_status = self.status
        if self.status == self.Status.ACTIVE and self.end_date < now:
            new_status = self.Status.EXPIRED
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status"])

    def activate(self) -> None:
        self.status = self.Status.ACTIVE
        self.save(update_fields=["status"])

    def cancel(self) -> None:
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.end_date = timezone.now()
        self.save(update_fields=["status", "cancelled_at", "end_date"])

    def extend(self, extra_days: Optional[int] = None) -> None:
        """Extend the subscription by the plan duration or extra days."""

        days = extra_days or self.plan.duration_days
        self.end_date = (self.end_date or timezone.now()) + timedelta(days=days)
        self.status = self.Status.ACTIVE
        self.save(update_fields=["end_date", "status"])

    @classmethod
    def create_for_plan(cls, user: User, plan: SubscriptionPlan, payment: Optional[Payment] = None) -> "Subscription":
        now = timezone.now()
        subscription = cls.objects.create(
            user=user,
            plan=plan,
            payment=payment,
            status=cls.Status.ACTIVE,
            start_date=now,
            end_date=now + timedelta(days=plan.duration_days),
        )
        return subscription


class VideoCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=130, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Video categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Series(models.Model):
    """Represents a collection of episodes, like a TV show."""
    title = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=260, unique=True, blank=True)
    description = models.TextField(blank=True)
    poster = models.ImageField(upload_to="series_posters/", blank=True, null=True)
    release_year = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-release_year', 'title']
        verbose_name_plural = "Series"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)




class Video(models.Model):
    """Represents a piece of video content available on the platform."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"
    
    series = models.ForeignKey(
        Series,
        on_delete=models.CASCADE,
        related_name="episodes",
        null=True,
        blank=True,
        help_text="The series this video belongs to, if it's an episode."
    )
    season_number = models.PositiveIntegerField(null=True, blank=True)
    episode_number = models.PositiveIntegerField(null=True, blank=True)
    
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=260, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(VideoCategory, on_delete=models.SET_NULL, null=True, related_name="videos")
    duration_seconds = models.PositiveIntegerField()
    trailer_url = models.URLField(blank=True)
    stream_url = models.URLField(blank=True)
    video_file = models.FileField(upload_to="videos/", blank=True, null=True)
    thumbnail_url = models.URLField(blank=True)
    thumbnail_image = models.ImageField(upload_to="thumbnails/", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_subscription_level = models.PositiveIntegerField(default=1)
    is_premium = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_videos",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["series", "season_number", "episode_number", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=['series', 'season_number', 'episode_number'],
                name='unique_episode_in_series',
                condition=models.Q(series__isnull=False)
            )
        ]

    def __str__(self) -> str:
        if self.series:
            return f"{self.series.title} - S{self.season_number:02d}E{self.episode_number:02d}: {self.title}"
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def can_user_access(self, user: User) -> bool:
        if self.status != self.Status.PUBLISHED:
            return False
        if not self.is_premium:
            return True
        if not user.is_authenticated:
            return False
        return user.subscription_level >= self.min_subscription_level

    @property
    def average_rating(self) -> float:
        result = self.watch_history.filter(rating__isnull=False).aggregate(models.Avg("rating"))
        return float(result["rating__avg"] or 0.0)

    @property
    def views_count(self) -> int:
        return self.watch_history.count()

    @property
    def playback_url(self) -> str | None:
        """Return the preferred playback URL for embedding in templates."""

        if self.video_file:
            try:
                return self.video_file.url
            except ValueError:
                return None
        return self.stream_url or None

    @property
    def display_thumbnail(self) -> str | None:
        """Return the most appropriate thumbnail source."""

        if self.thumbnail_image:
            try:
                return self.thumbnail_image.url
            except ValueError:
                return None
        return self.thumbnail_url or None


class WatchHistory(models.Model):
    """Tracks video playback and interactions per user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watch_history")
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="watch_history")
    watched_at = models.DateTimeField(default=timezone.now)
    progress = models.PositiveIntegerField(default=0, help_text="Watch progress in seconds")
    completed = models.BooleanField(default=False)
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True
    )
    review = models.TextField(blank=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="watch_entries")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-watched_at"]

    def __str__(self) -> str:
        return f"{self.user} -> {self.video}"


class VideoComment(models.Model):
    """Stores comments made on videos."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="video_comments")
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="comments")
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_spoiler = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.user} on {self.video}"


class VideoBookmark(models.Model):
    """User saved videos to watch later."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="bookmarked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "video")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Bookmark {self.user} -> {self.video}"