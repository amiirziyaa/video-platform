"""Router configuration for the streaming API."""
from __future__ import annotations
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "streaming"

router = DefaultRouter()
router.register(r"users", views.UserViewSet, basename="user")
router.register(r"plans", views.SubscriptionPlanViewSet, basename="plan")
router.register(r"series", views.SeriesViewSet, basename="series") # ADDED
router.register(r"subscriptions", views.SubscriptionViewSet, basename="subscription")
router.register(r"videos", views.VideoViewSet, basename="video")
router.register(r"history", views.WatchHistoryViewSet, basename="history")
router.register(r"comments", views.VideoCommentViewSet, basename="comment")
router.register(r"bookmarks", views.BookmarkViewSet, basename="bookmark")

urlpatterns = [
    path("", include(router.urls)),
]
