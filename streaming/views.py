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
from .services import ZarinpalGateway
from . import forms, models, permissions as custom_permissions, serializers, services
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from django.contrib.auth.decorators import login_required

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
        queryset = models.Video.objects.filter(status=models.Video.Status.PUBLISHED)
        
        category_slug = self.request.GET.get("category")
        content_type = self.request.GET.get("type")
        series_slug = self.request.GET.get("series_slug")

        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        if content_type == "movie":
            queryset = queryset.filter(series__isnull=True)
        
        if series_slug:
            queryset = queryset.filter(series__slug=series_slug)
            return queryset.select_related("category", "series").order_by("season_number", "episode_number")

        return queryset.select_related("category").order_by("-published_at", "-created_at")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["categories"] = models.VideoCategory.objects.all()
        context["selected_category"] = self.request.GET.get("category", "")
        return context

class SeriesListView(generic.ListView):
    """Public list of all series."""
    template_name = "streaming/series_list.html"
    context_object_name = "series_list"
    queryset = models.Series.objects.order_by('-release_year', 'title')
    paginate_by = 12

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
        context['comment_form'] = forms.CommentForm()

        if self.request.user.is_authenticated:
            context['is_bookmarked'] = models.VideoBookmark.objects.filter(
                user=self.request.user, video=video
            ).exists()

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
    
    def get(self, request, *args, **kwargs):
        active_sub = request.user.active_subscription
        if active_sub and self.plan.level < active_sub.plan.level:
            messages.error(request, "You cannot downgrade to a lower-level plan.")
            return redirect("subscription_plans")
        
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["plan"] = self.plan
        context["active_subscription"] = self.request.user.active_subscription
        return context

    def post(self, request, *args, **kwargs):
        service = services.SubscriptionService()
        try:
            _payment, payment_url = service.start_payment_process(request.user, self.plan, request)
            if payment_url:
                return redirect(payment_url)
            messages.error(request, "Error connecting to payment gateway")
            return self.get(request, *args, **kwargs)

        except ValueError as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, generic.TemplateView):
    """Private dashboard summarising the user activity."""

    template_name = "streaming/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user: User = self.request.user
        context["active_subscription"] = user.active_subscription
        context["recent_history"] = (
            user.watch_history.select_related("video", "video__category")
            .order_by("-watched_at")[:3]
        )
        context["bookmarks"] = (
            user.bookmarks.select_related("video", "video__category")
            .order_by("-created_at")[:3]
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
    paginate_by = 20

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
    

class ProfileUpdateView(LoginRequiredMixin, generic.UpdateView):
    """View for a user to edit their own profile."""
    model = User
    form_class = forms.UserUpdateForm
    template_name = 'streaming/profile_form.html'
    success_url = reverse_lazy('dashboard')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated successfully.")
        return super().form_valid(form)


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


class SeriesViewSet(viewsets.ReadOnlyModelViewSet):
    """A viewset for viewing series and their episodes."""
    queryset = models.Series.objects.all()
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.SeriesDetailSerializer
        return serializers.SeriesSerializer


class SubscriptionViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = serializers.SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = 'streaming/subscription_history.html'

    def get_queryset(self) -> QuerySet[models.Subscription]:
        return self.request.user.subscriptions.select_related("plan", "payment")

    def list(self, request, *args, **kwargs):
        subscription_response = super().list(request, *args, **kwargs)
        if request.accepted_renderer.format != 'html':
            return subscription_response
        
        payments_qs = models.Payment.objects.filter(
            user=request.user, 
            status=models.Payment.Status.SUCCESS
        ).select_related('plan').order_by('-processed_at')
        
        payment_serializer = serializers.PaymentSerializer(payments_qs, many=True)
        
        context = {
            'subscriptions': subscription_response.data.get('results', []),
            'payments': payment_serializer.data
        }
        return Response(context)

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
            return Response({"detail": "No active subscriptions found."}, status=status.HTTP_404_NOT_FOUND)
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
    filterset_fields = ["category__slug", "status", "is_premium", "series__slug"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "published_at", "title"]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return serializers.VideoWriteSerializer
        return serializers.VideoSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], serializer_class=serializers.WatchHistoryCreateSerializer, permission_classes=[permissions.IsAuthenticated, custom_permissions.HasActiveSubscription, custom_permissions.CanAccessVideo])
    def watch(self, request, slug=None):
        video = self.get_object()
        serializer = serializers.WatchHistoryCreateSerializer(
            data={'video': video.pk},
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        history = serializer.save()
        return Response(
            serializers.WatchHistorySerializer(history, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"], serializer_class=serializers.VideoLiveStatusSerializer, permission_classes=[permissions.IsAuthenticated])
    def live_status(self, request, slug=None):
        video = self.get_object()
        status_payload = services.VideoAnalyticsService.live_status(video)
        serializer = self.get_serializer(status_payload)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], serializer_class=serializers.VideoCommentSerializer, permission_classes=[permissions.IsAuthenticated, custom_permissions.CanAccessVideo])
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

class PaymentCallbackView(LoginRequiredMixin, generic.View):
    """Handle the user returning from the payment gateway."""

    def get(self, request, *args, **kwargs):
        authority = request.GET.get("Authority")
        status = request.GET.get("Status")

        if not authority or status != "OK":
            messages.error(request, "The transaction was canceled by you.")
            return redirect("dashboard")

        try:
            payment = models.Payment.objects.get(authority_code=authority)
        except models.Payment.DoesNotExist:
            messages.error(request, "Payment information not found.")
            return redirect("dashboard")

        amount_in_toman = int(payment.amount)
        gateway = ZarinpalGateway()
        verification = gateway.verify_payment(amount_in_toman, authority)

        if verification.success:
            payment.mark_success(verification.reference)

            user = payment.user
            new_plan = payment.plan
            existing_sub = user.active_subscription

            if existing_sub:
                existing_sub.plan = new_plan 
                existing_sub.extend(new_plan.duration_days)
                existing_sub.payment = payment
                existing_sub.save(update_fields=['plan', 'end_date', 'payment', 'status'])
                
                messages.success(request, f"Your subscription has been successfully upgraded to {new_plan.name}.")
            else:
                models.Subscription.create_for_plan(user=user, plan=new_plan, payment=payment)
                messages.success(request, f"Your new {new_plan.name} subscription is now active.")
        else:
            payment.mark_failed(verification.message)
            messages.error(request, f"Payment confirmation error: {verification.message}")

        return redirect("dashboard")



@login_required
def toggle_bookmark(request, slug):
    if request.method == 'POST':
        video = get_object_or_404(models.Video, slug=slug)
        try:
            bookmark = models.VideoBookmark.objects.get(user=request.user, video=video)
            bookmark.delete()
            messages.success(request, f"'{video.title}' was removed from your bookmarks.")
        except models.VideoBookmark.DoesNotExist:
            models.VideoBookmark.objects.create(user=request.user, video=video)
            messages.success(request, f"'{video.title}' was added to your bookmarks.")
    return redirect("video_detail", slug=slug)

@login_required
def add_review(request, slug):
    video = get_object_or_404(models.Video, slug=slug)
    if request.method == 'POST':
        form = forms.CommentForm(request.POST)
        if form.is_valid():
            models.VideoComment.objects.create(
                user=request.user,
                video=video,
                comment=form.cleaned_data['comment'],
                is_spoiler=form.cleaned_data['is_spoiler']
            )
            
            rating = form.cleaned_data.get('rating')
            if rating:
                history, _ = models.WatchHistory.objects.get_or_create(user=request.user, video=video)
                history.rating = rating
                history.save()
            
            messages.success(request, "Your review has been submitted.")
        else:
            messages.error(request, "There was an error with your submission. Please check the form.")
    
    return redirect("video_detail", slug=slug)



@login_required
def delete_bookmark(request, pk):
    bookmark = get_object_or_404(models.VideoBookmark, pk=pk, user=request.user)
    
    if request.method == 'POST':
        video_title = bookmark.video.title
        bookmark.delete()
        messages.success(request, f"'{video_title}' was removed from your bookmarks.")
    
    return redirect("bookmark_page")



@login_required
def cancel_subscription_view(request):
    if request.method == 'POST':
        active_sub = request.user.active_subscription
        
        if active_sub:
            services.SubscriptionService().cancel_subscription(active_sub)
            messages.success(request, "Your subscription has been successfully cancelled.")
        else:
            messages.error(request, "You do not have an active subscription to cancel.")
    
    return redirect("dashboard")
