"""View layer of the streaming API."""
from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import generic
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import forms, models, permissions as custom_permissions, serializers, services

User = get_user_model()


class HomePageView(generic.TemplateView):
    """Landing page showing highlighted videos and plans."""

    template_name = "streaming/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        featured = (
            models.Video.objects.filter(status=models.Video.Status.PUBLISHED)
            .select_related("category")
            .order_by("-published_at", "-created_at")[:6]
        )
        context["featured_videos"] = featured
        context["newest_videos"] = (
            models.Video.objects.filter(status=models.Video.Status.PUBLISHED)
            .select_related("category")
            .order_by("-created_at")[:8]
        )
        context["active_plans"] = models.SubscriptionPlan.objects.filter(is_active=True).order_by("level")
        return context


class VideoListView(generic.ListView):
    """Public catalog of published videos."""

    template_name = "streaming/video_list.html"
    context_object_name = "videos"
    paginate_by = 12

    def get_queryset(self) -> QuerySet[models.Video]:
        queryset = (
            models.Video.objects.filter(status=models.Video.Status.PUBLISHED)
            .select_related("category")
            .order_by("-published_at", "-created_at")
        )
        category_slug = self.request.GET.get("category")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["categories"] = models.VideoCategory.objects.all()
        context["selected_category"] = self.request.GET.get("category", "")
        return context


class VideoDetailView(generic.DetailView):
    """Detailed page for a single video."""

    template_name = "streaming/video_detail.html"
    model = models.Video
    context_object_name = "video"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self) -> QuerySet[models.Video]:
        queryset = (
            super()
            .get_queryset()
            .select_related("category", "created_by")
            .prefetch_related("comments__user")
        )
        return queryset.filter(status=models.Video.Status.PUBLISHED)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        video: models.Video = context["video"]
        context["can_watch"] = video.can_user_access(self.request.user)
        context["related_videos"] = (
            models.Video.objects.filter(status=models.Video.Status.PUBLISHED, category=video.category)
            .exclude(pk=video.pk)
            .order_by("-published_at")[:6]
        )
        context["recent_comments"] = video.comments.select_related("user")[:8]
        context["average_rating"] = video.average_rating
        return context


class SubscriptionPlanListView(generic.ListView):
    """Display all active subscription plans."""

    template_name = "streaming/subscription_plans.html"
    context_object_name = "plans"

    def get_queryset(self) -> QuerySet[models.SubscriptionPlan]:
        return models.SubscriptionPlan.objects.filter(is_active=True).order_by("level")


class SubscriptionCheckoutView(LoginRequiredMixin, generic.TemplateView):
    """Checkout-like view to start a subscription for a plan."""

    template_name = "streaming/subscription_checkout.html"

    def dispatch(self, request, *args, **kwargs):
        self.plan = get_object_or_404(
            models.SubscriptionPlan, slug=kwargs["slug"], is_active=True
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["plan"] = self.plan
        context["active_subscription"] = self.request.user.active_subscription
        return context

    def post(self, request, *args, **kwargs):
        service = services.SubscriptionService()
        try:
            subscription = service.start_subscription(request.user, self.plan)
        except ValueError as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)
        messages.success(
            request, f"اشتراک {subscription.plan.name} با موفقیت فعال یا تمدید شد."
        )
        return redirect("dashboard")


class DashboardView(LoginRequiredMixin, generic.TemplateView):
    """Private dashboard summarising the user activity."""

    template_name = "streaming/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user: User = self.request.user
        context["active_subscription"] = user.active_subscription
        context["recent_history"] = (
            user.watch_history.select_related("video", "video__category")
            .order_by("-watched_at")[:10]
        )
        context["bookmarks"] = (
            user.bookmarks.select_related("video", "video__category")
            .order_by("-created_at")[:8]
        )
        context["recommended_videos"] = (
            models.Video.objects.filter(status=models.Video.Status.PUBLISHED, is_premium=False)
            .order_by("-published_at")[:6]
        )
        return context


