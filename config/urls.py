"""URL configuration for the video platform project."""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from streaming import views as frontend_views

urlpatterns = [
    path("", frontend_views.HomePageView.as_view(), name="home"),
    path("videos/", frontend_views.VideoListView.as_view(), name="video_catalog"),
    path("videos/<slug:slug>/", frontend_views.VideoDetailView.as_view(), name="video_detail"),
    path("plans/", frontend_views.SubscriptionPlanListView.as_view(), name="subscription_plans"),
    path(
        "plans/<slug:slug>/subscribe/",
        frontend_views.SubscriptionCheckoutView.as_view(),
        name="subscription_checkout",
    ),
    path("dashboard/", frontend_views.DashboardView.as_view(), name="dashboard"),
    path(
        "dashboard/history/",
        frontend_views.WatchHistoryListView.as_view(),
        name="history_page",
    ),
    path(
        "dashboard/bookmarks/",
        frontend_views.BookmarkListView.as_view(),
        name="bookmark_page",
    ),
    path("accounts/register/", frontend_views.RegisterView.as_view(), name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("streaming.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
