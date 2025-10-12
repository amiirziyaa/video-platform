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
    plan = SubscriptionPlanSerializer(read_only=True)
    class Meta:
        model = models.Payment
        fields = [
            "id",
            "plan",
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
    series = serializers.StringRelatedField() 
    average_rating = serializers.FloatField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)
    playback_url = serializers.SerializerMethodField()
    thumbnail_source = serializers.SerializerMethodField()

    class Meta:
        model = models.Video
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "series",
            "season_number",
            "episode_number",
            "category",
            "duration_seconds",
            "trailer_url",
            "stream_url",
            "video_file",
            "thumbnail_url",
            "thumbnail_image",
            "price",
            "min_subscription_level",
            "is_premium",
            "status",
            "published_at",
            "created_at",
            "updated_at",
            "average_rating",
            "views_count",
            "playback_url",
            "thumbnail_source",
        ]
        read_only_fields = [
            "id",
            "slug",
            "published_at",
            "created_at",
            "updated_at",
            "average_rating",
            "views_count",
            "playback_url",
            "thumbnail_source",
        ]

    def get_playback_url(self, obj: models.Video) -> str | None:
        url = obj.playback_url
        request = self.context.get("request") if hasattr(self, "context") else None
        if url and request and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url

    def get_thumbnail_source(self, obj: models.Video) -> str | None:
        url = obj.display_thumbnail
        request = self.context.get("request") if hasattr(self, "context") else None
        if url and request and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url


class VideoWriteSerializer(serializers.ModelSerializer):
    series = serializers.PrimaryKeyRelatedField(
        queryset=models.Series.objects.all(),
        required=False,
        allow_null=True
    )
    class Meta:
        model = models.Video
        fields = [
            "title",
            "description",
            "category",
            "series",
            "season_number",
            "episode_number",
            "duration_seconds",
            "trailer_url",
            "stream_url",
            "video_file",
            "thumbnail_url",
            "thumbnail_image",
            "price",
            "min_subscription_level",
            "is_premium",
            "status",
        ]
        extra_kwargs = {
            "stream_url": {"required": False, "allow_blank": True},
            "video_file": {"required": False, "allow_null": True},
            "thumbnail_url": {"required": False, "allow_blank": True},
            "thumbnail_image": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        stream_url = attrs.get("stream_url")
        video_file = attrs.get("video_file")
        instance = getattr(self, "instance", None)
        existing_stream = getattr(instance, "stream_url", "") if instance else ""
        existing_file = getattr(instance, "video_file", None) if instance else None
        if not (stream_url or video_file or existing_stream or existing_file):
            raise serializers.ValidationError(
                "Uploading a video file or entering a stream address is required."
            )
        return super().validate(attrs)

    def to_representation(self, instance):
        return VideoSerializer(instance, context=self.context).data

class EpisodeSerializer(serializers.ModelSerializer):
    """A simple serializer just for listing episodes within a series."""
    class Meta:
        model = models.Video
        fields = ["title", "slug", "season_number", "episode_number", "duration_seconds"]

class SeriesSerializer(serializers.ModelSerializer):
    """Serializer for the list view of all series."""
    class Meta:
        model = models.Series
        fields = ["title", "slug", "description", "poster", "release_year"]

class SeriesDetailSerializer(serializers.ModelSerializer):
    """Serializer for a single series, including all its episodes."""
    episodes = EpisodeSerializer(many=True, read_only=True)

    class Meta:
        model = models.Series
        fields = ["title", "slug", "description", "poster", "release_year", "episodes"]

class WatchHistorySerializer(serializers.ModelSerializer):
    episodes = EpisodeSerializer(many=True, read_only=True)

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