class WatchHistoryListView(LoginRequiredMixin, generic.ListView):
    """Full watch history for the authenticated user."""

    template_name = "streaming/history_list.html"
    context_object_name = "history"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[models.WatchHistory]:
        return (
            self.request.user.watch_history.select_related("video", "video__category")
            .order_by("-watched_at")
        )


class BookmarkListView(LoginRequiredMixin, generic.ListView):
    """List of all bookmarks for the authenticated user."""

    template_name = "streaming/bookmark_list.html"
    context_object_name = "bookmarks"
    paginate_by = 24

    def get_queryset(self) -> QuerySet[models.VideoBookmark]:
        return (
            self.request.user.bookmarks.select_related("video", "video__category")
            .order_by("-created_at")
        )


class RegisterView(generic.CreateView):
    """User-facing registration page."""

    form_class = forms.UserRegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form: forms.UserRegistrationForm) -> Any:
        self.object = form.save()
        login(self.request, self.object)
        return redirect(self.get_success_url())


class UserViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """User registration and profile retrieval."""

    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["username", "email"]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        if self.action in {"me", "update", "partial_update"}:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.UserCreateSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = serializers.SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    filterset_fields = ["level"]
    ordering_fields = ["price", "level"]


class SubscriptionViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = serializers.SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[models.Subscription]:
        return self.request.user.subscriptions.select_related("plan", "payment")

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.SubscriptionCreateSerializer
        if self.action == "renew":
            return serializers.SubscriptionRenewSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["get"], url_path="active")
    def active_subscription(self, request):
        subscription = request.user.active_subscription
        if not subscription:
            return Response({"detail": "هیچ اشتراک فعالی یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(subscription)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        subscription = self.get_object()
        services.SubscriptionService().cancel_subscription(subscription)
        serializer = self.get_serializer(subscription)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="renew")
    def renew(self, request, pk=None):
        subscription = self.get_object()
        serializer = self.get_serializer(subscription, data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        data = serializers.SubscriptionSerializer(subscription, context=self.get_serializer_context()).data
        return Response(data)


class VideoViewSet(viewsets.ModelViewSet):
    queryset = models.Video.objects.select_related("category", "created_by")
    permission_classes = [custom_permissions.IsAdminOrReadOnly]
    lookup_field = "slug"
    filterset_fields = ["category__slug", "status", "is_premium"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "published_at", "title"]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return serializers.VideoWriteSerializer
        return serializers.VideoSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(
        detail=True,
        methods=["post"],
        serializer_class=serializers.WatchHistoryCreateSerializer,
        permission_classes=[
            permissions.IsAuthenticated,
            custom_permissions.HasActiveSubscription,
            custom_permissions.CanAccessVideo,
        ],
    )
    def watch(self, request, slug=None):
        video = self.get_object()
        payload = request.data.copy()
        payload["video"] = video.pk
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        history = serializer.save()
        return Response(serializers.WatchHistorySerializer(history, context=self.get_serializer_context()).data)

    @action(
        detail=True,
        methods=["get"],
        serializer_class=serializers.VideoLiveStatusSerializer,
        permission_classes=[permissions.IsAuthenticated],
    )
    def live_status(self, request, slug=None):
        video = self.get_object()
        status_payload = services.VideoAnalyticsService.live_status(video)
        serializer = self.get_serializer(status_payload)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        serializer_class=serializers.VideoCommentSerializer,
        permission_classes=[permissions.IsAuthenticated, custom_permissions.CanAccessVideo],
    )
    def comment(self, request, slug=None):
        video = self.get_object()
        payload = request.data.copy()
        payload["video"] = video.pk
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        return Response(serializers.VideoCommentSerializer(comment, context=self.get_serializer_context()).data)


class WatchHistoryViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.WatchHistorySerializer

    def get_queryset(self):
        return self.request.user.watch_history.select_related("video", "video__category")

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.WatchHistoryCreateSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save()


class VideoCommentViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.VideoCommentSerializer

    def get_queryset(self):
        return models.VideoComment.objects.filter(user=self.request.user).select_related("video")


class BookmarkViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.BookmarkSerializer

    def get_queryset(self):
        return models.VideoBookmark.objects.filter(user=self.request.user).select_related("video")

    def perform_create(self, serializer):
        serializer.save()
