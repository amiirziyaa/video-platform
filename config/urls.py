"""URL configuration for the video platform project."""
from __future__ import annotations
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from streaming.views import PaymentCallbackView 
from streaming import views as frontend_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", frontend_views.HomePageView.as_view(), name="home"),
    path("videos/", frontend_views.VideoListView.as_view(), name="video_catalog"),
    path("videos/<slug:slug>/", frontend_views.VideoDetailView.as_view(), name="video_detail"),
    path("series/", frontend_views.SeriesListView.as_view(), name="series_list"),
    path("videos/<slug:slug>/bookmark/", frontend_views.toggle_bookmark, name="toggle_bookmark"),
    path("videos/<slug:slug>/review/", frontend_views.add_review, name="add_review"),
    path("plans/", frontend_views.SubscriptionPlanListView.as_view(), name="subscription_plans"),
    path("plans/<slug:slug>/subscribe/",frontend_views.SubscriptionCheckoutView.as_view(),name="subscription_checkout",),
    path("dashboard/", frontend_views.DashboardView.as_view(), name="dashboard"),
    path("dashboard/subscription/cancel/", frontend_views.cancel_subscription_view, name="cancel_subscription"),
    path("dashboard/history/",frontend_views.WatchHistoryListView.as_view(),name="history_page",),
    path("dashboard/bookmarks/",frontend_views.BookmarkListView.as_view(),name="bookmark_page",),
    path("dashboard/bookmarks/<int:pk>/delete/",frontend_views.delete_bookmark,name="delete_bookmark",),
    path("accounts/profile/",frontend_views.ProfileUpdateView.as_view(),name="profile_edit",),
    path("accounts/register/", frontend_views.RegisterView.as_view(), name="register"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_change/",auth_views.PasswordChangeView.as_view(template_name="registration/password_change_form.html"),name="password_change",),
    path("accounts/password_change/done/",auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),name="password_change_done",),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("streaming.urls")),
    path("payment/callback/", PaymentCallbackView.as_view(), name="payment_callback"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)