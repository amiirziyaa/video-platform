"""DRF serializers for the streaming API."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from . import models, services

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Expose public information about a user."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "preferred_language",
            "marketing_opt_in",
        ]
        read_only_fields = ["id", "username", "email"]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer used during registration."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SubscriptionPlan
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "currency",
            "duration_days",
            "level",
            "is_active",
        ]
        read_only_fields = ["id", "slug", "is_active"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Payment
        fields = [
            "id",
            "amount",
            "currency",
            "authority_code",
            "reference_code",
            "status",
            "requested_at",
            "processed_at",
            "metadata",
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = models.Subscription
        fields = [
            "id",
            "plan",
            "status",
            "start_date",
            "end_date",
            "auto_renew",
            "payment",
            "is_active",
        ]
        read_only_fields = fields

    def get_is_active(self, obj: models.Subscription) -> bool:
        return obj.is_active


class SubscriptionCreateSerializer(serializers.Serializer):
    plan_id = serializers.PrimaryKeyRelatedField(
        source="plan", queryset=models.SubscriptionPlan.objects.filter(is_active=True)
    )

    def create(self, validated_data):
        request = self.context["request"]
        plan = validated_data["plan"]
        service = services.SubscriptionService()
        try:
            subscription = service.start_subscription(request.user, plan)
        except ValueError as exc:
            raise serializers.ValidationError({"payment": str(exc)}) from exc
        return subscription

    def to_representation(self, instance):
        return SubscriptionSerializer(instance, context=self.context).data


class SubscriptionRenewSerializer(serializers.Serializer):
    extra_days = serializers.IntegerField(required=False, min_value=1)

    def update(self, instance: models.Subscription, validated_data):
        extra_days = validated_data.get("extra_days")
        if extra_days:
            instance.extend(extra_days)
        else:
            services.SubscriptionService().renew_subscription(instance)
        return instance

    def to_representation(self, instance):
        return SubscriptionSerializer(instance, context=self.context).data


class VideoCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VideoCategory
        fields = ["id", "name", "slug", "description"]
        read_only_fields = ["id", "slug"]


class VideoSerializer(serializers.ModelSerializer):
    category = VideoCategorySerializer(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Video
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "duration_seconds",
            "trailer_url",
            "stream_url",
            "thumbnail_url",
            "price",
            "min_subscription_level",
            "is_premium",
            "status",
            "published_at",
            "created_at",
            "updated_at",
            "average_rating",
            "views_count",
        ]
        read_only_fields = [
            "id",
            "slug",
            "published_at",
            "created_at",
            "updated_at",
            "average_rating",
            "views_count",
        ]


class VideoWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Video
        fields = [
            "title",
            "description",
            "category",
            "duration_seconds",
            "trailer_url",
            "stream_url",
            "thumbnail_url",
            "price",
            "min_subscription_level",
            "is_premium",
            "status",
        ]


class WatchHistorySerializer(serializers.ModelSerializer):
    video = VideoSerializer(read_only=True)

    class Meta:
        model = models.WatchHistory
        fields = [
            "id",
            "video",
            "watched_at",
            "progress",
            "completed",
            "rating",
            "review",
        ]
        read_only_fields = ["id", "watched_at"]


class WatchHistoryCreateSerializer(serializers.ModelSerializer):
    video = serializers.PrimaryKeyRelatedField(
        queryset=models.Video.objects.filter(status=models.Video.Status.PUBLISHED)
    )

    class Meta:
        model = models.WatchHistory
        fields = ["video", "progress", "completed", "rating", "review"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data.setdefault("watched_at", timezone.now())
        return super().create(validated_data)


class VideoCommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = models.VideoComment
        fields = ["id", "user", "video", "comment", "is_spoiler", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class VideoLiveStatusSerializer(serializers.Serializer):
    video_id = serializers.IntegerField()
    views = serializers.IntegerField()
    average_rating = serializers.FloatField()
    recent_comments = serializers.ListField(child=serializers.DictField())


class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VideoBookmark
        fields = ["id", "video", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
