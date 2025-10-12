"""Admin registrations for streaming models."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from . import models


@admin.register(models.User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "is_staff", "is_active", "subscription_level")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Video platform", {"fields": ("phone_number", "preferred_language", "marketing_opt_in")}),
    )


@admin.register(models.SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "price", "duration_days", "level", "is_active")
    list_filter = ("is_active", "level")


@admin.register(models.Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "start_date", "end_date")
    list_filter = ("status", "plan__level")
    search_fields = ("user__username", "plan__name")

@admin.register(models.Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ("title", "release_year")
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}


@admin.register(models.VideoCategory)
class VideoCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "slug")


@admin.register(models.Video)
class VideoAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("__str__", "status", "is_premium")
    list_filter = ("status", "is_premium", "category", "series")
    search_fields = ("title", "description", "series__title")
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'description')
        }),
        ('Episode Information', {
            'classes': ('collapse',),
            'fields': ('series', 'season_number', 'episode_number'),
            'description': "Fill these fields if this video is an episode of a series. Leave them blank for a standalone movie."
        }),
        ('Content & Files', {
            'fields': ('category', 'duration_seconds', 'video_file', 'stream_url', 'thumbnail_image')
        }),
        ('Permissions & Status', {
            'fields': ('min_subscription_level', 'is_premium', 'status')
        }),
    )


@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "status", "requested_at", "processed_at")
    list_filter = ("status",)
    search_fields = ("user__username", "reference_code")


@admin.register(models.WatchHistory)
class WatchHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "video", "watched_at", "completed", "rating")
    list_filter = ("completed", "rating")


@admin.register(models.VideoComment)
class VideoCommentAdmin(admin.ModelAdmin):
    list_display = ("user", "video", "created_at", "is_spoiler")
    list_filter = ("is_spoiler",)


@admin.register(models.VideoBookmark)
class VideoBookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "video", "created_at")
    search_fields = ("user__username", "video__title")